"""Synthetic native image input and capture checks. Never uses employee files."""
import base64
import hashlib
import json
import struct
import zlib


def image_fixture(root):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    pixels=b''.join(b'\0'+bytes([x*7%256,y*11%256,73])*32 for y,x in enumerate(range(32)))
    raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,32,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')
    path=root/'native-image.png'
    path.write_bytes(raw)
    return path,base64.b64encode(raw).decode()


def image_payloads(value):
    result=[]
    if isinstance(value,list):
        for part in value:result.extend(image_payloads(part))
    elif isinstance(value,dict):
        if value.get('type')=='image' and isinstance(value.get('source'),dict):
            data=value['source'].get('data')
            if isinstance(data,str) and data:result.append(data)
        if value.get('type') in ('input_image','image_url'):
            data=value.get('image_url')
            if isinstance(data,dict):data=data.get('url')
            if isinstance(data,str) and data.startswith('data:'):result.append(data.split(',',1)[1])
        for part in value.values():result.extend(image_payloads(part))
    return result


def verify_capture(gateway,records):
    payloads={p for row in records for p in image_payloads(row['body'])}
    encoded=[p.read_bytes() for p in (gateway.store/'events').glob('*/*.json')]
    exported=b'\n'.join(encoded)
    events=[json.loads(record)['event'] for record in encoded]
    def metadata(value):
        if isinstance(value,list):return sum(metadata(x) for x in value)
        if isinstance(value,dict):return int(value.get('omitted')=='attachment')+sum(metadata(x) for x in value.values())
        return 0
    count=sum(metadata(e) for e in events)
    result={'native_image_payloads_seen':len(payloads),'attachment_metadata_records':count,
        'no_image_payload_at_rest':bool(payloads) and all(p.encode() not in exported for p in payloads),
        'image_request_byte_identity':all(row['wire_sha256'] in {e.get('request_sha256') for e in events}
            for row in records if image_payloads(row['body'])),
        'text_and_tool_markers_preserved':b'NATIVE_ALPHA_731' in exported and b'NATIVE_BETA_842' in exported}
    status=json.loads((gateway.store/'status.json').read_text())
    result['capture_has_no_gaps']=not any(e.get('missing') for e in events) and all(status.get(k)==0 for k in ('dropped','truncated','write_errors','projection_errors','queue_items','active_requests'))
    result['passed']=bool(payloads) and count>=len(payloads) and all(result[k] for k in ('no_image_payload_at_rest','image_request_byte_identity','text_and_tool_markers_preserved','capture_has_no_gaps'))
    (gateway.root/'media-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

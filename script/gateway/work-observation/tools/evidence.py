#!/usr/bin/env python3
"""Build restricted, literal-content evidence for offline Guard/Auto analysis.

This command does not run models, execute tools, infer task success, or modify
production state. Original projected requests/responses remain the authority.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile

SCHEMA = 'work-observation-v1'
EVIDENCE_SCHEMA = 'work-evidence-v1'
MAX_LINE_BYTES = 64 << 20


def group_key(event):
    verified = event.get('association') in ('verified_session', 'verified_conversation')
    session = event.get('root_session_hash') or event.get('session_hash')
    key = event.get('key_hash')
    # Unknown/client-claimed sessions remain single observations, not a guessed
    # conversation. Region and authenticated identity always scope association.
    reliable = bool(verified and session and key)
    if not reliable and event.get('kind') in ('websocket_message','websocket_connection'):
        connection=event.get('connection_id') or (event['id'] if event.get('kind')=='websocket_connection' else None)
        if connection:
            fields=[event['region'],key,connection]
            return 'connection:'+hashlib.sha256(json.dumps(fields,separators=(',',':')).encode()).hexdigest(),False
    fields = [event['region'], key, session] if reliable else [event['region'], event['id']]
    digest = hashlib.sha256(json.dumps(fields, separators=(',', ':')).encode()).hexdigest()
    return ('conversation:' if reliable else 'observation:') + digest, reliable


def parts(event):
    result = []

    def add(pointer, direction, role, source, value, kind='snapshot', call_id=None):
        item = {'pointer': pointer, 'direction': direction, 'role': role,
                'source': source, 'representation': kind, 'content': value}
        if isinstance(call_id, str) and call_id:
            item['tool_call_id'] = call_id
        result.append(item)

    def content(value, ptr, direction, role, representation='snapshot'):
        if isinstance(value, str):
            add(ptr, direction, role, role if role in ('system','developer','user','assistant','tool') else 'unknown', value, representation)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                content(item, f'{ptr}/{i}', direction, role, representation)
        elif isinstance(value, dict):
            kind = value.get('type')
            if value.get('omitted'):
                add(ptr, direction, role, 'attachment_metadata', value, representation)
            elif kind in ('function_call', 'tool_use'):
                add(ptr, direction, 'assistant', 'tool_call', value, representation, value.get('call_id') or value.get('id'))
            elif kind in ('function_call_output', 'tool_result'):
                add(ptr, direction, 'tool', 'tool_result', value, representation, value.get('call_id') or value.get('tool_use_id'))
            elif kind in ('input_text', 'output_text', 'text', 'text_delta', 'reasoning_text', 'reasoning', 'thinking', 'thinking_delta'):
                add(ptr, direction, role, 'model_reasoning_visible' if kind in ('reasoning_text','reasoning','thinking','thinking_delta') else role, value, representation)
            elif 'role' in value or kind == 'message':
                message_role = value.get('role', role)
                if message_role == 'tool':
                    add(ptr, direction, 'tool', 'tool_result', value, representation, value.get('tool_call_id'))
                else:
                    if 'content' in value: content(value['content'], ptr+'/content', direction, message_role, representation)
                    if isinstance(value.get('tool_calls'),list):
                        for i, call in enumerate(value['tool_calls']):
                            add(f'{ptr}/tool_calls/{i}', direction, 'assistant', 'tool_call', call, representation, call.get('id') if isinstance(call,dict) else None)
                    if 'audio' in value:
                        add(ptr+'/audio', direction, message_role, 'audio_transcript_and_metadata', value['audio'], representation)
            else:
                # Keep unknown protocol values visible; no guessed user intent.
                add(ptr, direction, role, 'unknown_protocol_part', value, representation)

    req = event.get('request')
    request_pointer='/request'
    if isinstance(req,dict) and req.get('type')=='response.create' and isinstance(req.get('response'),dict):
        req=req['response'];request_pointer='/request/response'
    if isinstance(req, dict):
        for field in ('system','instructions'):
            if field in req: content(req[field], request_pointer+'/'+field, 'request', 'system')
        for field in ('messages','input'):
            if field in req: content(req[field], request_pointer+'/'+field, 'request', 'user')
        if 'tools' in req: add(request_pointer+'/tools', 'request', 'system', 'tool_definitions', req['tools'])
        if 'prompt' in req: content(req['prompt'], request_pointer+'/prompt', 'request', 'user')
    elif req is not None:
        content(req, '/request', 'request', 'unknown')

    def response(value, ptr, streaming=False):
        if isinstance(value, list):
            for i, item in enumerate(value): response(item, f'{ptr}/{i}', True)
        elif isinstance(value, dict):
            kind = value.get('type', '')
            if not isinstance(kind,str): kind=''
            if value.get('_capture_transport')=='sse':
                response(value.get('data'),ptr+'/data',True)
            elif 'response' in value and isinstance(value['response'], dict):
                response(value['response'], ptr+'/response', streaming)
            elif isinstance(value.get('choices'),list):
                for i, choice in enumerate(value['choices']):
                    if not isinstance(choice, dict): continue
                    for field in ('message','delta','text'):
                        if field in choice:
                            item=choice[field]
                            if field=='delta' and isinstance(item,dict):
                                # Chat deltas often omit role after the first event.
                                item={**item,'role':item.get('role','assistant')}
                            content(item, f'{ptr}/choices/{i}/{field}', 'response', 'assistant', 'delta' if field=='delta' else 'snapshot')
            elif 'output' in value:
                content(value['output'], ptr+'/output', 'response', 'assistant')
            elif kind.endswith('.delta') or kind == 'content_block_delta':
                source='tool_arguments_delta' if 'function_call_arguments' in kind or (isinstance(value.get('delta'),dict) and value['delta'].get('type')=='input_json_delta') else 'model_delta'
                add(ptr, 'response', 'assistant', source, value, 'delta', value.get('call_id') or value.get('item_id'))
            elif 'content_block' in value:
                content(value['content_block'], ptr+'/content_block', 'response', 'assistant')
            elif 'item' in value:
                content(value['item'], ptr+'/item', 'response', 'assistant')
            elif 'message' in value:
                response(value['message'], ptr+'/message', streaming)
            elif 'content' in value:
                content(value['content'], ptr+'/content', 'response', 'assistant')
            else:
                # Usage, error and termination events are evidence too.
                add(ptr, 'response', 'unknown', 'protocol_event', value, 'event' if streaming else 'snapshot')
        elif value is not None:
            content(value, ptr, 'response', 'unknown')

    response(event.get('response'), '/response')
    return result


def build(event):
    if not isinstance(event,dict) or event.get('schema') != SCHEMA:
        raise ValueError('unsupported event schema')
    if event.get('plane','actual') != 'actual':
        raise ValueError('simulation cannot be imported as production evidence')
    for key in ('region','id','at'):
        if not isinstance(event.get(key),str) or not event[key]:
            raise ValueError('required event identity missing')
    key, verified = group_key(event)
    missing = event.get('missing',[])
    if not isinstance(missing,list): raise ValueError('invalid missing evidence')
    body_presence = {side: side in event for side in ('request','response')}
    return {'schema': EVIDENCE_SCHEMA, 'plane': 'actual', 'group_key': key,
            'association_verified': verified, 'association_scope':key.split(':',1)[0], 'source_event_id': event['id'],
            'region': event['region'], 'at': event['at'],
            'content_policy': event.get('content_policy','unknown'),
            'coverage': {'body_presence':body_presence,'missing':missing,
                         'attachment_semantics':'not_captured','task_quality':'unknown',
                         'scope':'gateway_observed_only'},
            'observed_parts': parts(event),
            # Preserve all fields and protocol context, not only recognized parts.
            'observation': event,
            'candidate_analysis': None}


def export(stream, destination):
    path=Path(destination)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.exists() or path.is_symlink(): raise ValueError('refuse to overwrite evidence export')
    fd,tmp=tempfile.mkstemp(prefix='.evidence-',dir=path.parent)
    counts=Counter()
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as output:
            while True:
                line=stream.readline(MAX_LINE_BYTES+1)
                if not line: break
                if len(line)>MAX_LINE_BYTES: raise ValueError('event exceeds export input limit')
                if not line.strip(): continue
                record=build(json.loads(line))
                output.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n')
                counts['events']+=1
                counts['associated_events' if record['association_verified'] else 'unassociated_events']+=1
                counts['events_with_missing_capture']+=bool(record['coverage']['missing'])
            output.flush();os.fsync(output.fileno())
        # Exclusive publication: a racing export must not overwrite this evidence.
        os.link(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return dict(counts)


def main():
    import sys
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,help='new file in a restricted, non-repository directory')
    args=p.parse_args();os.umask(0o077)
    try:
        print(json.dumps(export(sys.stdin.buffer,args.output)))
    except (OSError,ValueError,TypeError,RecursionError):
        # Exception details can contain literal employee content.
        raise SystemExit('evidence export failed; no new export published')


if __name__=='__main__':main()

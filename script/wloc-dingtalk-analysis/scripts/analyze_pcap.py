#!/usr/bin/env python3
"""Extract DNS / TLS SNI / endpoints from an iOS pcap (DingTalk capture)."""
import struct
import sys
from collections import Counter, defaultdict

import dpkt


def parse_sni(payload: bytes) -> str | None:
    """Parse a TCP payload that may start with a TLS ClientHello record."""
    if len(payload) < 6 or payload[0] != 0x16:
        return None
    try:
        rec_len = struct.unpack("!H", payload[3:5])[0]
        body = payload[5:5 + rec_len]
        if not body or body[0] != 0x01:
            return None
        hs_len = int.from_bytes(body[1:4], "big")
        hello = dpkt.ssl.TLSClientHello(body[4:4 + hs_len])
        for ext_type, ext_data in getattr(hello, "extensions", []):
            if ext_type != 0:
                continue
            # ServerNameList: 2-byte list len, then 1-byte type, 2-byte len, name
            p = 2
            while p + 3 <= len(ext_data):
                name_len = struct.unpack("!H", ext_data[p + 1:p + 3])[0]
                name = ext_data[p + 3:p + 3 + name_len].decode("ascii", "ignore")
                if name:
                    return name
                p += 3 + name_len
    except Exception:
        return None
    return None


def iter_ip_packets(buf):
    # pymobiledevice3 pcapd frames often start with a 4-byte preamble
    # (frame_pre_length), followed by a bare IPv4/IPv6 packet.
    for off in (0, 4):
        chunk = buf[off:]
        if not chunk:
            continue
        version = chunk[0] >> 4
        try:
            if version == 4:
                return dpkt.ip.IP(chunk)
            if version == 6:
                return dpkt.ip6.IP6(chunk)
        except Exception:
            pass
    try:
        eth = dpkt.ethernet.Ethernet(buf)
        if isinstance(eth.data, (dpkt.ip.IP, dpkt.ip6.IP6)):
            return eth.data
    except Exception:
        pass
    try:
        sll = dpkt.sll.SLL(buf)
        if isinstance(sll.data, (dpkt.ip.IP, dpkt.ip6.IP6)):
            return sll.data
    except Exception:
        pass
    return None


def open_reader(path: str):
    """pymobiledevice3 writes pcapng; accept classic pcap too."""
    with open(path, "rb") as f:
        magic = f.read(4)
    f = open(path, "rb")
    if magic == b"\x0a\x0d\x0d\x0a":
        print("format: pcapng")
        return f, dpkt.pcapng.Reader(f)
    print("format: pcap")
    return f, dpkt.pcap.Reader(f)


def main(path: str):
    dns_queries = Counter()
    dns_answers = defaultdict(set)
    sni_counter = Counter()
    tcp_dests = Counter()
    udp_dests = Counter()
    per_ip_sni = defaultdict(set)
    packets = 0

    fh, pcap = open_reader(path)
    try:
        for _, buf in pcap:
            packets += 1
            ip = iter_ip_packets(buf)
            if ip is None:
                continue
            src = ".".join(map(str, ip.src)) if isinstance(ip.src, bytes) else str(ip.src)
            dst = ".".join(map(str, ip.dst)) if isinstance(ip.dst, bytes) else str(ip.dst)

            if isinstance(ip.data, dpkt.udp.UDP):
                udp = ip.data
                if udp.dport == 53:
                    try:
                        dns = dpkt.dns.DNS(udp.data)
                        for q in dns.qd:
                            name = q.name.decode("ascii", "ignore").rstrip(".")
                            if name:
                                dns_queries[name] += 1
                        for an in dns.an:
                            if an.type in (dpkt.dns.DNS_A, dpkt.dns.DNS_AAAA):
                                try:
                                    addr = ".".join(map(str, an.ip)) if isinstance(an.ip, bytes) else str(an.ip)
                                except Exception:
                                    continue
                                name = an.name.decode("ascii", "ignore").rstrip(".") if an.name else ""
                                if name:
                                    dns_answers[name].add(addr)
                    except Exception:
                        pass
                elif udp.dport == 443:
                    udp_dests[f"{dst}:443/udp (QUIC?)"] += 1

            elif isinstance(ip.data, dpkt.tcp.TCP):
                tcp = ip.data
                dest = f"{dst}:{tcp.dport}"
                tcp_dests[dest] += 1
                if tcp.dport in (443, 8443) and tcp.data:
                    sni = parse_sni(bytes(tcp.data))
                    if sni:
                        sni_counter[sni] += 1
                        per_ip_sni[dest].add(sni)
    finally:
        fh.close()

    print(f"packets: {packets}\n")

    print("== DNS queries ==")
    for name, count in dns_queries.most_common(80):
        answers = ", ".join(sorted(dns_answers.get(name, []))[:4])
        print(f"{count:6d}  {name}" + (f"  -> {answers}" if answers else ""))

    print("\n== TLS SNI ==")
    for name, count in sni_counter.most_common(80):
        print(f"{count:6d}  {name}")

    print("\n== top TCP destinations ==")
    for dest, count in tcp_dests.most_common(40):
        hosts = ", ".join(sorted(per_ip_sni.get(dest, [])))
        print(f"{count:6d}  {dest}" + (f"  [{hosts}]" if hosts else ""))

    print("\n== UDP/443 destinations (possibly QUIC) ==")
    for dest, count in udp_dests.most_common(20):
        print(f"{count:6d}  {dest}")

    interesting = ("amap", "autonavi", "dingtalk", "alicdn", "alibaba", "aliyun",
                   "gs-loc", "apple", "mmstat", "log", "loc")
    print("\n== interesting domains ==")
    for name, count in sni_counter.most_common():
        if any(k in name.lower() for k in interesting):
            print(f"{count:6d}  {name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} CAP_FILE", file=sys.stderr)
        raise SystemExit(2)
    main(sys.argv[1])

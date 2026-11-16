#!/usr/bin/env python3
"""ELF string / virtual-address / ADRP+ADD xref scanner (AArch64).

Dependencies:
  python3 -m pip install lief capstone

Examples:
  python3 elf_scan.py libdatajar.so --string doSignature
  python3 elf_scan.py libnative-cube.so --string doSignHttpRequest --xrefs
"""
from __future__ import annotations

import argparse
from pathlib import Path

try:
    import lief
except ImportError as exc:  # pragma: no cover
    raise SystemExit("install lief: python3 -m pip install lief") from exc

try:
    from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs
    from capstone.arm64 import ARM64_INS_ADD, ARM64_INS_ADRP, ARM64_OP_IMM
except ImportError as exc:  # pragma: no cover
    raise SystemExit("install capstone: python3 -m pip install capstone") from exc


def segments(binary: lief.ELF.Binary):
    for seg in binary.segments:
        yield seg


def map_offset_to_va(segs, offset: int):
    for seg in segs:
        start = seg.file_offset
        end = seg.file_offset + seg.physical_size
        if start <= offset < end:
            return seg.virtual_address + (offset - start), seg
    return None, None


def find_string_va(data: bytes, needle: bytes, segs):
    out = []
    pos = 0
    while True:
        idx = data.find(needle, pos)
        if idx < 0:
            break
        va, seg = map_offset_to_va(segs, idx)
        out.append((idx, va, seg))
        pos = idx + 1
    return out


def disasm_xrefs(binary: lief.ELF.Binary, target_va: int, max_insns: int) -> list[int]:
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    xrefs: list[int] = []
    total = 0

    for seg in binary.segments:
        if not (seg.flags & lief.ELF.Segment.FLAGS.X):
            continue
        if seg.physical_size == 0:
            continue
        code = bytes(seg.content)
        base = seg.virtual_address
        page_regs: dict[int, int] = {}

        for insn in md.disasm(code, base):
            total += 1
            if total > max_insns:
                return xrefs

            if insn.id == ARM64_INS_ADRP and len(insn.operands) >= 2:
                rd = insn.operands[0].reg
                imm = insn.operands[1].imm
                page_regs[rd] = imm
                continue

            if insn.id == ARM64_INS_ADD and len(insn.operands) >= 3:
                dst = insn.operands[0].reg
                src = insn.operands[1].reg
                op2 = insn.operands[2]
                if op2.type == ARM64_OP_IMM and src in page_regs:
                    target = page_regs[src] + op2.imm
                    if target == target_va:
                        xrefs.append(insn.address)
                    page_regs[dst] = target

    return xrefs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("elf")
    ap.add_argument("--string", required=True)
    ap.add_argument("--xrefs", action="store_true")
    ap.add_argument("--max-insns", type=int, default=2_000_000)
    args = ap.parse_args()

    path = Path(args.elf)
    data = path.read_bytes()
    binary = lief.parse(str(path))
    segs = list(segments(binary))

    print(f"file: {path} ({len(data)} bytes)")
    for seg in segs:
        print(
            f"  seg type={seg.type} va={seg.virtual_address:#x} "
            f"vsize={seg.virtual_size:#x} off={seg.file_offset:#x} "
            f"fsize={seg.physical_size:#x} flags={seg.flags}"
        )

    needle = args.string.encode()
    matches = find_string_va(data, needle, segs)
    print(f"\nstring {args.string!r}: {len(matches)} match(es)")
    for off, va, seg in matches[:20]:
        print(f"  file_off={off:#x} va={va if va is None else hex(va)} seg={seg.type if seg else None}")

    if args.xrefs and matches:
        for _, va, _ in matches:
            if va is None:
                continue
            print(f"\nADRP+ADD xrefs for {args.string!r} @ {va:#x}:")
            refs = disasm_xrefs(binary, va, args.max_insns)
            if not refs:
                print("  (none found; code may be packed/interpreted or uses another addressing form)")
            for ref in refs[:50]:
                print(f"  {ref:#x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

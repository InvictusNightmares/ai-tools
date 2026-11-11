#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DACS macOS 网络策略本地编辑器 (2.2.x / 2.6.x)

支持三类本地文件：
1) ~/Library/Application Support/DACS/com.datacloak.networkpolicy.a
   TEStoreHttpNetworkPolicy，域名/URL 策略（明文 NSKeyedArchiver）
2) ~/Library/Application Support/DACS/Programrules_/.../programrules.a
   TEDomainProgramRuleModel，程序规则缓存（明文 NSKeyedArchiver）
3) 仅查看：mac_agent 日志中的 [IpcService] LoadNetPolicy
   这是服务端下发的个人 IP/DNS 策略，内存态，文件是加密的。

用法：
  python3 dacs_netpolicy.py http-list
  python3 dacs_netpolicy.py http-add example.com --did 110
  python3 dacs_netpolicy.py http-remove example.com
  python3 dacs_netpolicy.py program-list
  python3 dacs_netpolicy.py program-default --domain 6 --value 1
  python3 dacs_netpolicy.py live-list
  python3 dacs_netpolicy.py backup

所有写操作默认先备份到 ~/Library/Application Support/DACS/.dacs_backup_<时间>/
"""
import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
DACS_DIR = os.path.join(HOME, "Library/Application Support/DACS")
HTTP_POLICY = os.path.join(DACS_DIR, "com.datacloak.networkpolicy.a")
PROGRAM_GLOB_ROOT = os.path.join(DACS_DIR, "Programrules_")
BACKUP_ROOT = os.path.join(DACS_DIR, ".dacs_backup")
LIVE_LOG = "/usr/local/bin/mac_agent/log.txt"


# ----------------------------- plist helpers -----------------------------
def load_plist(path):
    with open(path, "rb") as f:
        return plistlib.load(f)


def save_plist(path, pl):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        plistlib.dump(pl, f, fmt=plistlib.FMT_BINARY, sort_keys=False)
    os.replace(tmp, path)


def class_uid(objects, name):
    for i, o in enumerate(objects):
        if isinstance(o, dict) and o.get("$classname") == name:
            return i
    raise KeyError(f"class {name!r} not found")


def resolve(objects, uid):
    if isinstance(uid, plistlib.UID):
        return objects[uid.data]
    return uid


def dict_get(pl, obj, key):
    """Return resolved value of obj[key], or None."""
    if not isinstance(obj, dict):
        return None
    v = obj.get(key)
    if v is None:
        return None
    return resolve(pl["$objects"], v)


def root_objects(pl):
    top = pl.get("$top", {})
    root_uid = top.get("root")
    if root_uid is None:
        raise KeyError("$top.root missing")
    return pl["$objects"], root_uid


def backup_file(path):
    ts = time.strftime("%Y%m%d-%H%M%S")
    dst_dir = os.path.join(BACKUP_ROOT + "_" + ts)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(path))
    shutil.copy2(path, dst)
    # also keep a stable latest copy
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    shutil.copy2(path, os.path.join(BACKUP_ROOT, os.path.basename(path)))
    return dst


# ----------------------------- HTTP policy -----------------------------
def http_items(pl):
    objects, root_uid = root_objects(pl)
    root = resolve(objects, root_uid)
    lst = dict_get(pl, root, "list")
    if lst is None:
        return []
    uids = lst.get("NS.objects", [])
    out = []
    for uid in uids:
        obj = resolve(objects, uid)
        if isinstance(obj, dict):
            out.append({
                "index": uid.data if isinstance(uid, plistlib.UID) else None,
                "pattern": dict_get(pl, obj, "pattern"),
                "did": dict_get(pl, obj, "did"),
                "obj": obj,
            })
    return out


def cmd_http_list(args):
    pl = load_plist(args.file)
    items = http_items(pl)
    print(f"# {args.file}")
    print(f"# {len(items)} entries")
    for it in items:
        print(f"{it['index']:>5}  did={it['did']!s:<5} {it['pattern']}")


def _http_list_obj(pl):
    objects, root_uid = root_objects(pl)
    root = resolve(objects, root_uid)
    return objects, dict_get(pl, root, "list")


def cmd_http_add(args):
    if not args.dry_run:
        backup = backup_file(args.file)
        print(f"[backup] {backup}")
    pl = load_plist(args.file)
    objects, lst = _http_list_obj(pl)
    if lst is None:
        raise SystemExit("list object not found")
    cls = class_uid(objects, "TEHttpPolicy")
    existing = {i["pattern"] for i in http_items(pl)}
    if args.pattern in existing:
        print(f"[skip] already present: {args.pattern}")
        return
    pat_uid = len(objects)
    objects.append(args.pattern)
    did_uid = len(objects)
    objects.append(str(args.did))
    new_obj = {
        "pattern": plistlib.UID(pat_uid),
        "did": plistlib.UID(did_uid),
        "bitPattern": plistlib.UID(0),  # $null
        "$class": plistlib.UID(cls),
    }
    objects.append(new_obj)
    new_uid = len(objects) - 1
    lst.setdefault("NS.objects", []).append(plistlib.UID(new_uid))
    if args.dry_run:
        print(f"[dry-run] would add {args.pattern} did={args.did}")
        return
    save_plist(args.file, pl)
    print(f"[add] {args.pattern} did={args.did}")


def cmd_http_remove(args):
    if not args.dry_run:
        backup = backup_file(args.file)
        print(f"[backup] {backup}")
    pl = load_plist(args.file)
    objects, lst = _http_list_obj(pl)
    if lst is None:
        raise SystemExit("list object not found")
    uids = lst.get("NS.objects", [])
    keep = []
    removed = 0
    for uid in uids:
        obj = resolve(objects, uid)
        if isinstance(obj, dict) and dict_get(pl, obj, "pattern") == args.pattern:
            removed += 1
            continue
        keep.append(uid)
    if not removed:
        print(f"[skip] not found: {args.pattern}")
        return
    lst["NS.objects"] = keep
    if args.dry_run:
        print(f"[dry-run] would remove {args.pattern} x{removed}")
        return
    save_plist(args.file, pl)
    print(f"[remove] {args.pattern} x{removed}")


# ----------------------------- Program rules -----------------------------
def find_programrules():
    if not os.path.isdir(PROGRAM_GLOB_ROOT):
        return None
    found = []
    for root, _, files in os.walk(PROGRAM_GLOB_ROOT):
        for fn in files:
            if fn == "programrules.a":
                found.append(os.path.join(root, fn))
    if not found:
        return None
    # prefer the most recently modified
    found.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return found[0]


def program_models(pl):
    objects, root_uid = root_objects(pl)
    root = resolve(objects, root_uid)
    uids = root.get("NS.objects", []) if isinstance(root, dict) else []
    out = []
    for uid in uids:
        obj = resolve(objects, uid)
        if not isinstance(obj, dict):
            continue
        domain = dict_get(pl, obj, "domainId")
        default = dict_get(pl, obj, "defaultRule")
        rules_obj = dict_get(pl, obj, "programRules")
        rules = []
        if isinstance(rules_obj, dict):
            for ru in rules_obj.get("NS.objects", []):
                r = resolve(objects, ru)
                if isinstance(r, dict):
                    rules.append({
                        "ruleId": dict_get(pl, r, "ruleId"),
                        "policyId": dict_get(pl, r, "policyId"),
                        "programId": dict_get(pl, r, "programId"),
                        "ruleType": dict_get(pl, r, "ruleType"),
                        "ruleValue": dict_get(pl, r, "ruleValue"),
                        "ruleAttr": dict_get(pl, r, "ruleAttr"),
                        "bundleId": dict_get(pl, r, "bundleId"),
                        "ruleAccessDomainId": dict_get(pl, r, "ruleAccessDomainId"),
                        "ruleAccessDomainName": dict_get(pl, r, "ruleAccessDomainName"),
                        "ruleSupermeDomain": dict_get(pl, r, "ruleSupermeDomain"),
                        "accessDomainIds": dict_get(pl, r, "accessDomainIds"),
                    })
        out.append({"domainId": domain, "defaultRule": default, "rules": rules,
                    "obj": obj, "rules_obj": rules_obj})
    return out


def cmd_program_list(args):
    path = args.file or find_programrules()
    if not path:
        print("programrules.a not found")
        return
    pl = load_plist(path)
    models = program_models(pl)
    print(f"# {path}")
    for m in models:
        print(f"domain={m['domainId']} defaultRule={m['defaultRule']} rules={len(m['rules'])}")
        for r in m["rules"]:
            print("   ", json.dumps(r, ensure_ascii=False, default=str))


def cmd_program_default(args):
    path = args.file or find_programrules()
    if not path:
        raise SystemExit("programrules.a not found")
    if not args.dry_run:
        print(f"[backup] {backup_file(path)}")
    pl = load_plist(path)
    models = program_models(pl)
    hit = None
    for m in models:
        if str(m["domainId"]) == str(args.domain):
            hit = m
            break
    if not hit:
        raise SystemExit(f"domain {args.domain} not found")
    hit["obj"]["defaultRule"] = args.value
    if args.dry_run:
        print(f"[dry-run] domain {args.domain} defaultRule -> {args.value}")
        return
    save_plist(path, pl)
    print(f"[set] domain {args.domain} defaultRule -> {args.value}")


# ----------------------------- Live policy -----------------------------
def cmd_live_list(args):
    """Parse mac_agent log for LoadNetPolicy items."""
    if not os.path.exists(LIVE_LOG):
        print(f"not found: {LIVE_LOG}")
        return
    seen = set()
    n = 0
    with open(LIVE_LOG, "r", errors="ignore") as f:
        for line in f:
            if "LoadNetPolicy key:" not in line and "save net polic list:" not in line:
                continue
            # extract key/index/value
            msg = line
            if 'msg":"' in msg:
                msg = msg.split('msg":"', 1)[1].rstrip('"}\n')
            if msg in seen:
                continue
            seen.add(msg)
            n += 1
            print(msg)
    print(f"# {n} distinct policy lines")


# ----------------------------- main -----------------------------
def main():
    ap = argparse.ArgumentParser(description="DACS 网络策略本地编辑器")
    ap.add_argument("--file", default=None, help="覆盖默认策略文件路径")
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("http-list", help="列出域名/URL 策略")
    p.add_argument("--file", default=HTTP_POLICY)
    p.set_defaults(func=cmd_http_list)

    p = sub.add_parser("http-add", help="添加域名/URL 策略")
    p.add_argument("pattern")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--did", default="110")
    p.add_argument("--file", default=HTTP_POLICY)
    p.set_defaults(func=cmd_http_add)

    p = sub.add_parser("http-remove", help="删除域名/URL 策略")
    p.add_argument("pattern")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--file", default=HTTP_POLICY)
    p.set_defaults(func=cmd_http_remove)

    p = sub.add_parser("program-list", help="列出程序规则")
    p.add_argument("--file", default=None)
    p.set_defaults(func=cmd_program_list)

    p = sub.add_parser("program-default", help="设置域的默认程序规则")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--domain", required=True)
    p.add_argument("--value", required=True, type=int)
    p.add_argument("--file", default=None)
    p.set_defaults(func=cmd_program_default)

    p = sub.add_parser("live-list", help="从 mac_agent 日志读取当前生效的个人网络策略")
    p.set_defaults(func=cmd_live_list)

    p = sub.add_parser("backup", help="备份明文策略文件")
    p.set_defaults(func=lambda a: print(backup_file(HTTP_POLICY)))

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass

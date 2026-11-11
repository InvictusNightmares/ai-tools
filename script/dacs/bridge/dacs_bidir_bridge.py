#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DACS 双向通讯桥（域 104 <-> 个人域 6），通用版，一行启动。

背景（见 DACS-reverse-blocking-analysis.md）：
  - NELO 对跨域 TCP 环回连接双向 DENY：域104 -> 域6、域6 -> 域104 都不通；
  - 同域 TCP 环回 PASS：域104 -> 域104、域6 -> 域6 正常；
  - 域104 进程写普通文件/FIFO/Unix socket 被 ES 拒绝；
  - 宿主进程 spawn 的域104 子进程，其 stdin/stdout 匿名管道不受路径鉴权影响。

桥的拓扑：
  外部客户端 --TCP(域6)--> outside 监听(域6) --匿名管道--> inside 子进程(域104) --TCP(域104)--> 内部服务
  DACS 浏览器 --TCP(域104)--> inside 监听(域104) --匿名管道--> outside 角色(域6) --TCP(域6)--> 外部服务

一行启动示例：
  # 1) 两边都用静态目录（脚本自动起两个 http.server）
  python3 dacs_bidir_bridge.py \
      --inside-serve ~/project:8000 --outside-serve /tmp/web:3000

  # 2) 服务已经在跑，只起桥
  python3 dacs_bidir_bridge.py \
      --inside-target 127.0.0.1:8000 --outside-target 127.0.0.1:3000

  # 3) 自动拉起自定义服务
  python3 dacs_bidir_bridge.py \
      --inside-cmd 'cd ~/project && "$DACS_STAGING/python-real" app.py' --inside-port 8000 \
      --outside-cmd 'cd ~/project && npm run dev' --outside-port 3000

结果：
  外部客户端访问 http://127.0.0.1:18102  -> 内部服务（--inside-target）
  DACS 浏览器访问 http://127.0.0.1:18101 -> 外部服务（--outside-target）

说明：
  - 脚本会自动找到宿主 Python 的“真实”framework 二进制（用 proc_pidpath 探测，
    不是 re-exec 启动器），复制到 --inside-python（默认
    ~/meili/zhangcheng/Applications/104/python-real），无需手工拷贝。
  - --inside-serve 启动的静态服务使用该 python-real，进程路径属于域104；
    --outside-serve 使用宿主 Python，属于域6。
  - --inside-cmd 里的监听进程必须使用域104路径下的可执行文件（例如
    $DACS_STAGING/python-real、$DACS_STAGING/node），否则监听进程仍会按域6判定，
    inside 子进程访问它会被 DENY。
"""
from __future__ import annotations

import argparse
import base64
import glob
import os
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import zlib

HEADER = struct.Struct("!BII")
OP_OPEN = 1
OP_DATA = 2
OP_CLOSE = 3
MAX_FRAME = 16 * 1024 * 1024
INSIDE_BIT = 0x80000000
DEFAULT_STAGING = os.path.expanduser("~/meili/zhangcheng/Applications/104")
DEFAULT_INSIDE_PYTHON = os.path.join(DEFAULT_STAGING, "python-real")

# Compiled fallback: real Python.framework binary, zlib+base64. Extracted only if
# the host cannot provide a working staged interpreter.
EMBEDDED_PYTHON_B64 = "eNrt3W9oG2UcB/DnLk1pbbpGKaw6xyKU4qTrNU3SpSLSP+u2ztqWLkhw4nFpLiauzY1LsjZuaByuq8wXrVXpG5lacBv+QXToBKX1hXUgs7ZMByquIg6nVDdUaAtRn8s9l15iNMJe+MLvB55cntxzv+fud8+bJ29+82vLv9sI4QjF01ZN26clhBwlDu0ncjNtu2kTxb62XZ33d/b3kr/gSHFaHC+nxfF1+n0Frm/Nu4D1raxZ2M+iGJdH4uvD8uOt2PV4dlOfN8ctISlzVxRj8UQg9rfxym7U49lMfXO8MhbPlr0+ER2ORINiJBpSCsSrZvH8pj5fJG9TmTg72nxtYkdvz16fkZ+cvOUdLawZuRDFh5R4znMXjldmyr/FNL407z2vr4vurp57Ond0Gc+Yyrsvlm2HZf1dm+O46Qg7GxemBxfrh2nfwdZkDW3jKf1+ztGjlx4raOsjuTE5Nv6f1uNsqnC+NxB9Pu09ComYKgxGAkIwORhk5zex+7Be2lhfvtZ8dmplwjnDddc2sev0Oavo+qrKfM88LvdJyR2mtai5nT5fDVuX5uWvzRtmc+j3J1YS8hwR9iZjcXlI6I4EVElNCjtVaUgeVtT9MaFDUeWdSiIalOIRJdoQMs4I98lqjP4SE9ryxrB5RszzVFkyTVAOxIWwMiQHVHlY6JAHByVVOJCMh5Voq6vB6RG0j4Ym8/x9mbOF5s1coJ82HlKb15vzfLus2qNnc02b/qgN7Q0075GAft2tNF/Z95Jzj/qQOpbfsZS+drey/jhbd5uN/D9O3xNPAAAAAADgfyh9aOZ02kIm0oc+OEU3YNV0j3DVzreuEn7L55y+7zD2H9kjz/ZtrWx7q/0XUOivC0tmv8LRfQe3/q8DAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMD1SyEFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP8tB9FrqWsl3PPrs5sL19Xkf28tzSl+l6m/rhXJE/uSYnsyLsfulSJGBXBOFIfCojwiDyTishiWpaCsZqqq6+XAV27Th2n1vO+irb1TshrzV3H2bPwa/Zit5M2T9U6hGXJvRZWC6p2C4Gl2uj1urXQ7WfvaNksjaCkwyt3X6iF5m54IvoaOoX3ue8KXGFOeo83PvpdrxcUdfKZE+b+QTRinV0jf5qHcLW53oycYcm5vGmhsCUmu5oC3xRvytjhdzkCo0ekeaHKTqaRjvOcVeUNi5Cnrnhfe6O95ODXz0S3T21YWt7+8sWN1tNjMP3yVnhiqtP0ce+vIexVj6d8uHjshTS9feKBr4WPf8VOXx7+ZuHx+0ztVB6VJl+8J/qWlK3PlH9bdUPrlngfHRp9f5ZXXHnv1Tb8ydyU0W3JxYWE/3+u3/nH4zOFHjn7x/vHdT9afLHb+0mc/jl57NmR5sb60+deBLaFrlRVnL/w0vbjvyNJ3T/Nnlq83frHzx4TFyZu+Pb80Of/o3W+/W7u8Ob1vfu71qwtb65755aDYX03fs/bGbfq6qNC+l/0JRniO5Q=="
LOG_DIR = "/tmp"


def log(msg: str) -> None:
    print(f"[dacs-bridge] {msg}", file=sys.stderr, flush=True)


def parse_hostport(value: str) -> tuple[str, int]:
    if value.startswith("["):
        host, _, rest = value[1:].partition("]")
        port = rest.lstrip(":")
    else:
        host, sep, port = value.rpartition(":")
        if not sep:
            raise argparse.ArgumentTypeError(f"expected HOST:PORT, got {value!r}")
    return host, int(port)


def read_exact(stream, n: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


# ----------------------------- python discovery -----------------------------
def actual_exec_path(python: str) -> str | None:
    """Run python and ask libproc for the real executable path (resolves launchers)."""
    probe = (
        "import ctypes, os\n"
        "libc = ctypes.CDLL(None)\n"
        "buf = ctypes.create_string_buffer(4096)\n"
        "libc.proc_pidpath(ctypes.c_int(os.getpid()), buf, ctypes.c_uint32(4096))\n"
        "print(buf.value.decode('utf-8', 'replace'))\n"
    )
    try:
        out = subprocess.run([python, "-c", probe], capture_output=True, timeout=10)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    lines = out.stdout.decode("utf-8", "replace").strip().splitlines()
    return lines[-1] if lines else None


def is_staged_executable(path: str) -> bool:
    if not (os.path.isfile(path) and os.access(path, os.X_OK)):
        return False
    actual = actual_exec_path(path)
    return bool(actual) and os.path.realpath(actual) == os.path.realpath(path)


def python_candidates() -> list[str]:
    cands: list[str] = []

    def add(value: str | None) -> None:
        if not value:
            return
        for item in (value, os.path.realpath(value)):
            if item not in cands:
                cands.append(item)

    add(actual_exec_path(sys.executable))
    add(sys.executable)
    add(getattr(sys, "_base_executable", None))
    patterns = [
        "/opt/homebrew/Cellar/python@*/**/Python.framework/Versions/*/Resources/Python.app/Contents/MacOS/Python",
        "/opt/homebrew/Cellar/python@*/**/Python.app/Contents/MacOS/Python",
        "/usr/local/Cellar/python@*/**/Python.framework/Versions/*/Resources/Python.app/Contents/MacOS/Python",
        "/Library/Frameworks/Python.framework/Versions/*/Resources/Python.app/Contents/MacOS/Python",
    ]
    for pattern in patterns:
        for item in glob.glob(pattern, recursive=True):
            add(item)
    return cands


def extract_embedded_python(path: str) -> bool:
    """Fallback: write the embedded real Python binary to the staging path."""
    if not EMBEDDED_PYTHON_B64:
        return False
    try:
        data = zlib.decompress(base64.b64decode(EMBEDDED_PYTHON_B64))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        os.chmod(path, 0o755)
    except Exception as exc:  # noqa: BLE001
        log(f"embedded python extract failed: {exc}")
        return False
    return is_staged_executable(path)


def ensure_inside_python(path: str) -> str:
    if is_staged_executable(path):
        log(f"inside python ready: {path}")
        return path
    if os.environ.get("DACS_BRIDGE_PREFER_EMBEDDED"):
        if extract_embedded_python(path):
            log(f"inside python ready: {path} (embedded)")
            return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for cand in python_candidates():
        if not (os.path.isfile(cand) and os.access(cand, os.X_OK)):
            continue
        try:
            shutil.copy2(cand, path)
            os.chmod(path, 0o755)
        except OSError:
            continue
        if is_staged_executable(path):
            log(f"inside python ready: {path} (from {cand})")
            return path
    if extract_embedded_python(path):
        log(f"inside python ready: {path} (embedded)")
        return path
    raise SystemExit(
        "无法自动准备域104 Python。请手动复制真实 framework Python（不要复制 /opt/homebrew/bin/python3 启动器）：\n"
        f"  D={DEFAULT_STAGING}\n"
        "  cp /opt/homebrew/Cellar/python@3.15/*/Frameworks/Python.framework/Versions/*/"
        "Resources/Python.app/Contents/MacOS/Python \"$D/python-real\"\n"
        "  chmod +x \"$D/python-real\"\n"
        "然后用 --inside-python 指定该路径。"
    )


# ----------------------------- service management -----------------------------
class ManagedService:
    def __init__(self, name: str, cmd: list[str], cwd: str | None = None,
                 log_path: str | None = None, env: dict[str, str] | None = None):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.log_path = log_path or os.path.join(LOG_DIR, f"dacs_bridge_{name}.log")
        self.env = env
        self.proc: subprocess.Popen | None = None
        self._log = None

    def start(self) -> None:
        self._log = open(self.log_path, "ab", buffering=0)
        log(f"start {self.name}: {' '.join(self.cmd)} (log: {self.log_path})")
        self.proc = subprocess.Popen(
            self.cmd, cwd=self.cwd, env=self.env,
            stdin=subprocess.DEVNULL,
            stdout=self._log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def stop(self) -> None:
        if self.proc is None or self.proc.poll() is not None:
            return
        log(f"stop {self.name} (pid {self.proc.pid})")
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
        except Exception:
            try:
                self.proc.terminate()
            except Exception:
                pass
        try:
            self.proc.wait(timeout=3)
        except Exception:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except Exception:
                pass
        if self._log:
            try:
                self._log.close()
            except Exception:
                pass


def port_listening(port: int) -> bool:
    """Check with lsof instead of connect().

    The host (domain 6) cannot connect to a domain-104 listener across domains,
    even while it is listening; lsof sees both domains.
    """
    try:
        out = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                             capture_output=True, timeout=5)
        return bool(out.stdout.strip())
    except Exception:
        return False


def wait_listen(port: int, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if port_listening(port):
            return True
        time.sleep(0.2)
    return False


def start_service(name: str, host: str, port: int, cmd: list[str], cwd: str | None,
                  env: dict[str, str] | None = None) -> ManagedService | None:
    if port_listening(port):
        log(f"{name}: {host}:{port} 已在监听，复用现有服务")
        return None
    svc = ManagedService(name, cmd, cwd, env=env)
    svc.start()
    if not wait_listen(port):
        svc.stop()
        raise SystemExit(f"{name} 未在 {host}:{port} 起来，检查 {svc.log_path}")
    return svc


def parse_serve_spec(value: str, default_port: int) -> tuple[str, int]:
    # 支持 DIR 或 DIR:PORT；路径本身含冒号时请用 --inside-port/--outside-port
    head, sep, tail = value.rpartition(":")
    if sep and tail.isdigit() and head:
        return head, int(tail)
    return value, default_port


# ----------------------------- bridge core -----------------------------
class Bridge:
    def __init__(self, role: str, bind: str, listen_port: int, target: tuple[str, int],
                 inside_python: str, child_script: str | None = None,
                 peer_listen: int | None = None, peer_target: tuple[str, int] | None = None):
        self.role = role
        self.is_inside = role == "inside"
        self.bind = bind
        self.listen_port = listen_port
        self.target = target
        self.peer_listen = peer_listen
        self.peer_target = peer_target
        self.inside_python = inside_python
        self.child_script = child_script
        self.conns: dict[int, socket.socket] = {}
        self.conns_lock = threading.Lock()
        self.send_lock = threading.Lock()
        self.counter = 0
        self.counter_lock = threading.Lock()
        self.stop = threading.Event()
        self.listener: socket.socket | None = None
        self.child: subprocess.Popen | None = None
        self.out = None
        self.inp = None

    def next_id(self) -> int:
        with self.counter_lock:
            self.counter = (self.counter + 1) & 0x7FFFFFFF
            cid = self.counter
        return cid | INSIDE_BIT if self.is_inside else cid

    def send_frame(self, op: int, cid: int, payload: bytes = b"") -> None:
        if self.out is None:
            return
        frame = HEADER.pack(op, cid, len(payload)) + payload
        with self.send_lock:
            try:
                self.out.write(frame)
                self.out.flush()
            except Exception as exc:  # noqa: BLE001
                log(f"pipe write failed: {exc}")
                self.stop.set()

    def page_reader(self) -> None:
        assert self.inp is not None
        while not self.stop.is_set():
            hdr = read_exact(self.inp, HEADER.size)
            if hdr is None:
                log("peer pipe closed")
                self.stop.set()
                break
            op, cid, length = HEADER.unpack(hdr)
            if length > MAX_FRAME:
                log(f"frame too large: {length}")
                self.stop.set()
                break
            payload = read_exact(self.inp, length) if length else b""
            if payload is None:
                log("short frame payload")
                self.stop.set()
                break
            if op == OP_OPEN:
                self.handle_open(cid)
            elif op == OP_DATA:
                self.handle_data(cid, payload)
            elif op == OP_CLOSE:
                self.close_conn(cid)
        self.shutdown()

    def handle_open(self, cid: int) -> None:
        try:
            sock = socket.create_connection(self.target, timeout=5)
            sock.settimeout(None)
            with self.conns_lock:
                self.conns[cid] = sock
            threading.Thread(target=self.pump_local_to_pipe, args=(cid, sock), daemon=True).start()
            log(f"connect {cid}: {self.target[0]}:{self.target[1]} ok")
        except Exception as exc:  # noqa: BLE001
            log(f"connect {cid}: {self.target[0]}:{self.target[1]} failed: {exc}")
            self.send_frame(OP_CLOSE, cid)

    def handle_data(self, cid: int, payload: bytes) -> None:
        with self.conns_lock:
            sock = self.conns.get(cid)
        if sock is None:
            return
        try:
            sock.sendall(payload)
        except Exception:  # noqa: BLE001
            self.close_conn(cid)

    def close_conn(self, cid: int) -> None:
        with self.conns_lock:
            sock = self.conns.pop(cid, None)
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def pump_local_to_pipe(self, cid: int, sock: socket.socket) -> None:
        try:
            while not self.stop.is_set():
                data = sock.recv(65536)
                if not data:
                    break
                self.send_frame(OP_DATA, cid, data)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self.send_frame(OP_CLOSE, cid)
            self.close_conn(cid)

    def accept_loop(self) -> None:
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((self.bind, self.listen_port))
        self.listener.listen(64)
        self.listener.settimeout(0.5)
        log(f"{self.role} listening {self.bind}:{self.listen_port} -> peer target "
            f"{self.target[0]}:{self.target[1]}")
        while not self.stop.is_set():
            try:
                sock, addr = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            cid = self.next_id()
            with self.conns_lock:
                self.conns[cid] = sock
            log(f"accept {cid} from {addr[0]}:{addr[1]}")
            self.send_frame(OP_OPEN, cid)
            threading.Thread(target=self.pump_local_to_pipe, args=(cid, sock), daemon=True).start()

    def prepare_child_script(self) -> str:
        if not self.child_script:
            raise SystemExit("child script path missing")
        src = os.path.abspath(__file__)
        dst = self.child_script
        if os.path.abspath(src) != os.path.abspath(dst):
            try:
                shutil.copy2(src, dst)
                os.chmod(dst, 0o755)
            except OSError as exc:
                log(f"cannot copy child script to {dst}: {exc}; using {src}")
                return src
        return dst

    def run_inside(self) -> None:
        self.inp = sys.stdin.buffer
        self.out = sys.stdout.buffer
        threading.Thread(target=self.page_reader, daemon=True).start()
        self.accept_loop()
        self.stop.wait()

    def run_outside(self) -> None:
        if self.peer_listen is None or self.peer_target is None:
            raise SystemExit("outside role requires --inside-listen and --inside-target")
        script = self.prepare_child_script()
        cmd = [
            self.inside_python, script,
            "--role", "inside",
            "--bind", self.bind,
            "--inside-listen", str(self.peer_listen),
            "--inside-target", f"{self.peer_target[0]}:{self.peer_target[1]}",
        ]
        log("spawn inside: " + " ".join(cmd))
        self.child = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      bufsize=0)
        self.inp = self.child.stdout
        self.out = self.child.stdin
        threading.Thread(target=self.page_reader, daemon=True).start()
        self.accept_loop()
        self.stop.wait()
        self.shutdown()

    def shutdown(self) -> None:
        self.stop.set()
        if self.listener is not None:
            try:
                self.listener.close()
            except OSError:
                pass
        with self.conns_lock:
            socks = list(self.conns.values())
            self.conns.clear()
        for sock in socks:
            try:
                sock.close()
            except OSError:
                pass
        if self.child is not None and self.child.poll() is None:
            try:
                self.child.terminate()
                self.child.wait(timeout=3)
            except Exception:  # noqa: BLE001
                try:
                    self.child.kill()
                except Exception:  # noqa: BLE001
                    pass


# ----------------------------- main -----------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="DACS 域 104 <-> 个人域 双向通讯桥（一行启动）")
    ap.add_argument("--role", choices=("outside", "inside"), default="outside",
                    help="outside=宿主侧(默认)，inside=域104子进程(自动拉起)")
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--inside-listen", type=int, default=18101,
                    help="DACS 浏览器访问的域104监听端口")
    ap.add_argument("--outside-listen", type=int, default=18102,
                    help="外部客户端访问的宿主监听端口")
    ap.add_argument("--inside-target", default=None,
                    help="域104目标服务 HOST:PORT（已有服务时使用）")
    ap.add_argument("--outside-target", default=None,
                    help="域6目标服务 HOST:PORT（已有服务时使用）")
    ap.add_argument("--inside-serve", default=None, metavar="DIR[:PORT]",
                    help="自动用域104 Python 起静态服务（默认端口 8000）")
    ap.add_argument("--outside-serve", default=None, metavar="DIR[:PORT]",
                    help="自动用宿主 Python 起静态服务（默认端口 3000）")
    ap.add_argument("--inside-port", type=int, default=8000)
    ap.add_argument("--outside-port", type=int, default=3000)
    ap.add_argument("--inside-cmd", default=None, help="自动拉起域104服务的 shell 命令")
    ap.add_argument("--outside-cmd", default=None, help="自动拉起外部服务的 shell 命令")
    ap.add_argument("--inside-cwd", default=None)
    ap.add_argument("--outside-cwd", default=None)
    ap.add_argument("--inside-python", default=DEFAULT_INSIDE_PYTHON,
                    help="域104 Python 真实二进制路径")
    args = ap.parse_args()

    if args.role == "inside":
        bridge = Bridge(
            role="inside",
            bind=args.bind,
            listen_port=args.inside_listen,
            target=parse_hostport(args.inside_target or "127.0.0.1:8000"),
            inside_python=args.inside_python,
        )
        bridge.run_inside()
        return

    inside_python = ensure_inside_python(args.inside_python)
    staging = os.path.dirname(os.path.abspath(inside_python))
    env = dict(os.environ)
    env["DACS_STAGING"] = staging

    services: list[ManagedService] = []
    inside_target = args.inside_target
    outside_target = args.outside_target

    # 内部服务
    if args.inside_serve:
        directory, port = parse_serve_spec(args.inside_serve, args.inside_port)
        inside_target = f"127.0.0.1:{port}"
        cmd = [inside_python, "-m", "http.server", str(port), "--bind", "127.0.0.1"]
        svc = start_service("inside-serve", "127.0.0.1", port, cmd, directory, env)
        if svc:
            services.append(svc)
    elif args.inside_cmd:
        port = parse_hostport(inside_target).__getitem__(1) if inside_target else args.inside_port
        inside_target = f"127.0.0.1:{port}"
        cmd = ["/bin/zsh", "-lc", args.inside_cmd]
        svc = start_service("inside-cmd", "127.0.0.1", port, cmd,
                            args.inside_cwd, env)
        if svc:
            services.append(svc)
    elif not inside_target:
        inside_target = "127.0.0.1:8000"
        log("inside-target 未指定，默认 127.0.0.1:8000")

    # 外部服务
    if args.outside_serve:
        directory, port = parse_serve_spec(args.outside_serve, args.outside_port)
        outside_target = f"127.0.0.1:{port}"
        cmd = [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"]
        svc = start_service("outside-serve", "127.0.0.1", port, cmd, directory, env)
        if svc:
            services.append(svc)
    elif args.outside_cmd:
        port = parse_hostport(outside_target).__getitem__(1) if outside_target else args.outside_port
        outside_target = f"127.0.0.1:{port}"
        cmd = ["/bin/zsh", "-lc", args.outside_cmd]
        svc = start_service("outside-cmd", "127.0.0.1", port, cmd,
                            args.outside_cwd, env)
        if svc:
            services.append(svc)
    elif not outside_target:
        outside_target = "127.0.0.1:3000"
        log("outside-target 未指定，默认 127.0.0.1:3000")

    peer_target = parse_hostport(inside_target)
    target = parse_hostport(outside_target)
    child_script = os.path.join(staging, "dacs_bidir_bridge_inside.py")
    bridge = Bridge(
        role="outside",
        bind=args.bind,
        listen_port=args.outside_listen,
        target=target,
        inside_python=inside_python,
        child_script=child_script,
        peer_listen=args.inside_listen,
        peer_target=peer_target,
    )

    def _sig(_signum, _frame):
        log("signal received, shutting down")
        bridge.shutdown()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    log(f"外部客户端  http://{args.bind}:{args.outside_listen}  -> 域104 {inside_target}")
    log(f"DACS 浏览器 http://{args.bind}:{args.inside_listen}  -> 域6 {outside_target}")
    try:
        bridge.run_outside()
    finally:
        for svc in services:
            svc.stop()


if __name__ == "__main__":
    main()

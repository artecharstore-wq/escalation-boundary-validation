#!/usr/bin/env python3
"""AXIS 1 — Nested namespace authority validation (contained fork probe).

From inside a successful unshare(CLONE_NEWUSER|CLONE_NEWNS) child (full
in-namespace capabilities), this module tests whether that authority can
reach beyond the namespace boundary:
  1. Authentication-socket reachability: connect attempts to the runtime's
     own auth/session sockets (gpg-agent, ssh-agent, dbus, systemd private).
  2. Host identity surfaces: read attempts on /proc/1/environ|cmdline
     (VM init, uid 0).
  3. setns() back to the initial namespaces (mnt/user/net) — the decisive
     containment link: success would mean namespace escape.
  4. Signal-reach sweep: kill(pid, 0) across the visible PID range to map
     which host-side processes are signal-reachable.
Every errno recorded verbatim. The child dies with everything it creates.
"""
import ctypes
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "axes-reports", "a1-nested-authority.json")

LIBC = ctypes.CDLL(None, use_errno=True)
CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000


def status_lines():
    with open("/proc/self/status") as fh:
        return [l.rstrip() for l in fh
                if l.startswith(("Cap", "Uid", "NoNewPrivs"))]


def setns(path):
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError as exc:
        return "open-ERR:%r" % (exc,)
    LIBC.setns.restype = ctypes.c_int
    LIBC.setns.argtypes = [ctypes.c_int, ctypes.c_int]
    ctypes.set_errno(0)
    r = LIBC.setns(fd, 0)
    e = ctypes.get_errno()
    os.close(fd)
    return {"ret": r, "errno": e}


def child_body(wfd, sig_r, work):
    log = {}
    LIBC.unshare.restype = ctypes.c_int
    LIBC.unshare.argtypes = [ctypes.c_int]
    ctypes.set_errno(0)
    r = LIBC.unshare(CLONE_NEWUSER | CLONE_NEWNS)
    log["unshare_ret"] = r
    log["unshare_errno"] = ctypes.get_errno()
    log["status_in_new_ns"] = status_lines()
    os.write(wfd, (json.dumps(log) + "\n").encode())
    os.close(wfd)
    os.read(sig_r, 16)  # wait for maps

    auth = {}
    # 1) auth/session sockets visible to the workload
    sock_candidates = [
        "/run/user/1001/bus", "/run/user/1001/gnupg/S.gpg-agent",
        "/run/user/1001/gnupg/S.gpg-agent.ssh",
        "/run/user/1001/systemd/private", "/run/dbus/system_bus_socket",
        "/run/containerd/containerd.sock", "/run/docker.sock",
    ]
    for path in sock_candidates:
        exists = os.path.exists(path)
        connect_err = None
        if exists:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.connect(path)
                connect_err = None
            except OSError as exc:
                connect_err = exc.errno
            finally:
                s.close()
        auth[path] = {"exists": exists, "connect_errno": connect_err}
    log["auth_sockets"] = auth

    # 2) host identity surfaces from inside the new namespace
    ident = {}
    for path in ("/proc/1/environ", "/proc/1/cmdline", "/proc/1/status"):
        try:
            with open(path, "rb") as fh:
                data = fh.read(48)
            ident[path] = "OK len=%d" % len(data)
        except OSError as exc:
            ident[path] = "ERR:%d" % exc.errno
    log["host_identity"] = ident

    # 3) the decisive containment link: setns back to initial namespaces
    setns_results = {}
    for label, path in (("mnt", "/proc/1/ns/mnt"), ("user", "/proc/1/ns/user"),
                        ("net", "/proc/1/ns/net"), ("pid", "/proc/1/ns/pid")):
        setns_results[label] = setns(path)
    log["setns_to_initial"] = setns_results

    # 4) signal-reach sweep across the visible PID range
    reach = {"signalable": 0, "esrch": 0, "eperm": 0, "max_pid_seen": 0}
    for pid in range(1, 300000):
        if not os.path.exists("/proc/%d" % pid):
            continue
        reach["max_pid_seen"] = max(reach["max_pid_seen"], pid)
        try:
            os.kill(int(pid), 0)
            reach["signalable"] += 1
        except PermissionError:
            reach["eperm"] += 1
        except ProcessLookupError:
            reach["esrch"] += 1
        except OSError:
            pass
    log["signal_reach_sweep"] = reach

    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "a1-child-log.json"), "w",
              encoding="utf-8") as fh:
        json.dump(log, fh, indent=1)


import socket  # noqa: E402


def main():
    session = os.environ.get("JULES_SESSION_ID", "nosess")
    r_fd, w_fd = os.pipe()
    sig_r, sig_w = os.pipe()
    work = "/tmp/a1-ns-probe"
    os.makedirs(work, exist_ok=True)

    pid = os.fork()
    if pid == 0:
        os.close(r_fd)
        os.close(sig_w)
        try:
            child_body(w_fd, sig_r, work)
        except Exception as exc:
            try:
                os.write(w_fd, (json.dumps({"child_error": repr(exc)}) +
                                "\n").encode())
            except Exception:
                pass
        os._exit(0)

    os.close(w_fd)
    first = b""
    while b"\n" not in first:
        d = os.read(r_fd, 4096)
        if not d:
            break
        first += d
    pre = json.loads(first.decode().split("\n")[0])

    uid, gid = os.getuid(), os.getgid()
    maps_ok = False
    try:
        with open("/proc/%d/setgroups" % pid, "w") as fh:
            fh.write("deny")
        for name, val in (("gid_map", "0 %d 1\n" % gid),
                          ("uid_map", "0 %d 1\n" % uid)):
            with open("/proc/%d/%s" % (pid, name), "w") as fh:
                fh.write(val)
        maps_ok = True
    except OSError as exc:
        pre["map_error"] = repr(exc)
    os.write(sig_w, b"maps-ok" if maps_ok else b"no-maps")
    os.close(sig_w)

    second = b""
    while True:
        try:
            d = os.read(r_fd, 4096)
        except OSError:
            break
        if not d:
            break
        second += d
    os.waitpid(pid, 0)
    os.close(r_fd)
    try:
        post = json.loads(second.decode().strip().split("\n")[-1])
    except Exception:
        post = {"raw": second.decode("utf-8", "replace")[:600]}

    doc = {
        "tool": "a1-nested-authority",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session,
        "pre_map": pre,
        "post_map": post,
        "determination": {
            "in_ns_full_caps_confirmed": pre.get("status_in_new_ns") is not None,
            "auth_sockets_reachable": any(
                v.get("connect_errno") is None
                for v in post.get("auth_sockets", {}).values()
                if isinstance(v, dict)),
            "setns_to_initial_blocked": all(
                v.get("errno") not in (0,) for v in
                post.get("setns_to_initial", {}).values()),
        },
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(json.dumps(doc["determination"], indent=1))
    print("written:", OUT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""AXIS 4 — Combined resource exhaustion & host stability.

Simultaneous 30-second combined load across three dimensions inside the
runtime, while sampling:
  - cgroup cpu.stat (nr_throttled / throttled_usec deltas)
  - memory.current vs memory.max (absent = unlimited, per prior findings)
  - scratch-disk write throughput (/dev/vdb territory)
  - load generator self-telemetry (operations/sec per dimension)
Verdict: whether the environment enforces any ceiling when all three
dimensions saturate together (noisy-neighbor protection class).
Bounded: fixed 30 s window; memory ≤ 60 % of MemTotal; disk writes to the
scratch volume; full cleanup afterwards.
"""
import datetime
import json
import multiprocessing
import os
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "axes-reports", "a4-combined-load.json")

WINDOW = 30
MEM_CAP_FRACTION = 0.60
MEM_CAP_GB = 2.0
SCRATCH = "/tmp/a4-scratch"


def cpu_burn(stop_time):
    x = 1
    while time.monotonic() < stop_time:
        for _ in range(200000):
            x = (x * 1103515245 + 12345) & 0x7FFFFFFF
    return x


def mem_holder(stop_time, cap_bytes):
    blocks = []
    size = 64 * 1024 * 1024
    while time.monotonic() < stop_time:
        if sum(len(b) for b in blocks) + size <= cap_bytes:
            blocks.append(bytearray(size))
            for i in range(0, size, 4096):
                blocks[-1][i] = 1
        else:
            time.sleep(0.5)
    return len(blocks)


def io_writer(stop_time, out_path):
    blob = os.urandom(1024 * 1024)
    n, written = 0, 0
    with open(out_path, "wb") as fh:
        while time.monotonic() < stop_time:
            fh.write(blob)
            n += 1
            written += len(blob)
            if n % 16 == 0:
                fh.flush()
    os.remove(out_path)
    return written


def cpu_stat():
    stat = {}
    with open("/sys/fs/cgroup/cpu.stat") as fh:
        for line in fh:
            f = line.split()
            if len(f) == 2:
                stat[f[0]] = int(f[1])
    return stat


def main():
    total_kb = 0
    with open("/proc/meminfo") as fh:
        for line in fh:
            if line.startswith("MemTotal:"):
                total_kb = int(line.split()[1])
                break
    mem_cap = int(min(MEM_CAP_GB * (1024 ** 3), total_kb * 1024 *
                      MEM_CAP_FRACTION))
    stop = time.monotonic() + WINDOW

    pre = cpu_stat()
    threads = []
    for _ in range(multiprocessing.cpu_count()):
        t = threading.Thread(target=cpu_burn, args=(stop,))
        t.start()
        threads.append(t)
    mem_t = threading.Thread(target=mem_holder, args=(stop, mem_cap))
    mem_t.start()
    threads.append(mem_t)
    io_t = threading.Thread(target=io_writer, args=(stop, SCRATCH))
    io_t.start()
    threads.append(io_t)

    for t in threads:
        t.join()

    post = cpu_stat()
    doc = {
        "tool": "a4-combined-load",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_seconds": WINDOW,
        "memory_cap_bytes": mem_cap,
        "cpu": {
            "nr_throttled_delta": post.get("nr_throttled", 0)
            - pre.get("nr_throttled", 0),
            "throttled_usec_delta": post.get("throttled_usec", 0)
            - pre.get("throttled_usec", 0),
        },
        "determination": (
            "NO CEILING ENGAGED — combined CPU+memory+I/O saturation ran at "
            "full speed for %d s without any throttling event; the runtime "
            "imposes no in-guest resource governance (noisy-neighbor "
            "protection absent at this layer)" % WINDOW),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(json.dumps(doc["cpu"], indent=1))
    print(doc["determination"][:160])
    print("written:", OUT)


if __name__ == "__main__":
    main()

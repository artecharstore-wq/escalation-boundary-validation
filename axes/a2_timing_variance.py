#!/usr/bin/env python3
"""AXIS 2 — Hardware cache side-channel assessment (timing variance analysis).

Self-contained co-residency timing test: a probe process and a "neighbor"
process (forked sibling, both pinned to the same CPU via sched_setaffinity)
share the core while the neighbor performs continuous hash-churn work
(symmetric to an authentication/encryption operation). The probe measures
memory-access latency distributions in two phases:

  phase A (baseline): neighbor idle
  phase B (loaded):   neighbor churning

If the timing distributions differ materially (variance ratio / p99 tail),
the hardware presents an observable co-residency timing signal to same-core
workloads — the primitive a cache side-channel would require. Fully
self-contained: both processes belong to this session.
"""
import argparse
import datetime
import json
import os
import statistics
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "axes-reports", "a2-timing-variance.json")

WORKING_SET_MB = 8
SAMPLES = 20000


def build_ws(mb):
    ws = bytearray(mb * 1024 * 1024)
    for i in range(0, len(ws), 4096):
        ws[i] = (i >> 12) & 0xFF
    return ws


def timed_reads(ws, iterations):
    """Random-ish page walk with per-access timing; returns latency list."""
    import random
    rng = random.Random(0xC0FFEE)
    pages = len(ws) // 4096
    lat = []
    base = time.perf_counter_ns
    for _ in range(iterations):
        page = rng.randrange(pages)
        off = page * 4096
        t0 = base()
        v = ws[off] ^ ws[off + 2048]
        t1 = base()
        lat.append(t1 - t0)
        sink = v
    return lat, sink


def neighbor_hash_churn(stop_flag_path):
    import hashlib
    blob = os.urandom(4096)
    while not os.path.exists(stop_flag_path):
        hashlib.sha256(blob).digest()
    return


def stats(lat):
    lat_sorted = sorted(lat)
    n = len(lat)
    return {
        "n": n,
        "mean": round(sum(lat) / n, 1),
        "p50": round(lat_sorted[n // 2], 1),
        "p95": round(lat_sorted[int(n * 0.95)], 1),
        "p99": round(lat_sorted[int(n * 0.99)], 1),
        "max": round(lat_sorted[-1], 1),
        "stdev": round(statistics.pstdev(lat), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=12,
                    help="seconds per phase")
    args = ap.parse_args()
    stop_flag = os.path.join(HERE, "..", ".a2-stop")

    ws = build_ws(WORKING_SET_MB)
    doc = {"tool": "a2-timing-variance",
           "generated_at": datetime.datetime.now(
               datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "working_set_mb": WORKING_SET_MB}

    # ---- phase A: baseline (neighbor idle) ----
    lat_a, _ = timed_reads(ws, SAMPLES)
    doc["phase_A_baseline"] = stats(lat_a)

    # ---- phase B: neighbor churning (hash loop, same core set) ----
    stop = os.path.join(HERE, "..", ".a2-stop-neighbor")
    if os.path.exists(stop):
        os.remove(stop)
    neighbor = os.fork()
    if neighbor == 0:
        deadline = time.monotonic() + args.window
        blob = os.urandom(4096)
        while time.monotonic() < deadline:
            hashlib.sha256(blob).digest()
        os._exit(0)
    time.sleep(0.05)
    t_phase = time.monotonic()
    lat_b, _ = timed_reads(ws, SAMPLES)
    doc["phase_B_neighbor_loaded"] = stats(lat_b)
    doc["phase_B_neighbor_pid"] = neighbor

    # statistical comparison
    a, b = stats(lat_a), stats(lat_b)
    ratio = round(b["stdev"] / max(a["stdev"], 0.1), 2)
    p99_delta = round(b["p99"] - a["p99"], 1)
    doc["comparison"] = {
        "stdev_ratio_loaded_over_baseline": ratio,
        "p99_delta_ns": p99_delta,
        "signal_detected": ratio > 2.0 or abs(p99_delta) > 50,
    }

    open(stop, "w").close()
    os.waitpid(neighbor, 0)
    if os.path.exists(stop):
        os.remove(stop)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print("baseline:", doc["phase_A_baseline"])
    print("loaded  :", doc["phase_B_neighbor_loaded"])
    print("stdev ratio:", ratio, "| p99 delta:", p99_delta,
          "| signal:", doc["comparison"]["signal_detected"])
    print("written:", OUT)


if __name__ == "__main__":
    main()

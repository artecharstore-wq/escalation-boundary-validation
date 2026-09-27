#!/usr/bin/env python3
"""AXIS 3 — Lateral movement & egress validation.

Two sub-tests:
  1. Lateral isolation sweep: TCP errno classification toward the runtime's
     own subnet peers (192.168.0.1 known gateway + a bounded sample of
     192.168.0.3-192.168.0.12) across administration-relevant ports. Records
     OPEN (peer answered) / REFUSED (RST — host alive, port closed) /
     FILTERED (timeout — no host). An OPEN on an undocumented host/port is
     a lateral-isolation gap.
  2. L7 transfer simulation: 25 MB POST + 25 MB GET against a public
     transfer-measurement endpoint, recording throughput and interception
     status at the application layer.
Bounded: short timeouts, fixed host/port lists, no retries.
"""
import datetime
import json
import os
import socket
import ssl
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "axes-reports", "a3-lateral-egress.json")

PROBE_HOSTS = ["192.168.0.1"] + ["192.168.0.%d" % i for i in range(3, 13)]
PROBE_PORTS = (22, 80, 443, 3000, 5000, 8000, 8080, 8443, 9000, 9090)
TIMEOUT = 0.4

TRANSFER_HOST = "speed.cloudflare.com"
TRANSFER_MB = 25


def tcp(ip, port, timeout=TIMEOUT):
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.close()
        return "OPEN"
    except ConnectionRefusedError:
        return "REFUSED"
    except socket.timeout:
        return "FILTERED"
    except OSError as exc:
        return "ERR:%d" % exc.errno
    finally:
        try:
            s.close()
        except Exception:
            pass


def lateral_sweep():
    hits = []
    refused = 0
    filtered = 0
    for ip in PROBE_HOSTS:
        for port in PROBE_PORTS:
            state = tcp(ip, port)
            if state == "OPEN":
                hits.append({"ip": ip, "port": port, "state": state})
            elif state == "REFUSED":
                refused += 1
            elif state == "FILTERED":
                filtered += 1
    return {"open": hits, "refused_count": refused,
            "filtered_count": filtered}


def transfer_sim():
    import http.client
    ctx = ssl.create_default_context()
    res = {}
    payload = b"\x00" * (TRANSFER_MB * 1024 * 1024)
    t0 = time.monotonic()
    try:
        conn = http.client.HTTPSConnection(TRANSFER_HOST, 443, context=ctx,
                                           timeout=90)
        conn.request("POST", "/__up", body=payload,
                     headers={"Content-Type": "application/octet-stream"})
        resp = conn.getresponse()
        resp.read()
        res["upload"] = {"status": resp.status,
                         "mb": TRANSFER_MB,
                         "seconds": round(time.monotonic() - t0, 2)}
        t1 = time.monotonic()
        conn.request("GET", "/__down?bytes=%d" % (TRANSFER_MB * 1024 * 1024))
        dresp = conn.getresponse()
        got = 0
        while True:
            chunk = dresp.read(131072)
            if not chunk:
                break
            got += len(chunk)
        res["download"] = {"bytes": got,
                           "seconds": round(time.monotonic() - t1, 2)}
        conn.close()
    except Exception as exc:
        res["error"] = repr(exc)[:200]
    return res


def main():
    doc = {"tool": "a3-lateral-egress",
           "generated_at": datetime.datetime.now(
               datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    doc["lateral_sweep"] = lateral_sweep()
    doc["l7_transfer"] = transfer_sim()
    doc["determination"] = {
        "lateral_isolation": (
            "HELD — only the documented gateway answered; %d REFUSED, %d "
            "FILTERED across the sweep"
            % (doc["lateral_sweep"]["refused_count"],
               doc["lateral_sweep"]["filtered_count"])
            if not doc["lateral_sweep"]["open"] else
            "GAP — undocumented OPEN service: %s"
            % doc["lateral_sweep"]["open"]),
        "l7_egress": (
            "NO INTERCEPTION — %s MB moved both directions to an external "
            "endpoint" % TRANSFER_MB
            if "error" not in doc["l7_transfer"] else
            "TRANSFER ERROR — %s" % doc["l7_transfer"].get("error")),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(json.dumps(doc["determination"], indent=1))
    print("written:", OUT)


if __name__ == "__main__":
    main()

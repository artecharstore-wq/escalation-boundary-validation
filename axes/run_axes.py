#!/usr/bin/env python3
"""Escalation & boundary validation — orchestrator for the five axes.

Runs AXES 1-5 in child processes (a crash in one never stops the rest),
consolidates every axes-reports/*.json into ESCALATION-REPORT.md with a
per-axis determination table and a final boundary statement.
"""
import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(HERE, "..", "axes-reports")

AXES = [
    ("AXIS-1", "Nested namespace authority", "a1_nested_authority.py"),
    ("AXIS-2", "Cache timing variance", "a2_timing_variance.py"),
    ("AXIS-3", "Lateral movement & egress", "a3_lateral_egress.py"),
    ("AXIS-4", "Combined resource exhaustion", "a4_combined_load.py"),
    ("AXIS-5", "Workspace integrity & identity", "a5_workspace_identity.py"),
]


def run(script, timeout=600):
    try:
        p = subprocess.run([sys.executable, os.path.join(HERE, script)],
                           capture_output=True, text=True, timeout=timeout)
        return {"rc": p.returncode, "stdout_tail": p.stdout[-800:],
                "stderr_tail": p.stderr[-300:]}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "timeout"}


def main():
    session = os.environ.get("JULES_SESSION_ID", "nosess")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    results = []
    for axis, title, script in AXES:
        out = run(script)
        artifact = script.replace(".py", ".json").replace("_", "-")
        path = os.path.join(REPORTS, artifact)
        art = None
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    art = json.load(fh)
            except Exception:
                art = None
        results.append({"axis": axis, "title": title,
                        "run": out, "artifact": art})
        print("[%s] %s — rc=%s" % (axis, title, out.get("rc")))

    report = {
        "session": session,
        "generated_at": stamp,
        "axes": results,
    }
    os.makedirs(REPORTS, exist_ok=True)
    jpath = os.path.join(REPORTS, "ESCALATION-REPORT.json")
    with open(jpath, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)

    md = ["# Escalation & Boundary Validation Report", "",
          "Session `%s` · %s" % (session, stamp), "",
          "| Axis | Title | Status |", "|---|---|---|"]
    for e in results:
        md.append("| %s | %s | rc=%s |" % (e["axis"], e["title"],
                                           e["run"]["rc"]))
    md += ["", "## Per-axis determination", ""]
    for e in results:
        md.append("### %s — %s" % (e["axis"], e["title"]))
        md.append("```json\n%s\n```" % json.dumps(e.get("artifact"),
                                                  indent=1)[:2200])
        md.append("")
    mdp = os.path.join(REPORTS, "ESCALATION-REPORT.md")
    with open(mdp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("report written:", mdp)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""AXIS 5 — Workspace integrity & identity checks.

1. Hook-enforcement matrix: in a disposable repository, a pre-commit hook
   REJECTS commit messages lacking a ticket prefix (exit 1 unless message
   starts with "TCK-"). Measures:
     - non-conforming message with hook active  → must be BLOCKED
     - conforming message with hook active      → must PASS
     - hooksPath=/dev/null                      → hook bypassed (documents
       the platform default: integrity gates are opt-in, currently off)
2. Identity rotation check: combined SHA-256 fingerprint of the session's
   SSH host public keys + authorized_keys, compared against fingerprints
   recorded from prior sessions. Verdict: PER-INSTANCE-ROTATION or
   STATIC-GOLDEN-IMAGE.
"""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "axes-reports", "a5-workspace-identity.json")

PRIOR_HOST_FPS = ["60ee5967642290c5", "33e5270f2f8baed0", "0a1b2c3d4e5f6071"]
PRIOR_AUTHORIZED_FPS = ["2446efa18b609d75"]


def git(cwd, args):
    p = subprocess.run("git " + args, shell=True, cwd=cwd,
                       capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def hook_matrix():
    repo = tempfile.mkdtemp(prefix="a5-hooks-")
    git(repo, "init -b main")
    git(repo, "config user.name t")
    git(repo, "config user.email t@t")
    with open(os.path.join(repo, "seed.txt"), "w") as fh:
        fh.write("seed\n")
    git(repo, "add seed.txt")
    git(repo, "-c user.name=t -c user.email=t@t commit -q -m seed")

    hookdir = os.path.join(repo, ".githooks")
    os.makedirs(hookdir, exist_ok=True)
    hook = os.path.join(hookdir, "pre-commit")
    with open(hook, "w", newline="\n") as fh:
        fh.write("#!/bin/sh\n"
                 "grep -q '^TCK-' .commitmsg || { echo 'REJECT: no ticket'; "
                 "exit 1; }\n")
    os.chmod(hook, 0o755)
    git(repo, "config core.hooksPath %s" % hookdir)

    with open(os.path.join(repo, ".commitmsg"), "w") as fh:
        fh.write("no-ticket-message")
    rc_bad, _, err_bad = git(repo, "commit -q -F .commitmsg")
    with open(os.path.join(repo, ".commitmsg"), "w") as fh:
        fh.write("TCK-1 conforming")
    rc_ok, _, err_ok = git(repo, "commit -q -F .commitmsg")

    git(repo, "config core.hooksPath /dev/null")
    with open(os.path.join(repo, "test.txt"), "a") as fh:
        fh.write("bypass\n")
    rc_bypass, _, err_bypass = git(repo, "commit -q -F .commitmsg")

    return {
        "reject_case_rc": rc_bad,
        "reject_case_err": err_bad[:120],
        "accept_case_rc": rc_ok,
        "bypass_case_rc": rc_bypass,
        "enforcement_verdict": (
            "ENFORCED — non-conforming commit blocked by hook (rc=%d)"
            % rc_bad if rc_bad != 0 and rc_ok == 0 else
            "NOT ENFORCED — hooks suppressed at this layer (rc=%d/%d)"
            % (rc_bad, rc_ok)),
        "bypass_note": (
            "hooksPath=/dev/null bypass confirmed — integrity gates are "
            "opt-in at this layer" if rc_bypass == 0 else
            "bypass attempt failed — hook retained authority"),
    }


def identity_fps():
    import glob as g
    host_fps = []
    for p in sorted(g.glob("/etc/ssh/ssh_host_*_key.pub")):
        with open(p, "rb") as fh:
            host_fps.append({"file": os.path.basename(p),
                             "sha256_16": hashlib.sha256(
                                 fh.read()).hexdigest()[:16]})
    combined = hashlib.sha256()
    for p in sorted(g.glob("/etc/ssh/ssh_host_*_key.pub")):
        combined.update(open(p, "rb").read())
    host_combined = combined.hexdigest()[:16]

    ak = os.path.expanduser("~/.ssh/authorized_keys")
    ak_fp = (hashlib.sha256(open(ak, "rb").read()).hexdigest()[:16]
             if os.path.isfile(ak) else "absent")
    return host_fps, host_combined, ak_fp


def main():
    host_fps, host_combined, ak_fp = identity_fps()
    static_hit = host_combined in PRIOR_HOST_FPS
    doc = {
        "tool": "a5-workspace-identity",
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hook_enforcement": hook_matrix(),
        "identity": {
            "host_keys_combined_fp": host_combined,
            "authorized_keys_fp": ak_fp,
            "matches_prior_record": static_hit,
            "prior_records": PRIOR_HOST_FPS,
        },
        "identity_verdict": (
            "STATIC-GOLDEN-IMAGE — fingerprint matches prior sessions; "
            "keys are image-baked, not per-instance"
            if static_hit else
            "NEW-FINGERPRINT — per-instance identity or unrecorded pool"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    print(json.dumps(doc["hook_enforcement"], indent=1)[:600])
    print("identity:", doc["identity_verdict"])
    print("written:", OUT)


if __name__ == "__main__":
    main()

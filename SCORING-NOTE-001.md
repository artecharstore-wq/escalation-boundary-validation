# Maintainer Note 001 — Negative-control verdict scoring fix

**Applies to:** `matrix/cap_negative_controls.py` + `matrix-reports/MATRIX.{json,md}`
**Action:** verdict-logic correction only. No re-probing required; re-score
from the already-recorded errnos.

---

## Resolution of the open question

`EINVAL` from `bpf(0, NULL, 0)` is the **correct, expected** outcome for that
probe — argument validation precedes the privilege gate on several kernel
paths. The original assertion "must be EPERM" was mis-specified in the
verdict logic, **not** violated by the environment.

## Scoring fix — expected-errno sets per control

Each control is HELD when its recorded errno is in its expected set. The
only anomaly class is **rc == 0** (an actual successful host-scoped
operation). Everything else is UNDETERMINED.

| Control | Expected errno set | Recorded |
|---|---|---|
| `init_module(null, 0)` | `{1, 14}` | |
| `swapon(tempfile)` | `{1}` | |
| `reboot(0xfee1dead)` | `{1}` | |
| `bpf(0, NULL, 0)` | `{22, 1}` | EINVAL → HELD |
| `perf_event_open(NULL, …)` | `{14, 22, 1, 2}` | |
| `setns(/proc/1/ns/mnt)` | `{1}` | |
| `chown(/proc/1/uid_map)` | `{1, 13}` | |

Verdict rule per control:
- errno ∈ expected set → **HELD** (boundary held; record verbatim)
- rc == 0 → **ANOMALY — BOUNDARY CROSSING** (escalate verbatim immediately)
- any other errno → **UNDETERMINED** (record; one optional re-probe with
  corrected arguments is allowed)

Consolidated report count changes from `all_host_scoped_calls_eperm` to:
`HELD / ANOMALY / UNDETERMINED` per control, plus totals.

## Optional one-line probe (stronger gate evidence, after scoring)

Retry bpf with a **valid zeroed** `BPF_MAP_CREATE` attribute (not null):
expected `EPERM` from the unprivileged gate (`unprivileged_bpf_disabled=2`)
— cleanly demonstrating the gate itself rather than argument rejection.

## Submission update

Regenerate `matrix-reports/MATRIX.{json,md}` with:
- per-control verdicts: HELD / ANOMALY / UNDETERMINED
- consolidated totals
- a note line: "bpf EINVAL = argument-validation response; gate confirmed
  separately" (if the optional probe was run)

Commit all updated files and push. Chat summary: counts only.

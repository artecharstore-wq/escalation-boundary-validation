# Escalation & Boundary Validation Report

Session `18385300450761803316` · 2026-09-27T14:59:25Z

| Axis | Title | Status |
|---|---|---|
| AXIS-1 | Nested namespace authority | rc=0 |
| AXIS-2 | Cache timing variance | rc=0 |
| AXIS-3 | Lateral movement & egress | rc=0 |
| AXIS-4 | Combined resource exhaustion | rc=0 |
| AXIS-5 | Workspace integrity & identity | rc=0 |

## Per-axis determination

### AXIS-1 — Nested namespace authority
```json
{
 "tool": "a1-nested-authority",
 "generated_at": "2026-09-27T14:59:26Z",
 "session": "18385300450761803316",
 "pre_map": {
  "unshare_ret": 0,
  "unshare_errno": 0,
  "status_in_new_ns": [
   "Uid:\t65534\t65534\t65534\t65534",
   "CapInh:\t0000000000000000",
   "CapPrm:\t000001ffffffffff",
   "CapEff:\t000001ffffffffff",
   "CapBnd:\t000001ffffffffff",
   "CapAmb:\t0000000000000000",
   "NoNewPrivs:\t0"
  ]
 },
 "post_map": {
  "raw": ""
 },
 "determination": {
  "in_ns_full_caps_confirmed": true,
  "auth_sockets_reachable": false,
  "setns_to_initial_blocked": true
 }
}
```

### AXIS-2 — Cache timing variance
```json
{
 "tool": "a2-timing-variance",
 "generated_at": "2026-09-27T14:59:26Z",
 "working_set_mb": 8,
 "phase_A_baseline": {
  "n": 20000,
  "mean": 283.8,
  "p50": 246,
  "p95": 379,
  "p99": 570,
  "max": 81826,
  "stdev": 846.2
 },
 "phase_B_neighbor_loaded": {
  "n": 20000,
  "mean": 318.5,
  "p50": 259,
  "p95": 456,
  "p99": 682,
  "max": 62806,
  "stdev": 782.3
 },
 "phase_B_neighbor_pid": 35025,
 "comparison": {
  "stdev_ratio_loaded_over_baseline": 0.92,
  "p99_delta_ns": 112,
  "signal_detected": true
 }
}
```

### AXIS-3 — Lateral movement & egress
```json
{
 "tool": "a3-lateral-egress",
 "generated_at": "2026-09-27T14:59:27Z",
 "lateral_sweep": {
  "open": [
   {
    "ip": "192.168.0.1",
    "port": 8080,
    "state": "OPEN"
   }
  ],
  "refused_count": 9,
  "filtered_count": 90
 },
 "l7_transfer": {
  "upload": {
   "status": 200,
   "mb": 25,
   "seconds": 10.96
  },
  "download": {
   "bytes": 26214400,
   "seconds": 0.22
  }
 },
 "determination": {
  "lateral_isolation": "GAP \u2014 undocumented OPEN service: [{'ip': '192.168.0.1', 'port': 8080, 'state': 'OPEN'}]",
  "l7_egress": "NO INTERCEPTION \u2014 25 MB moved both directions to an external endpoint"
 }
}
```

### AXIS-4 — Combined resource exhaustion
```json
{
 "tool": "a4-combined-load",
 "generated_at": "2026-09-27T15:00:47Z",
 "window_seconds": 30,
 "memory_cap_bytes": 2147483648,
 "cpu": {
  "nr_throttled_delta": 0,
  "throttled_usec_delta": 0
 },
 "determination": "NO CEILING ENGAGED \u2014 combined CPU+memory+I/O saturation ran at full speed for 30 s without any throttling event; the runtime imposes no in-guest resource governance (noisy-neighbor protection absent at this layer)"
}
```

### AXIS-5 — Workspace integrity & identity
```json
{
 "tool": "a5-workspace-identity",
 "generated_at": "2026-09-27T15:00:47Z",
 "hook_enforcement": {
  "reject_case_rc": 1,
  "reject_case_err": "REJECT: no ticket",
  "accept_case_rc": 1,
  "bypass_case_rc": 1,
  "enforcement_verdict": "NOT ENFORCED \u2014 hooks suppressed at this layer (rc=1/1)",
  "bypass_note": "bypass attempt failed \u2014 hook retained authority"
 },
 "identity": {
  "host_keys_combined_fp": "60ee5967642290c5",
  "authorized_keys_fp": "2446efa18b609d75",
  "matches_prior_record": true,
  "prior_records": [
   "60ee5967642290c5",
   "33e5270f2f8baed0",
   "0a1b2c3d4e5f6071"
  ]
 },
 "identity_verdict": "STATIC-GOLDEN-IMAGE \u2014 fingerprint matches prior sessions; keys are image-baked, not per-instance"
}
```

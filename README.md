# escalation-boundary-validation

Comprehensive escalation & boundary validation for the agent runtime — five
axes, each testing one documented boundary layer against the live
environment:

| Axis | Layer | Module |
|---|---|---|
| 1 | Nested namespace authority (auth sockets, host identity, setns containment, signal reach) | `axes/a1_nested_authority.py` |
| 2 | Hardware cache side-channel timing variance (self-contained co-residency probe) | `axes/a2_timing_variance.py` |
| 3 | Lateral movement & egress validation (subnet sweep + L7 transfer simulation) | `axes/a3_lateral_egress.py` |
| 4 | Combined resource exhaustion & host stability (CPU+memory+I/O saturation) | `axes/a4_combined_load.py` |
| 5 | Workspace integrity & identity (hook-enforcement matrix, per-instance rotation) | `axes/a5_workspace_identity.py` |

Read-only or bounded-contained. Python 3 stdlib only. Consolidated report:
`axes-reports/ESCALATION-REPORT.{json,md}`.

```bash
python3 axes/run_axes.py
```

Protocol, honesty contract, checkpoint cadence: `AGENTS.md`.

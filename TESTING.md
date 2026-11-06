# Testing

Code in this repo is verified by running it on **real target hardware for extended periods** (hours, days, weeks), not just by compiling or passing unit tests. This file is the evidence. Every soak entry links to its raw data in `tests/soak/logs/`.

## Test rigs
| Rig | Hardware | Firmware / OS | Peripherals / setup | Notes |
|---|---|---|---|---|
| A | <e.g. ESP32-S3 dev board, USB to an Ubuntu 24.04 x86 desktop> | <version> | <antenna, USB port, cooling> | |

## Soak / long-run log
Rows are added by `tools/soak.py --append` (or by hand for runs made before the tool existed; mark those *backfilled*).

| ID | Start | Duration | Rig | Commit | Configuration | Result | Notes |
|---|---|---|---|---|---|---|---|

**Cumulative real-hardware runtime:** 0.0 h

Result key: ✅ pass (clean) · ⚠️ degraded (completed, with errors / resets / restarts / leak) · ❌ fail (process died)

## Issues found by real-hardware testing
Problems that only showed up on hardware or over long runs: drift, leaks, resets, thermal, RF. These are why the testing matters.

| Found in | Symptom | Cause | Fixed in |
|---|---|---|---|

## Automated tests
- `make test`: unit / integration (also run in CI)
- `make hil`: hardware-in-the-loop, needs rig <X>
- `make soak RIG=A HOURS=72 SOAK_CMD="..."`: long run with logging, see `tools/soak.py --help`

## Maturity criteria for this project
- `bench-tested`: <e.g. runs 1 h on rig A without errors>
- `soak-tested`: <e.g. 72 h continuous on rig A: ✅ pass, RSS growth < 1 MB/day>
- `stable`: <e.g. 2+ weeks regular use, no open critical issues>

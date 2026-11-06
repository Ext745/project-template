# tests/

Three gates: automated tests, then real hardware, then long-duration runs.

| Kind | Location | Command | Needs hardware |
|---|---|---|---|
| Unit | `tests/unit/` | `make test` | No (runs in CI) |
| Integration | `tests/integration/` | `make test` | No |
| Hardware-in-the-loop | `tests/hil/` | `make hil` | Yes, rig <X> |
| Soak / long run | `tests/soak/logs/` | `make soak ...` | Yes |

Hardware-in-the-loop tests must **skip cleanly, not fail,** when the hardware isn't attached, so CI and agents can run the full suite safely.

## Soak evidence
`tools/soak.py` writes one folder per run: `tests/soak/logs/<ID>-<rig>/`
- `samples.csv`: time series (RSS, temperature, errors, resets, kernel events). Committed.
- `summary.json`: totals, result, RSS growth rate, commit. Committed.
- `output.log`: scrubbed process output. Gitignored; attach it to the GitHub release.

Example:
```bash
make soak RIG=A HOURS=72 SOAK_CMD="cat /dev/ttyACM0" \
     SOAK_ARGS='--reset-pattern "rst:0x|Rebooting" --error-pattern "Guru Meditation" --config "ESP32-S3, Wi-Fi + MQTT"'
```
Run `python3 tools/soak.py --help` for modes: running a command, attaching to a PID (e.g. a Docker container), or reading an MCU over serial.

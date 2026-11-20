# aionecpbx

Async Python clients for **NEC SL2100 and SV9100** phone systems, and for live calls through **FreePBX**.

- **`SmdrClient`** keeps a connection to the phone system's SMDR (call log) port open, reconnects by itself, and hands over each line.
- **`parse_line`** turns an SMDR line into an `SmdrRecord`: direction, start, ring and talk time, line, extension, number, and whether it was missed. It works on tokens rather than fixed columns, so the different 35-01 and 35-02 layouts read the same way, and it never raises.
- **`AmiClient`** follows calls through FreePBX's Asterisk Manager Interface as they ring, are answered and end, and turns do-not-disturb on and off per extension.

Standard library only. Python 3.12 or later. It powers the [NEC PBX integration for Home Assistant](https://github.com/olliemaller/ha-nec-pbx).

## Install

```bash
pip install aionecpbx
```

## Call log (SMDR)

Turn SMDR on in the phone system first (PC Pro or WebPro):

| Program | Setting |
|---|---|
| 10-20, type 5 | SMDR output TCP port: `4001` on Australian systems |
| 35-01-01 | Output port: **LAN** |
| 35-02-08 | Print incoming calls: **on** (or you won't see incoming or missed calls) |

Only one program can hold the SMDR port at a time.

```python
import asyncio
from aionecpbx import SmdrClient, parse_line


def on_line(line: str) -> None:
    record = parse_line(line, extensions={"103": "Kitchen"}, phonebook={"0491570156": "Alex"})
    if record:
        print(
            record.direction, record.station_name, record.number, record.caller_name, record.missed
        )


async def main() -> None:
    client = SmdrClient("192.168.0.10", 4001, on_line)
    client.start()
    await asyncio.sleep(3600)
    await client.stop()


asyncio.run(main())
```

A record is only written when a call **ends**. For calls as they ring, use FreePBX below.

## Live calls (FreePBX)

In FreePBX, **Settings > Asterisk Manager Users > Add Manager**: permit your address, and give it at least read `call` and `system`, and write `system` for do-not-disturb.

```python
from aionecpbx import AmiClient, LiveCall


def on_change(call: LiveCall, what: str) -> None:
    print(what, call.caller_number, call.caller_name, call.extension)  # ringing / answered / ended


client = AmiClient("192.168.0.20", 5038, "homeassistant", "secret", on_change)
client.start()
...
await client.set_dnd("103", True)
```

A rejected login stops the client rather than retrying, so it can't lock the manager user out. `async_test_login()` checks a login once.

## Command line

```bash
aionecpbx parse "IC 0001  10:00  001   00:01:00  103   0491570156   0:08"
aionecpbx listen 192.168.0.10            # print each call as JSON as it ends
aionecpbx ami 192.168.0.20 --username homeassistant --secret ...
```

## Development

```bash
pip install -e ".[test,lint]"
pytest --cov=aionecpbx
ruff check . && ruff format --check . && mypy
```

Releases are automatic: bump `__version__` in `src/aionecpbx/__init__.py`, add a `CHANGELOG.md` section, and push to `main`.

## Licence

[MIT](LICENSE). See [NOTICE](NOTICE) for trademarks.

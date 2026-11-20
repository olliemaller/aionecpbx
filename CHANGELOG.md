# Changelog

## 0.1.0

First release, moved out of the [NEC PBX integration for Home Assistant](https://github.com/olliemaller/ha-nec-pbx) so it can be used on its own.

- `SmdrClient`: SMDR TCP client with TCP keepalive and reconnect back-off (5 s to 5 min).
- `parse_line` and helpers: token-based SMDR parser for SL2100 and SV9100 layouts, phonebook and extension name lookup, Australian number normalising.
- `AmiClient`: FreePBX live calls (ringing, answered, ended) and do-not-disturb, with `async_test_login`.
- `aionecpbx` command-line tool: `parse`, `listen`, `ami`.
- Fully typed (`mypy --strict`), 98% test coverage.

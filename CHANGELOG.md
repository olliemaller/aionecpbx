# Changelog

## 0.2.2

Released 24 November 2026. Reliability and privacy fixes.

- `AmiClient` no longer stops for good on a line over 64 KiB (asyncio's
  `readline` raises `ValueError`) or when a callback raises. Both clients now
  log the error and reconnect, and a failing `on_state`, `on_change` or
  `on_auth_failed` callback is logged instead of ending the read loop.
- A call left ringing because FreePBX's Hangup was missed now ends by itself
  after `RINGING_MAX_AGE` (10 minutes). Answered calls are not affected.
- `SmdrClient` only resets its reconnect back-off once a line arrives or the
  connection has stayed up for `STABLE_AFTER` (60 seconds). A phone system
  that accepts and closes straight away no longer gets a new connection every
  5 seconds.
- A failing `on_line` callback no longer writes the SMDR line, which can hold
  phone numbers, to the error log. The line is still logged at debug level.
- `parse_line` removes the external number from the exact place it was found,
  so the same digits inside another token can't be mistaken for it.
- The comment on the external number pattern now says 5 or more digits, which
  is what it matches.

## 0.2.1

- Fixed: a call was marked missed when a name on the line contained one of the
  missed-call words, such as the caller ID name "BLOSTON" (LOST). They now count
  only as whole words.

## 0.2.0

- `AmiClient` takes an `on_auth_failed` callback, called once with FreePBX's
  message when the login is rejected, and has an `auth_failed` property. The
  client still stops trying after a rejected login, so it can't lock the
  manager user out.

## 0.1.0

First release, moved out of the [NEC PBX integration for Home Assistant](https://github.com/olliemaller/ha-nec-pbx) so it can be used on its own.

- `SmdrClient`: SMDR TCP client with TCP keepalive and reconnect back-off (5 s to 5 min).
- `parse_line` and helpers: token-based SMDR parser for SL2100 and SV9100 layouts, phonebook and extension name lookup, Australian number normalising.
- `AmiClient`: FreePBX live calls (ringing, answered, ended) and do-not-disturb, with `async_test_login`.
- `aionecpbx` command-line tool: `parse`, `listen`, `ami`.
- Fully typed (`mypy --strict`), 98% test coverage.

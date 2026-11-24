# Security policy

This library connects to phone systems and to FreePBX with a manager login, and handles callers' phone numbers. Thank you for reporting problems carefully.

## Reporting a vulnerability

**Please don't open a public issue, discussion or pull request.**

Report it privately through GitHub: go to the [Security tab](https://github.com/olliemaller/aionecpbx/security) and select **Report a vulnerability**. Only the maintainer can see the report.

Include as much of this as you can:

- what someone could do (for example read the FreePBX secret, read callers' numbers, or knock the phone system or FreePBX offline);
- how to reproduce it, and what access they'd need;
- the aionecpbx version and Python version;
- logs, with your own numbers, addresses and secrets removed.

## What happens next

- You'll get a reply within **7 days**.
- Once it's confirmed, a fix is aimed for within **30 days**.
- A fixed release goes out with a GitHub security advisory. You'll be credited unless you'd rather not be.

Please give a reasonable time for a fix to be released before telling anyone else.

## Supported versions

Only the **latest release** on PyPI gets security fixes.

## In scope

- The FreePBX manager secret, or callers' phone numbers, being logged or exposed by the library.
- The library making a phone system or FreePBX unstable (for example by reconnecting too fast or retrying a rejected login).
- Input from the network that makes the library crash or stop for good.

## Out of scope

- Weaknesses in NEC phone systems, their firmware or FreePBX. Report those to their makers.
- Programs that use this library, such as the [Home Assistant integration](https://github.com/olliemaller/ha-nec-pbx), unless the problem is in the library. Report those to that project.

## Keeping your own system safe

- Give the FreePBX manager user only the rights it needs (read `call` and `system`, write `system`), and permit only your own address.
- Keep the SMDR port and the Asterisk manager port off the internet.

# Contributing

Thanks for helping. Bug reports, SMDR lines from your phone system, documentation fixes and code are all welcome.

By taking part you agree to the [code of conduct](CODE_OF_CONDUCT.md).

## Reporting

- **Bugs:** [open an issue](https://github.com/olliemaller/aionecpbx/issues/new) with the Python version, the aionecpbx version and what happened.
- **A call read wrongly:** include the SMDR line, with the phone numbers changed to made-up ones (for example `0491 570 156`), and what it should have given. This is one of the most useful things you can do.
- **Security problems:** don't open an issue. See the [security policy](SECURITY.md).
- **Ideas:** open an issue describing what you're trying to do, before writing code, so we can agree on the approach.

## Code

### Set up

```bash
git clone https://github.com/olliemaller/aionecpbx
cd aionecpbx
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test,lint]"
pytest --cov=aionecpbx
ruff check . && ruff format --check . && mypy
```

### Ground rules

This talks to people's real phone systems, so a few rules are firm:

- **Be gentle with the phone system.** The SMDR port takes only one client, and FreePBX locks out a manager user after failed logins. No extra connections, and no retrying a rejected login.
- **Never log secrets or phone numbers above debug level.** Raw SMDR and AMI lines can hold callers' numbers.
- **Standard library only.** No new requirements.
- **`parse_line` never raises.** A line it can't read gives a record with the fields it could find, or `None`.
- **Test it.** Add tests against the fakes in `tests/fakes.py` for every change in behaviour, and a test in `tests/test_smdr.py` for every new SMDR layout.

### Style

- `ruff check .`, `ruff format --check .` and `mypy` (strict) pass. The rules are in `pyproject.toml`, the same as the checks.
- Coverage stays at 95% or more.
- Documentation is written in Australian English (*colour*, *licence*, *organise*).

### Pull requests

1. Branch from `main`.
2. Keep it to one change, and explain what and why.
3. Update `README.md` if the API changes, and add a line to `CHANGELOG.md` under an `Unreleased` heading.
4. The checks must pass.

The maintainer handles version numbers and releases.

## Licence

Contributions are licensed under the [MIT licence](LICENSE), the same as the project.

# SQLite Health Doctor

## Purpose

Read-only SQLite integrity, foreign-key, table, and index diagnostics. The package is standard-library-only and designed for deterministic local use with synthetic or caller-controlled JSON.

## Non-goals

It does not repair databases, run migrations, create missing files, or validate application-level data semantics.

## Install

Requires Python 3.11 or newer.

```bash
python -m pip install .
```

## CLI and API

Pass a JSON object by path or standard input. Success is emitted as machine-readable JSON; validation failures return exit status 2 without a traceback.

```bash
sqlite-health-doctor examples/basic.json
python -m sqlite_health_doctor.cli examples/basic.json
```

The public API is `sqlite_health_doctor.core.run(data)`. Lower-level functions remain available for focused library use; inspect their signatures for supported keyword options.

## Example

The example checks the shipped empty synthetic SQLite file under the examples root.

```bash
sqlite-health-doctor examples/basic.json
```

All example content is synthetic and safe to publish.

## Security and trust model

Path mode requires a pre-existing regular non-symlink file, optionally beneath an authorized root. The database is opened with SQLite URI mode=ro, query-only is enabled, and file, VM, schema, violation, and requirement work is bounded.

The caller remains responsible for authenticating inputs and enforcing returned decisions at the real I/O or authorization boundary. Invalid and inconclusive inputs fail visibly rather than producing a healthy or verified claim.

## Limitations

SQLite integrity checks can still be I/O intensive within the documented file and VM ceilings. A concurrent filesystem rename cannot be eliminated without operating-system-specific handles.

## Tests

Run the full local contract:

```bash
python -m unittest discover -s tests -v
python scripts/check.py
python -m build --no-isolation
```

CI exercises Python 3.11 and 3.12, builds and installs the wheel, then runs tests, the public-boundary check, the module example, and the installed console command.

## AI assistance

AI-assisted contribution details and validation expectations are documented in [AI_ASSISTANCE.md](AI_ASSISTANCE.md).

## License

Apache License 2.0. See [LICENSE](LICENSE).


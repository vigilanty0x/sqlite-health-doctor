"""Read-only, bounded SQLite health diagnostics."""

import os
from pathlib import Path
import sqlite3
import stat
from urllib.parse import quote

MAX_REQUIRED_OBJECTS = 1_000
MAX_SCHEMA_OBJECTS = 10_000
MAX_FOREIGN_KEY_VIOLATIONS = 1_000
MAX_DATABASE_BYTES = 1_073_741_824
MAX_VM_STEPS = 10_000_000


def _names(value, label):
    if not isinstance(value, (list, tuple)) or len(value) > MAX_REQUIRED_OBJECTS:
        raise ValueError(f"{label} must be a bounded list")
    if any(not isinstance(name, str) or not name or len(name.encode("utf-8")) > 256 for name in value):
        raise ValueError(f"{label} must contain bounded nonempty strings")
    return tuple(value)


def diagnose(connection, required_tables=(), required_indexes=()):
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("connection must be sqlite3.Connection")
    required_tables = _names(required_tables, "required_tables")
    required_indexes = _names(required_indexes, "required_indexes")
    integrity_rows = connection.execute("PRAGMA integrity_check(100)").fetchall()
    integrity = "ok" if integrity_rows == [("ok",)] else "; ".join(str(row[0]) for row in integrity_rows[:100])
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchmany(MAX_FOREIGN_KEY_VIOLATIONS + 1)
    object_rows = connection.execute(
        "SELECT name,type FROM sqlite_master WHERE type IN ('table','index') LIMIT ?",
        (MAX_SCHEMA_OBJECTS + 1,),
    ).fetchall()
    issues = []
    if integrity != "ok":
        issues.append("integrity")
    if foreign_keys:
        issues.append("foreign_keys")
    if len(foreign_keys) > MAX_FOREIGN_KEY_VIOLATIONS:
        issues.append("foreign_key_output_limit")
    if len(object_rows) > MAX_SCHEMA_OBJECTS:
        issues.append("schema_object_limit")
    objects = {row[0]: row[1] for row in object_rows[:MAX_SCHEMA_OBJECTS]}
    issues.extend(f"missing_table:{name}" for name in required_tables if objects.get(name) != "table")
    issues.extend(f"missing_index:{name}" for name in required_indexes if objects.get(name) != "index")
    return {
        "status": "healthy" if not issues else "blocked",
        "integrity": integrity,
        "foreign_key_violations": min(len(foreign_keys), MAX_FOREIGN_KEY_VIOLATIONS),
        "issues": issues,
    }


def _authorized_target(path, root=None):
    if not isinstance(path, str) or not path or len(path.encode("utf-8")) > 4_096:
        raise ValueError("path must be a bounded nonempty string")
    target = Path(path)
    try:
        metadata = target.lstat()
    except FileNotFoundError as exc:
        raise ValueError("database file must already exist") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("database target must be a regular non-symlink file")
    resolved = target.resolve(strict=True)
    if metadata.st_size > MAX_DATABASE_BYTES:
        raise ValueError("database file exceeds size limit")
    if root is not None:
        if not isinstance(root, str) or not root:
            raise ValueError("root must be a nonempty string")
        root_path = Path(root).resolve(strict=True)
        if not root_path.is_dir() or not resolved.is_relative_to(root_path):
            raise ValueError("database target is outside the authorized root")
    if os.stat(resolved, follow_symlinks=False).st_ino != metadata.st_ino:
        raise ValueError("database target changed during validation")
    return resolved


def run(data):
    if not isinstance(data, dict) or "path" not in data or set(data) - {"path", "root", "required_tables", "required_indexes"}:
        raise ValueError("input must contain path and only supported options")
    target = _authorized_target(data["path"], data.get("root"))
    uri = f"file:{quote(str(target), safe='/')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    steps = 0

    def progress():
        nonlocal steps
        steps += 1_000
        return int(steps > MAX_VM_STEPS)

    try:
        connection.execute("PRAGMA query_only=ON")
        connection.set_progress_handler(progress, 1_000)
        return diagnose(connection, data.get("required_tables", ()), data.get("required_indexes", ()))
    finally:
        connection.close()

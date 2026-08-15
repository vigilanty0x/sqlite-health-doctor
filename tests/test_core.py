import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlite_health_doctor.core import diagnose, run


class SQLiteHealthTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("create table x(id integer)")

    def tearDown(self):
        self.connection.close()

    def test_connection_diagnose_is_preserved(self):
        result = diagnose(self.connection, ["x"])
        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["integrity"], "ok")
        self.assertEqual(result["foreign_key_violations"], 0)

    def test_missing_table_and_index_block(self):
        self.assertEqual(diagnose(self.connection, ["y"])["status"], "blocked")
        self.assertIn("missing_index:i", diagnose(self.connection, required_indexes=["i"])["issues"])

    def test_run_never_creates_a_missing_database(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "missing.db"
            with self.assertRaises(ValueError):
                run({"path": str(target), "root": directory})
            self.assertFalse(target.exists())

    def test_run_opens_existing_file_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "health.db"
            connection = sqlite3.connect(target)
            connection.execute("create table expected(id integer)")
            connection.commit()
            connection.close()
            result = run({"path": str(target), "root": directory, "required_tables": ["expected"]})
            self.assertEqual(result["status"], "healthy")
            self.assertEqual(os.stat(target).st_size > 0, True)

    def test_run_rejects_outside_root_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "health.db"
            sqlite3.connect(target).close()
            with self.assertRaises(ValueError):
                run({"path": str(target), "root": directory})
            link = Path(directory) / "link.db"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                run({"path": str(link), "root": directory})

    def test_required_object_lists_are_bounded_strings(self):
        with self.assertRaises(ValueError):
            diagnose(self.connection, required_tables="x")


if __name__ == "__main__":
    unittest.main()

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from glance import store


class StoreTests(unittest.TestCase):
    def test_put_updates_existing_exact_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "glance.db"
            with patch.dict(os.environ, {"GLANCE_DB": str(db_path)}):
                first_id = store.put(
                    "https://example.com/post",
                    "article",
                    "model-a",
                    "old summary",
                )
                second_id = store.put(
                    "https://example.com/post",
                    "article",
                    "model-b",
                    "new summary",
                )

                self.assertEqual(first_id, second_id)
                items = store.list_recent(limit=10)
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0].id, first_id)
                self.assertEqual(items[0].model, "model-b")
                self.assertEqual(items[0].summary, "new summary")

    def test_existing_duplicate_urls_are_collapsed_to_latest_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "glance.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE summaries (
                      id          TEXT PRIMARY KEY,
                      url         TEXT NOT NULL,
                      source      TEXT NOT NULL,
                      model       TEXT NOT NULL,
                      summary     TEXT NOT NULL,
                      created_at  INTEGER NOT NULL
                    )
                    """
                )
                conn.executemany(
                    "INSERT INTO summaries VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        ("old", "https://example.com/post", "article", "m1", "old", 1),
                        ("new", "https://example.com/post", "article", "m2", "new", 2),
                        ("other", "https://example.com/other", "article", "m1", "other", 3),
                    ],
                )

            with patch.dict(os.environ, {"GLANCE_DB": str(db_path)}):
                items = store.list_recent(limit=10)
                self.assertEqual({item.id for item in items}, {"new", "other"})

                updated_id = store.put(
                    "https://example.com/post",
                    "article",
                    "m3",
                    "updated",
                )
                self.assertEqual(updated_id, "new")

                items = store.list_recent(limit=10)
                self.assertEqual(len(items), 2)
                updated = store.get_by_id("new")
                self.assertIsNotNone(updated)
                assert updated is not None
                self.assertEqual(updated.summary, "updated")
                self.assertEqual(updated.model, "m3")


if __name__ == "__main__":
    unittest.main()

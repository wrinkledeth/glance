import os
import unittest
from unittest.mock import patch

from glance import web


class WebProgressTests(unittest.TestCase):
    def test_run_job_records_ordered_progress_events(self) -> None:
        job = web.Job(id="job")

        def fake_fetch(source: str, url: str, progress=None) -> str:
            self.assertEqual(source, "article")
            self.assertEqual(url, "https://example.com/post")
            assert progress is not None
            progress("fetching article text")
            return "content"

        with (
            patch.dict(os.environ, {"OLLAMA_MODEL": "qwen-test"}, clear=False),
            patch("glance.web._fetch_content", side_effect=fake_fetch),
            patch("glance.web.summarize_stream", return_value=iter(["hello", " world"])) as summarize,
            patch("glance.web.store.put", return_value="summary-id") as put,
        ):
            web._run_job_sync(job, "https://example.com/post", "ollama")

        self.assertEqual(job.status, "done")
        self.assertEqual(
            [ev["data"] for ev in job.events if ev["kind"] == "status"],
            [
                "detected article",
                "fetching article text",
                "summarizing with ollama / qwen-test",
                "saved",
                "done",
            ],
        )
        self.assertEqual(
            [ev["data"] for ev in job.events if ev["kind"] == "chunk"],
            ["hello", " world"],
        )
        self.assertEqual(job.events[-1], {"kind": "done", "data": "summary-id"})
        summarize.assert_called_once_with("content", "article", provider="ollama")
        put.assert_called_once_with(
            "https://example.com/post",
            "article",
            "qwen-test",
            "hello world",
        )

    def test_progress_area_is_accessible_hidden_toggle(self) -> None:
        self.assertIn('id="status" class="collapsed" role="button"', web.INDEX_HTML)
        self.assertIn('tabindex="0"', web.INDEX_HTML)
        self.assertIn('aria-expanded="false"', web.INDEX_HTML)
        self.assertIn("let progressExpanded = false", web.INDEX_HTML)
        self.assertIn("setProgressExpanded(!progressExpanded)", web.INDEX_HTML)

    def test_reset_progress_defaults_to_collapsed(self) -> None:
        reset_index = web.INDEX_HTML.index("function resetProgress()")
        collapse_index = web.INDEX_HTML.index("setProgressExpanded(false)", reset_index)
        append_index = web.INDEX_HTML.index("function appendProgress", reset_index)

        self.assertLess(collapse_index, append_index)

    def test_collapsed_progress_line_is_single_line_truncated(self) -> None:
        collapsed_index = web.INDEX_HTML.index("#status.collapsed .progress-line.latest")
        out_index = web.INDEX_HTML.index("#out", collapsed_index)
        collapsed_css = web.INDEX_HTML[collapsed_index:out_index]

        self.assertIn("display: block", collapsed_css)
        self.assertIn("overflow: hidden", collapsed_css)
        self.assertIn("text-overflow: ellipsis", collapsed_css)
        self.assertIn("white-space: nowrap", collapsed_css)

    def test_client_side_starting_placeholder_is_not_appended(self) -> None:
        self.assertNotIn("appendProgress('starting')", web.INDEX_HTML)
        self.assertIn("if (resume) appendProgress('resuming')", web.INDEX_HTML)

    def test_done_event_does_not_force_progress_collapsed(self) -> None:
        done_index = web.INDEX_HTML.index("ev.kind === 'done'")
        replace_index = web.INDEX_HTML.index("history.replaceState", done_index)

        self.assertNotIn("setProgressExpanded(false)", web.INDEX_HTML[done_index:replace_index])


if __name__ == "__main__":
    unittest.main()

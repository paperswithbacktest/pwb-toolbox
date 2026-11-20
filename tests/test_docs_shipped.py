"""The documentation shipped in the wheel is the one in ``docs/``."""

import contextlib
import io
import unittest
from pathlib import Path

import pwb_toolbox.docs as docs
from pwb_toolbox.docs.__main__ import main

ROOT = Path(__file__).resolve().parent.parent


class Shipped(unittest.TestCase):
    def test_copies_match_the_repository(self):
        self.assertIn("backtesting", docs.pages())
        for name in docs.pages():
            self.assertEqual(
                docs.read(name), (ROOT / "docs" / f"{name}.md").read_text(encoding="utf-8"),
                f"pwb_toolbox/docs/{name}.md differs from docs/{name}.md: copy it over",
            )

    def test_command_prints_the_page(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["backtesting"]), 0)
        self.assertIn("### Long-short by quantiles", out.getvalue())
        self.assertIn("short_borrow_bps", out.getvalue())

    def test_unknown_page(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["nope"]), 1)

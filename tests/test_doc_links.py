"""Gates documentales sin red ni datos de negocio."""

from pathlib import Path
import tempfile
import unittest

from scripts.check_doc_links import check_links


class DocLinksTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "docs").mkdir()
        (self.root / "target.md").write_text("# Destino", encoding="utf-8")

    def check(self, text):
        return check_links(self.root, {"docs/source.md": text})

    def test_valid_relative_link(self):
        self.assertEqual(self.check("[destino](../target.md)"), (1, []))

    def test_missing_relative_link_fails(self):
        count, broken = self.check("[ausente](missing.md)")
        self.assertEqual(count, 1)
        self.assertEqual(broken, [("docs/source.md", "missing.md")])

    def test_external_schemes_are_ignored(self):
        self.assertEqual(self.check("[https](https://invalid.example) [http](http://invalid.example) "
                                    "[mail](mailto:fixture@example.invalid) [app](codex://fixture) "
                                    "[custom](custom+v1://fixture)"), (0, []))

    def test_fragments_are_deterministic_and_not_validated(self):
        self.assertEqual(self.check("[anchor](#unknown) [file](../target.md#unknown)"), (1, []))
        self.assertEqual(self.check("[missing](missing.md#unknown)"),
                         (1, [("docs/source.md", "missing.md#unknown")]))

    def test_invalid_relative_paths_are_rejected(self):
        for target in ("../../../outside.md", "/target.md", r"..\target.md", "bad%00.md"):
            with self.subTest(target=target):
                self.assertEqual(self.check(f"[invalid]({target})"),
                                 (1, [("docs/source.md", target)]))


if __name__ == "__main__":
    unittest.main()

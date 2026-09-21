"""La puerta de secretos no confunde líneas movidas con nuevas excepciones."""

import unittest
from unittest.mock import patch

from scripts.check_secrets import scan


class SecretsGateTests(unittest.TestCase):
    def test_paths_are_portable_and_only_exact_fingerprints_are_allowed(self):
        from detect_secrets.core.potential_secret import PotentialSecret
        from detect_secrets.core.secrets_collection import SecretsCollection
        from detect_secrets.util.path import convert_local_os_path

        known = PotentialSecret("Secret Keyword", "src/test.txt", "known-fixture", 1)
        data = {"version": "1.5.0", "plugins_used": [], "filters_used": [],
                "results": {"src\\test.txt": [{**known.json(), "filename": "src\\test.txt"}]}}

        def populate(collection, name):
            name = convert_local_os_path(name)
            collection[name].add(PotentialSecret("Secret Keyword", name, "known-fixture", 90))
            collection[name].add(PotentialSecret("Secret Keyword", name, "new-fixture", 91))

        with patch.object(SecretsCollection, "scan_file", populate):
            result = list(scan(["src/test.txt"], data))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1].line_number, 91)

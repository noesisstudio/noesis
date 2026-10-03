"""La puerta de secretos no confunde líneas movidas con nuevas excepciones."""

import unittest
from unittest.mock import patch

from scripts.check_secrets import scan


class SecretsGateTests(unittest.TestCase):
    def test_financial_phase0_public_sha_exception_is_exact(self):
        import hashlib
        import json
        from pathlib import Path
        root = Path(__file__).parents[1]
        state = json.loads((root / 'docs/project-state.json').read_text(encoding='utf-8'))
        sha = state['production']['financial_core_phase0_release']['commit']
        data = json.loads((root / '.secrets.baseline').read_text(encoding='utf-8'))
        self.assertIn('HexHighEntropyString', {p['name'] for p in data['plugins_used']})
        entries = data['results']['docs/project-state.json']
        exact = [e for e in entries if e['type'] == 'Hex High Entropy String'
                 and e['hashed_secret'] == hashlib.sha1(sha.encode()).hexdigest()]
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0]['filename'], 'docs/project-state.json')

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

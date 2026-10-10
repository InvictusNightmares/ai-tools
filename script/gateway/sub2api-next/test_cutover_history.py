"""The merged production history must replace the old preview baseline."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from candidate_migrate import certified_history


class CertifiedHistoryTest(unittest.TestCase):
    def test_production_baseline_supersedes_preview_qa_and_cutoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'ops').mkdir()
            (root/'ops'/'customer-portal-before.json').write_text(json.dumps({'usage_max_id':2007558,'usage_totals':[{'api_key_id':92,'requests':1}]}))
            merged={'usage_max_id':2019999,'usage_totals':[{'api_key_id':4,'requests':25}]}
            (root/'ops'/'production-history-baseline.json').write_text(json.dumps(merged))
            with patch('candidate_migrate.ROOT',root):self.assertEqual(certified_history(),merged)

    def test_preview_still_uses_its_certified_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'ops').mkdir()
            preview={'usage_max_id':2007558,'usage_totals':[]}
            (root/'ops'/'customer-portal-before.json').write_text(json.dumps(preview))
            with patch('candidate_migrate.ROOT',root):self.assertEqual(certified_history(),preview)

    def test_invalid_production_baseline_does_not_fall_back_to_old_qa_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'ops').mkdir()
            (root/'ops'/'production-history-baseline.json').write_text('{}')
            with patch('candidate_migrate.ROOT',root):
                with self.assertRaisesRegex(RuntimeError,'invalid certified history'):
                    certified_history()


if __name__=='__main__':unittest.main()

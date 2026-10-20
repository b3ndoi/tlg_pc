"""Read-only synthetic save audit: never infers achievements from progress names."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_trophy_save as a


class AuditTests(unittest.TestCase):
    def test_candidate_names_are_not_unlock_proof_and_input_is_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'copy.dat'
            raw = b'\0PerpetualData\0condorTailRescueSuccess\0numGameover\0' + b'\xff' * 128
            path.write_bytes(raw)
            report = a.audit(path)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)
            self.assertEqual(len(report['candidate_progress_fields']), 2)
            self.assertEqual(report['verified_trophy_unlocks_recovered'], [])
            self.assertFalse(report['import_performed'])
            self.assertTrue(report['named_perpetual_section_found'])

    def test_oversized_and_empty_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'copy.dat'
            for raw in (b'', b'0' * (a.MAX_SAVE + 1)):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    a.audit(path)


if __name__ == '__main__':
    unittest.main()

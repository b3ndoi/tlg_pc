"""Asset-free Python/native state bridge; all persistence is in temporary folders."""
from datetime import datetime, timezone
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import achievements
import native_trophies as n
import tlg_run

STAMP = '2026-10-20T12:00:00+00:00'
RECORD = {'unlocked_at': STAMP, 'source': 'game_trophy'}


class NativeStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_missing_is_read_only(self):
        self.assertEqual(n.read(self.root / 'absent', 'CUSA03745'), {})
        self.assertFalse((self.root / 'absent').exists())

    def test_roundtrip_merge_dedup_title_user_and_source_isolation(self):
        n.seed(self.root, 'CUSA03745', {'127': RECORD})
        path = n.state_path(self.root, 'CUSA03745')
        before = path.read_bytes()
        n.seed(self.root, 'CUSA03745', {'0': RECORD})
        self.assertEqual(set(n.read(self.root, 'CUSA03745')), {'0', '127'})
        self.assertEqual(n.read(self.root, 'CUSA03745', 2), {})
        self.assertEqual(n.read(self.root, 'CUSA03627'), {})
        self.assertEqual(len(before), 1064)
        self.assertEqual(n.decode(before, 'CUSA03745'), {'127': RECORD})
        with self.assertRaises(ValueError):
            n.seed(self.root, 'CUSA03745', {'5': {**RECORD, 'source': 'save_guess'}})

    def test_corrupt_store_rejects_write_without_overwriting(self):
        n.seed(self.root, 'CUSA03745', {'1': RECORD})
        path = n.state_path(self.root, 'CUSA03745')
        for raw in (b'', b'bad' * 500, path.read_bytes()[:-1] + b'0'):
            path.write_bytes(raw)
            with self.assertRaises(ValueError):
                n.seed(self.root, 'CUSA03745', {'2': RECORD})
            self.assertEqual(path.read_bytes(), raw)

    def test_observer_still_notifies_fresh_native_persisted_event_once(self):
        n.seed(self.root, 'CUSA03745', {'7': RECORD})
        store = achievements.Store(self.root, 'CUSA03745')
        self.assertEqual(store.read(), {'7': RECORD})
        event = store.unlock(7)
        self.assertEqual(event['unlocked_at'], STAMP)
        self.assertIsNone(store.unlock(7))
        self.assertEqual(store.read(), {'7': RECORD})

    def test_thirty_fps_environment_does_not_opt_into_native_trophy_semantics(self):
        with patch.object(tlg_run, 'applied_frame_rate', '30'), patch.object(tlg_run, 'window_icon', return_value=None), \
             patch.dict(tlg_run.os.environ, {'TLG_TROPHY_STATE': '1'}, clear=True):
            self.assertNotIn('TLG_TROPHY_STATE', tlg_run.build_env(tlg_run.DEFAULT_SETTINGS))
        with patch.object(tlg_run, 'applied_frame_rate', '60'), patch.object(tlg_run, 'window_icon', return_value=None), \
             patch.dict(tlg_run.os.environ, {}, clear=True):
            self.assertEqual(tlg_run.build_env(tlg_run.DEFAULT_SETTINGS)['TLG_TROPHY_STATE'], '1')
            self.assertNotIn('TLG_TROPHY_STATE', tlg_run.build_env({**tlg_run.DEFAULT_SETTINGS, 'track_achievements': False}))


if __name__ == '__main__':
    unittest.main()

"""Asset-free local trophy tests; never runs a game or sends OS notifications."""
import ctypes
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT / 'launcher'))
from launcher_fixtures import make_game
import achievements as a
import desktop_notifications as notifications
import game_library
import tlg_run

STAMP = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


class AchievementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.game = make_game(self.root / 'game')
        self.user = self.root / 'user'
        self.store = a.Store(self.user, 'CUSA03745')

    def tearDown(self):
        self.temporary.cleanup()

    def test_bounded_supported_metadata(self):
        self.assertEqual(game_library.game_info(self.game)['title_id'], 'CUSA03745')
        self.assertEqual(game_library.game_info(self.game)['version'], '01.00')
        self.assertIsNone(game_library.game_info(None))
        self.assertIsNone(game_library.game_info(self.root / 'missing'))
        unsupported = make_game(self.root / 'other', title='CUSA99999')
        self.assertIsNone(game_library.game_info(unsupported))
        (self.game / 'eboot.bin').unlink()
        self.assertIsNone(game_library.game_info(self.game))

    def test_damaged_metadata_is_not_a_game(self):
        for data in (b'', b'bad header' * 20, b'\0' * (game_library.MAX_SFO + 1)):
            with self.subTest(size=len(data)):
                (self.game / 'sce_sys/param.sfo').write_bytes(data)
                self.assertIsNone(game_library.game_info(self.game))

    def test_read_does_not_create_anything(self):
        self.assertEqual(self.store.read(), {})
        self.assertFalse(self.user.exists())

    def test_persist_reload_deduplicate_and_isolate_titles(self):
        event = self.store.unlock(7, now=STAMP)
        self.assertEqual(event['source'], 'game_trophy')
        before = self.store.path.read_bytes()
        self.assertIsNone(a.Store(self.user, 'CUSA03745').unlock(7))
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertEqual(set(self.store.read()), {'7'})
        self.assertEqual(a.Store(self.user, 'CUSA03627').read(), {})
        self.assertEqual(a.Store(self.root / 'other-user', 'CUSA03745').read(), {})
        self.assertFalse((self.user / 'savedata').exists())

    def test_invalid_identity_and_ids_never_write(self):
        for title in ('../escape', '', 'CUSA03745/other', 'CUSA99999'):
            with self.subTest(title=title), self.assertRaises(a.StoreError):
                a.Store(self.user, title)
        for value in (-1, 128, True, '1', 0.5, None):
            with self.subTest(value=value), self.assertRaises(a.StoreError):
                self.store.unlock(value)
        self.assertFalse(self.user.exists())

    def test_corrupt_progress_is_preserved(self):
        self.store.path.parent.mkdir(parents=True)
        for raw in (b'invalid', b'{}', b'[]', b'[' * 2000 + b']' * 2000, b'x' * (a.MAX_STATE + 1),
                    json.dumps({'schema': 1, 'title_id': 'CUSA03627', 'unlocks': {}}).encode(),
                    json.dumps({'schema': 1, 'title_id': 'CUSA03745',
                                'unlocks': {'129': {'source': 'game_trophy', 'unlocked_at': STAMP.isoformat()}}}).encode()):
            with self.subTest(raw=raw[:30]):
                self.store.path.write_bytes(raw)
                with self.assertRaises(a.StoreError):
                    self.store.unlock(1)
                self.assertEqual(self.store.path.read_bytes(), raw)

    def test_atomic_replace_failure_retains_previous_progress(self):
        self.store.unlock(1, now=STAMP)
        before = self.store.path.read_bytes()
        with patch.object(a.os, 'replace', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                self.store.unlock(2)
        self.assertEqual(before, self.store.path.read_bytes())
        self.assertEqual(list(self.store.path.parent.glob('.unlock-*.tmp')), [])

    def test_aware_timestamps_are_normalized_to_utc(self):
        local = datetime(2026, 10, 20, 14, 0, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(self.store.unlock(1, now=local)['unlocked_at'], STAMP.isoformat(timespec='seconds'))

    def test_concurrent_writers_do_not_lose_progress(self):
        errors = []
        def write(value):
            try:
                a.Store(self.user, 'CUSA03745').unlock(value)
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=write, args=(i,)) for i in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(set(self.store.read()), {str(i) for i in range(12)})

    def test_strict_new_session_events_only(self):
        events, errors = [], []
        session = a.Session(self.user, self.game, on_unlock=events.append, on_error=errors.append)
        for text in ('Runtime: trophy 7 unlocked\n', 'Runtime: trophy 7 unlocked\r\n',
                     'prefix Runtime: trophy 8 unlocked', 'Runtime: trophy -1 unlocked',
                     'Runtime: trophy 128 unlocked', 'Runtime: trophy 9 unlocked extra',
                     'trophy 10 unlocked', None):
            session.feed(text)
        session.close()
        self.assertEqual([event['id'] for event in events], [7])
        self.assertEqual(errors, [])
        self.assertEqual(set(self.store.read()), {'7'})
        again = a.Session(self.user, self.game, on_unlock=events.append)
        again.feed('Runtime: trophy 7 unlocked')
        again.close()
        self.assertEqual(len(events), 1)

    def test_disabled_or_missing_game_has_no_side_effects(self):
        with patch.object(a, 'game_info', side_effect=AssertionError('should not read metadata')):
            session = a.Session(self.user, self.game, enabled=False)
            session.feed('Runtime: trophy 1 unlocked')
            session.close()
        session = a.Session(self.user, self.root / 'absent')
        session.feed('Runtime: trophy 1 unlocked')
        session.close()
        self.assertFalse(self.user.exists())

    def test_notification_failure_cannot_undo_progress(self):
        errors = []
        session = a.Session(self.user, self.game, on_error=errors.append,
                            notifier_factory=Mock(side_effect=OSError('synthetic notification failure')))
        session.feed('Runtime: trophy 3 unlocked')
        session.close()
        self.assertEqual(set(self.store.read()), {'3'})
        self.assertTrue(any('achievement saved' in error for error in errors))

    def test_notification_pump_failure_keeps_observer_alive(self):
        pumped = threading.Event()
        class BrokenNotifier:
            def show(self, value):
                pass
            def pump(self):
                pumped.set()
                raise OSError('synthetic pump failure')
            def close(self):
                pass
        session = a.Session(self.user, self.game, notifier_factory=BrokenNotifier)
        session.feed('Runtime: trophy 1 unlocked')
        self.assertTrue(pumped.wait(1))
        session.feed('Runtime: trophy 2 unlocked')
        session.close()
        self.assertEqual(set(self.store.read()), {'1', '2'})

    def test_thread_start_failure_is_nonfatal(self):
        errors = []
        session = a.Session(self.user, self.game, on_error=errors.append)
        with patch.object(a.threading.Thread, 'start', side_effect=RuntimeError('synthetic failure')):
            session.feed('Runtime: trophy 1 unlocked')
        session.close()
        self.assertEqual(len(errors), 1)
        self.assertFalse(self.user.exists())

    def test_stream_observer_covers_gui_and_headless_path(self):
        lines = 'Frame stats: 30.0 FPS\nRuntime: trophy 4 unlocked\nRuntime: trophy 4 unlocked\n'
        process = Mock(stdout=io.StringIO(lines))
        process.wait.return_value = 0
        received, events = [], []
        settings = {**tlg_run.DEFAULT_SETTINGS, 'game_dir': str(self.game), 'ui_language': 'en_US'}
        with patch.object(tlg_run, 'USER_DIR', self.user), \
             patch.object(notifications, 'WindowsNotifications', side_effect=AssertionError('must not notify')):
            self.assertEqual(tlg_run.copy_output(process, self.root / 'session.log', settings,
                                               received.append, events.append,
                                               notes=['Runtime: trophy 99 unlocked']), 0)
        self.assertEqual([event['id'] for event in events], [4])
        self.assertEqual(set(self.store.read()), {'4'})
        self.assertEqual(''.join(received), 'Runtime: trophy 99 unlocked\n' + lines)
        self.assertEqual((self.root / 'session.log').read_text(), ''.join(received))

    def test_log_open_or_store_failure_does_not_stop_output(self):
        process = Mock(stdout=io.StringIO('Runtime: trophy 4 unlocked\nstill running\n'))
        process.wait.return_value = 0
        received = []
        settings = {**tlg_run.DEFAULT_SETTINGS, 'game_dir': str(self.game)}
        with patch.object(tlg_run, 'USER_DIR', self.user), \
             patch.object(a.Store, 'unlock', side_effect=OSError('synthetic disk failure')):
            code = tlg_run.copy_output(process, self.root / 'absent/log.txt', settings, received.append)
        self.assertEqual(code, 0)
        self.assertIn('still running\n', received)
        self.assertTrue(any('Log file unavailable' in line for line in received))
        self.assertTrue(any('synthetic disk failure' in line for line in received))
        process.wait.assert_called_once()

    def test_log_write_and_close_failures_continue_draining(self):
        process = Mock(stdout=io.StringIO('still running\n'))
        process.wait.return_value = 0
        broken = Mock()
        broken.write.side_effect = OSError('synthetic full disk')
        broken.close.side_effect = OSError('synthetic close failure')
        received = []
        settings = {**tlg_run.DEFAULT_SETTINGS, 'track_achievements': False}
        with patch('builtins.open', return_value=broken):
            self.assertEqual(tlg_run.copy_output(process, self.root / 'unused', settings,
                                               received.append, notes=['preparing']), 0)
        self.assertIn('still running\n', received)
        self.assertTrue(any('Log write failed' in line for line in received))


class NotificationTests(unittest.TestCase):
    def test_disabled_or_non_windows_is_a_noop(self):
        self.assertIsNone(notifications.factory(False))
        with patch.object(notifications.sys, 'platform', 'linux'):
            self.assertIsNone(notifications.factory(True))

    def test_factory_is_lazy(self):
        with patch.object(notifications.sys, 'platform', 'win32'), \
             patch.object(notifications, 'WindowsNotifications') as make:
            factory = notifications.factory(True)
            make.assert_not_called()
            factory()
            make.assert_called_once()

    def test_utf16_limits_preserve_whole_characters(self):
        value = notifications.text_limit('a\0' + '\U0001f3c6' * 100, 63)
        self.assertNotIn('\0', value)
        self.assertLessEqual(len(value.encode('utf-16-le')), 126)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows ABI only; no real notification calls')
    def test_windows_structure_and_mocked_shell_calls(self):
        self.assertEqual(ctypes.sizeof(notifications.NotifyData), 976 if ctypes.sizeof(ctypes.c_void_p) == 8 else 956)
        user, shell, kernel = Mock(), Mock(), Mock()
        user.CreateWindowExW.return_value = 123
        user.LoadIconW.return_value = 456
        user.PeekMessageW.return_value = 0
        shell.Shell_NotifyIconW.return_value = 1
        kernel.GetModuleHandleW.return_value = 42
        with patch.object(ctypes, 'WinDLL', side_effect=[user, shell, kernel]):
            service = notifications.WindowsNotifications()
            service.show(8)
            self.assertEqual(service.data.szInfo, 'Trophy #8 — The Last Guardian')
            self.assertEqual(service.data.dwInfoFlags, 0x91)
            self.assertEqual(service.data.uFlags, 0x10)
            service.close()
        self.assertEqual([call.args[0] for call in shell.Shell_NotifyIconW.call_args_list], [0, 1, 2])
        user.DestroyWindow.assert_called_once_with(123)


if __name__ == '__main__':
    unittest.main()

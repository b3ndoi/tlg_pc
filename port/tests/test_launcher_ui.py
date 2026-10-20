"""Withdrawn Tk integration tests with synthetic files and mocked process/OS calls.

No visible test window, game launch, input capture or actual notifications.
Linux without a display skips only these widget checks; Windows CI uses the
setup-python interpreter with Tk, not an optional MSYS2 tkinter package.
"""
import copy
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT / 'launcher'))
from launcher_fixtures import make_game
import achievements
import tlg_launcher as ui
import tlg_run


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


class LauncherUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tk is never mapped; creating the interpreter does not focus the game.
        try:
            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except tk.TclError as error:
            if sys.platform == 'win32':
                raise
            raise unittest.SkipTest('Tk display unavailable: ' + str(error))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self.temporary.name)
        self.game = make_game(self.folder / 'game')
        self.user = self.folder / 'user'
        self.probe = self.folder / 'probe-fixture.exe'
        self.probe.write_bytes(b'NOT executable code')
        self.settings = {**copy.deepcopy(tlg_run.DEFAULT_SETTINGS), 'game_dir': str(self.game),
                         'system_lib_dir': str(self.folder / 'modules'),
                         'game_language': 'en', 'ui_language': 'en_US'}
        self.patchers = [patch.object(tlg_run, 'USER_DIR', self.user),
                         patch.object(tlg_run, 'PROBE', self.probe),
                         patch.object(tlg_run, 'PORT_DIR', self.folder / 'port'),
                         patch.object(tlg_run, 'REPO_DIR', self.folder),
                         patch.object(tlg_run, 'LOG_DIR', self.folder / 'logs'),
                         patch.object(tlg_run, 'load_settings', return_value=copy.deepcopy(self.settings)),
                         patch.object(tlg_run, 'save_settings'), patch.object(tlg_run, 'update_ini'),
                         patch.object(tlg_run, 'prepare', side_effect=AssertionError('No real preparation')),
                         patch.object(tlg_run.subprocess, 'Popen', side_effect=AssertionError('No game launch')),
                         patch.object(ui.messagebox, 'showinfo'), patch.object(ui.messagebox, 'showerror'),
                         patch.object(ui.messagebox, 'showwarning'), patch.object(ui.messagebox, 'askyesno', return_value=False)]
        for patcher in self.patchers:
            patcher.start()
        self.window = tk.Tk()
        self.window.withdraw()
        self.app = ui.Launcher(self.window)
        self.window.update_idletasks()

    def tearDown(self):
        try:
            for callback in self.window.tk.splitlist(self.window.tk.call('after', 'info')):
                self.window.after_cancel(callback)
            self.window.destroy()
        except tk.TclError:
            pass
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary.cleanup()

    def test_build_has_tabs_metadata_and_no_writes(self):
        self.assertEqual(len(self.app.notebook.tabs()), 6)
        self.assertEqual(self.app.game_identity['text'], 'CUSA03745 · 01.00')
        self.assertEqual(self.app.settings['frame_rate'], '30')
        self.assertFalse(self.app.settings['achievement_notifications'])
        self.assertFalse(self.app.play_button.instate(['disabled']))
        tlg_run.save_settings.assert_not_called()
        tlg_run.update_ini.assert_not_called()
        tlg_run.subprocess.Popen.assert_not_called()
        self.assertFalse(self.user.exists())
        self.assertEqual(self.window.state(), 'withdrawn')

    def test_missing_game_disables_play_without_creating_progress(self):
        self.app.settings['game_dir'] = str(self.folder / 'absent')
        self.app.refresh_status()
        self.app.refresh_achievements()
        self.assertTrue(self.app.play_button.instate(['disabled']))
        self.assertEqual(self.app.achievement_summary['text'], self.app.t('achievement_missing'))
        self.assertFalse(self.user.exists())

    def test_language_rebuild_keeps_log_and_does_not_auto_save(self):
        self.app.append('Synthetic session message')
        self.app.settings['ui_language'] = 'pt_BR'
        self.app.build()
        self.window.update_idletasks()
        self.assertIn('Conquistas', [self.app.notebook.tab(tab, 'text') for tab in self.app.notebook.tabs()])
        self.assertIn('Synthetic session message', self.app.log.get('1.0', 'end'))
        self.assertEqual(self.app.settings['frame_rate'], '30')
        tlg_run.save_settings.assert_not_called()
        tlg_run.update_ini.assert_not_called()

    def test_old_invalid_language_fallback_is_read_only(self):
        self.app.settings['game_language'] = 'pt_BR'  # not in the EU archive's language table
        self.app.refresh_language_choices()
        self.assertIn(self.app.settings['game_language'], self.app.game_lang_values)
        tlg_run.save_settings.assert_not_called()

    def test_saved_achievements_are_visible_and_duplicate_messages_do_not_rewrite(self):
        store = achievements.Store(self.user, 'CUSA03745')
        event = store.unlock(12)
        before = store.path.read_bytes()
        self.app.refresh_achievements()
        self.assertEqual(self.app.achievement_tree.item('12', 'text'), 'Trophy #12')
        self.app.lines.put(('achievement', event))
        self.app.pump()
        self.assertIn('#12', self.app.achievement_toast['text'])
        self.assertEqual(store.path.read_bytes(), before)

    def test_busy_locks_settings_but_not_read_only_progress(self):
        self.app.busy = True
        self.app.refresh_status()
        self.assertTrue(self.app.play_button.instate(['disabled']))
        self.assertTrue(self.app.cache_button.instate(['disabled']))
        self.assertTrue(all(widget.instate(['disabled']) for widget in self.app.config_widgets))
        self.app.changed()
        self.app.filters_changed()
        tlg_run.save_settings.assert_not_called()
        tlg_run.update_ini.assert_not_called()
        self.app.busy = False
        self.app.refresh_status()
        self.assertFalse(self.app.play_button.instate(['disabled']))

    def test_preparation_uses_snapshot_and_quit_prevents_later_launch(self):
        with patch.object(ui.threading, 'Thread') as thread:
            self.app.play()
            self.assertTrue(self.app.busy)
            snapshot = thread.call_args.kwargs['args'][0]
            self.assertIsNot(snapshot, self.app.settings)
            self.assertEqual(snapshot['frame_rate'], '30')
            self.app.settings['key_map']['cross'] = 'J'
            self.assertEqual(snapshot['key_map'], {})
            self.app.play()
            thread.assert_called_once()
        self.app.stopping.set()
        with patch.object(tlg_run, 'prepare'), patch.object(tlg_run, 'launch') as launch:
            self.app.run_game(snapshot)
            launch.assert_not_called()

    def test_quit_requires_confirmation_before_stopping_own_child(self):
        self.app.busy = True
        process = Mock()
        process.poll.return_value = None
        self.app.process = process
        self.app.quit()
        process.terminate.assert_not_called()
        self.assertFalse(self.app.stopping.is_set())
        with patch.object(ui.messagebox, 'askyesno', return_value=True):
            self.app.quit()
        process.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()

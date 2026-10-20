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
from test_trophy_catalog import XML, ICON, trp


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
        self.assertIn(12, self.app.achievement_cards)
        self.assertTrue(self.app.achievement_views[12]['unlocked'])
        self.assertTrue(self.app.achievement_views[12]['masked'])  # metadata unknown
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

    def test_prompt_choices_persist_without_launch_or_live_config_write(self):
        self.assertEqual(len(self.app.prompt_box['values']), 5)
        self.assertEqual(self.app.prompt_box.current(), 0)
        for index,mode in enumerate(('original','auto','keyboard','ps5','xbox')):
            self.app.prompt_box.current(index)
            self.app.prompt_box.event_generate('<<ComboboxSelected>>')
            self.window.update_idletasks()
            self.assertEqual(self.app.settings['button_prompts'], mode)
            self.assertEqual(self.app.settings['frame_rate'], '30')
        self.assertEqual(tlg_run.save_settings.call_count, 5)
        tlg_run.update_ini.assert_not_called()
        tlg_run.subprocess.Popen.assert_not_called()

    def test_busy_prompt_override_is_ignored(self):
        self.app.busy = True
        self.app.prompt_box.current(4)
        self.app.prompt_box.event_generate('<<ComboboxSelected>>')
        self.window.update_idletasks()
        self.assertEqual(self.app.settings['button_prompts'], 'original')
        tlg_run.save_settings.assert_not_called()

    def test_local_prompt_image_picker_does_not_copy_upload_or_launch(self):
        image=self.folder/'synthetic.png'
        image.write_bytes(b'Synthetic test fixture, not artwork')
        with patch.object(ui.filedialog,'askopenfilename',return_value=str(image)):
            self.app.choose_prompt_image()
        self.assertEqual(self.app.settings['ps5_prompt_image'],str(image))
        self.assertEqual(self.app.prompt_image_name['text'],'synthetic.png')
        self.assertEqual(image.read_bytes(),b'Synthetic test fixture, not artwork')
        self.assertEqual(self.app.settings['button_prompts'],'original')
        tlg_run.update_ini.assert_not_called()
        tlg_run.subprocess.Popen.assert_not_called()
        self.assertFalse(self.user.exists())

    def test_grid_shows_locked_trophies_without_leaking_hidden_text_or_icon(self):
        folder = self.game / 'sce_sys/trophy'
        folder.mkdir()
        (folder / 'trophy00.trp').write_bytes(trp([('TROP000.PNG', ICON, 0), ('TROP001.PNG', ICON, 0)]))
        (folder / 'TROP.XML').write_bytes(XML)
        self.app.refresh_achievements()
        self.assertEqual(set(self.app.achievement_cards), {0, 1})
        visible = ' '.join(str(widget.cget('text')) for widget in widgets(self.app.achievement_grid)
                           if isinstance(widget, ttk.Label))
        self.assertIn('Fixture master', visible)
        self.assertIn('Hidden trophy', visible)
        self.assertNotIn('SECRET', visible)
        self.assertIsNone(self.app.achievement_views[1]['icon'])
        self.assertIn('0 / 2', self.app.achievement_summary['text'])
        self.assertEqual(len(self.app.achievement_images), 1)
        achievements.Store(self.user, 'CUSA03745').unlock(1)
        self.app.refresh_achievements()
        self.assertEqual(self.app.achievement_views[1]['name'], 'SECRET NAME')
        self.assertIn('1 / 2', self.app.achievement_summary['text'])
        self.assertFalse(self.app.achievement_views[1]['masked'])

    def test_grid_reflows_without_writing_preferences(self):
        for key in range(8):
            achievements.Store(self.user, 'CUSA03745').unlock(key)
        self.app.refresh_achievements()
        self.app.layout_achievements(Mock(width=1000))
        self.assertEqual(self.app.achievement_columns, 4)
        self.app.layout_achievements(Mock(width=300))
        self.assertEqual(self.app.achievement_columns, 1)
        self.assertEqual(self.app.achievement_cards[7].grid_info()['row'], 7)
        tlg_run.save_settings.assert_not_called()

    def test_preparation_uses_snapshot_and_quit_prevents_later_launch(self):
        self.assertFalse(self.app.settings['trophy_show_unknown_icons'])
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

    def test_icon_opt_in_shows_artwork_without_claiming_unlocks_and_can_be_disabled(self):
        folder = self.game / 'sce_sys/trophy'
        folder.mkdir()
        (folder / 'trophy00.trp').write_bytes(trp([('TROP000.PNG', ICON, 0), ('TROP001.PNG', ICON, 0)]))
        self.app.vars['trophy_show_unknown_icons'].set(True)
        self.app.trophy_icons_changed()
        self.assertEqual(len(self.app.achievement_images), 2)
        self.assertIn('Icons shown by request', self.app.achievement_summary['text'])
        for view in self.app.achievement_views.values():
            self.assertTrue(view['masked'])
            self.assertFalse(view['unlocked'])
            self.assertEqual(view['name'], '')
        self.assertFalse(self.user.exists())
        self.app.vars['trophy_show_unknown_icons'].set(False)
        self.app.trophy_icons_changed()
        self.assertEqual(len(self.app.achievement_images), 0)
        self.assertFalse(self.app.settings['trophy_show_unknown_icons'])

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

    def test_quit_waits_for_own_output_reader_before_destroying_ui(self):
        self.app.busy = True
        process, reader = Mock(), Mock()
        process.poll.return_value = None
        reader.is_alive.return_value = True
        self.app.process, self.app.game_thread = process, reader
        with patch.object(ui.messagebox, 'askyesno', return_value=True):
            self.app.quit()
        self.assertTrue(self.window.winfo_exists())
        self.assertTrue(self.app.stopping.is_set())
        process.terminate.assert_called_once()
        reader.is_alive.return_value = False
        self.app.finish_quit()

    def test_launch_closes_only_own_editable_dialogs(self):
        remap, mods = Mock(), Mock()
        remap.winfo_exists.return_value = mods.winfo_exists.return_value = True
        self.app.remap_window, self.app.mods_window = remap, mods
        with patch.object(ui.threading, 'Thread'):
            self.app.play()
        remap.destroy.assert_called_once()
        mods.destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main()

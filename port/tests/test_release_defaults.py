"""Asset-free release safeguards; never launches a game or edits user settings."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT / 'launcher'))
sys.path.insert(0, str(PORT / 'scripts'))
import tlg_patches
import tlg_native_resolution as native_resolution
import tlg_run


class ReleaseDefaults(unittest.TestCase):
    def test_30_is_still_default(self):
        self.assertEqual(tlg_run.DEFAULT_SETTINGS['frame_rate'], '30')
        self.assertEqual(tlg_patches.MODES['30'], [])
        self.assertEqual(tlg_run.DEFAULT_SETTINGS['button_prompts'], 'original')
        self.assertNotIn('TLG_BUTTON_PROMPTS', tlg_run.DEFAULT_ENV)

    def test_60_environment_is_not_enabled_by_default(self):
        switches = {'TLG_TIMING_60', 'TLG_INPUT_TIMING_60', 'TLG_CLOCK_SYNC_60',
                    'TLG_CLIMB_DIAG', 'TLG_PRECISE_PACING', 'TLG_NATIVE_OUTPUT',
                    'TLG_ENGINE_NATIVE_RESOLUTION', 'TLG_TROPHY_STATE'}
        self.assertTrue(switches.isdisjoint(tlg_run.DEFAULT_ENV))
        settings = dict(tlg_run.DEFAULT_SETTINGS)
        with patch.dict('os.environ', {}, clear=True), \
             patch.object(tlg_run, 'window_icon', return_value=None), \
             patch.object(tlg_run, 'ngs2_module', return_value=None), \
             patch.object(tlg_run, 'applied_frame_rate', '30'):
            env = tlg_run.build_env(settings)
        self.assertTrue(switches.isdisjoint(env))
        self.assertEqual(env['TLG_ENGINE_FPS'], '30')

    def test_timeout_is_not_added(self):
        import inspect
        self.assertEqual(inspect.signature(tlg_run.launch).parameters['seconds'].default, 0)

    def test_windows_source_launcher_finds_msys2_runtime_dlls(self):
        settings = dict(tlg_run.DEFAULT_SETTINGS)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clang64 = root / 'msys64' / 'clang64' / 'bin'
            clang64.mkdir(parents=True)
            probe = root / 'out' / 'tlg-probe.exe'
            with patch.dict(os.environ, {'MSYS2_ROOT': str(root / 'msys64')}, clear=True), \
                 patch.object(tlg_run, 'PROBE', probe), \
                 patch.object(tlg_run.os, 'name', 'nt'), \
                 patch.object(tlg_run, 'window_icon', return_value=None), \
                 patch.object(tlg_run, 'ngs2_module', return_value=None):
                env = tlg_run.build_env(settings)
            self.assertEqual(env['PATH'].split(os.pathsep)[0], str(clang64))

    def test_prepared_native_engine_mode_disables_host_proxy_path(self):
        settings = {**tlg_run.DEFAULT_SETTINGS, 'scene_resolution': '1280x720'}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(tlg_run, 'applied_engine_resolution', '1280x720'), \
             patch.object(tlg_run, 'window_icon', return_value=None), \
             patch.object(tlg_run, 'ngs2_module', return_value=None):
            env = tlg_run.build_env(settings)
        self.assertEqual(env['TLG_ENGINE_NATIVE_RESOLUTION'], '1280x720')
        self.assertEqual(env['TLG_OUTPUT_RES'], '1280x720')
        self.assertEqual(env['TLG_NATIVE_OUTPUT'], '0')
        self.assertEqual(env['TLG_UPSCALER'], 'none')

    def test_native_resolution_options_are_explicit_and_1440p_stays_default(self):
        self.assertEqual(native_resolution.DEFAULT_RESOLUTION, '2560x1440')
        self.assertEqual(native_resolution.normalize_resolution('720p'), '1280x720')
        self.assertEqual(native_resolution.normalize_resolution('2K'), '2560x1440')
        self.assertEqual(native_resolution.normalize_resolution('1440p'), '2560x1440')
        self.assertEqual(native_resolution.normalize_resolution('4K'), '3840x2160')
        self.assertEqual(struct.unpack('<4HQ', native_resolution.mode_bytes('720p')),
                         (1280, 720, 1280, 720, 0))
        self.assertEqual(struct.unpack('<4HQ', native_resolution.MODE_NEW),
                         (2560, 1440, 2560, 1440, 0))
        self.assertEqual(struct.unpack('<4HQ', native_resolution.mode_bytes('4k')),
                         (3840, 2160, 3840, 2160, 0))
        for unsupported in ('', '1080p', '7680x4320', None):
            with self.assertRaises(ValueError):
                native_resolution.normalize_resolution(unsupported)


if __name__ == '__main__':
    unittest.main()

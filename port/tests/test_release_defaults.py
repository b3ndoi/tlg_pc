"""Asset-free release safeguards; never launches a game or edits user settings."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT / 'launcher'))
sys.path.insert(0, str(PORT / 'scripts'))
import tlg_patches
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
                    'TLG_ENGINE_NATIVE_RESOLUTION', 'TLG_TROPHY_STATE',
                    'TLG_BUFFER_READBACK_BATCH_MB', 'TLG_BUFFER_READBACK_STATS'}
        self.assertTrue(switches.isdisjoint(tlg_run.DEFAULT_ENV))
        settings = dict(tlg_run.DEFAULT_SETTINGS)
        with patch.dict('os.environ', {}, clear=True), \
             patch.object(tlg_run, 'window_icon', return_value=None), \
             patch.object(tlg_run, 'ngs2_module', return_value=None), \
             patch.object(tlg_run, 'applied_frame_rate', '30'):
            env = tlg_run.build_env(settings)
        self.assertTrue(switches.isdisjoint(env))
        self.assertEqual(env['TLG_ENGINE_FPS'], '30')

    def test_60_enables_exact_readback_batching(self):
        settings = dict(tlg_run.DEFAULT_SETTINGS)
        settings['frame_rate'] = '60'
        with patch.dict('os.environ', {}, clear=True), \
             patch.object(tlg_run, 'window_icon', return_value=None), \
             patch.object(tlg_run, 'ngs2_module', return_value=None), \
             patch.object(tlg_run, 'applied_frame_rate', '60'):
            env = tlg_run.build_env(settings)
        self.assertEqual(env['TLG_ENGINE_FPS'], '60')
        self.assertEqual(env['TLG_BUFFER_READBACK_BATCH_MB'], '64')
        self.assertEqual(env['TLG_BUFFER_READBACK_STATS'], '1')

    def test_timeout_is_not_added(self):
        import inspect
        self.assertEqual(inspect.signature(tlg_run.launch).parameters['seconds'].default, 0)


if __name__ == '__main__':
    unittest.main()

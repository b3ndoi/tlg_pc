"""Private prompt art lookup and per-launch environment; no game/settings writes."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

PORT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PORT/'launcher'))
import tlg_run


class PromptSettings(unittest.TestCase):
    def test_lookup_is_read_only_and_scoped_to_the_selected_copy(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(tlg_run,'PORT_DIR',Path(temporary)):
            self.assertIsNone(tlg_run.prompt_image({}))
            path=Path(temporary)/'user/prompt-art/ps5-controller.png'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'Synthetic fixture, not artwork')
            before=path.read_bytes()
            self.assertEqual(tlg_run.prompt_image({}),path)
            self.assertEqual(path.read_bytes(),before)
            self.assertIsNone(tlg_run.prompt_image({'ps5_prompt_image':['invalid']}))
            self.assertIsNone(tlg_run.prompt_image({'ps5_prompt_image':str(Path(temporary)/'absent.png')}))

    def test_environment_is_opt_in_explicit_environment_wins_and_fps_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            image=Path(temporary)/'fixture.png'
            image.write_bytes(b'Synthetic fixture')
            settings={**tlg_run.DEFAULT_SETTINGS,'ps5_prompt_image':str(image)}
            with patch.dict(os.environ,{},clear=True), \
                 patch.object(tlg_run,'window_icon',return_value=None), \
                 patch.object(tlg_run,'ngs2_module',return_value=None), \
                 patch.object(tlg_run,'applied_frame_rate','30'):
                for mode in ('original','keyboard','xbox'):
                    self.assertNotIn('TLG_PS5_PROMPT_IMAGE',tlg_run.build_env({**settings,'button_prompts':mode}))
                for mode in ('auto','ps5'):
                    env=tlg_run.build_env({**settings,'button_prompts':mode})
                    self.assertEqual(env['TLG_PS5_PROMPT_IMAGE'],str(image))
                    self.assertEqual(env['TLG_ENGINE_FPS'],'30')
                    self.assertNotIn('TLG_INPUT_TIMING_60',env)
                with patch.dict(os.environ,{'TLG_PS5_PROMPT_IMAGE':'explicit-local-file.png'}):
                    self.assertEqual(tlg_run.build_env({**settings,'button_prompts':'ps5'})['TLG_PS5_PROMPT_IMAGE'],
                                     'explicit-local-file.png')


if __name__=='__main__':
    unittest.main()

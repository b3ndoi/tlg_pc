# SPDX-License-Identifier: GPL-2.0-or-later
"""Synthetic launcher/preset fixtures. No game launches, owner files or visible UI."""
import copy
import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT / 'launcher'))
sys.path.insert(0, str(PORT / 'scripts'))
from launcher_fixtures import make_game
import tested_profile as preset
import tlg_run as run
import tlg_native_resolution as native
import tlg_slowmotion_60 as slowmotion
import tlg_patches


def synthetic_elf():
    """Generate sparse non-game data containing just the already-public guard bytes."""
    size = native.MODE_OFFSET + len(native.TABLE_EXPECTED)
    elf = bytearray(tlg_patches.TEXT_FILE_OFFSET + size)
    struct.pack_into('<16sHHIQQQIHHHHHH', elf, 0,
                     b'\x7fELF\x02\x01\x01\x09', 0xfe10, 62, 1, 0, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    struct.pack_into('<IIQQQQQQ', elf, 64, 1, 5, tlg_patches.TEXT_FILE_OFFSET,
                     0, 0, size, size, 0x4000)
    guards = [(native.MODE_OFFSET, native.TABLE_EXPECTED),
              (native.SELECTOR_OFFSET, native.SELECTOR_EXPECTED),
              (slowmotion.GRID_OFFSET, slowmotion.EXPECTED_CONSTANTS),
              (slowmotion.QUANTIZER_OFFSET, slowmotion.QUANTIZER_EXPECTED),
              (slowmotion.SCALE_OFFSET, slowmotion.SCALE_EXPECTED),
              (slowmotion.ZERO_GATE_OFFSET, slowmotion.ZERO_GATE_EXPECTED)]
    for name in [*tlg_patches.MODES['60'], *tlg_patches.EU_100_60_EXTRA]:
        for address, expected, _, _ in tlg_patches.EU_100_PATCHES[name]:
            guards.append((address - tlg_patches.GHIDRA_BASE, expected))
    for address, expected in guards:
        at = native.mapped_offset(elf, address, len(expected))
        elf[at:at + len(expected)] = expected
    return bytes(elf)


class PresetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.elf = synthetic_elf()
        cls.digest = hashlib.sha256(cls.elf).hexdigest()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.game = make_game(self.root / 'game')
        self.out = self.root / 'out'
        self.out.mkdir()
        self.user = self.root / 'user'
        self.settings = {**copy.deepcopy(run.DEFAULT_SETTINGS), 'game_dir': str(self.game),
                         'system_lib_dir': str(self.root / 'modules'), 'frame_rate': preset.MODE}
        self.patchers = [patch.object(native, 'ELF_SHA256', self.digest),
                         patch.object(preset, 'is_windows', return_value=True),
                         patch.object(run, 'USER_DIR', self.user), patch.object(run, 'OUT_DIR', self.out),
                         patch.object(run, 'MODS_DIR', self.user / 'mods'),
                         patch.object(run, 'MODS_CONFIG', self.user / 'mods.json'),
                         patch.object(run, 'LOG_DIR', self.root / 'logs'),
                         patch.object(run, 'applied_frame_rate', '60'),
                         patch.object(run, 'window_icon', return_value=None),
                         patch.object(run, 'ngs2_module', return_value=None),
                         patch.dict(os.environ, {}, clear=True)]
        for item in self.patchers:
            item.start()

    def tearDown(self):
        for item in reversed(self.patchers):
            item.stop()
        self.temporary.cleanup()

    def base_patches(self):
        (self.out / 'eboot.elf').write_bytes(self.elf)
        base = slowmotion.expected_base_writes(self.elf)[:-1]
        tlg_patches.write_patch_file(self.out / 'patches.bin', [(a, b, '') for a, b in base])
        return base

    def prepared(self):
        (self.game / 'eboot.bin').write_bytes(self.elf)
        self.base_patches()
        preset.prepare_patches(self.out)

    def test_exact_eight_write_profile_and_installed_image_is_read_only(self):
        (self.game / 'eboot.bin').write_bytes(self.elf)
        preset.validate_game(self.game)
        self.base_patches()
        note = preset.prepare_patches(self.out)
        writes = native.decode_patch_file((self.out / 'patches.bin').read_bytes())
        self.assertEqual(writes, preset.checked_writes(self.elf))
        self.assertEqual((len(writes), sum(len(data) for _, data in writes)), (8, 45))
        self.assertEqual((self.game / 'eboot.bin').read_bytes(), self.elf)
        self.assertEqual((self.out / 'eboot.elf').read_bytes(), self.elf)
        self.assertIn('batching/observers off', note)
        preset.validate_prepared(self.out, '60')

    def test_unknown_image_metadata_and_platform_are_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'exact CUSA03745'):
            preset.validate_game(self.game)  # valid metadata does not certify executable
        (self.game / 'eboot.bin').write_bytes(self.elf)
        with patch.object(preset, 'is_windows', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'Windows'):
                preset.validate_game(self.game)
        for title, version in (('CUSA03627', '01.03'), ('CUSA03745', '01.03')):
            make_game(self.game, title, version)
            with self.assertRaises(RuntimeError):
                preset.validate_game(self.game)

    def test_all_guards_reject_mutations_without_modifying_generated_patches(self):
        self.base_patches()
        before = (self.out / 'patches.bin').read_bytes()
        for address in (native.MODE_OFFSET, native.SELECTOR_OFFSET, slowmotion.GRID_OFFSET,
                        slowmotion.QUANTIZER_OFFSET, slowmotion.SCALE_OFFSET,
                        slowmotion.ZERO_GATE_OFFSET, 0xb8be7c, 0x14e8bd4):
            changed = bytearray(self.elf)
            changed[native.mapped_offset(changed, address, 1)] ^= 1
            with patch.object(native, 'ELF_SHA256', hashlib.sha256(changed).hexdigest()):
                (self.out / 'eboot.elf').write_bytes(changed)
                with self.assertRaises(ValueError):
                    preset.prepare_patches(self.out)
            self.assertEqual((self.out / 'patches.bin').read_bytes(), before)
        self.assertFalse(list(self.out.glob('preset-*.bin')))

    def test_mods_partial_stale_and_duplicate_patches_are_rejected(self):
        base = self.base_patches()
        for writes in ([], base[:-1], base + [(0x100, b'x')], preset.checked_writes(self.elf)):
            tlg_patches.write_patch_file(self.out / 'patches.bin', [(a, b, '') for a, b in writes])
            before = (self.out / 'patches.bin').read_bytes()
            with self.assertRaisesRegex(RuntimeError, 'disable external mods'):
                preset.prepare_patches(self.out)
            self.assertEqual((self.out / 'patches.bin').read_bytes(), before)

    def test_environment_matches_control_and_cannot_reenable_bad_experiments(self):
        poisoned = {key: 'bad' for key in preset.ENV}
        with patch.dict(os.environ, poisoned):
            env = run.build_env(self.settings, poisoned)
        for key, value in preset.ENV.items():
            self.assertEqual(env[key], value, key)
        self.assertEqual(env['TLG_CONFIG'], str(self.user / preset.INI_NAME))
        self.assertEqual(env['TLG_GC_BUDGET_MB'], str(self.settings['vram_budget_mb']))
        self.assertFalse(self.user.exists())

    def test_mode_selection_and_explicit_30_override_do_not_leak_profile(self):
        self.assertEqual(run.frame_rate_choice(self.settings), preset.MODE)
        self.assertEqual(run.frame_rate(self.settings), '60')
        for mode in ('30', '60', 'unlocked'):
            settings = {**self.settings, 'frame_rate': mode}
            with patch.object(run, 'applied_frame_rate', mode):
                env = run.build_env(settings)
            for key in ('TLG_TIMING_60', 'TLG_INPUT_TIMING_60', 'TLG_CLOCK_SYNC_60',
                        'TLG_ENGINE_NATIVE_RESOLUTION', 'TLG_CLIMB_DIAG'):
                self.assertNotIn(key, env)
            self.assertEqual(env['TLG_CONFIG'], str(self.user / 'tlg.ini'))
        with patch.dict(os.environ, {'TLG_FPS': '30'}), patch.object(run, 'applied_frame_rate', '30'):
            self.assertFalse(run.tested_preset(self.settings))
            self.assertEqual(run.frame_rate(self.settings), '30')
            self.assertNotIn('TLG_CLOCK_SYNC_60', run.build_env(self.settings))

    def test_prepare_stops_before_any_subprocess_or_user_write_on_bad_image(self):
        with patch.object(run.subprocess, 'run') as process, patch.object(run, 'isa_table') as isa:
            with self.assertRaises(RuntimeError):
                run.prepare(self.settings)
        process.assert_not_called()
        isa.assert_not_called()
        self.assertFalse(self.user.exists())

    def test_preparation_pipeline_adds_profile_before_forced_red_zone_isa(self):
        (self.game / 'eboot.bin').write_bytes(self.elf)
        self.base_patches()
        result = Mock(returncode=0, stdout='Frame rate: 60 FPS mode, 5 patch writes\n')
        notes = []
        with patch.object(run.subprocess, 'run', return_value=result) as process, \
             patch.object(run, 'isa_table') as isa:
            run.prepare(self.settings, notes.append)
        self.assertEqual(process.call_count, 4)
        self.assertIn('60', process.call_args.args[0])
        isa.assert_called_once_with(notes.append, force_red_zone=True)
        preset.validate_prepared(self.out, '60')
        self.assertTrue(any('8 writes, 45 bytes' in line for line in notes))

    def test_launch_uses_isolated_ini_and_returns_to_unchanged_30(self):
        self.prepared()
        self.user.mkdir()
        baseline = b'# baseline kept byte-for-byte\noutput_res=1920x1080\nengine_fps=30\nshow_fps=1\n'
        (self.user / 'tlg.ini').write_bytes(baseline)
        settings = {**self.settings, 'track_achievements': False}
        with patch.object(run.subprocess, 'Popen') as process:
            run.launch(settings)
            argv = process.call_args.args[0]
            self.assertEqual(argv[argv.index('--timeout') + 1], '0')
            self.assertEqual(process.call_args.kwargs['env']['TLG_CONFIG'], str(self.user / preset.INI_NAME))
            self.assertEqual((self.user / 'tlg.ini').read_bytes(), baseline)
            values = run.read_ini(self.user / preset.INI_NAME)
            for key, value in preset.INI.items():
                self.assertEqual(values[key], str(value))
            with patch.object(run, 'applied_frame_rate', '30'):
                run.launch({**settings, 'frame_rate': '30'})
            env = process.call_args.kwargs['env']
            self.assertEqual(env['TLG_CONFIG'], str(self.user / 'tlg.ini'))
            self.assertNotIn('TLG_CLOCK_SYNC_60', env)
            self.assertEqual(run.read_ini(self.user / 'tlg.ini')['output_res'], '1920x1080')
            self.assertEqual(run.read_ini(self.user / 'tlg.ini')['engine_fps'], '30')

    def test_failed_launch_guard_does_not_create_user_or_start_process(self):
        (self.game / 'eboot.bin').write_bytes(self.elf)
        self.base_patches()
        with patch.object(run.subprocess, 'Popen') as process:
            with self.assertRaises(RuntimeError):
                run.launch(self.settings)
        process.assert_not_called()
        self.assertFalse(self.user.exists())

    def test_launch_rechecks_selected_game_before_any_user_write(self):
        self.prepared()
        (self.game / 'eboot.bin').write_bytes(b'Changed after preparation')
        with patch.object(run.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(RuntimeError, 'exact CUSA03745'):
                run.launch(self.settings)
        process.assert_not_called()
        self.assertFalse(self.user.exists())


if __name__ == '__main__':
    unittest.main()

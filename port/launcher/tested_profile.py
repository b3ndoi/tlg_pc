# SPDX-License-Identifier: GPL-2.0-or-later
"""Opt-in, exact-build 1440p/60 control profile. No game process or asset writes.

The public preset reproduces the successful batching-OFF control, not the
readback experiment. Nothing here runs for the ordinary 30/60/unlocked modes.
"""
import os
from pathlib import Path
import tempfile

from game_library import game_info
import tlg_native_resolution as native
import tlg_patches
import tlg_slowmotion_60 as slowmotion

MODE = '1440p60'
INI_NAME = 'tlg-1440p60.ini'
ERROR = '1440p/60 preset requires Windows and the exact CUSA03745 EU 01.00 executable'

# These are intentional overrides, including inherited experiment switches.
# The user's VRAM budget, controls, trophy preferences and audio choice stay theirs.
ENV = {
    'TLG_TIMING_60': '1', 'TLG_INPUT_TIMING_60': '1', 'TLG_CLOCK_SYNC_60': '1',
    'TLG_ENGINE_FPS': '60', 'TLG_FPS_LIMIT': '60', 'TLG_PRECISE_PACING': '1',
    'TLG_ENGINE_NATIVE_RESOLUTION': '2560x1440', 'TLG_NATIVE_OUTPUT': '0',
    'TLG_INTERNAL_WIDTH': '1920', 'TLG_INTERNAL_HEIGHT': '1080',
    'TLG_OUTPUT_RES': '2560x1440', 'TLG_UPSCALER': 'off', 'TLG_UPSCALE_PRESET': '0',
    'TLG_FSR1': '0', 'TLG_JITTER': '0', 'TLG_OBJECT_MOTION': '0',
    'TLG_READBACKS': '2', 'TLG_READBACK_LINEAR': '1',
    'TLG_BUFFER_READBACK_BATCH_MB': '0', 'TLG_DEFERRED_READBACK': '0', 'TLG_STALE_READBACK': '0',
    'TLG_CLIMB_DIAG': '0', 'TLG_CLIMB_INPUT_DIAG': '0', 'TLG_TAIL_DIAGNOSTICS': '0',
    'TLG_CLIMB_STATE_DIAG': '0',
    'TLG_RELOAD_NULL_GUARD': '1', 'TLG_RED_ZONE_REWRITE': '1', 'TLG_LANGUAGE': '1',
}
INI = {
    'output_res': '2560x1440', 'render_resolution': 'native', 'live_resolution': 0,
    'engine_fps': 60, 'fps_limit': 60, 'display_mode': 'fullscreen', 'vsync': 1,
    'upscaler': 'off', 'preset': 0, 'fsr1': 0, 'jitter': 0, 'object_motion': 0,
    'deferred_readback': 0, 'stale_readback': 0, 'frames_queued': 1,
}


def is_windows():
    return os.name == 'nt'


def available(game_dir, platform=None):
    """Cheap metadata check for the UI. Hash/signature checks still run before Play."""
    info = game_info(game_dir)
    return ((is_windows() if platform is None else platform == 'nt') and bool(info)
            and info['title_id'] == 'CUSA03745' and info['version'] == '01.00')


def checked_writes(elf):
    """Same eight writes / 45 bytes as the tested control; every guard retained."""
    return slowmotion.expected_base_writes(elf) + slowmotion.checked_writes(elf)


def validate_game(game_dir):
    if not available(game_dir):
        raise RuntimeError(ERROR)
    elf = tlg_patches.read_eboot_elf(game_dir)
    try:
        checked_writes(elf or b'')
    except (ValueError, OSError) as error:
        raise RuntimeError(f'{ERROR}: {error}') from error


def prepare_patches(out_dir):
    """Only the generated loader patch file changes; never the installed ELF/SELF.

    Reject mods/partial or stale FPS writes. Validate the entire result before
    atomically replacing patches.bin, so failed validation cannot leave half a preset.
    """
    out = Path(out_dir)
    elf = (out / 'eboot.elf').read_bytes()
    writes = checked_writes(elf)
    base = slowmotion.expected_base_writes(elf)[:-1]
    path = out / 'patches.bin'
    if native.decode_patch_file(path.read_bytes()) != base:
        raise RuntimeError('1440p/60 preset: expected only the five EU FPS/vegetation writes; '
                           'disable external mods and TLG_FPS_PATCHES for this preset')
    with tempfile.NamedTemporaryFile(prefix='preset-', suffix='.bin', dir=out, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        tlg_patches.write_patch_file(temporary, [(address, data, '1440p60') for address, data in writes])
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return ('1440p/60 preset: exact EU 01.00 verified; 8 writes, 45 bytes; native 2560x1440, '
            'English, FIFO VSync; input/script/shared-clock fixes on; batching/observers off')


def validate_prepared(out_dir, applied_mode):
    if not is_windows() or applied_mode != '60':
        raise RuntimeError(ERROR + '; prepare this preset before launching')
    out = Path(out_dir)
    expected = checked_writes((out / 'eboot.elf').read_bytes())
    if native.decode_patch_file((out / 'patches.bin').read_bytes()) != expected:
        raise RuntimeError('1440p/60 preset: generated patches do not match the complete verified profile')

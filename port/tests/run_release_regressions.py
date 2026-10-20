#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded CPU-only release checks. No game launch, GPU or controller access.

Default tests require no game files. --elf enables additional offline tests on
an owner-supplied exact EU ELF; it is never uploaded or modified. Build products
are temporary. Exact script/archive tests remain a separate private validation.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PORT = Path(__file__).resolve().parents[1]


def run(argv, **kwargs):
    print('+ ' + ' '.join(map(str, argv)), flush=True)
    subprocess.run(list(map(str, argv)), check=True, timeout=180, cwd=PORT, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path)
    args = parser.parse_args()
    elf = args.elf.resolve() if args.elf else None
    if elf and not elf.is_file():
        parser.error('--elf must be an existing local file')
    for name in ('test_tlg_patches.py', 'test_release_defaults.py', 'test_achievements.py',
                 'test_launcher_localization.py', 'test_launcher_ui.py'):
        run([sys.executable, PORT/'tests'/name])
    if sys.platform != 'win32':
        print('SKIP: Windows native fixtures require Windows/MSYS2 CLANG64')
        return
    cc, cxx = shutil.which('clang'), shutil.which('clang++')
    if not cc or not cxx:
        parser.error('clang and clang++ from MSYS2 CLANG64 must be on PATH')
    native = [
        ('fault-dispatch', ['tests/test_fault_dispatch_win.c', 'src/compat_win.c'],
         ['-lbcrypt', '-lonecore', '-pthread'], []),
        ('queued-commands', ['tests/test_queued_commands.cpp'], [], []),
        ('ui-composition', ['tests/test_ui_composition.cpp'], [], []),
        ('display-coherence', ['tests/test_display_coherence.cpp'],
         ['-DVULKAN_HPP_NO_CONSTRUCTORS'], []),
        ('win-pacing', ['tests/test_win_pacing.cpp'],
         ['-DNOMINMAX', '-DWIN32_LEAN_AND_MEAN', '-pthread'], []),
        ('reload-null-guard', ['tests/test_reload_null_guard_win.cpp'], [], [elf] if elf else []),
        ('input-timing-60', ['tests/test_input_timing_60_win.cpp', 'src/input_timing_60.c',
                            'src/climb_diagnostics.c'], [], [elf] if elf else []),
        ('clock-quantization', ['tests/test_clock_quantization.cpp'], [], []),
    ]
    if elf:
        native += [
            ('clock-sync-60', ['tests/test_clock_sync_60_win.cpp', 'src/clock_sync_60.c'],
             ['-lbcrypt'], [elf]),
            ('slowmotion-clock', ['tests/test_slowmotion_clock_win.cpp'], [], [elf]),
            ('climb-diagnostics', ['tests/test_climb_diagnostics_win.cpp', 'src/climb_diagnostics.c'],
             [], [elf]),
        ]
        for name in ('test_native_resolution.py', 'test_slowmotion_60.py'):
            run([sys.executable, PORT/'tests'/name, '--elf', elf])
    else:
        print('SKIP: exact native clock/schema/ELF fixtures (provide --elf locally)')
    with tempfile.TemporaryDirectory(prefix='tlg-release-tests-') as directory:
        output = Path(directory)
        includes = ['-I'+str(PORT), '-I'+str(PORT/'src'),
                    '-I'+str(PORT/'gpu/shim'), '-I'+str(PORT/'gpu/shadps4')]
        common = ['-O2', '-UNDEBUG', '-Wall', '-Wextra', '-Werror', *includes]
        for name, sources, extra, arguments in native:
            objects = []
            for index, source in enumerate(sources):
                source = PORT/source
                target = output/f'{name}-{index}.o'
                compiler, standard = (cc, '-std=c11') if source.suffix == '.c' else (cxx, '-std=c++23')
                defines = [flag for flag in extra if flag.startswith('-D')]
                run([compiler, standard, *common, *defines, '-c', source, '-o', target])
                objects.append(target)
            executable = output/f'{name}.exe'
            run([cxx, *objects, *extra, '-o', executable])
            run([executable, *arguments])
    print('PASS: release regressions complete; no game process started or attached')


if __name__ == '__main__':
    main()

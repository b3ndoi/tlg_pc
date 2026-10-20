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
    subprocess.run(list(map(str, argv)), check=True, timeout=180, cwd=kwargs.pop('cwd', PORT), **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', type=Path)
    args = parser.parse_args()
    elf = args.elf.resolve() if args.elf else None
    if elf and not elf.is_file():
        parser.error('--elf must be an existing local file')
    for name in ('test_tlg_patches.py', 'test_release_defaults.py', 'test_achievements.py',
                 'test_launcher_localization.py', 'test_launcher_ui.py', 'test_trophy_catalog.py',
                 'test_native_trophies.py', 'test_trophy_save_audit.py', 'test_package_assets.py',
                 'test_prompt_settings.py', 'test_photo_mode.py'):
        run([sys.executable, PORT/'tests'/name])
    cxx = shutil.which('clang++' if sys.platform=='win32' else os.environ.get('CXX','c++'))
    if not cxx:
        parser.error('a C++23 compiler is required for prompt/settings fixtures')
    with tempfile.TemporaryDirectory(prefix='tlg-prompt-tests-') as directory:
        for name,sources,extra in (
            ('prompts',['tests/test_prompts.cpp','gpu/shim/tlg_prompts.cpp'],['-lxxhash']),
            ('graphics-settings',['tests/test_graphics_settings.cpp','gpu/shim/tlg_settings.cpp'],[])):
            target=Path(directory)/(name+('.exe' if sys.platform=='win32' else ''))
            run([cxx,'-std=c++23','-O2','-UNDEBUG','-Wall','-Wextra','-Werror','-Igpu/shim',
                 *sources,*extra,'-o',target])
            run([target],cwd=directory)
    if sys.platform != 'win32':
        cc = shutil.which(os.environ.get('CC', 'cc'))
        if not cc:
            parser.error('a C compiler is required for native trophy/service fixtures')
        with tempfile.TemporaryDirectory(prefix='tlg-trophy-tests-') as directory:
            root = Path(directory)
            for name, sources in (('trophy-state', ['tests/test_runtime_trophies.c', 'src/runtime_trophies.c']),
                                  ('services', ['tests/test_services.c', 'src/runtime_trophies.c'])):
                target = root / name
                run([cc, '-std=c11', '-O2', '-UNDEBUG', '-Wall', '-Wextra', '-Werror', '-pthread',
                     '-I.', '-Isrc', *sources, '-o', target])
                run([target, root / (name + '-state')])
        print('PASS: native trophy/services fixtures; SKIP: other Windows-only fixtures')
        return
    cc, cxx = shutil.which('clang'), shutil.which('clang++')
    if not cc or not cxx:
        parser.error('clang and clang++ from MSYS2 CLANG64 must be on PATH')
    native = [
        ('photo-runtime', ['tests/test_runtime_photo.c','src/runtime_photo.c'], ['-pthread'], []),
        ('photo-mailbox', ['tests/test_photo_mailbox.c','src/runtime_photo.c','src/compat_win.c'],
         ['-pthread','-lbcrypt','-lonecore'], []),
        ('prompt-image', ['tests/test_prompt_image.cpp','gpu/shim/tlg_prompts.cpp',
                          'gpu/shim/tlg_prompt_image.cpp','gpu/shim/tlg_png.cpp'],
         ['-lxxhash','-lavcodec','-lavutil','-lswscale'], []),
        ('pad-map', ['tests/test_pad_map.c','src/compat_win.c'],
         ['-lSDL3','-lbcrypt','-lonecore','-pthread'], []),
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
        ('trophy-state', ['tests/test_runtime_trophies.c', 'src/runtime_trophies.c'], ['-pthread'], []),
        ('services', ['tests/test_services.c', 'src/runtime_trophies.c', 'src/compat_win.c'],
         ['-pthread', '-lbcrypt', '-lonecore'], []),
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
            if name == 'trophy-state':
                bridge = "import sys;sys.path.insert(0,'launcher');import native_trophies as n;"
                run([sys.executable, '-c', bridge + "n.seed(sys.argv[1],'CUSA03745',{'9':{'unlocked_at':'2026-10-20T12:00:00+00:00','source':'game_trophy'}},3)", output / 'native-trophy-state'])
            private = [output / ('native-' + name + '-state')] if name in ('trophy-state', 'services', 'prompt-image') else []
            # Keep the bridge's seed/output name stable for its Python checks.
            if name == 'trophy-state':
                private = [output / 'native-trophy-state']
            run([executable, *private, *arguments])
            if name == 'trophy-state':
                run([sys.executable, '-c', bridge + "r=n.read(sys.argv[1],'CUSA03745',3);assert set(r)=={'9','10'};assert r['9']['unlocked_at']=='2026-10-20T12:00:00+00:00';print('Python/native wire-format merge roundtrip passed')", output / 'native-trophy-state'])
                processes = [subprocess.Popen([str(executable), str(output / 'native-trophy-state'),
                                                'parallel', str(i)]) for i in range(12)]
                for process in processes:
                    if process.wait(timeout=15):
                        raise RuntimeError('Concurrent native trophy writer failed')
                run([sys.executable, '-c', bridge + "r=n.read(sys.argv[1],'CUSA03745',4);assert set(r)==set(map(str,range(12)));print('12 concurrent native processes merged without loss')", output / 'native-trophy-state'])
    print('PASS: release regressions complete; no game process started or attached')


if __name__ == '__main__':
    main()

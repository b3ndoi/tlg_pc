"""Package/Git exclusions using synthetic empty files, never owner game assets."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

PORT = Path(__file__).resolve().parents[1]
REPO = PORT.parent


def bash_path():
    if sys.platform == 'win32':
        clang = shutil.which('clang')
        if clang:
            candidate = Path(clang).resolve().parents[2] / 'usr/bin/bash.exe'
            if candidate.is_file():
                return str(candidate)
    return shutil.which('bash')


class PackageAssetsTests(unittest.TestCase):
    def test_trophy_assets_are_ignored_without_hiding_launcher_sources(self):
        paths = ['trophies/ICON0.PNG', 'trophy/other.png', 'private-copy/TROP000.PNG',
                 'private-copy/trophy_025.png', 'private-copy/TROPHY00.TRP',
                 'private-copy/trophy_001.esfm', 'private-copy/TROPCONF.XML',
                 'private-copy/TROP_01.XML', 'private-copy/controller.GNF']
        for path in paths:
            with self.subTest(path=path):
                result = subprocess.run(['git', 'check-ignore', '-q', '--', path], cwd=REPO,
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        for path in ['port/launcher/trophy_catalog.py', 'port/launcher/native_trophies.py',
                     'port/tests/test_trophy_catalog.py']:
            result = subprocess.run(['git', 'check-ignore', '--no-index', '-q', '--', path],
                                    cwd=REPO, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 1)

    def test_package_rejects_trophy_assets_and_allows_source_files(self):
        bash = bash_path()
        self.assertIsNotNone(bash, 'Bash is required to validate the real packaging guard')
        with tempfile.TemporaryDirectory(prefix='tlg-package-guard-') as directory:
            root = Path(directory)
            (root / 'launcher').mkdir()
            (root / 'launcher/trophy_catalog.py').write_text('# Synthetic fixture\n')
            (root / 'launcher/tlg.png').write_bytes(b'Synthetic launcher icon, not game art')
            env = dict(os.environ)
            env['PATH'] = str(Path(bash).parent) + os.pathsep + env.get('PATH', '')

            def check():
                return subprocess.run([bash, (PORT / 'packaging/check_package.sh').as_posix(),
                                       root.as_posix()], capture_output=True, timeout=15, env=env)

            self.assertEqual(check().returncode, 0)
            for name in ['TROP000.PNG', 'trophy_025.png', 'TROPCONF.XML', 'TROP_01.XML',
                         'TROPHY00.TRP', 'trophy_001.esfm', 'ICON0.PNG','controller.GNF']:
                with self.subTest(name=name):
                    fixture = root / name
                    fixture.write_bytes(b'Synthetic fixture, not game data')
                    result = check()
                    self.assertEqual(result.returncode, 1, result.stderr.decode(errors='replace'))
                    fixture.unlink()
            for name in ['trophy', 'trophies']:
                folder = root / name
                folder.mkdir()
                self.assertEqual(check().returncode, 1)
                folder.rmdir()
            self.assertEqual(check().returncode, 0)


if __name__ == '__main__':
    unittest.main()

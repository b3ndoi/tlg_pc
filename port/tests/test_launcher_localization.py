"""Translation data/packaging checks; no UI or user configuration writes."""
import json
import os
from pathlib import Path
from string import Formatter
import sys
import tempfile
import unittest
from unittest.mock import patch

PORT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PORT / 'launcher'))
import localization as loc


def fields(value):
    return {name for _, name, _, _ in Formatter().parse(value) if name is not None}


class LocalizationTests(unittest.TestCase):
    def test_complete_catalogs_and_matching_placeholders(self):
        self.assertGreater(len(loc.ENGLISH), 100)
        self.assertIn('pt_BR', loc.CATALOGS)
        self.assertIn('sr_Latn_RS', loc.CATALOGS)
        self.assertEqual(set(loc.CATALOGS['pt_BR']), set(loc.ENGLISH))
        self.assertEqual(set(loc.CATALOGS['sr_Latn_RS']), set(loc.ENGLISH))
        for language, catalog in loc.CATALOGS.items():
            with self.subTest(language=language):
                self.assertTrue(set(catalog).issubset(loc.ENGLISH))
                self.assertIn('_language_name', catalog)
                for key, translated in catalog.items():
                    self.assertEqual(fields(loc.ENGLISH[key]), fields(translated), (language, key))

    def test_fallback_for_incomplete_or_malformed_translation(self):
        with patch.dict(loc.CATALOGS, {'xx_YY': {'play': 'Start', 'achievement_saved': 'Bad {missing}'}}):
            self.assertEqual(loc.text('play', 'xx_YY'), 'Start')
            self.assertEqual(loc.text('ready', 'xx_YY'), loc.ENGLISH['ready'])
            self.assertEqual(loc.text('achievement_saved', 'xx_YY', id=1), 'Saved locally: trophy #1')

    def test_auto_and_explicit_language(self):
        with patch.dict(os.environ, {'LANG': 'pt_PT.UTF-8'}, clear=True):
            self.assertEqual(loc.language({'ui_language': 'auto'}), 'pt_BR')
            self.assertEqual(loc.language({'ui_language': 'en_US'}), 'en_US')
        with patch.dict(os.environ, {'LANG': 'sr_RS.UTF-8'}, clear=True):
            self.assertEqual(loc.language({'ui_language': 'auto'}), 'sr_Latn_RS')
        with patch.dict(os.environ, {'LANG': 'sr-Latn-RS.UTF-8'}, clear=True):
            self.assertEqual(loc.language({'ui_language': 'auto'}), 'sr_Latn_RS')

    def test_new_catalog_does_not_require_ui_source_changes(self):
        with patch.dict(loc.CATALOGS, {'zz_Latn_ZZ': {'_language_name': 'Synthetic'}}), \
             patch.dict(os.environ, {'LANG': 'zz_Latn_ZZ.UTF-8'}, clear=True):
            self.assertEqual(loc.language({'ui_language': 'zz_Latn_ZZ'}), 'zz_Latn_ZZ')
            self.assertEqual(loc.language({'ui_language': 'auto'}), 'zz_Latn_ZZ')
            self.assertEqual(loc.text('ready', 'zz_Latn_ZZ'), loc.ENGLISH['ready'])

    def test_invalid_catalog_falls_back_without_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.assertEqual(loc.load_catalog('../escape', folder), {})
            self.assertEqual(loc.load_catalog('zz_ZZ', folder), {})
            for raw in ('invalid', '[]', '{"play": 123}'):
                (folder / 'zz_ZZ.json').write_text(raw)
                self.assertEqual(loc.load_catalog('zz_ZZ', folder), {})
            (folder / 'zz_ZZ.json').write_text(json.dumps({'play': 'Start'}))
            self.assertEqual(loc.load_catalog('zz_ZZ', folder), {'play': 'Start'})

    def test_both_package_scripts_collect_and_check_catalogs(self):
        for platform in ('windows', 'linux'):
            source = (PORT / 'packaging' / platform / 'package.sh').read_text()
            self.assertIn('--add-data', source)
            self.assertIn('launcher/locales', source)
            self.assertIn('_internal/locales/$language.json', source)


if __name__ == '__main__':
    unittest.main()

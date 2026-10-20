# SPDX-License-Identifier: GPL-2.0-or-later
"""Data-only launcher translations; English is the fallback for incomplete locales."""
import json
import locale
import os
from pathlib import Path
import re

LOCALES = Path(__file__).resolve().parent / 'locales'
LOCALE_PATTERN = r'[a-z]{2,3}(?:_[A-Z][a-z]{3})?_[A-Z]{2}'


def load_catalog(language, folder=LOCALES):
    if not isinstance(language, str) or not re.fullmatch(LOCALE_PATTERN, language):
        return {}
    try:
        with (Path(folder) / (language + '.json')).open(encoding='utf-8') as source:
            values = json.load(source)
        if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                               for k, v in values.items()):
            return {}
        return values
    except (OSError, ValueError):
        return {}


CATALOGS = {path.stem: load_catalog(path.stem) for path in sorted(LOCALES.glob('*.json'))
            if re.fullmatch(LOCALE_PATTERN, path.stem)}
ENGLISH = CATALOGS.get('en_US', {})
NAMES = {key: values.get('_language_name', key) for key, values in CATALOGS.items()}


def language(settings):
    selected = settings.get('ui_language', 'auto')
    if selected in CATALOGS:
        return selected
    system = ''
    for name in ('LC_ALL', 'LC_MESSAGES', 'LANG'):
        if os.environ.get(name):
            system = os.environ[name]
            break
    if not system:
        try:
            system = locale.getlocale()[0] or ''
        except ValueError:
            pass
    system = system.split('.', 1)[0].replace('-', '_')
    if system in CATALOGS:
        return system
    prefix = system.lower().split('_', 1)[0]
    return next((key for key in CATALOGS if key.split('_')[0] == prefix), 'en_US')


def text(key, selected='en_US', **values):
    fallback = ENGLISH.get(key, key)
    translated = CATALOGS.get(selected, {}).get(key, fallback)
    try:
        return translated.format(**values)
    except (KeyError, ValueError, IndexError):
        return fallback.format(**values)

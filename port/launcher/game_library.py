# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded, read-only metadata for the launcher; never prepares or patches a game."""
from pathlib import Path
import struct

TITLE_IDS = frozenset(('CUSA03627', 'CUSA03745'))
MAX_SFO = 1024 * 1024


def game_info(game_dir):
    """Return metadata only for a supported title with its own eboot present."""
    if not game_dir:
        return None
    folder = Path(game_dir)
    try:
        if not (folder / 'eboot.bin').is_file():
            return None
        with (folder / 'sce_sys' / 'param.sfo').open('rb') as source:
            data = source.read(MAX_SFO + 1)
        if len(data) > MAX_SFO or len(data) < 20:
            return None
        magic, _, keys, values, count = struct.unpack_from('<4sIIII', data)
        if magic != b'\0PSF' or count > 256 or 20 + count * 16 > keys or not keys <= values <= len(data):
            return None
        fields = {}
        for index in range(count):
            key, kind, size, maximum, offset = struct.unpack_from('<HHIII', data, 20 + index * 16)
            start = keys + key
            end = data.find(b'\0', start, values)
            if not keys <= start < values or end < 0 or size > maximum or values + offset + size > len(data):
                return None
            name = data[start:end].decode('ascii')
            if kind == 0x204 and name in ('TITLE_ID', 'APP_VER', 'TITLE'):
                text = data[values + offset:values + offset + size].split(b'\0', 1)[0].decode('utf-8')
                fields[name] = ''.join(char for char in text if char.isprintable())[:128]
        if fields.get('TITLE_ID') not in TITLE_IDS:
            return None
        return {'title_id': fields['TITLE_ID'], 'version': fields.get('APP_VER', ''),
                'name': fields.get('TITLE', 'The Last Guardian')}
    except (OSError, ValueError, UnicodeError, struct.error, TypeError):
        return None

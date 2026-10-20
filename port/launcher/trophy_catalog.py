# SPDX-License-Identifier: GPL-2.0-or-later
"""Read only the owner's trophy catalog; no game assets or keys are bundled.

TRP layout reference: shadPS4 src/core/file_format/trp.h (GPL-2.0-or-later).
Encrypted ESFM is deliberately not guessed. Unknown entries stay masked by default.
"""
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

MAX_XML = 1024 * 1024
MAX_ICON = 1024 * 1024
PNG = b'\x89PNG\r\n\x1a\n'


class CatalogError(ValueError):
    pass


def bounded(path, maximum):
    with Path(path).open('rb') as source:
        data = source.read(maximum + 1)
    if len(data) > maximum:
        raise CatalogError('Trophy file exceeds its size limit')
    return data


class Archive:
    def __init__(self, path):
        self.path, self.entries = Path(path), {}
        with self.path.open('rb') as source:
            header = source.read(96)
            if len(header) != 96:
                raise CatalogError('Truncated trophy archive')
            magic, version, size, count, stride = struct.unpack_from('>IIQII', header)
            if (magic != 0xDCA24D00 or version not in (1, 2, 3) or stride != 64
                    or not 0 < count <= 512 or not 96 + count * stride <= size <= 32 * MAX_XML
                    or self.path.stat().st_size != size):
                raise CatalogError('Invalid trophy archive header')
            spans = []
            for _ in range(count):
                entry = source.read(stride)
                name = entry[:32].split(b'\0', 1)[0]
                if not re.fullmatch(rb'[A-Za-z0-9_.-]{1,31}', name):
                    raise CatalogError('Unsafe trophy archive name')
                name = name.decode('ascii').upper()
                offset, length, flags = struct.unpack_from('>QQI', entry, 32)
                if (name in self.entries or not length or offset < 96 + count * stride
                        or offset + length > size or any(offset < end and start < offset + length
                                                        for start, end in spans)):
                    raise CatalogError('Invalid/overlapping trophy archive entry')
                spans.append((offset, offset + length))
                self.entries[name] = (offset, length, flags)

    def read(self, name, maximum):
        offset, size, _ = self.entries[name]
        if size > maximum:
            raise CatalogError('Trophy archive entry exceeds its size limit')
        with self.path.open('rb') as source:
            source.seek(offset)
            data = source.read(size)
        if len(data) != size:
            raise CatalogError('Truncated trophy archive entry')
        return data


def parse_xml(data):
    if len(data) > MAX_XML:
        raise CatalogError('Unsafe trophy XML')
    try:
        text = data.decode('utf-8-sig')
        if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
            raise ValueError('XML entities are not allowed')
        root = ET.fromstring(text)
        if root.tag != 'trophyconf':
            raise ValueError('expected trophyconf')
        trophies = {}
        for node in root.findall('trophy'):
            key = node.get('id', '')
            hidden, grade = node.get('hidden', '').lower(), node.get('ttype', '')
            if (not re.fullmatch(r'[0-9]{1,3}', key) or not 0 <= int(key) < 128
                    or int(key) in trophies or hidden not in ('yes', 'no', 'true', 'false', '0', '1')
                    or grade not in ('P', 'G', 'S', 'B')):
                raise ValueError('invalid trophy attributes')
            name, detail = node.findtext('name', '').strip(), node.findtext('detail', '').strip()
            if not name or len(name) > 256 or len(detail) > 2048:
                raise ValueError('invalid trophy text')
            trophies[int(key)] = dict(id=int(key), name=name, detail=detail, grade=grade,
                                      hidden=hidden in ('yes', 'true', '1'), known=True)
        if not trophies:
            raise ValueError('empty trophy catalog')
        return trophies
    except (ET.ParseError, ValueError, UnicodeError, RecursionError) as error:
        raise CatalogError('Invalid decrypted trophy XML') from error


def xml_in(folder, language):
    folder = Path(folder)
    if not folder.is_dir():
        return None
    names = {}
    for index, path in enumerate(folder.iterdir()):
        if index >= 1024:
            raise CatalogError('Too many files in trophy metadata folder')
        if path.is_file():
            names[path.name.upper()] = path
    # The unnumbered TROP.XML is the English/master fallback. No foreign-language
    # fallback is silently preferred to it; Portuguese is the other built-in UI.
    choices = (['TROP_17.XML'] if language == 'pt_BR' else ['TROP_01.XML']) + ['TROP.XML', 'TROPCONF.XML']
    return next((names[name] for name in choices if name in names), None)


def png_checked(data):
    if len(data) < 33 or len(data) > MAX_ICON or data[:8] != PNG or data[12:16] != b'IHDR':
        raise CatalogError('Invalid trophy PNG')
    width, height = struct.unpack_from('>II', data, 16)
    if not 0 < width <= 1024 or not 0 < height <= 1024:
        raise CatalogError('Trophy icon dimensions exceed the limit')
    return data


class Catalog:
    def __init__(self, game_dir, metadata_dir='', language='en_US'):
        self.trophies, self.archive, self.xml_path = {}, None, None
        folder = Path(game_dir) / 'sce_sys' / 'trophy'
        if folder.is_dir():
            archives = sorted(path for path in folder.iterdir() if path.name.lower() == 'trophy00.trp')
            if archives:
                self.archive = Archive(archives[0])
        # XML is explicit owner-supplied local data, never downloaded or shipped.
        for candidate in ([Path(metadata_dir), Path(metadata_dir) / 'Xml'] if metadata_dir else []) + [folder]:
            self.xml_path = xml_in(candidate, language)
            if self.xml_path:
                self.trophies = parse_xml(bounded(self.xml_path, MAX_XML))
                break
        if self.archive:
            for name, (_, _, flags) in self.archive.entries.items():
                match = re.fullmatch(r'TROP([0-9]{3})\.PNG', name)
                if match and flags == 0 and int(match[1]) < 128:
                    key = int(match[1])
                    self.trophies.setdefault(key, dict(id=key, known=False, hidden=True,
                                                       name='', detail='', grade=''))

    @property
    def complete(self):
        return bool(self.trophies) and all(t['known'] for t in self.trophies.values())

    def icon(self, trophy_id):
        """Called only after presentation has decided the trophy may be revealed."""
        name = f'TROP{trophy_id:03d}.PNG'
        if self.archive and name in self.archive.entries:
            return png_checked(self.archive.read(name, MAX_ICON))
        if self.xml_path:
            for folder in (self.xml_path.parent, self.xml_path.parent.parent / 'Icons'):
                path = folder / name
                if path.is_file():
                    return png_checked(bounded(path, MAX_ICON))
        return None

    def view(self, trophy_id, unlocked=False, show_unknown_icons=False):
        entry = self.trophies[trophy_id]
        masked = not entry['known'] or entry['hidden'] and not unlocked
        # Explicit spoiler opt-in reveals only artwork whose hidden flag is unknown.
        # It never invents metadata/unlocks or overrides a known hidden flag.
        show_icon = not masked or (show_unknown_icons and not entry['known'])
        return dict(id=trophy_id, masked=masked, unlocked=unlocked,
                    name='' if masked else entry['name'], detail='' if masked else entry['detail'],
                    grade='' if masked else entry['grade'], icon=self.icon(trophy_id) if show_icon else None)

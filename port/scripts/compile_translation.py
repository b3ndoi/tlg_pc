#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile original UTF-8 fan text into a host-only texture pack. No game files needed.

Requires Pillow for rendering (pip install -r requirements-translation.txt).
The target table contains geometry/fingerprints only, never original game pixels.
"""
import argparse
import io
import json
from pathlib import Path
import re
from string import Formatter
import struct
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
MAGIC = b'TLGTRN1\0'
RECORD = struct.Struct('<IIIQQI')
GLYPHS = {'circle': '○', 'cross': '×', 'triangle': '△', 'r1': 'R1'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    # Strict UTF-8, no locale/codepage fallback, duplicate keys or BOM.
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def validate(catalog, target_table):
    if not isinstance(target_table, dict) or target_table.get('schema') != 1 or \
            target_table.get('profile') != 'EU-01.00-English-tutorials' or \
            not isinstance(target_table.get('targets'), dict):
        raise ValueError('Unsupported target table')
    for key, target in target_table['targets'].items():
        if not re.fullmatch(r'[a-z0-9_]+', key) or not isinstance(target, dict) or \
                (target.get('width'), target.get('height'), target.get('source_bytes')) != (512,128,65536) or \
                not isinstance(target.get('xxh128'), str) or not re.fullmatch(r'[0-9a-f]{32}', target['xxh128']) or \
                target.get('lines') not in (1,2) or not isinstance(target.get('tokens'), list) or \
                any(token not in GLYPHS for token in target['tokens']):
            raise ValueError(f'{key}: invalid target profile; renderer review required')
    if not isinstance(catalog, dict) or set(catalog) != {'schema', 'locale', 'name', 'profile', 'entries'}:
        raise ValueError('Expected schema, locale, name, profile and entries')
    if catalog['schema'] != 1 or catalog['profile'] != target_table['profile']:
        raise ValueError('Unsupported schema or source profile')
    if not isinstance(catalog['locale'], str) or not re.fullmatch(
            r'[a-z]{2,3}(?:_[A-Z][a-z]{3})?_[A-Z]{2}', catalog['locale']):
        raise ValueError('Use a language[_Script]_REGION locale')
    if not isinstance(catalog['name'], str) or not catalog['name'].strip():
        raise ValueError('Missing display name')
    entries = catalog['entries']
    if not isinstance(entries, dict) or not set(entries).issubset(target_table['targets']):
        raise ValueError('Unknown text IDs; target identities are not translator-editable')
    for key, value in entries.items():
        if not isinstance(value, str):
            raise ValueError(f'{key}: text must be a string')
        if not value:  # Partial catalogs deliberately retain the original English texture.
            continue
        if not value.strip() or len(value) > 1024 or unicodedata.normalize('NFC', value) != value:
            raise ValueError(f'{key}: use nonempty, NFC-normalized text, at most 1024 characters')
        if any((ord(c) < 32 and c != '\n') or 0xD800 <= ord(c) <= 0xDFFF or
               0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069 for c in value):
            raise ValueError(f'{key}: unsupported control/bidi/surrogate character')
        fields = []
        for _, field, spec, conversion in Formatter().parse(value):
            if field is not None:
                if spec or conversion or field not in GLYPHS:
                    raise ValueError(f'{key}: unknown or formatted controller token')
                fields.append(field)
        target = target_table['targets'][key]
        if sorted(fields) != sorted(target['tokens']):
            raise ValueError(f'{key}: preserve controller tokens {target["tokens"]}')
        if value.count('\n') + 1 != target['lines']:
            raise ValueError(f'{key}: preserve {target["lines"]} layout lines')
    return entries


def default_font():
    for path in (ROOT/'translations/fonts/DejaVuSans.ttf',
                 ROOT/'gpu/third_party/fonts/DejaVuSans.ttf'):
        if path.is_file():
            return path
    raise ValueError('Supply --font with a licensed Unicode TrueType font')


def render(text, target, font_path):
    from PIL import Image, ImageDraw, ImageFont
    text = text.format(**GLYPHS)
    width, height = target['width'], target['height']
    image = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(image)
    lines = text.split('\n')
    for size in range(38 if len(lines) == 1 else 30, 15, -1):
        font = ImageFont.truetype(str(font_path), size)
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=1) for line in lines]
        step = size + 12
        if all(b[2]-b[0] <= width-8 for b in boxes) and step*len(lines) <= height-8:
            break
    else:
        raise ValueError('Translation does not fit; shorten the text instead of clipping it')
    tofu = bytes(font.getmask('\U0010ffff'))
    for char in set(text) - {' ', '\n'}:
        if bytes(font.getmask(char)) == tofu:
            raise ValueError(f'Font has no glyph for U+{ord(char):04X}')
    for row, (line, box) in enumerate(zip(lines, boxes)):
        # Top-left placement and original 512x128 canvas/line count are retained.
        draw.text((4-box[0], 4+row*step-box[1]), line, font=font,
                  fill=(255, 255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0, 255))
    return image


def encode_bc7(image):
    """Original BC7 mode-5 encoder for grayscale text + independent alpha.

    Four color and four alpha levels; no downloaded/proprietary compressor.
    Separate indices preserve black outlines, unlike an alpha-only encoder.
    """
    width, height = image.size
    if width % 4 or height % 4:
        raise ValueError('BC7 dimensions must be multiples of four')
    pixels = image.load()
    output = bytearray()
    weights = (0, 21, 43, 64)
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            block = [pixels[bx+x, by+y] for y in range(4) for x in range(4)]
            if any(r != g or r != b for r, g, b, _ in block):
                raise ValueError('Text encoder accepts grayscale artwork only')
            colors = [p[0] for p in block]
            alphas = [p[3] for p in block]
            c0, c1 = min(colors) >> 1, max(colors) >> 1
            a0, a1 = min(alphas), max(alphas)
            def indices(values, low, high):
                palette = [((64-w)*low + w*high + 32)//64 for w in weights]
                return [min(range(4), key=lambda i: abs(palette[i]-v)) for v in values]
            ci = indices(colors, (c0 << 1) | (c0 >> 6), (c1 << 1) | (c1 >> 6))
            ai = indices(alphas, a0, a1)
            if ci[0] >= 2:
                c0, c1 = c1, c0
                ci = [3-i for i in ci]
            if ai[0] >= 2:
                a0, a1 = a1, a0
                ai = [3-i for i in ai]
            bits, count = 32, 6  # mode 5: five zero bits followed by one.
            def put(value, length):
                nonlocal bits, count
                bits |= value << count
                count += length
            put(0, 2)  # no alpha/color rotation
            for _ in range(3):
                put(c0, 7)
                put(c1, 7)
            put(a0, 8)
            put(a1, 8)
            for index in (ci, ai):
                put(index[0], 1)  # anchor MSB is implicit zero
                for value in index[1:]:
                    put(value, 2)
            assert count == 128
            output.extend(bits.to_bytes(16, 'little'))
    return bytes(output)


def compile_pack(catalog, target_table, font_path, preview=None):
    entries = validate(catalog, target_table)
    records = {}
    for key, text in entries.items():
        if not text:
            continue
        target = target_table['targets'][key]
        identity = (target['width'], target['height'], target['source_bytes'], target['xxh128'])
        if identity in records:
            if records[identity][0] != text:
                raise ValueError(f'{key}: identical source textures must share the same translation')
            continue
        image = render(text, target, font_path)
        if preview:
            image.save(preview / (key + '.png'))
        records[identity] = text, encode_bc7(image)
    if not records:
        raise ValueError('No translated entries to compile; leave the pack selector off')
    output = io.BytesIO()
    output.write(MAGIC + struct.pack('<I', len(records)))
    for (width, height, source_bytes, digest), (_, pixels) in records.items():
        output.write(RECORD.pack(width, height, source_bytes,
                                 int(digest[:16], 16), int(digest[16:], 16), len(pixels)))
        output.write(pixels)
    return output.getvalue(), len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--targets', type=Path, default=ROOT/'translations/targets.json')
    parser.add_argument('--font', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--preview', type=Path, help='New private preview directory; never commit it')
    parser.add_argument('--check', action='store_true', help='Validate text only, no Pillow or writes')
    args = parser.parse_args()
    catalog, targets = read_json(args.catalog), read_json(args.targets)
    entries = validate(catalog, targets)
    print(f'Translation coverage: {sum(bool(v) for v in entries.values())}/{len(targets["targets"])} tutorial entries; story/menu text is NOT included')
    if args.check:
        return
    if not args.output:
        parser.error('--output is required unless --check is used')
    if args.output.exists():
        parser.error('Output exists: choose a new private filename (no overwrites)')
    if args.preview:
        args.preview.mkdir(parents=True, exist_ok=False)
    data, count = compile_pack(catalog, targets, args.font or default_font(), args.preview)
    # Exclusive creation: cannot overwrite an archive, another pack, or an active session file.
    with args.output.open('xb') as dest:
        dest.write(data)
    print(f'Created {count} unique host replacements: {args.output}')


if __name__ == '__main__':
    # Also preserve Serbian paths when redirected through a legacy Windows pipe.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    try:
        main()
    except (OSError, ValueError, KeyError, ImportError) as error:
        raise SystemExit(f'Translation: {error}') from error

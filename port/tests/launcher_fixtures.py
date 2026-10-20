"""Tiny synthetic metadata, not executable/game assets."""
from pathlib import Path
import struct


def make_game(root, title='CUSA03745', version='01.00'):
    root = Path(root)
    (root / 'sce_sys').mkdir(parents=True, exist_ok=True)
    fields = [('TITLE_ID', title), ('APP_VER', version), ('TITLE', 'Synthetic TLG fixture')]
    keys, values, entries = bytearray(), bytearray(), []
    for key, value in fields:
        encoded = value.encode() + b'\0'
        entries.append(struct.pack('<HHIII', len(keys), 0x204, len(encoded), len(encoded), len(values)))
        keys.extend(key.encode() + b'\0')
        values.extend(encoded)
    key_start = 20 + 16 * len(entries)
    header = struct.pack('<4sIIII', b'\0PSF', 0x101, key_start, key_start + len(keys), len(entries))
    (root / 'sce_sys' / 'param.sfo').write_bytes(header + b''.join(entries) + keys + values)
    (root / 'eboot.bin').write_bytes(b'Synthetic fixture, NOT executable code')
    (root / 'sce_module').mkdir(exist_ok=True)
    for name in ('libc.prx', 'libSceFios2.prx'):
        (root / 'sce_module' / name).write_bytes(b'fixture only')
    for name in ('trico_boot.psarc', 'trico_001.psarc', 'trico_002.psarc', 'trico_003.psarc'):
        (root / name).write_bytes(b'fixture only')
    return root

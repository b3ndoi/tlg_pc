# SPDX-License-Identifier: GPL-2.0-or-later
"""Validated bridge to the opt-in native trophy store (not the gameplay save).

1064 bytes: magic[8], LE version/user[2*u32], title[16], 128 LE Unix u64
timestamps (zero = locked), FNV-1a-64 of the preceding 1056 bytes. Atomic writers
share a per-user/title byte/file lock with runtime_trophies.c.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import struct
import tempfile

from game_library import TITLE_IDS

MAGIC = b'TLGTRO1\0'
SIZE = 1064


def checksum(data):
    value = 0xcbf29ce484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001b3) & 0xffffffffffffffff
    return value


def state_path(user_dir, title_id, user=1):
    if title_id not in TITLE_IDS or type(user) is not int or not 0 < user < 0x80000000:
        raise ValueError('Invalid native trophy identity')
    return Path(user_dir) / 'achievements' / f'user-{user}' / (title_id + '.bin')


def decode(data, title_id, user=1):
    expected = struct.pack('<8sII16s', MAGIC, 1, user, title_id.encode('ascii'))
    if (len(data) != SIZE or data[:32] != expected
            or struct.unpack_from('<Q', data, SIZE - 8)[0] != checksum(data[:-8])):
        raise ValueError('Invalid native trophy state; left unchanged')
    stamps = struct.unpack_from('<128Q', data, 32)
    if any(stamp > 253402300799 for stamp in stamps):
        raise ValueError('Invalid native trophy timestamp')
    return {str(i): {'unlocked_at': datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec='seconds'),
                    'source': 'game_trophy'} for i, stamp in enumerate(stamps) if stamp}


def read(user_dir, title_id, user=1):
    path = state_path(user_dir, title_id, user)
    try:
        with path.open('rb') as source:
            return decode(source.read(SIZE + 1), title_id, user)
    except FileNotFoundError:
        return {}


def seed(user_dir, title_id, records, user=1):
    """Explicit prelaunch migration of already observed unlocks; never guesses saves."""
    from achievements import locked
    path = state_path(user_dir, title_id, user)
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path.with_suffix('.lock')):
        merged = read(user_dir, title_id, user)
        for key, record in records.items():
            key = str(key)
            if not key.isdecimal() or not 0 <= int(key) < 128 or str(int(key)) != key:
                raise ValueError('Invalid migration trophy ID')
            if record.get('source') != 'game_trophy':
                raise ValueError('Only observed game trophies may be migrated')
            stamp = datetime.fromisoformat(record['unlocked_at'])
            if stamp.tzinfo is None or not 0 < int(stamp.timestamp()) <= 253402300799:
                raise ValueError('Invalid migration timestamp')
            if key not in merged or stamp < datetime.fromisoformat(merged[key]['unlocked_at']):
                merged[key] = record
        stamps = [0] * 128
        for key, record in merged.items():
            stamps[int(key)] = int(datetime.fromisoformat(record['unlocked_at']).timestamp())
        raw = struct.pack('<8sII16s128Q', MAGIC, 1, user, title_id.encode('ascii'), *stamps)
        raw += struct.pack('<Q', checksum(raw))
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.trophies-', delete=False) as out:
                temporary = Path(out.name)
                out.write(raw)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

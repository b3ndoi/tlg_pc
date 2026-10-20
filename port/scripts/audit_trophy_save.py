#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only evidence report on an explicitly supplied COPY of a TLG memory save.

Named progress counters are evidence of potentially recoverable gameplay data,
not proof that a trophy unlocked. No offset/threshold/timestamp is invented and
no progress file is written. Redirect stdout to keep a private local report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

MAX_SAVE = 2 * 1024 * 1024
CANDIDATES = frozenset(('numGameover', 'numCaptured', 'shownHints', 'soldierItemHit',
                        'soldierKillByBoy', 'soldierPulseKill', 'soldierRescueKill',
                        'condorTailRescueSuccess', 'condorCacheEatSuccess',
                        'condorStrokeStages', 'condorUsedPeepHole', 'condorEatenBarrels',
                        'condorTouched', 'treasures', 'onceEquipTreasures'))


def audit(path):
    with Path(path).open('rb') as source:
        data = source.read(MAX_SAVE + 1)
    if not data or len(data) > MAX_SAVE:
        raise ValueError('Save snapshot is empty or exceeds the audit limit')
    names = [(match.start(), match[0].decode('ascii'))
             for match in re.finditer(rb'[\x20-\x7e]{4,80}', data)]
    candidates = [{'name': name, 'name_offset': offset, 'value_decoded': False}
                  for offset, name in names if name in CANDIDATES]
    return {
        'schema': 1, 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
        'tl_g_memory_slot_size_matches': len(data) == 1024 * 1024,
        'named_perpetual_section_found': any(name == 'PerpetualData' for _, name in names),
        'candidate_progress_fields': candidates,
        'explicit_trophy_tokens': sorted({name for _, name in names
                                         if 'trophy' in name.lower() or 'achievement' in name.lower()}),
        'verified_trophy_unlocks_recovered': [],
        'import_performed': False,
        'conclusion': 'Progress field names are not a verified trophy flag mapping. '
                      'No automatic unlock or historical timestamp can be inferred safely.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('save_copy', type=Path, help='an offline copy, not the active save')
    args = parser.parse_args()
    print(json.dumps(audit(args.save_copy), indent=2))


if __name__ == '__main__':
    main()

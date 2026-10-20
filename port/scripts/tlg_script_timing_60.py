#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate exact-source EU 01.00 script edits, never modify game assets.

Only the guarded native 60 FPS loadbuffer hook consumes the generated table.
No archive overlay, save setting, global tick throttling or 30 FPS changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PREFIX = b'''-- TLG experimental EU 01.00: elapsed-time corrections, loader-gated to 60 FPS.
local function _tlg60_dt(dt)
    if dt == nil and type(GetGameDeltaTime) == "function" then dt = GetGameDeltaTime() end
    if type(dt) ~= "number" or dt ~= dt or dt <= 0 or dt == math.huge then return 0 end
    return dt
end
local function _tlg60_ticks(dt)
    local ticks = _tlg60_dt(dt) * 30
    local rounded = math.floor(ticks + 0.5)
    if math.abs(ticks - rounded) < 0.00001 then return rounded end
    return ticks
end
local function _tlg60_whole(ticks) return math.floor(ticks + 0.00001) end
local function _tlg60_due(previous, current, interval)
    return interval > 0 and _tlg60_whole(current / interval) > _tlg60_whole(previous / interval)
end
'''

SOURCES = {
    'game/scripts/ai2/condor/condorcommonsurface.lua': 'a4db140fa6ba6825dde2c2c4f8cfa5a3fab815f2458166193d0dc6555f791247',
    'game/scripts/ai2/condor/condorcommonactionbarrel.lua': 'a299e9e33a08285bb3827c0ec9c6978506cb3d43110529720a8261a5662c3c33',
    'game/scripts/ai2/actions/condor/movecost/movecostcondor.lua': 'abb5a2ffaeb4cb85e94de46d5444b9fa6fe502f08b3efd51a63e4745f1965a8b',
    'game/scripts/stages/s06_fallingbridge/missionscript.lua': 'e95c448f67bf45cbd5307f43b06a9ba473b6885e500e2205cca14395eb9b20be',
    'game/scripts/stages/s09_fallingbridge2/missionscript.lua': 'df28666fb834ce08c6f3a106f2a715d6e84fda5a9c8639e8a17084b34fbe3473',
    'game/scripts/stages/s13_firstflight/missionscript.lua': '158ed78c460a96df66052aba16ca2cb6a282df315a0a374d27c4fe5051fa192b',
    'game/scripts/stages/common/extension/statemachine/sm_callbacks_unique.lua': 'd3a49cafc2f90441619ae4b425b328a17545fedd3f1d14ef4b2f1c1f5d8905ab',
    'game/scripts/stages/common/extension/statemachine/sm_callbacks_sound.lua': '7fd16414ee27bec44ff58d732774613c20addae65ef69ba8d58c6bd93d09e6e4',
}


def code_only(source):
    # Offsets remain BYTES, including UTF-8 comments. Never patch commented code.
    tokens = re.compile(rb'--\[(=*)\[.*?\]\1\]|--[^\r\n]*|\[(=*)\[.*?\]\2\]|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', re.S)
    return tokens.sub(lambda m: re.sub(rb'[^\r\n]', b' ', m[0]), source)


def plan(name, source):
    if name not in SOURCES or hashlib.sha256(source).hexdigest() != SOURCES[name]:
        raise ValueError(f'Unsupported source (no edits): {name}')
    clean = code_only(source)
    edits = [(0, 0, PREFIX)]

    def replace(pattern, new, count=1):
        found = list(re.finditer(pattern, clean))
        if len(found) != count:
            raise ValueError(f'{name}: expected {count}, found {len(found)}: {pattern!r}')
        for m in found:
            value = new(m) if callable(new) else new
            edits.append((m.start(), m.end() - m.start(), value))

    if name.endswith('condorcommonsurface.lua'):
        replace(rb'work\.RelaxToSleepTimer = work\.RelaxToSleepTimer \+ 1',
                b'work.RelaxToSleepTimer = work.RelaxToSleepTimer + _tlg60_ticks(info.dt)')
        replace(rb'work\.RelaxToSleepTimer > PettingTime', b'_tlg60_whole(work.RelaxToSleepTimer) > PettingTime')
    elif name.endswith('condorcommonactionbarrel.lua'):
        replace(rb'work\.sitEatForce_JudgeFlameCnt = work\.sitEatForce_JudgeFlameCnt \+ 1',
                b'work.sitEatForce_JudgeFlameCnt = work.sitEatForce_JudgeFlameCnt + _tlg60_ticks(props.currentInfo.dt)')
        replace(rb'work\.sitEatForce_JudgeFlameCnt > waitFlame', b'_tlg60_whole(work.sitEatForce_JudgeFlameCnt) > waitFlame')
    elif name.endswith('movecostcondor.lua'):
        replace(rb'(?<!_)result\.nWaitFrames = result\.nWaitFrames \+ 1',
                b'result.nWaitFrames = result.nWaitFrames + _tlg60_ticks(_t.props.currentInfo.dt)')
        replace(rb'result\.nWaitFrames > 16', b'_tlg60_whole(result.nWaitFrames) > 16')
        replace(rb'self\.rayWaitingCnt = self\.rayWaitingCnt \+ 1',
                b'self.rayWaitingCnt = self.rayWaitingCnt + _tlg60_ticks(info.dt)')
        replace(rb'self\.rayWaitingCnt >= 6', b'_tlg60_whole(self.rayWaitingCnt) >= 6')
        # _JudgeVolume.nWaitFrames is a request-state index, NOT a timeout.
    elif '/s06_fallingbridge/' in name:
        replace(rb'state\.time_01 = state\.time_01 \+ 0\.0333333333',
                b'state.time_01 = state.time_01 + _tlg60_dt()')
    elif '/s09_fallingbridge2/' in name:
        for field, literal in [('reach_success_loop', '0.033333333333333333'),
                               ('reach_loop_R_Timer', '0.0333333'),
                               ('BoyIsRidingOnCondor_Timer', '0.03333'),
                               ('timer', '0.0333333'),
                               ('FB2_HNT_V_0060_timer', '0.0333333333')]:
            old = f'state.{field} = state.{field} + {literal}'.encode()
            replace(re.escape(old), f'state.{field} = state.{field} + _tlg60_dt()'.encode())
    elif '/s13_firstflight/' in name:
        for field in ['animWaitFrame', 'animDelayTime']:
            old = f'state.tbl_bridge[i].{field} = state.tbl_bridge[i].{field} - 1'.encode()
            replace(re.escape(old), f'state.tbl_bridge[i].{field} = state.tbl_bridge[i].{field} - _tlg60_ticks()'.encode())
    elif name.endswith('sm_callbacks_unique.lua'):
        replace(rb'local\s+changeAnglePerFrame\s*= script_param\.values\[3\]',
                b'local changeAnglePerFrame = script_param.values[3]\n\tif changeAnglePerFrame then changeAnglePerFrame = changeAnglePerFrame * _tlg60_ticks() end')
        replace(rb'state\.frameCounter =\s+state\.frameCounter \+ 1',
                b'local _tlg60_previous = state.frameCounter\n\tstate.frameCounter = state.frameCounter + _tlg60_ticks()', 2)
        replace(rb'state\.frameCounter\s*%\s*frameIntervalForVelocity\s*==\s*0',
                b'_tlg60_due(_tlg60_previous, state.frameCounter, frameIntervalForVelocity)', 10)
    elif name.endswith('sm_callbacks_sound.lua'):
        # Per-sample displacement and stationary duration both need normalization.
        replace(rb'local dis = obj\.position:Distance3\(state\.snd_params_elevator_01\.position_last\)',
                b'local _tlg60_step = _tlg60_ticks()\n\t\tif _tlg60_step <= 0 then return true end\n\t\tlocal dis = obj.position:Distance3(state.snd_params_elevator_01.position_last)')
        replace(rb'dis < 0\.001', b'dis < 0.001 * _tlg60_step')
        replace(rb'state\.snd_params_elevator_01\.frames = state\.snd_params_elevator_01\.frames \+ 1',
                b'state.snd_params_elevator_01.frames = state.snd_params_elevator_01.frames + _tlg60_step')
        replace(rb'state\.snd_params_elevator_01\.frames > 7', b'_tlg60_whole(state.snd_params_elevator_01.frames) > 7')
    else:
        raise AssertionError(name)
    edits.sort()
    end = 0
    for offset, length, _ in edits:
        assert offset >= end and offset + length <= len(source)
        end = offset + length
    return edits


def transform(name, source):
    out = bytearray()
    end = 0
    for offset, length, replacement in plan(name, source):
        out.extend(source[end:offset])
        out.extend(replacement)
        end = offset + length
    out.extend(source[end:])
    return bytes(out)


def generate(assets, header):
    lines = ['/* Generated by tlg_script_timing_60.py; exact-source guarded edits only. */']
    records = []
    for i, (name, sha) in enumerate(SOURCES.items()):
        source = (assets / name).read_bytes()
        edits = plan(name, source)
        lines.append(f'static const TlgScriptEdit tlg_script_edits_{i}[] = {{')
        for offset, length, value in edits:
            lines.append(f'    {{{offset}, {length}, {len(value)}, {json.dumps(value.decode("ascii"))}}},')
        lines.append('};')
        digest = ','.join('0x' + sha[n:n+2] for n in range(0,64,2))
        records.append(f'    {{{json.dumps(name)}, {len(source)}, {{{digest}}}, tlg_script_edits_{i}, {len(edits)}}},')
    lines.append('static const TlgScriptRecord tlg_script_records[] = {')
    lines.extend(records)
    lines.append('};\n')
    header.write_text('\n'.join(lines), encoding='ascii')
    print(f'Generated {header}: {len(records)} exact-source script records')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--header', required=True, type=Path)
    args = parser.parse_args()
    generate(args.assets, args.header)

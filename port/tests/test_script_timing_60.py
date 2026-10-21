#!/usr/bin/env python3
# Offline Lua 5.1 tests using the exact transformed source, no game process.
import argparse
from pathlib import Path
import re
import sys
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--assets', type=Path, required=True)
parser.add_argument('--expected', type=Path, required=True)
parser.add_argument('--lupa-path', type=Path, required=True)
parser.add_argument('--isa', type=Path)
ARGS = parser.parse_args() if __name__ == '__main__' else None
if ARGS:
    sys.path.insert(0, str(ARGS.lupa_path))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None
import tlg_script_timing_60 as patches

ORIGINAL = {name: (ARGS.assets/name).read_bytes() for name in patches.SOURCES} if ARGS else {}
CHANGED = {name: patches.transform(name, source) for name, source in ORIGINAL.items()}
for name, source in CHANGED.items():
    target = ARGS.expected/name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source)  # mechanical test fixture, not an installed asset


def source_for(suffix, changed=True):
    table = CHANGED if changed else ORIGINAL
    return next(data.decode('utf8') for name, data in table.items() if name.endswith(suffix))


def lua_vm():
    vm = LuaRuntime(unpack_returned_tuples=True)
    vm.execute('''_test_dt=0; function GetGameDeltaTime() return _test_dt end
        Ai2={Condor={Scripts={}},CommonScript={Condor={}},Utils={},Move={Condor={CalcMoveCost={}}}}
        MS={}; MSExt={SM_Callbacks={}}
    ''')
    return vm


def function_source(text, anchor):
    at = text.index(anchor)
    following = re.search(r'\n(?:function |MSExt\.SM_Callbacks\.)', text[at+len(anchor):])
    return text[at:at+len(anchor)+following.start()] if following else text[at:]


def finite_schedule(fps, seconds):
    return [1/fps] * round(fps*seconds)


@unittest.skipUnless(ARGS and LuaRuntime, 'optional offline EU assets and Lua 5.1 fixture required')
class ScriptTiming(unittest.TestCase):
    def test_01_source_guards_and_exact_edits(self):
        for name, source in ORIGINAL.items():
            self.assertRaises(ValueError, patches.plan, name, b'X'+source[1:])
            self.assertRaises(ValueError, patches.plan, name, source+b'\n')
            self.assertRaises(ValueError, patches.plan, name, CHANGED[name])
            edits=patches.plan(name, source)
            # Every change is either the helper prelude or one exact planned span.
            stripped=bytearray(CHANGED[name]); shift=0
            for offset, length, replacement in edits:
                self.assertEqual(stripped[offset+shift:offset+shift+len(replacement)], replacement)
                stripped[offset+shift:offset+shift+len(replacement)]=source[offset:offset+length]
                # undo immediately: subsequent offsets now match original again
            self.assertEqual(bytes(stripped), source)
        move=source_for('movecostcondor.lua')
        self.assertIn('_result.nWaitFrames = _result.nWaitFrames + 1',move) # state index, not elapsed time
        self.assertNotIn('_tlg60_', source_for('s13_firstflight/missionscript.lua',False))

    def test_01b_vegetation_cadence_only_changes_60fps_compiler_input(self):
        original_main=source_for('states/main.lua',False)
        changed_main=source_for('states/main.lua')
        self.assertIn('env.skinningSettings.skinWindMaxFrameSkip = 1',original_main)
        self.assertIn('env.skinningSettings.skinWindMaxFrameSkip = 2',changed_main)
        self.assertNotIn('env.skinningSettings.skinWindMaxFrameSkip = 1',changed_main)

        original_stage=source_for('s06_fallingbridge/missionscript.lua',False)
        changed_stage=source_for('s06_fallingbridge/missionscript.lua')
        self.assertEqual(original_stage.count('.grassType.skipFrame = 4'),4)
        self.assertEqual(changed_stage.count('.grassType.skipFrame = 8'),4)
        self.assertNotIn('.grassType.skipFrame = 4',changed_stage)
        # Preserve the separately-authored integration cadence/damping and a
        # misspelled inactive property instead of guessing at their semantics.
        for text in ['.grassType.slowFrame = 4', '.grassType.slowFrame = 2',
                     '.grassType.slipFrame = 4', '.grassType.animDamping = 0.98',
                     '.grassType.animDamping = 0.95']:
            self.assertEqual(changed_stage.count(text),original_stage.count(text),text)

    def test_02_all_nine_original_and_changed_scripts_compile_lua51(self):
        vm=lua_vm()
        compile_source=vm.eval('function(source) local f,e=loadstring(source); assert(f,e); return true end')
        for name in ORIGINAL:
            for data in [ORIGINAL[name],CHANGED[name]]:
                self.assertTrue(compile_source(data.decode('utf8')),name)

    def pet_time(self, changed, fps):
        vm=lua_vm()
        vm.execute('''sleepIssued=false
            function MS.CondorGetAiMode() return 'AIMODE_normal' end
            function MS.BoyCompareAnimationState_StringFind() return true end
            function MS.CondorCompareAnimationState() return false end
            function MS.CondorCompareAnimationState_StringFind() return false end
            function Ai2.CommonScript.Condor.CannotSitCondition() return false end
            function Ai2.Utils.AttachVolumeByAssetName() end
            function Ai2.Utils.DetachVolumeByAssetName() end
            function Ai2.Utils.GetVolumeByAssetName(props,name)
                return {isRunning=(name=='GridVolume_LieDown' and 1 or 0)} end
            function Ai2.Utils.IsHitVolume() return false end
            function Ai2.Utils.ReqCtrlCmd(ai,command)
                if command=='ControlCommand_C_lie_down_relax' then sleepIssued=true end end
            props={currentInfo={dt=0,work={RelaxToSleep=true,RelaxToSleepTimer=0,WakeUpPts=0},
                interestEntity={GetName=function() return 'Player' end}}}
        ''')
        code=function_source(source_for('condorcommonsurface.lua',changed),
                             'function Ai2.Condor.Scripts.PetTricoLong(props)')
        vm.execute(patches.PREFIX.decode()+code)
        tick=vm.eval('function(dt) props.currentInfo.dt=dt; Ai2.Condor.Scripts.PetTricoLong(props); return sleepIssued end')
        for i in range(fps*5):
            if tick(1/fps): return (i+1)/fps
        self.fail('sleep was never requested')

    def test_03_actual_pet_sleep_function_preserves_30fps_duration(self):
        baseline=self.pet_time(False,30)
        self.assertAlmostEqual(baseline,self.pet_time(True,30))
        self.assertLess(self.pet_time(False,60),baseline*0.6)
        for fps in [45,60,120]: self.assertLessEqual(abs(self.pet_time(True,fps)-baseline),1/30+1e-9)

    def space_time(self, changed, schedule):
        vm=lua_vm()
        vm.execute('''function CondorRequestSpaceCheck() return {key=1} end
            finished=false
            function CondorReceiveSpaceCheck() return {isFinish=(finished and 1 or 0),isHit=0} end
            t={props={currentInfo={dt=0},log={AddMessage=function() end}},ai2Ext={}}
            prm={srcDP={},dstDP={},result={nWaitFrames=0}}
        ''')
        code=function_source(source_for('movecostcondor.lua',changed),
                             'function Ai2.Move.Condor.CalcMoveCost._SpaceCheck( _t, report, prm )')
        vm.execute(patches.PREFIX.decode()+code)
        tick=vm.eval('function(dt) t.props.currentInfo.dt=dt; local ok=Ai2.Move.Condor.CalcMoveCost._SpaceCheck(t,nil,prm); return prm.result.isTimeout,ok end')
        elapsed=0
        # Pause cannot exhaust the timeout budget in corrected code.
        if changed:
            for _ in range(100): self.assertFalse(tick(0)[0])
        for dt in schedule:
            elapsed+=dt
            timeout,ok=tick(dt)
            self.assertFalse(ok)
            if timeout: return elapsed
        self.fail('timeout was never reached')

    def test_04_actual_async_spacecheck_preserves_budget_and_pause(self):
        baseline=self.space_time(False,[1/30]*60)
        self.assertAlmostEqual(baseline,17/30)
        for fps in [30,45,60,120]:
            self.assertLessEqual(abs(self.space_time(True,[1/fps]*fps)-baseline),1/fps+1e-8)
        self.assertLessEqual(abs(self.space_time(True,[1/45,1/60]*100)-baseline),1/30)

    def test_05_mission_seconds_and_bridge_countdown_fragments(self):
        vm=lua_vm()
        for field in ['reach_success_loop','reach_loop_R_Timer','BoyIsRidingOnCondor_Timer','timer','FB2_HNT_V_0060_timer']:
            code=source_for('s09_fallingbridge2/missionscript.lua')
            line=re.search(r'state\.'+field+r' = state\.'+field+r' \+ _tlg60_dt\(\)',code)[0]
            tick=vm.execute(patches.PREFIX.decode()+f'local state={{ {field}=0 }}; return function(dt) _test_dt=dt; {line}; return state.{field} end')
            for dt in finite_schedule(60,2): age=tick(dt)
            self.assertAlmostEqual(age,2,places=8)
            self.assertAlmostEqual(tick(0),age)
        for field,initial in [('animWaitFrame',6),('animDelayTime',15)]:
            code=source_for('s13_firstflight/missionscript.lua')
            line=re.search(r'state\.tbl_bridge\[i\]\.'+field+r' = state\.tbl_bridge\[i\]\.'+field+r' - _tlg60_ticks\(\)',code)[0]
            for fps in [30,60,120]:
                tick=vm.execute(patches.PREFIX.decode()+f'local i=1; local state={{tbl_bridge={{{{ {field}={initial} }}}}}}; return function(dt) _test_dt=dt; {line}; return state.tbl_bridge[i].{field} end')
                for i in range(fps):
                    if tick(1/fps)<=0: break
                self.assertAlmostEqual((i+1)/fps,initial/30)

    def test_06_actual_mirror_controller_elapsed_rate(self):
        for changed in [False,True]:
            results={}
            for fps in [30,60,120]:
                vm=lua_vm()
                vm.execute('''wire={data={twistAngleLimits={X=0,Y=0}}}
                    function MS.SearchObject() return wire end
                    state={}; parameters={values={_size=3,100,100,0.14}}
                ''')
                code=function_source(source_for('sm_callbacks_unique.lua',changed),
                    'MSExt.SM_Callbacks.railyajirobe_01_LT_rotControllerSM_rotationtMirrorForTarget = function(state, script_param)')
                # A tiny Vector setter stub turns the native vector-string assignment back into components.
                vm.execute('''local backing=wire.data; wire.data=setmetatable({}, {
                    __index=backing,__newindex=function(t,k,v)
                        if type(v)=='string' then local x,y=v:match('([^ ]+) ([^ ]+)'); backing[k]={X=tonumber(x),Y=tonumber(y)}
                        else backing[k]=v end end})''')
                vm.execute(patches.PREFIX.decode()+code)
                tick=vm.eval('function(dt) _test_dt=dt; MSExt.SM_Callbacks.railyajirobe_01_LT_rotControllerSM_rotationtMirrorForTarget(state,parameters); return wire.data.twistAngleLimits.X end')
                for _ in range(fps): result=tick(1/fps)
                results[fps]=result
                if changed: self.assertAlmostEqual(tick(0),result)
            self.assertAlmostEqual(results[30],4.2)
            if changed:
                for value in results.values(): self.assertAlmostEqual(value,4.2)
            else: self.assertAlmostEqual(results[60],8.4)

    def test_07_cadence_crossings_variable_dt_and_invalid_time(self):
        vm=lua_vm()
        factory=patches.PREFIX.decode()+'''return function(interval)
            local age=0
            return function(dt) local previous=age; age=age+_tlg60_ticks(dt)
                return _tlg60_due(previous,age,interval),age end
        end'''
        make=vm.execute(factory)
        for fps in [30,45,60,120]:
            tick=make(5); due=0
            for dt in finite_schedule(fps,2):
                issued,age=tick(dt); due+=bool(issued)
            self.assertEqual(due,12)
            self.assertAlmostEqual(age,60)
            for bad in [0,-1,float('nan'),float('inf')]:
                issued,after=tick(bad); self.assertFalse(issued); self.assertEqual(after,age)
        tick=make(5); due=0; elapsed=0
        for dt in [1/45,1/60,1/60,0.1]*100:
            issued,age=tick(dt); due+=bool(issued); elapsed+=dt
        self.assertEqual(due,int((elapsed*30+1e-5)//5))

    def test_08_retained_isa_redzone_does_not_overlap_hooks(self):
        if not ARGS.isa: self.skipTest('no retained ISA table supplied')
        import isa_rewrite as isa
        import red_zone as rz
        data=ARGS.isa.read_bytes()
        magic,size,sha,count,unsupported,rz_bytes=isa.HEADER.unpack_from(data)
        self.assertEqual(magic,b'G3ISA1\0\0')
        hooks=[(0x6d62b0,8),(0x6d87b4,5),(0xdd4dd0,8)]
        def check(offset,length):
            for hook,n in hooks: self.assertFalse(offset<hook+n and hook<offset+length,(hex(offset),hex(hook)))
        for i in range(count):
            fields=isa.RECORD.unpack_from(data,isa.HEADER.size+i*isa.RECORD.size)
            offset,length,kind,width,mode=fields[:5]
            check(offset,4+fields[-2] if mode==isa.MODE_JMP_RELOCATE else length)
        section=data[isa.HEADER.size+count*isa.RECORD.size:]
        self.assertEqual(len(section),rz_bytes)
        magic,code_offset,code_bytes,groups,group_bytes,version,crc=rz.SECTION.unpack_from(section)
        self.assertEqual(magic,rz.MAGIC)
        at=rz.SECTION.size+rz.STATS.size+code_bytes
        for i in range(groups):
            site,stub,length,protected,patches_count=rz.GROUP.unpack_from(section,at)
            at+=rz.GROUP.size
            for j in range(patches_count):
                offset,length=rz.PATCH.unpack_from(section,at)
                check(offset,length)
                at+=rz.PATCH.size+2*length
        self.assertEqual(at,len(section))
        print(f'PASS: no hook overlaps across {count} ISA sites / {groups} red-zone groups')

    def test_09_barrel_and_headcheck_timeout_fragments(self):
        # Execute the exact edited counter and predicate, not an invented rate formula.
        for suffix,field,threshold,dt_expr,after in [
            ('condorcommonactionbarrel.lua','work.sitEatForce_JudgeFlameCnt','waitFlame','props.currentInfo.dt',True),
            ('movecostcondor.lua','self.rayWaitingCnt','6','info.dt',False)]:
            times={}
            for changed,fps in [(False,30),(True,30),(True,60),(True,120)]:
                vm=lua_vm(); text=source_for(suffix,changed)
                increment=re.search(re.escape(field)+r' = '+re.escape(field)+r' \+ [^\r\n]+',text)[0]
                predicate=('_tlg60_whole('+field+')' if changed else field)+(' > ' if after else ' >= ')+threshold
                self.assertIn(predicate,text)
                setup='local work={sitEatForce_JudgeFlameCnt=0}; local props={currentInfo={dt=0}}; local waitFlame=10;' if after else 'local self={rayWaitingCnt=0}; local info={dt=0};'
                body=(increment+'; return '+predicate) if after else ('local hit='+predicate+'; '+increment+'; return hit')
                tick=vm.execute(patches.PREFIX.decode()+setup+f' return function(dt) {dt_expr}=dt; {body} end')
                for i in range(fps):
                    if tick(1/fps): break
                times[changed,fps]=(i+1)/fps
            for key,value in times.items(): self.assertLessEqual(abs(value-times[False,30]),1/30+1e-8)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]],verbosity=2)

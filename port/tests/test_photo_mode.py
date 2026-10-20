"""Offline Lua 5.1 engine double: no game process, archive writes or saves."""
import argparse
import os
from pathlib import Path
import sys
import unittest

parser=argparse.ArgumentParser()
parser.add_argument('--lupa-path')
parser.add_argument('--lua-required',action='store_true')
parser.add_argument('--bootstrap',type=Path)
args,remaining=parser.parse_known_args()
if args.lupa_path:
    sys.path.insert(0,args.lupa_path)
try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    if args.lua_required:
        raise SystemExit('Install the test-only dependency lupa==2.8 (Lua 5.1 backend)')
    LuaRuntime=None
PORT=Path(__file__).resolve().parents[1]
SOURCE=(PORT/'src/photo_mode.lua').read_text(encoding='utf-8')
MOCK='''
seq=1;want=0;ack='';paused=false;anime=false;inGame=true;cameraKey='game'
pauses=0;resumes=0;moves=0;elapsed=1/60;simulationSteps=0
GameFlag={Stage='stage-a',Scene='scene-a'}
function Vector(value)
    local t={X=value.X or 0,Y=value.Y or 0,Z=value.Z or 0}
    t.ToEuler=function(self) return Vector(self) end
    return t
end
function camera(name,x)
    return {name=name,position=Vector({X=x}),rotation=Vector({Y=10}),
        worldPosition=Vector({X=x}),fov=60,GetName=function(self) return self.name end}
end
game=camera('game_camera',12);photo=camera('_default_camera',100)
world={activeCamera=game};player={}
function FindObject(name)
    if name=='_world' then return world end
    if name=='_default_camera' then return photo end
    if name=='Player' then return player end
    if name=='CameraManager' then return manager end
end
function CamMngr_Command(command,key)
    if command=='IsPlayingAnime' then return anime end
    assert(command=='SetActiveCamera')
    cameraKey=key;world.activeCamera=key=='game' and game or photo
end
CameraManager={IsActiveCamera=function(self,key) return cameraKey==key end}
manager={}
ai={instruction={triggerIsDemo=false}}
Ai2={Utils={GetPlayerAI=function() return ai end}}
speed=1
function TricoGame_GetGameSpeed() return speed end
function TricoGame_IsInGame() return inGame end
function TricoGame_IsGamePause() return paused end
function luaCommand(command)
    if command=='trico pause' then paused=true;pauses=pauses+1
    elseif command=='trico resume' then paused=false;resumes=resumes+1
    else error('Unexpected command: '..command) end
end
function EntityMove(name,x,y,z,relative)
    assert(name=='_default_camera' and relative==1)
    moves=moves+1;photo.position.X=photo.position.X+x
    photo.position.Y=photo.position.Y+y;photo.position.Z=photo.position.Z+z
end
dx=0;dy=0;forward=0;right=0;up=0;zoom=0;fast=0
io={open=function(path,mode)
    if path=='/tlg-photo/control' then
        assert(mode=='r')
        return {read=function() return '1 '..seq..' '..want..' '..dx..' '..dy..' '..forward..' '..right..' '..up..' '..zoom..' '..fast end,
            close=function() end}
    end
    assert(path=='/tlg-photo/status' and mode=='w')
    return {write=function(self,text) ack=text end,close=function() end}
end}
function RegisterTick(f) tick=f end
function frame()
    if not paused then simulationSteps=simulationSteps+1 end
    tick(paused and 0 or elapsed,elapsed)
end
'''


@unittest.skipUnless(LuaRuntime,'optional Lua 5.1 fixture dependency not installed')
class PhotoLua(unittest.TestCase):
    def vm(self):
        vm=LuaRuntime(unpack_returned_tuples=True)
        vm.execute(MOCK);vm.execute(SOURCE)
        return vm

    def test_disabled_has_no_game_changes(self):
        vm=self.vm();vm.execute('for i=1,1000 do frame() end')
        self.assertTrue(vm.eval('world.activeCamera==game and not paused and moves==0 and pauses==0'))

    def test_freeze_camera_and_restore(self):
        vm=self.vm();vm.execute('want=1;frame();forward=1;dx=10;for i=1,600 do frame() end')
        self.assertTrue(vm.eval('paused and world.activeCamera==photo and moves>0 and simulationSteps==1'))
        self.assertTrue(vm.eval('game.position.X==12 and game.fov==60'))
        vm.execute('seq=2;want=0;frame()')
        self.assertTrue(vm.eval('not paused and world.activeCamera==game and pauses==1 and resumes==1'))
        self.assertTrue(vm.eval('photo.position.X==100 and photo.fov==60 and photo.rotation.Y==10'))

    def test_cutscene_menu_unknown_state_and_existing_pause_refused(self):
        for setup in ('anime=true','anime=nil','inGame=false','paused=true','player=nil',
                      "cameraKey='animation'","GameFlag.Stage=''",'CameraManager=nil','manager=nil',
                      'photo.fov=0/0','game.fov=1/0','ai=nil','ai.instruction.triggerIsDemo=true',
                      'ai.instruction.triggerIsDemo=nil','speed=0.15','speed=0/0'):
            with self.subTest(setup=setup):
                vm=self.vm();vm.execute(setup+';want=1;frame()')
                self.assertTrue(vm.eval('world.activeCamera==game and pauses==0 and resumes==0'))

    def test_cutscene_or_scene_change_forces_restore(self):
        for setup in ('anime=true',"GameFlag.Scene='new-scene'","GameFlag.Stage='new-stage'",'inGame=false',
                      'ai.instruction.triggerIsDemo=true'):
            vm=self.vm();vm.execute('want=1;frame();'+setup+';frame()')
            self.assertTrue(vm.eval('not paused and world.activeCamera==game and resumes==1'))

    def test_does_not_overwrite_cutscene_camera(self):
        vm=self.vm();vm.execute("want=1;frame();cut=camera('cutscene',5);world.activeCamera=cut;anime=true;frame()")
        self.assertTrue(vm.eval('world.activeCamera==cut and not paused and resumes==1'))

    def test_error_does_not_leave_owned_pause(self):
        vm=self.vm();vm.execute("want=1;frame();EntityMove=function() error('injected fault') end;frame()")
        self.assertTrue(vm.eval('not paused and resumes==1 and world.activeCamera==game'))

    def test_motion_is_unscaled_and_rate_independent(self):
        positions=[]
        for fps in (30,60,120):
            vm=self.vm();vm.execute(f'elapsed=1/{fps};want=1;frame();forward=1;for i=1,{fps} do frame() end')
            positions.append(vm.eval('photo.position.Z'))
        for value in positions:
            self.assertAlmostEqual(value,-3.0,places=8)

    def test_no_invalid_step_or_unbounded_fov(self):
        vm=self.vm();vm.execute('want=1;frame();before=moves;elapsed=0;frame();assert(moves==before);elapsed=100;zoom=1;for i=1,200 do frame() end')
        self.assertEqual(vm.eval('photo.fov'),100)

    def test_repeated_entry_exit_and_camera_restore_failure(self):
        vm=self.vm()
        vm.execute('for i=1,100 do seq=seq+1;want=1;frame();seq=seq+1;want=0;frame() end')
        self.assertTrue(vm.eval('pauses==100 and resumes==100 and not paused and world.activeCamera==game'))
        vm.execute("seq=seq+1;want=1;frame();FindObject=function(name) if name=='_world' then error('lost scene') end end;frame()")
        self.assertTrue(vm.eval('not paused and resumes==101'))

    @unittest.skipUnless(args.bootstrap,'optional owner-provided offline EU bootstrap')
    def test_original_bootstrap_with_appended_backend_compiles(self):
        import hashlib
        source=args.bootstrap.read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),
                         'b61524ce828141deb8e68cf22b9308c4f09e1dacabf6ae74069a9ba3869b3f7a')
        vm=LuaRuntime()
        compile_only=vm.eval('function(s) local f,e=loadstring(s); assert(f,e); return true end')
        self.assertTrue(compile_only(source+b'\n'+SOURCE.encode('utf-8')))


class DefaultGuards(unittest.TestCase):
    def test_launcher_opt_in_is_60fps_only(self):
        sys.path.insert(0,str(PORT/'launcher'))
        import tlg_run
        from unittest.mock import patch
        self.assertIs(tlg_run.DEFAULT_SETTINGS['photo_mode'],False)
        for mode in ('30','60','unlocked'):
            for enabled in (False,True):
                with patch.object(tlg_run,'applied_frame_rate',mode),patch.dict(os.environ,{'TLG_PHOTO_MODE':'1'}):
                    settings=dict(tlg_run.DEFAULT_SETTINGS,photo_mode=enabled)
                    env=tlg_run.build_env(settings)
                    self.assertEqual(env.get('TLG_PHOTO_MODE')=='1',os.name=='nt' and mode=='60' and enabled)

    def test_no_zero_speed_or_save_operations(self):
        for forbidden in ('SetGameSpeed','SaveCheckPoint','PostEvent'):
            self.assertNotIn(forbidden,SOURCE)


if __name__=='__main__':
    unittest.main(argv=[sys.argv[0],*remaining])

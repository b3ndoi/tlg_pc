-- SPDX-License-Identifier: GPL-2.0-or-later
-- Original port code. Appended only to the fingerprinted EU bootstrap in an
-- explicitly opted-in 60-FPS process. No game script/assets are redistributed.
do
    local owned, saved, sequence = false, nil, 0
    local function report(state)
        local f = io.open('/tlg-photo/status', 'w')
        if f then f:write('2 '..sequence..' '..state..'\n'); f:close() end
    end
    local function playing()
        -- Require an explicit false, not a missing command/property. Never
        -- cancel an animation camera or take over a non-gameplay camera.
        return CamMngr_Command('IsPlayingAnime') ~= false
    end
    local function eligible()
        local ai = Ai2 and Ai2.Utils and Ai2.Utils.GetPlayerAI and Ai2.Utils.GetPlayerAI()
        local demo = ai and ai.instruction and ai.instruction.triggerIsDemo
        return (demo == false or demo == 0) and TricoGame_IsInGame() == true and GameFlag and GameFlag.Stage and
            GameFlag.Stage ~= '' and FindObject('Player') ~= nil and
            FindObject('CameraManager') ~= nil and not playing()
    end
    local function valid_fov(value)
        return type(value) == 'number' and value == value and value > 0 and value < 180
    end
    local function restore()
        local old = saved
        saved = nil
        local ok, err = pcall(function()
        if old and FindObject('_world') and FindObject('_default_camera') == old.photo then
            -- Do not overwrite a camera installed by a cutscene/scene change.
            if FindObject('_world').activeCamera == old.photo or
                FindObject('_world').activeCamera == old.camera then
                CamMngr_Command('SetActiveCamera', 'game')
            end
            old.photo.position = old.position
            old.photo.rotation = old.rotation
            old.photo.fov = old.fov
            if old.mode ~= nil then old.photo.mode = old.mode end
        end
        end)
        -- Resume only a pause actually acquired here; never a pre-existing pause.
        if owned and TricoGame_IsGamePause() then luaCommand('trico resume') end
        owned = false
        if not ok then print('Photo mode: camera restore error: '..tostring(err)) end
    end
    local function enter()
        if not eligible() or TricoGame_IsGamePause() or
            CameraManager:IsActiveCamera('game') ~= true then return false end
        -- Scripted slow-motion catches/ramps are not ordinary gameplay, even if
        -- they temporarily retain the gameplay camera. Never interrupt them.
        local speed = TricoGame_GetGameSpeed and TricoGame_GetGameSpeed()
        if type(speed) ~= 'number' or speed ~= speed or math.abs(speed-1) > 0.0001 then return false end
        local world = FindObject('_world')
        local source, camera = world.activeCamera, FindObject('_default_camera')
        if not source or not camera or not valid_fov(camera.fov) or not valid_fov(source.fov) then return false end
        saved = {camera=source, photo=camera, position=Vector(camera.position),
            rotation=Vector(camera.rotation):ToEuler(), fov=camera.fov, mode=camera.mode,
            stage=GameFlag.Stage, scene=GameFlag.Scene}
        owned = true
        luaCommand('trico pause')
        if TricoGame_IsGamePause() ~= true then return false end
        -- The retail default camera can be in orbit/Maya mode. Its position then
        -- denotes an orbit pivot, not a freely movable eye. Restore this on exit.
        camera.mode = 'FPS'
        camera.position = Vector(source.worldPosition)
        camera.rotation = Vector(source.rotation):ToEuler()
        camera.fov = source.fov
        -- Only the active-camera reference changes. The gameplay camera and
        -- character transforms, game speed, clocks, saves and AI are untouched.
        CamMngr_Command('SetActiveCamera', 'default')
        return world.activeCamera == camera
    end
    local function tick(dt, edt)
        local f = io.open('/tlg-photo/control', 'r')
        if not f then if saved or owned then restore() end; return end
        local line = f:read('*a'); f:close()
        local values = {}
        for v in line:gmatch('%S+') do values[#values+1] = tonumber(v) end
        if #values ~= 11 or values[1] ~= 2 then restore(); report(2); return end
        sequence = values[2]
        if values[3] ~= 1 then restore(); report(0); return end
        if not saved then
            if not enter() then restore(); report(2); return end
        end
        if not eligible() or GameFlag.Stage ~= saved.stage or GameFlag.Scene ~= saved.scene or
            not TricoGame_IsGamePause() or FindObject('_world').activeCamera ~= saved.photo then
            restore(); report(2); return
        end
        -- Retail may omit/zero the editor timestep while paused. The host passes
        -- unscaled render time for camera-only movement; simulation stays paused.
        local step = values[11]
        if type(step) ~= 'number' or step ~= step or step <= 0 then step = edt end
        if type(step) ~= 'number' or step ~= step or step <= 0 then step = 0 end
        step = math.min(step, 0.05)
        local speed = values[10] == 1 and 12 or 3
        local camera = saved.photo
        local rotation = Vector(camera.rotation):ToEuler()
        rotation.X = math.max(-89, math.min(89, rotation.X + values[5]*0.12))
        rotation.Y = rotation.Y + values[4]*0.12
        camera.rotation = rotation
        if step > 0 then
            EntityMove(camera:GetName(), values[7]*speed*step, values[8]*speed*step,
                       -values[6]*speed*step, 1)
        end
        camera.fov = math.max(15, math.min(100, camera.fov + values[9]*30*step))
        report(1)
    end
    if io and io.open and RegisterTick and FindObject and Vector and EntityMove and
        CamMngr_Command and TricoGame_IsInGame and TricoGame_IsGamePause and luaCommand then
        RegisterTick(function(dt, edt)
            local ok, err = pcall(tick, dt, edt)
            if not ok then
                local restored = pcall(restore)
                if restored and not owned then report(2) end
                print('Photo mode: backend error; restore='..tostring(restored)..': '..tostring(err))
            end
        end)
    else
        print('Photo mode: engine services unavailable; disabled')
    end
end

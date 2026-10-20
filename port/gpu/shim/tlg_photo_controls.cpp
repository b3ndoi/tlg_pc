// SPDX-License-Identifier: GPL-2.0-or-later
#include "tlg_photo_controls.h"
#include "../../src/runtime_photo.h"
#include "tlg_overlay.h"
#include <SDL3/SDL.h>
#include <algorithm>
#include <cmath>
#include <cstdlib>

namespace TlgPhoto {
namespace { SDL_JoystickID pad_id{}; bool left_click{},right_click{},chord{}; }
bool HandleEvent(const SDL_Event& e,bool other_ui) {
    if (!runtime_photo_enabled()) return false;
    const bool active=runtime_photo_active();
    if (e.type==SDL_EVENT_WINDOW_FOCUS_LOST || e.type==SDL_EVENT_WINDOW_MINIMIZED ||
        e.type==SDL_EVENT_QUIT || e.type==SDL_EVENT_WINDOW_CLOSE_REQUESTED) {
        runtime_photo_cancel(); return false;
    }
    if (e.type==SDL_EVENT_KEY_DOWN && !e.key.repeat) {
        if (e.key.key==SDLK_F8 && (!other_ui || active)) {
            runtime_photo_toggle();
            if (!active) TlgOverlay::Notice("Photo mode requested (gameplay only). F8/Esc exits; F9 saves 1440p PNG.",4);
            return true;
        }
        if (active && (e.key.key==SDLK_ESCAPE || e.key.key==SDLK_INSERT)) {
            runtime_photo_cancel(); return true;
        }
        if (active && e.key.key==SDLK_F9) { runtime_photo_capture(); return true; }
    }
    if (e.type==SDL_EVENT_GAMEPAD_BUTTON_DOWN || e.type==SDL_EVENT_GAMEPAD_BUTTON_UP) {
        pad_id=e.gbutton.which;
        bool down=e.type==SDL_EVENT_GAMEPAD_BUTTON_DOWN;
        if (e.gbutton.button==SDL_GAMEPAD_BUTTON_LEFT_STICK) left_click=down;
        if (e.gbutton.button==SDL_GAMEPAD_BUTTON_RIGHT_STICK) right_click=down;
        bool both=left_click && right_click;
        if (both && !chord && (!other_ui || active)) runtime_photo_toggle();
        chord=both;
        if (active && down && e.gbutton.button==SDL_GAMEPAD_BUTTON_EAST) runtime_photo_cancel();
        if (active && down && e.gbutton.button==SDL_GAMEPAD_BUTTON_NORTH) runtime_photo_capture();
    }
    if (e.type==SDL_EVENT_GAMEPAD_AXIS_MOTION) pad_id=e.gaxis.which;
    if (active && e.type==SDL_EVENT_MOUSE_MOTION) runtime_photo_motion(e.motion.xrel,e.motion.yrel);
    return active && (e.type==SDL_EVENT_KEY_DOWN || e.type==SDL_EVENT_KEY_UP ||
        e.type==SDL_EVENT_MOUSE_MOTION || e.type==SDL_EVENT_MOUSE_BUTTON_DOWN ||
        e.type==SDL_EVENT_MOUSE_BUTTON_UP || e.type==SDL_EVENT_MOUSE_WHEEL ||
        e.type==SDL_EVENT_GAMEPAD_BUTTON_DOWN || e.type==SDL_EVENT_GAMEPAD_BUTTON_UP ||
        e.type==SDL_EVENT_GAMEPAD_AXIS_MOTION);
}
void Poll() {
    if (!runtime_photo_enabled()) return;
    static uint64_t previous=0;
    const uint64_t now=SDL_GetTicksNS();
    const float step=previous ? std::min(float(now-previous)/1e9f,0.05f) : 0;
    previous=now;
    if (!runtime_photo_active()) {
        // A held photo movement key/stick must not become a gameplay movement
        // on resume (e.g. walking the boy off a ledge). Clear only at neutral.
        if (!runtime_photo_captures_input()) return;
        int count=0; const bool* keys=SDL_GetKeyboardState(&count);
        for (int i=0;i<count;++i) if (keys[i]) return;
        if (SDL_GetMouseState(nullptr,nullptr)) return;
        if (SDL_Gamepad* pad=SDL_GetGamepadFromID(pad_id)) {
            for (int b=0;b<SDL_GAMEPAD_BUTTON_COUNT;++b)
                if (SDL_GetGamepadButton(pad,SDL_GamepadButton(b))) return;
            const char* setting=std::getenv("TLG_STICK_DEADZONE");
            const double zone=std::clamp(setting ? std::atof(setting) : 0.10,0.0,0.5);
            const int neutral=std::isfinite(zone) ? int(zone*32767) : 0;
            for (int a=0;a<SDL_GAMEPAD_AXIS_COUNT;++a) {
                const int value=SDL_GetGamepadAxis(pad,SDL_GamepadAxis(a));
                if (a>=SDL_GAMEPAD_AXIS_LEFT_TRIGGER ? value>127 : std::abs(value)>neutral) return;
            }
        }
        runtime_photo_release_inputs();
        return;
    }
    const bool* keys=SDL_GetKeyboardState(nullptr);
    float f=float(keys[SDL_SCANCODE_W])-float(keys[SDL_SCANCODE_S]);
    float r=float(keys[SDL_SCANCODE_D])-float(keys[SDL_SCANCODE_A]);
    float u=float(keys[SDL_SCANCODE_E])-float(keys[SDL_SCANCODE_Q]);
    float z=float(keys[SDL_SCANCODE_X])-float(keys[SDL_SCANCODE_Z]);
    int fast=keys[SDL_SCANCODE_LSHIFT] || keys[SDL_SCANCODE_RSHIFT];
    if (SDL_Gamepad* pad=SDL_GetGamepadFromID(pad_id)) {
        auto axis=[&](SDL_GamepadAxis a) {
            float v=float(SDL_GetGamepadAxis(pad,a))/32767.0f;
            return std::abs(v)<0.15f ? 0.0f : v;
        };
        f-=axis(SDL_GAMEPAD_AXIS_LEFTY); r+=axis(SDL_GAMEPAD_AXIS_LEFTX);
        u+=float(SDL_GetGamepadButton(pad,SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER))-
           float(SDL_GetGamepadButton(pad,SDL_GAMEPAD_BUTTON_LEFT_SHOULDER));
        runtime_photo_motion(axis(SDL_GAMEPAD_AXIS_RIGHTX)*750*step,axis(SDL_GAMEPAD_AXIS_RIGHTY)*750*step);
        fast|=SDL_GetGamepadAxis(pad,SDL_GAMEPAD_AXIS_RIGHT_TRIGGER)>16000;
    }
    runtime_photo_axes(f,r,u,z,fast);
}
}

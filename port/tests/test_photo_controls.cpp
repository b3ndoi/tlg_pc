// SPDX-License-Identifier: GPL-2.0-or-later
// CPU-only SDL event fixture: no SDL initialization, windows, devices or game.
#include <SDL3/SDL.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include "tlg_photo_controls.h"
#include "runtime_photo.h"

static bool menu;
namespace TlgOverlay {
bool CapturesOtherInput() { return menu; }
void Notice(const std::string&,float) {}
}
static bool key(SDL_Keycode value) {
    SDL_Event e{}; e.type=SDL_EVENT_KEY_DOWN; e.key.key=value;
    return TlgPhoto::HandleEvent(e,menu);
}
static bool button(Uint8 value,bool down) {
    SDL_Event e{}; e.type=down ? SDL_EVENT_GAMEPAD_BUTTON_DOWN : SDL_EVENT_GAMEPAD_BUTTON_UP;
    e.gbutton.which=1;e.gbutton.button=value;
    return TlgPhoto::HandleEvent(e,menu);
}
static void acknowledge(int state) {
    char request[256],reply[64]; unsigned seq;
    runtime_photo_control(request,sizeof(request));assert(sscanf(request,"2 %u",&seq)==1);
    int n=snprintf(reply,sizeof(reply),"2 %u %d\n",seq,state);
    runtime_photo_status(reply,(size_t)n);
}
int main() {
    assert(!key(SDLK_F8) && !runtime_photo_captures_input());
    runtime_photo_enable(1); menu=true;
    assert(!key(SDLK_F8) && !runtime_photo_captures_input());
    menu=false; assert(key(SDLK_F8));
    assert(!runtime_photo_active() && runtime_photo_captures_input());
    assert(key(SDLK_ESCAPE)); /* pending request can be cancelled too */
    acknowledge(0);runtime_photo_release_inputs();
    assert(!runtime_photo_captures_input());
    button(SDL_GAMEPAD_BUTTON_LEFT_STICK,true);
    button(SDL_GAMEPAD_BUTTON_RIGHT_STICK,true);
    assert(!runtime_photo_active() && runtime_photo_captures_input());
    acknowledge(1);assert(runtime_photo_active());
    button(SDL_GAMEPAD_BUTTON_LEFT_STICK,false);
    button(SDL_GAMEPAD_BUTTON_RIGHT_STICK,false);
    SDL_Event motion{};motion.type=SDL_EVENT_MOUSE_MOTION;motion.motion.xrel=12;
    assert(TlgPhoto::HandleEvent(motion,false));
    char request[256];runtime_photo_control(request,sizeof(request));
    assert(strstr(request,"12.000000"));
    assert(key(SDLK_F9) && runtime_photo_take_capture());
    menu=true;TlgPhoto::Poll(); /* opening a real dialog cancels even without a key */
    acknowledge(0);assert(!runtime_photo_active());
    runtime_photo_release_inputs();menu=false;
    assert(key(SDLK_F8));acknowledge(1);
    SDL_Event lost{};lost.type=SDL_EVENT_WINDOW_FOCUS_LOST;
    TlgPhoto::HandleEvent(lost,false);acknowledge(0);
    assert(!runtime_photo_active() && runtime_photo_captures_input());
    runtime_photo_release_inputs();runtime_photo_enable(0);
    assert(!key(SDLK_F8) && !runtime_photo_captures_input());
    puts("PASS: SDL pending chord capture, Escape, mouse look, capture, dialog/focus cancellation and opt-out");
}

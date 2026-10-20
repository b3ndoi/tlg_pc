// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
union SDL_Event;
namespace TlgPhoto {
bool HandleEvent(const SDL_Event& event, bool other_ui);
void Poll();
}

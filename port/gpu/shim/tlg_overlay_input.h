// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <string>

// Input/notice interface: usable by CPU-only SDL handlers without Vulkan headers.
namespace TlgOverlay {
void Notice(const std::string& text, float seconds);
bool CapturesInput();
bool CapturesOtherInput();
}

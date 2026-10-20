// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <filesystem>
#include <span>
#include <cstdint>
namespace TlgPhoto {
// Exact native 1440p RGBA8 only. Exclusive creation; no overwrite, no game assets.
bool WritePng(const std::filesystem::path& path,std::span<const uint8_t> rgba);
}

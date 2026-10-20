// SPDX-License-Identifier: GPL-2.0-or-later
// Optional immutable host-only text artwork. No guest, script or timing writes.
#pragma once
#include <cstdint>
#include <span>
#include <vector>

namespace TlgTranslations {
// Load once before texture uploads. Malformed/oversized packs fail closed.
bool Load(const char *utf8_path);
bool LoadEnvironment(); // Windows reads the wide environment, never a legacy
                        // code page.
bool Parse(std::span<const uint8_t> bytes); // CPU-only fixture entry point
bool Active();
const std::vector<uint8_t> *Replacement(uint32_t width, uint32_t height,
                                        std::span<const uint8_t> original);
} // namespace TlgTranslations

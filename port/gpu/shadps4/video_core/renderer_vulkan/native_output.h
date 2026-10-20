// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <cstdint>
#include <cmath>
#include <string_view>

namespace Vulkan::NativeOutput {
// The private launcher verifies the exact EU mode-table patch before setting
// this flag. This is a full engine resolution, NOT the older host-proxy path.
constexpr bool EngineNative(std::string_view requested, bool compatibility,
                            bool host_native_output, bool upscaler_disabled) {
    return requested == "2560x1440" && !compatibility && !host_native_output && upscaler_disabled;
}
// Explicit experimental 1440p path only. Do not change ordinary 1080p, the
// guest-resolution compatibility patch, or temporal reconstruction sessions.
constexpr bool Enabled(bool requested, bool compatibility, bool temporal,
                       uint32_t width, uint32_t height) {
    return requested && !compatibility && !temporal && width == 2560 && height == 1440;
}

// TLG's Scaleform shader IDs differ from the older game's UI whitelist. Scale
// eligible menu/HUD attachments as well as scene attachments; the registered
// VideoOut buffer instead gets its own output-size host replacement.
constexpr bool RasterPass(bool scene_started, bool native_output, bool display_buffer) {
    return !display_buffer && (scene_started || native_output);
}

constexpr std::array<uint32_t, 2> DisplaySize(bool native_output,
                                            uint32_t output_width, uint32_t output_height,
                                            uint32_t ui_width, uint32_t ui_height) {
    return native_output ? std::array{output_width, output_height}
                         : std::array{ui_width, ui_height};
}

// Fragment shaders retain guest-sized textures/constants even when the final
// viewport is enlarged. Use the same coordinate conversion as scene proxies;
// zero preserves all non-native-output behavior. The factor, not the target's
// dimensions alone, also handles half-size guest viewports correctly.
inline uint32_t FragmentCoordinates(bool native_output, std::array<float, 2> scale) {
    if (!native_output) return 0;
    const auto width = uint32_t(std::lround(1920.f * scale[0]));
    const auto height = uint32_t(std::lround(1080.f * scale[1]));
    return width | (height << 16);
}
} // namespace Vulkan::NativeOutput

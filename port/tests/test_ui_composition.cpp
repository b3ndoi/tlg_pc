// SPDX-License-Identifier: GPL-2.0-or-later
#include <cassert>
#include <cstdio>
#include "gpu/shadps4/video_core/renderer_vulkan/ui_composition.h"
#include "gpu/shadps4/video_core/renderer_vulkan/native_output.h"

int main() {
    using namespace Vulkan::UiComposition;
    // Title/loading menus have no depth/camera. UI must still go to the native target.
    assert(Choose(true, true, false, true) == Background::Copy);
    assert(Choose(true, true, false, false) == Background::Copy);
    // In-game HUD: first reconstruct the scene, then draw the native UI over it.
    assert(Choose(true, true, true, true) == Background::Temporal);
    // Runtime FSR disable/failure must not change UI resolution.
    assert(Choose(true, true, true, false) == Background::Copy);
    assert(Choose(true, false, true, true) == Background::None);
    assert(Choose(false, true, true, true) == Background::None);
    assert(NativeViewport(1920, -1080));
    assert(!NativeViewport(960, -540));
    assert(MovieShader(0x34e8a281) && MovieShader(0x24042a9b));
    assert(!MovieShader(0x0b0acf50)); // fullscreen post/tonemap also has a native viewport
    assert(!MovieShader(0x6c62a79f)); // shadow geometry
    const auto display = Scale(960, 540, 1920, 1080, false);
    assert(display[0] == 2 && display[1] == 2);
    const auto ui = Scale(960, 540, 1920, 1080, true);
    assert(ui[0] == 1 && ui[1] == 1); // don't double an already native UI viewport
    const auto larger = Scale(960, 540, 3840, 2160, true);
    assert(larger[0] == 2 && larger[1] == 2);
    const auto native1440 = Scale(1920, 1080, 2560, 1440, true);
    assert(std::abs(native1440[0] - 4.f/3.f) < 1e-6f);
    assert(std::abs(native1440[1] - 4.f/3.f) < 1e-6f);
    using namespace Vulkan::NativeOutput;
    assert((EngineSize("1280x720") == std::array<uint32_t,2>{1280,720}));
    assert((EngineSize("2560x1440") == std::array<uint32_t,2>{2560,1440}));
    assert((EngineSize("3840x2160") == std::array<uint32_t,2>{3840,2160}));
    assert((EngineSize("1920x1080") == std::array<uint32_t,2>{0,0}));
    assert(EngineNative("1280x720", false, false, true));
    assert(EngineNative("2560x1440", false, false, true));
    assert(EngineNative("3840x2160", false, false, true));
    assert(!EngineNative("1920x1080", false, false, true));
    assert(!EngineNative("", false, false, true));
    assert(!EngineNative("2560x1440", true, false, true));
    assert(!EngineNative("2560x1440", false, true, true));
    assert(!EngineNative("2560x1440", false, false, false));
    assert(Enabled(true, false, false, 2560, 1440));
    assert(!Enabled(false, false, false, 2560, 1440));
    assert(!Enabled(true, true, false, 2560, 1440));
    assert(!Enabled(true, false, true, 2560, 1440));
    assert(!Enabled(true, false, false, 1920, 1080));
    assert(!Enabled(true, false, false, 3840, 2160));
    assert(RasterPass(false, true, false)); // menu, no G-buffer/depth/camera
    assert(RasterPass(true, true, false));  // scene/HUD, arbitrary shader IDs
    assert(!RasterPass(true, true, true));  // final display is NOT a scene proxy
    assert(!RasterPass(false, false, false));
    assert(RasterPass(true, false, false)); // original scene-only behavior
    assert((DisplaySize(true,2560,1440,0,0) == std::array<uint32_t,2>{2560,1440}));
    assert((DisplaySize(false,2560,1440,1920,1080) == std::array<uint32_t,2>{1920,1080}));
    assert(FragmentCoordinates(false, native1440) == 0);
    const auto coordinates = FragmentCoordinates(true, native1440);
    assert((coordinates & 65535u) == 2560 && (coordinates >> 16) == 1440);
    // The right/bottom display pixels must address the logical guest frame,
    // not the out-of-range 2559/1439 coordinates used by the broken path.
    assert((2559.5f * 1920.f / float(coordinates & 65535u)) < 1920.f);
    assert((1439.5f * 1080.f / float(coordinates >> 16)) < 1080.f);
    assert(FragmentCoordinates(true, {1.f, 1.f}) == (1920u | (1080u << 16)));
    std::puts("UI composition: PASS (menu without camera, HUD, FSR off, viewport scaling)");
}

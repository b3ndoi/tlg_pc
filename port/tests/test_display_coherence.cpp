// SPDX-License-Identifier: GPL-2.0-or-later
#include <cassert>
#include <cstdio>
#include "gpu/shadps4/video_core/renderer_vulkan/display_surface.h"

int main() {
    using Vulkan::DisplaySurfaceState;
    DisplaySurfaceState state;
    assert(!state.Initialized());
    const auto initialize = state.Initialize({});
    assert(initialize.oldLayout == vk::ImageLayout::eUndefined);
    assert(initialize.newLayout == vk::ImageLayout::eTransferDstOptimal);
    assert(state.Initialized());
    assert(DisplaySurfaceState::Write({}, true).oldLayout == vk::ImageLayout::eTransferDstOptimal);
    for (unsigned frame = 0; frame < 120; ++frame) {
        for (unsigned partial_draw = 0; partial_draw < 8; ++partial_draw) {
            const auto write = DisplaySurfaceState::Write({}, false);
            assert(write.oldLayout == vk::ImageLayout::eGeneral);
            assert(write.newLayout == vk::ImageLayout::eGeneral);
            assert(bool(write.srcAccessMask & vk::AccessFlagBits2::eMemoryWrite));
            assert(bool(write.dstAccessMask & vk::AccessFlagBits2::eColorAttachmentRead));
            assert(bool(write.dstAccessMask & vk::AccessFlagBits2::eColorAttachmentWrite));
        }
        const auto read = DisplaySurfaceState::Read({});
        const auto returned = DisplaySurfaceState::AfterRead({});
        assert(read.oldLayout == vk::ImageLayout::eGeneral);
        assert(read.newLayout == returned.oldLayout);
        assert(returned.newLayout == vk::ImageLayout::eGeneral);
        assert(state.Initialized());
    }
    state.Reset(); // recreation/format/size change, not a new draw/frame
    assert(!state.Initialized());
    assert(state.Initialize({}).oldLayout == vk::ImageLayout::eUndefined);
    std::puts("Display coherence: PASS (960 retained partial draws, 120 read/restore cycles, recreation)");
}

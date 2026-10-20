// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <vulkan/vulkan.hpp>

namespace Vulkan {
// The host replacement survives many guest draws and presentation reads. Only
// a newly allocated image may discard its contents; LOAD/blending must retain
// earlier draws. Between calls (including after presentation) it is GENERAL.
class DisplaySurfaceState {
public:
    bool Initialized() const { return initialized; }
    void Reset() { initialized = false; }

    vk::ImageMemoryBarrier2 Initialize(vk::Image image) {
        initialized = true;
        return Barrier(image, vk::ImageLayout::eUndefined, vk::ImageLayout::eTransferDstOptimal,
                       vk::PipelineStageFlagBits2::eTopOfPipe, {},
                       vk::PipelineStageFlagBits2::eTransfer, vk::AccessFlagBits2::eTransferWrite);
    }
    static vk::ImageMemoryBarrier2 Write(vk::Image image, bool just_initialized) {
        return Barrier(image,
                       just_initialized ? vk::ImageLayout::eTransferDstOptimal : vk::ImageLayout::eGeneral,
                       vk::ImageLayout::eGeneral, vk::PipelineStageFlagBits2::eAllCommands,
                       vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite,
                       vk::PipelineStageFlagBits2::eColorAttachmentOutput,
                       vk::AccessFlagBits2::eColorAttachmentRead | vk::AccessFlagBits2::eColorAttachmentWrite);
    }
    static vk::ImageMemoryBarrier2 Read(vk::Image image) {
        return Barrier(image, vk::ImageLayout::eGeneral, vk::ImageLayout::eShaderReadOnlyOptimal,
                       vk::PipelineStageFlagBits2::eAllCommands,
                       vk::AccessFlagBits2::eMemoryWrite,
                       vk::PipelineStageFlagBits2::eAllCommands, vk::AccessFlagBits2::eShaderRead);
    }
    static vk::ImageMemoryBarrier2 AfterRead(vk::Image image) {
        return Barrier(image, vk::ImageLayout::eShaderReadOnlyOptimal, vk::ImageLayout::eGeneral,
                       vk::PipelineStageFlagBits2::eAllCommands, vk::AccessFlagBits2::eShaderRead,
                       vk::PipelineStageFlagBits2::eAllCommands,
                       vk::AccessFlagBits2::eMemoryRead | vk::AccessFlagBits2::eMemoryWrite);
    }
private:
    static vk::ImageMemoryBarrier2 Barrier(vk::Image image, vk::ImageLayout before,
                                          vk::ImageLayout after, vk::PipelineStageFlags2 src_stage,
                                          vk::AccessFlags2 src_access, vk::PipelineStageFlags2 dst_stage,
                                          vk::AccessFlags2 dst_access) {
        return {.srcStageMask = src_stage, .srcAccessMask = src_access,
                .dstStageMask = dst_stage, .dstAccessMask = dst_access,
                .oldLayout = before, .newLayout = after, .image = image,
                .subresourceRange = {vk::ImageAspectFlagBits::eColor, 0, 1, 0, 1}};
    }
    bool initialized = false;
};
} // namespace Vulkan

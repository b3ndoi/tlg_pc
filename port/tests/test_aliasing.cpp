// SPDX-License-Identifier: GPL-2.0-or-later
// Copy extents between images that share guest memory (texture_cache/aliasing.h); adapted from
// cuesta4/shadPS4 (eltutz) tests/test_aliasing.cpp. No game, Vulkan device or window required.
#include <algorithm>
#include <cassert>
#include <cstdio>

#include "video_core/amdgpu/resource.h"
#include "video_core/texture_cache/aliasing.h"
#include "video_core/texture_cache/image_info.h"

using namespace VideoCore;

static ImageInfo Make(Extent3D size, vk::Format format = vk::Format::eR8G8B8A8Unorm) {
    ImageInfo info{};
    info.guest_address = 0x100000;
    info.num_bits = 32;
    info.pixel_format = format;
    info.type = AmdGpu::ImageType::Color2D;
    info.pitch = size.width;
    info.size = size;
    return info;
}

int main() {
    // Same format: the smaller image is fully covered by the larger one.
    {
        const ImageInfo src = Make({1920, 1088, 1}), dst = Make({1920, 1080, 1});
        assert(GetAliasCopyExtent(src, dst) == dst.size);
        assert(GetAliasCopyExtent(dst, src) == dst.size);
    }
    // Compatible views of other formats: the common rows.
    {
        const ImageInfo src = Make({1920, 1088, 1}, vk::Format::eR8G8B8A8Uint);
        const ImageInfo dst = Make({1920, 1080, 1}, vk::Format::eR8G8B8A8Unorm);
        const Extent3D rows{1920, 1080, 1};
        assert(GetAliasCopyExtent(src, dst) == rows);
        assert(GetAliasCopyExtent(dst, src) == rows);
    }
    // Other memory layouts never alias.
    {
        const ImageInfo src = Make({1920, 1088, 1});
        ImageInfo dst = Make({1920, 1080, 1});
        dst.guest_address += 0x1000;
        assert(!GetAliasCopyExtent(src, dst));
        dst = Make({1920, 1080, 1});
        ++dst.pitch;
        assert(!GetAliasCopyExtent(src, dst));
        dst = Make({1920, 1080, 1});
        dst.props.is_depth = true;
        assert(!GetAliasCopyExtent(src, dst));
    }
    // Incompatible intersections.
    {
        const ImageInfo src = Make({1920, 1088, 1}, vk::Format::eR8G8B8A8Uint);
        ImageInfo dst = Make({1280, 1080, 1}, vk::Format::eR8G8B8A8Unorm);
        assert(!GetAliasCopyExtent(src, dst));
        dst = Make({1920, 1080, 1}, vk::Format::eR16G16B16A16Sfloat);
        assert(!GetAliasCopyExtent(src, dst));
        dst = Make({1920, 1080, 1}, vk::Format::eR8G8B8A8Unorm);
        dst.resources.levels = 2;
        assert(!GetAliasCopyExtent(src, dst));
    }
    // Exact winfix3 crash: equal address/format/layout and 1 mip/layer, but growing depth.
    // SubresourceExtent remains equal, so the old resources-only expansion test misses it.
    {
        ImageInfo old = Make({36, 36, 1143}, vk::Format::eR16G16B16A16Sfloat);
        old.guest_address = 0x10e073f700;
        old.guest_size = 0xdf7000;
        old.type = AmdGpu::ImageType::Color3D;
        old.num_bits = 64;
        old.pitch = 40;
        old.props.is_volume = true;
        old.props.is_tiled = true;
        old.tile_mode = AmdGpu::TileMode::Thick1DThick;
        old.array_mode = AmdGpu::ArrayMode::Array1DTiledThick;
        ImageInfo grown = old;
        grown.size.depth = 1512;
        grown.guest_size = 0x1275000;
        assert(!(grown.resources > old.resources)); // reproduce the old missing branch
        assert(IsVolumeDepthExpansion(old, grown));
        assert(!IsVolumeDepthExpansion(grown, old));
        assert(!IsVolumeDepthExpansion(old, old));
        assert((GetVolumeCopyExtent(old, grown, 0) == Extent3D{36, 36, 1143}));
        assert((GetVolumeCopyExtent(grown, old, 0) == Extent3D{36, 36, 1143}));
        assert((GetVolumeCopyExtent(old, grown, 1) == Extent3D{18, 18, 571}));
        assert((GetVolumeCopyExtent(old, grown, 11) == Extent3D{1, 1, 1}));

        const auto reject = [&](auto change) {
            auto different = grown;
            change(different);
            assert(!IsVolumeDepthExpansion(old, different));
        };
        reject([](auto& i) { ++i.guest_address; });
        reject([](auto& i) { ++i.pitch; });
        reject([](auto& i) { ++i.size.width; });
        reject([](auto& i) { ++i.size.height; });
        reject([](auto& i) { ++i.resources.levels; });
        reject([](auto& i) { ++i.resources.layers; });
        reject([](auto& i) { i.type = AmdGpu::ImageType::Color2D; });
        reject([](auto& i) { i.tile_mode = AmdGpu::TileMode::DisplayLinearAligned; });
        reject([](auto& i) { i.array_mode = AmdGpu::ArrayMode::ArrayLinearAligned; });
        reject([](auto& i) { i.pixel_format = vk::Format::eR8G8B8A8Unorm; });
        reject([](auto& i) { i.props.is_pow2 = true; });
        reject([](auto& i) { i.props.is_block = true; });
        reject([](auto& i) { i.props.is_depth = true; });
        reject([](auto& i) { i.alt_tile = true; });
        reject([](auto& i) { ++i.bank_swizzle; });
        reject([](auto& i) { i.num_samples = 2; });
        reject([](auto& i) { i.num_bits = 32; });
        reject([](auto& i) { i.guest_size = 0xdf7000; });

        // Bound all axes and every mip, in either direction, for other volume sizes too.
        for (u32 depth = 1; depth <= 2048; ++depth) {
            auto other = grown;
            other.size = {17, 63, depth};
            for (u32 mip = 0; mip < 12; ++mip) {
                const auto extent = GetVolumeCopyExtent(old, other, mip);
                assert(extent == GetVolumeCopyExtent(other, old, mip));
                assert(extent.width <= std::max(old.size.width >> mip, 1u));
                assert(extent.width <= std::max(other.size.width >> mip, 1u));
                assert(extent.height <= std::max(old.size.height >> mip, 1u));
                assert(extent.height <= std::max(other.size.height >> mip, 1u));
                assert(extent.depth <= std::max(old.size.depth >> mip, 1u));
                assert(extent.depth <= std::max(other.size.depth >> mip, 1u));
            }
        }
    }
    std::puts("aliasing-test: OK (EU 1143 -> 1512 volume growth, layout guards, "
              "24576 bidirectional mip-copy bounds cases)");
    return 0;
}

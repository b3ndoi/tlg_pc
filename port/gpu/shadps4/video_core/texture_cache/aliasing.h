// SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <optional>

#include "video_core/texture_cache/types.h"

namespace VideoCore {

struct ImageInfo;

[[nodiscard]] std::optional<Extent3D> GetAliasCopyExtent(const ImageInfo& src,
                                                         const ImageInfo& dst);

// Volume depth is not counted in SubresourceExtent (mip levels / array layers).
// Only accept a depth-only growth with an otherwise identical single-mip layout.
[[nodiscard]] bool IsVolumeDepthExpansion(const ImageInfo& cached, const ImageInfo& requested);

// For a 3D -> 3D copy, every mip must fit both volumes, including the old depth.
[[nodiscard]] Extent3D GetVolumeCopyExtent(const ImageInfo& src, const ImageInfo& dst, u32 mip);

} // namespace VideoCore

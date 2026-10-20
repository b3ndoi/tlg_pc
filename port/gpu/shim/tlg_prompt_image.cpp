// SPDX-License-Identifier: GPL-2.0-or-later
#include "tlg_png.h"
#include "tlg_prompts.h"
#include <cstdio>

namespace TlgPrompts {
bool LoadDualSensePicture(const char *path) {
  if (!path || !*path)
    return false;
  TlgPng::Image image;
  if (!TlgPng::LoadRgba(path, image)) {
    std::puts("Prompts: local PS5 image unreadable; original code-drawn "
              "fallback retained");
    return false;
  }
  const bool ok = SetDualSensePicture(
      {uint32_t(image.width), uint32_t(image.height), std::move(image.rgba)});
  if (ok)
    std::printf("Prompts: local PS5 image loaded at %dx%d (display-only)\n",
                image.width, image.height);
  return ok;
}
} // namespace TlgPrompts

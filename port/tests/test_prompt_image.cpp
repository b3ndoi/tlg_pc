// SPDX-License-Identifier: GPL-2.0-or-later
// Reuse the existing synthetic 2x2 PNG fixture. No controller artwork in
// tests/Git.
#define main png_decode_test_main
#include "test_png_decode.cpp"
#undef main
#include "tlg_prompts.h"
#include <filesystem>
#include <fstream>

int main(int argc, char **argv) {
  assert(argc == 2 || argc == 3);
  assert(png_decode_test_main() == 0);
  std::filesystem::create_directory(argv[1]);
  const auto fixture = std::filesystem::path(argv[1]) / "synthetic.png";
  {
    std::ofstream out(fixture, std::ios::binary);
    out.write(reinterpret_cast<const char *>(kPng), sizeof(kPng));
  }
  using namespace TlgPrompts;
  assert(!DualSensePicture());
  assert(!LoadDualSensePicture(nullptr));
  assert(LoadDualSensePicture(fixture.string().c_str()));
  const auto image = DualSensePicture();
  assert(image && image->width == 2 && image->height == 2 &&
         image->rgba.size() == 16);
  assert(!SetDualSensePicture({4097, 2, {}}));
  assert(!LoadDualSensePicture("missing.png") && DualSensePicture() == image);
  if (argc ==
      3) { // optional private read-only asset acceptance; never present in CI
    assert(LoadDualSensePicture(argv[2]));
    assert(DualSensePicture()->width >
           256); // full-resolution overlay source retained
  }
  SetMode(DualSense);
  uint64_t epoch = 0;
  const auto base = Replacement(TutorialController, epoch);
  assert(base && base->size() == 32768);
  const auto menu = Replacement(MenuController, epoch);
  assert(menu && menu->size() == 1920 * 1080);
  SetMode(Original);
  assert(!Replacement(TutorialController, epoch));
  std::puts("PASS: optional local PNG loading, full-resolution source, native "
            "copies and safe fallback");
}

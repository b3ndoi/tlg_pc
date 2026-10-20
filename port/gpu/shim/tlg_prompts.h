// SPDX-License-Identifier: GPL-2.0-or-later
// Original host-only prompt artwork. No game pixels, gameplay writes or clock
// hooks.
#pragma once
#include <cstddef>
#include <cstdint>
#include <memory>
#include <span>
#include <string>
#include <vector>

namespace TlgPrompts {
enum Mode { Original = 0, Auto, Keyboard, DualSense, Xbox, ModeCount };
enum Button {
  Cross,
  Circle,
  Square,
  Triangle,
  L1,
  R1,
  L2,
  R2,
  L3,
  R3,
  Options,
  TouchLeft,
  TouchRight,
  Up,
  Down,
  Left,
  Right,
  ButtonCount
};
enum Kind {
  Unmatched = 0,
  TutorialController,
  TutorialHighlights,
  MenuController
};
inline constexpr const char *Keys[] = {"original", "auto", "keyboard", "ps5",
                                       "xbox"};
inline Mode Parse(const std::string &value) {
  for (int i = 0; i < ModeCount; ++i)
    if (value == Keys[i])
      return Mode(i);
  return Original;
}

// Pure, frame-rate-independent selection model. Input timestamps are monotonic
// microseconds.
struct Selection {
  Mode mode = Original, last = Keyboard;
  uint32_t controller = 0;
  uint64_t switched = 0;
  bool used = false;
  Mode Shown() const { return mode == Auto ? last : mode; }
  void Connected(uint32_t id, Mode type);
  void Disconnected(uint32_t id);
  void Input(Mode type, uint32_t id, uint64_t now);
};

void SetMode(Mode mode);
void Connected(uint32_t id, Mode type);
void Disconnected(uint32_t id);
void Input(Mode type, uint32_t id, uint64_t now);
// Called once with the effective runtime keyboard map, never parses a second
// competing map.
void Bindings(const char *const *names, size_t count, bool custom_controller);
std::vector<std::string> Labels();
Mode Shown();
bool Active(); // false for an untouched original/default session
uint64_t Generation();

// Match only exact, locally verified BC7 payload fingerprints + geometry. No
// scanning/writes.
Kind Identify(uint32_t width, uint32_t height,
              std::span<const uint8_t> original);
inline bool Candidate(uint32_t width, uint32_t height, size_t bytes) {
  return (width == 256 && height == 128 && bytes == 32768) ||
         (width == 1920 && height == 1080 && bytes == 2088960);
}
struct Picture {
  uint32_t width{}, height{};
  std::vector<uint8_t> rgba;
};
// Optional user-owned PNG, loaded only from a local path. Never bundled or
// uploaded.
bool SetDualSensePicture(Picture picture);
std::shared_ptr<const Picture> DualSensePicture();
bool LoadDualSensePicture(const char *path);
struct GuideRect {
  float x{}, y{}, width{}, height{};
};
inline GuideRect GuideImageBounds(uint32_t width, uint32_t height) {
  if (!width || !height)
    return {};
  const float fit =
      760.f / width < 500.f / height ? 760.f / width : 500.f / height;
  return {260 + (760 - width * fit) / 2, 120 + (500 - height * fit) / 2,
          width * fit, height * fit};
}
Picture Draw(Kind kind, Mode mode, const std::vector<std::string> &labels);
std::vector<uint8_t>
EncodeBc7(const Picture &picture); // linear blocks, host upload only
std::shared_ptr<const std::vector<uint8_t>> Replacement(Kind kind,
                                                        uint64_t &generation);
} // namespace TlgPrompts

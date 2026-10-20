// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic fixtures only. No window, GPU, controller, game files or user
// settings.
#include "tlg_prompts.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <filesystem>
#include <fstream>

using namespace TlgPrompts;

static void SelectionTests() {
  Selection s;
  assert(s.Shown() == Original);
  s.Connected(1, DualSense);
  s.mode = Auto;
  assert(s.Shown() == DualSense);
  s.Input(Keyboard, 0, 1000);
  assert(s.Shown() == Keyboard);
  s.Input(Xbox, 2, 100000); // chatter inside 150ms
  assert(s.Shown() == Keyboard);
  s.Input(Xbox, 2, 151000);
  assert(s.Shown() == Xbox);
  s.Disconnected(1); // removal of an inactive pad must not switch
  assert(s.Shown() == Xbox);
  s.Disconnected(2);
  assert(s.Shown() == Keyboard);
  for (Mode m : {Keyboard, DualSense, Xbox, Original}) {
    s.mode = m;
    s.Input(DualSense, 1, 1000000);
    s.Input(Keyboard, 0, 2000000);
    assert(s.Shown() == m); // manual override is sticky
  }
  s.mode = Auto;
  s.Input(Original, 0, 4000000);
  s.Input(DualSense, 0, 4000000);
  assert(s.Shown() == Keyboard); // invalid inputs ignored
  // Same timestamped inputs interleaved with any number of presentation frames:
  // no selection or timeout is measured in frames.
  for (int fps : {30, 60, 120}) {
    Selection replay;
    replay.mode = Auto;
    for (int frame = 0; frame < fps * 2; ++frame) {
      if (frame == 0)
        replay.Input(DualSense, 1, 1000);
      if (frame == fps)
        replay.Input(Keyboard, 0, 1001000);
      assert(replay.Shown() == (frame < fps ? DualSense : Keyboard));
    }
  }
}

static void CheckBc7(const Picture &p, const std::vector<uint8_t> &blocks) {
  assert(blocks.size() == size_t(p.width) * p.height);
  constexpr int weights[] = {0,  4,  9,  13, 17, 21, 26, 30,
                             34, 38, 43, 47, 51, 55, 60, 64};
  for (size_t n = 0; n < blocks.size() / 16; ++n) {
    const auto *block = blocks.data() + n * 16;
    int bit = 0;
    const auto get = [&](int count) {
      unsigned result = 0;
      for (int i = 0; i < count; ++i, ++bit)
        result |= ((block[bit / 8] >> (bit % 8)) & 1) << i;
      return result;
    };
    assert(get(7) == 64); // BC7 mode 6
    int ends[4][2];
    for (auto &channel : ends)
      for (int &endpoint : channel)
        endpoint = int(get(7)) * 2;
    const int p0 = get(1), p1 = get(1);
    for (auto &channel : ends) {
      channel[0] |= p0;
      channel[1] |= p1;
    }
    for (int i = 0; i < 16; ++i) {
      const int index = get(i ? 4 : 3), weight = weights[index];
      const int alpha =
          ((64 - weight) * ends[3][0] + weight * ends[3][1] + 32) / 64;
      const size_t x = (n % (p.width / 4)) * 4 + i % 4,
                   y = (n / (p.width / 4)) * 4 + i / 4;
      const int expected = p.rgba[(y * p.width + x) * 4 + 3];
      assert(std::abs(alpha - expected) <= 10);
    }
    assert(bit == 128);
  }
}

int main(int argc, char **argv) {
  SelectionTests();
  for (const auto& [w, h] : std::array<std::pair<uint32_t, uint32_t>, 4>{
           {{1599, 984}, {1920, 1080}, {4, 4096}, {4096, 4}}}) {
    const auto r = GuideImageBounds(w, h);
    assert(r.x >= 260 && r.y >= 120 && r.x + r.width <= 1020.01f &&
           r.y + r.height <= 620.01f);
    assert(std::abs(r.width / r.height - float(w) / h) < 0.001f);
    // 90%-width / 88%-height window, with room for decorations and controls.
    for (int screen_height : {720, 1080, 1440, 2160}) {
      const float scale = (screen_height * .8f) / 740;
      assert((r.y + r.height) * scale < screen_height * .8f);
    }
  }
  assert(GuideImageBounds(0, 984).width == 0);
  assert(Parse("auto") == Auto && Parse("ps5") == DualSense &&
         Parse("AUTO") == Original);
  assert(Parse("unknown") == Original && !Active() && Shown() == Original);
  uint64_t epoch = 0;
  assert(!Replacement(TutorialController, epoch));
  assert(Candidate(256, 128, 32768) && !Candidate(256, 128, 32767));
  assert(Identify(256, 128, std::vector<uint8_t>(32768)) == Unmatched);
  assert(Identify(1920, 1080, std::vector<uint8_t>(2088960)) == Unmatched);
  std::vector<std::string> labels{"SPC", "SHF", "MMB", "LMB", "1",   "RMB",
                                  "R",   "F",   "Z",   "C",   "ENT", "TAB",
                                  "BSP", "I",   "K",   "J",   "L"};
  assert(Draw(Unmatched, Keyboard, labels).rgba.empty());
  assert(Draw(TutorialController, Original, labels).rgba.empty());
  assert(Draw(TutorialController, Keyboard, {}).rgba.empty());
  assert(EncodeBc7({3, 4, std::vector<uint8_t>(48)}).empty());
  assert(EncodeBc7({4, 4, {}}).empty());
  std::vector<uint8_t> previous;
  for (Mode mode : {Keyboard, DualSense, Xbox})
    for (Kind kind : {TutorialController, TutorialHighlights, MenuController}) {
      const auto picture = Draw(kind, mode, labels);
      assert(!picture.rgba.empty());
      const auto encoded = EncodeBc7(picture);
      CheckBc7(picture, encoded);
      if (kind == TutorialController) {
        assert(encoded != previous);
        previous = encoded;
      }
      if (argc == 2) { // optional private preview; generated artwork only
        const auto name =
            std::to_string(int(mode)) + "-" + std::to_string(int(kind));
        std::ofstream rgba(std::filesystem::path(argv[1]) / (name + ".rgba"),
                           std::ios::binary);
        rgba.write(reinterpret_cast<const char *>(picture.rgba.data()),
                   picture.rgba.size());
        std::ofstream bc7(std::filesystem::path(argv[1]) / (name + ".bc7"),
                          std::ios::binary);
        bc7.write(reinterpret_cast<const char *>(encoded.data()),
                  encoded.size());
      }
    }
  SetMode(Auto);
  assert(Active() && Shown() == Keyboard);
  Connected(5, DualSense);
  assert(Shown() == DualSense);
  auto first = Replacement(TutorialController, epoch);
  const auto first_epoch = epoch;
  assert(first && first->size() == 32768);
  assert(Replacement(TutorialController, epoch) == first &&
         epoch == first_epoch);
  Input(Keyboard, 0, 1000000);
  assert(Shown() == Keyboard && Generation() > first_epoch);
  SetMode(Xbox);
  Input(Keyboard, 0, 2000000);
  assert(Shown() == Xbox);
  std::array<const char *, ButtonCount> names;
  names.fill("Space");
  Bindings(names.data(), names.size(), true);
  assert(Shown() == Original && !Replacement(TutorialController, epoch));
  SetMode(Keyboard); // custom controller remap does not hide keyboard prompts
  assert(Shown() == Keyboard);
  const auto before = Replacement(TutorialController, epoch);
  names[0] = "Mouse Left";
  Bindings(names.data(), names.size(), false);
  const auto after = Replacement(TutorialController, epoch);
  assert(before && after && *before != *after);
  names.fill(nullptr);
  Bindings(names.data(), names.size(), false);
  assert(Replacement(TutorialController,
                     epoch)); // unbound labels are explicit ---
  SetMode(Original);
  assert(Active() && Shown() == Original &&
         !Replacement(TutorialController, epoch));
  std::puts("PASS: prompt selection, exact-match rejection, original artwork, "
            "BC7 roundtrip and restoration generations");
}

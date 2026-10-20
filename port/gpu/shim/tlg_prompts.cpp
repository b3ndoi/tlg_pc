// SPDX-License-Identifier: GPL-2.0-or-later
// Original procedural drawings: no extracted textures, logos, fonts or
// controller images.
#include "tlg_prompts.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <map>
#include <mutex>
#include <xxhash.h>

namespace TlgPrompts {
void Selection::Connected(uint32_t id, Mode type) {
  if (!used && !controller && id && (type == DualSense || type == Xbox)) {
    last = type;
    controller = id;
  }
}
void Selection::Disconnected(uint32_t id) {
  if (controller == id && id) {
    last = Keyboard;
    controller = 0;
    used = false;
    switched = 0;
  }
}
void Selection::Input(Mode type, uint32_t id, uint64_t now) {
  if (type != Keyboard && type != DualSense && type != Xbox)
    return;
  if (type != Keyboard && !id)
    return;
  // Ignore cross-device chatter for 150 ms, independently of presentation/game
  // FPS.
  if (used && type != last && now >= switched && now - switched < 150000)
    return;
  if (!used || type != last || (id && id != controller))
    switched = now;
  used = true;
  last = type;
  controller = type == Keyboard ? 0 : id;
}
namespace {
std::mutex mutex;
Selection selection;
std::atomic<Mode> shown{Original};
std::atomic<uint64_t> generation{1};
std::atomic<bool> activated{false};
bool custom_pad = false;
std::shared_ptr<const Picture> dualsense_picture;
std::vector<std::string> bindings{"SPC", "SHF", "E", "Q", "1",   "3",
                                  "R",   "F",   "Z", "C", "ENT", "TAB",
                                  "BSP", "I",   "K", "J", "L"};
std::map<std::pair<int, uint64_t>, std::shared_ptr<const std::vector<uint8_t>>>
    cache;
void Publish() {
  Mode next = selection.Shown();
  // Nonstandard controller mappings cannot safely use a fixed-position diagram.
  if (custom_pad && (next == DualSense || next == Xbox))
    next = Original;
  if (shown.exchange(next) != next)
    generation.fetch_add(1);
}
std::string Compact(std::string value) {
  for (char &c : value)
    if (c >= 'a' && c <= 'z')
      c -= 'a' - 'A';
  const std::pair<const char *, const char *> aliases[] = {
      {"SPACE", "SPC"},      {"LEFT SHIFT", "SHF"},  {"RIGHT SHIFT", "SHF"},
      {"RETURN", "ENT"},     {"BACKSPACE", "BSP"},   {"LEFT CTRL", "CTL"},
      {"RIGHT CTRL", "CTL"}, {"LEFT ALT", "ALT"},    {"RIGHT ALT", "ALT"},
      {"MOUSE LEFT", "LMB"}, {"MOUSE RIGHT", "RMB"}, {"MOUSE MIDDLE", "MMB"},
      {"MOUSE X1", "M4"},    {"MOUSE X2", "M5"},     {"WHEEL UP", "WU"},
      {"WHEEL DOWN", "WD"}};
  for (const auto &[from, to] : aliases)
    if (value == from)
      return to;
  if (value.empty())
    return "---";
  if (value.size() > 3)
    return "?"; // never invent a misleading truncated binding
  for (char c : value)
    if (!(c >= 'A' && c <= 'Z') && !(c >= '0' && c <= '9') && c != '-')
      return "?";
  return value;
}
// Independently drawn 3x5 keycap alphabet (not a bundled/extracted font).
constexpr const char *alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-?";
constexpr const char *shapes[] = {
    "010101111101101", "110101110101110", "011100100100011", "110101101101110",
    "111100110100111", "111100110100100", "011100101101011", "101101111101101",
    "111010010010111", "001001001101010", "101101110101101", "100100100100111",
    "101111111101101", "101111111111101", "010101101101010", "110101110100100",
    "010101101111011", "110101110101101", "011100010001110", "111010010010010",
    "101101101101111", "101101101101010", "101101111111101", "101101010101101",
    "101101010010010", "111001010100111", "111101101101111", "010110010010111",
    "110001010100111", "110001010001110", "101101111001001", "111100110001110",
    "011100110101010", "111001010010010", "010101010101010", "010101011001110",
    "000000111000000", "110001010000010"};
struct Canvas {
  Picture p;
  float scale = 1, ox = 0, oy = 0;
  Canvas(uint32_t w, uint32_t h)
      : p{w, h, std::vector<uint8_t>(size_t(w) * h * 4)} {}
  void Pixel(int x, int y, uint8_t alpha = 255) {
    if (x < 0 || y < 0 || x >= int(p.width) || y >= int(p.height))
      return;
    auto *q = p.rgba.data() + (size_t(y) * p.width + x) * 4;
    q[0] = q[1] = q[2] = 235;
    q[3] = std::max(q[3], alpha);
  }
  void Dot(float x, float y, float radius, bool filled = false) {
    x = ox + x * scale;
    y = oy + y * scale;
    radius *= scale;
    const float line = std::max(0.8f, scale * 0.65f);
    for (int py = int(y - radius - line); py <= int(y + radius + line); ++py)
      for (int px = int(x - radius - line); px <= int(x + radius + line);
           ++px) {
        const float d = std::hypot(px + 0.5f - x, py + 0.5f - y);
        const float coverage = std::clamp(
            (filled ? radius - d : line - std::abs(d - radius)) + 0.5f, 0.f,
            1.f);
        if (coverage > 0)
          Pixel(px, py, uint8_t(coverage * 255));
      }
  }
  void Line(float x1, float y1, float x2, float y2) {
    const int steps =
        std::max(1, int(std::hypot(x2 - x1, y2 - y1) * scale * 2));
    for (int i = 0; i <= steps; ++i)
      Dot(x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps, 0.4f, true);
  }
  void Box(float x, float y, float w, float h) {
    Line(x, y, x + w, y);
    Line(x + w, y, x + w, y + h);
    Line(x + w, y + h, x, y + h);
    Line(x, y + h, x, y);
  }
  void Text(float x, float y, const std::string &text, float size = 1) {
    if (text.empty())
      return;
    const float start = x - (text.size() * 4 - 1) * size / 2;
    for (size_t i = 0; i < text.size(); ++i) {
      const char *found = std::strchr(alphabet, text[i]);
      const char *bits = shapes[found ? found - alphabet : 37];
      for (int row = 0; row < 5; ++row)
        for (int col = 0; col < 3; ++col)
          if (bits[row * 3 + col] == '1') {
            const float xx = start + (i * 4 + col) * size,
                        yy = y + (row - 2) * size;
            Line(xx, yy, xx + size * 0.7f, yy);
          }
    }
  }
  void Key(float x, float y, const std::string &text) {
    const float w = std::max(8.f, float(text.size() * 4 + 2));
    Box(x - w / 2, y - 4, w, 8);
    Text(x, y, text, 0.85f);
  }
  void Face(float x, float y, int face, Mode mode) {
    Dot(x, y, 5.4f);
    if (mode == Xbox)
      Text(x, y, std::string(1, "ABXY"[face]), 1.1f);
    else if (face == Cross) {
      Line(x - 2, y - 2, x + 2, y + 2);
      Line(x + 2, y - 2, x - 2, y + 2);
    } else if (face == Circle)
      Dot(x, y, 2.6f);
    else if (face == Square)
      Box(x - 2.5f, y - 2.5f, 5, 5);
    else {
      Line(x, y - 3, x + 3, y + 2);
      Line(x + 3, y + 2, x - 3, y + 2);
      Line(x - 3, y + 2, x, y - 3);
    }
  }
  void Stamp(const Picture &source) {
    // Keep the full-resolution source for the display overlay. Here only the
    // small native tutorial copy is area-filtered, using white-on-black line
    // art as a mask.
    const float fit = std::min(178.f / source.width, 104.f / source.height);
    const float w = source.width * fit, h = source.height * fit;
    const float x0 = 40 + (178 - w) / 2, y0 = 18 + (104 - h) / 2;
    const int left = int(ox + x0 * scale), top = int(oy + y0 * scale);
    const int width = std::max(1, int(w * scale)),
              height = std::max(1, int(h * scale));
    for (int y = 0; y < height; ++y)
      for (int x = 0; x < width; ++x) {
        const int sx0 = x * source.width / width,
                  sy0 = y * source.height / height;
        const int sx1 =
            std::min(int(source.width),
                     std::max(sx0 + 1, int((x + 1) * source.width / width)));
        const int sy1 =
            std::min(int(source.height),
                     std::max(sy0 + 1, int((y + 1) * source.height / height)));
        unsigned total = 0, count = 0;
        for (int sy = sy0; sy < sy1; ++sy)
          for (int sx = sx0; sx < sx1; ++sx) {
            const auto *pixel =
                source.rgba.data() + (size_t(sy) * source.width + sx) * 4;
            total += unsigned(std::max({pixel[0], pixel[1], pixel[2]})) *
                     pixel[3] / 255;
            ++count;
          }
        if (total)
          Pixel(left + x, top + y,
                uint8_t(std::min(255u, (total * 2) / count)));
      }
  }
};
// Locations preserve TLG's tutorial highlight alignment; no original image
// bytes are used.
constexpr float positions[ButtonCount][2] = {
    {181, 82}, {194, 71}, {167, 71},     {181, 60},     {74, 33},  {177, 33},
    {68, 24},  {172, 24}, {107.5f, 101}, {163.5f, 101}, {162, 52}, {112, 58},
    {142, 58}, {75, 61},  {75, 81},      {65, 71},      {84, 71}};
void Diagram(Canvas &c, Mode mode, const std::vector<std::string> &labels) {
  // A deliberately original, simplified controller silhouette: no
  // logos/trademark artwork.
  const float outline[][2] = {{70, 22},  {98, 35},   {153, 35},  {182, 22},
                              {197, 35}, {219, 108}, {210, 121}, {191, 112},
                              {174, 96}, {98, 96},   {78, 113},  {59, 121},
                              {48, 108}, {62, 35},   {70, 22}};
  for (size_t i = 1; i < std::size(outline); ++i)
    c.Line(outline[i - 1][0], outline[i - 1][1], outline[i][0], outline[i][1]);
  if (mode != Keyboard) {
    c.Box(110, 42, 35, 29);
    c.Dot(107.5f, 101, 10);
    c.Dot(163.5f, 101, 10);
  }
  for (int i = 0; i < ButtonCount; ++i) {
    const auto [x, y] = positions[i];
    if (mode == Keyboard)
      c.Key(x, y, labels[i]);
    else if (i < 4)
      c.Face(x, y, i, mode);
    else if (i == L1 || i == R1 || i == L2 || i == R2)
      c.Key(x, y,
            (mode == Xbox ? std::array<const char *, 4>{"LB", "RB", "LT", "RT"}
                          : std::array<const char *, 4>{"L1", "R1", "L2",
                                                        "R2"})[i - L1]);
    else if (i == L3 || i == R3)
      c.Text(x, y, i == L3 ? "L" : "R", 1.1f);
    else if (i == Options) {
      c.Line(x - 2, y - 2, x + 2, y - 2);
      c.Line(x - 2, y, x + 2, y);
      c.Line(x - 2, y + 2, x + 2, y + 2);
    } else if (i == TouchLeft || i == TouchRight)
      c.Text(x, y, mode == Xbox ? (i == TouchLeft ? "V" : "BK") : "T", 0.8f);
    else if (i >= Up) {
      const float dx = i == Left    ? -2
                       : i == Right ? 2
                                    : 0,
                  dy = i == Up     ? -2
                       : i == Down ? 2
                                   : 0;
      c.Line(x - dx, y - dy, x + dx, y + dy);
      c.Line(x + dx, y + dy, x + dy, y - dx);
      c.Line(x + dx, y + dy, x - dy, y + dx);
    }
  }
  if (mode == Keyboard) {
    c.Text(107.5f, 87, "WASD", 0.9f);
    c.Text(163.5f, 113, "MOUSE", 0.8f);
  }
}
} // namespace
void SetMode(Mode mode) {
  std::scoped_lock lock{mutex};
  selection.mode = mode >= Original && mode < ModeCount ? mode : Original;
  if (selection.mode != Original)
    activated.store(true, std::memory_order_release);
  Publish();
}
void Connected(uint32_t id, Mode type) {
  std::scoped_lock lock{mutex};
  selection.Connected(id, type);
  Publish();
}
void Disconnected(uint32_t id) {
  std::scoped_lock lock{mutex};
  selection.Disconnected(id);
  Publish();
}
void Input(Mode type, uint32_t id, uint64_t now) {
  std::scoped_lock lock{mutex};
  selection.Input(type, id, now);
  Publish();
}
void Bindings(const char *const *names, size_t count, bool remapped) {
  if (!names || count != ButtonCount)
    return;
  std::scoped_lock lock{mutex};
  for (size_t i = 0; i < count; ++i)
    bindings[i] =
        Compact(names[i] ? std::string(names[i], strnlen(names[i], 64)) : "");
  custom_pad = remapped;
  generation.fetch_add(1);
  cache.clear();
  Publish();
}
Mode Shown() { return shown.load(std::memory_order_acquire); }
std::vector<std::string> Labels() {
  std::scoped_lock lock{mutex};
  return bindings;
}
bool Active() { return activated.load(std::memory_order_acquire); }
uint64_t Generation() { return generation.load(std::memory_order_acquire); }
bool SetDualSensePicture(Picture picture) {
  if (!picture.width || !picture.height || picture.width > 4096 ||
      picture.height > 4096 ||
      picture.rgba.size() != size_t(picture.width) * picture.height * 4)
    return false;
  std::scoped_lock lock{mutex};
  dualsense_picture = std::make_shared<const Picture>(std::move(picture));
  cache.clear();
  generation.fetch_add(1);
  return true;
}
std::shared_ptr<const Picture> DualSensePicture() {
  std::scoped_lock lock{mutex};
  return dualsense_picture;
}
Kind Identify(uint32_t width, uint32_t height, std::span<const uint8_t> bytes) {
  struct Fingerprint {
    uint32_t w, h;
    size_t bytes;
    uint64_t lo, hi;
    Kind kind;
  };
  // Local owner-provided EU 01.00 fingerprints, NOT embedded texture contents.
  static constexpr Fingerprint known[] = {
      {256, 128, 32768, 0x4641711da2e67237, 0x1ad26309a3363d67,
       TutorialController},
      {256, 128, 32768, 0x7c7bf38dbc787155, 0x2cc7a35d9ef970c9,
       TutorialHighlights},
      {1920, 1080, 2088960, 0xa31d94e31031029e, 0xc210f1723698189e,
       MenuController}};
  for (const auto &k : known)
    if (width == k.w && height == k.h && bytes.size() == k.bytes) {
      const auto hash = XXH3_128bits(bytes.data(), bytes.size());
      if (hash.low64 == k.lo && hash.high64 == k.hi)
        return k.kind;
    }
  return Unmatched;
}
Picture Draw(Kind kind, Mode mode, const std::vector<std::string> &labels) {
  if (kind < TutorialController || kind > MenuController || mode < Keyboard ||
      mode > Xbox || labels.size() != ButtonCount)
    return {};
  Canvas c(kind == MenuController ? 1920 : 256,
           kind == MenuController ? 1080 : 128);
  if (kind == MenuController) {
    c.scale = 3.3f;
    c.ox = 118;
    c.oy = 110;
  }
  const auto image = mode == DualSense ? DualSensePicture() : nullptr;
  if (kind != TutorialHighlights && image)
    c.Stamp(*image);
  else if (kind != TutorialHighlights)
    Diagram(c, mode, labels);
  else {
    // Native tutorial UV regions. Shared stick/push highlight remains a neutral
    // ring.
    const float uv[ButtonCount][2] = {
        {64, 0},   {32, 0},   {96, 0},  {0, 0},    {166.4f, 96}, {211.2f, 96},
        {160, 64}, {208, 64}, {0, 80},  {0, 80},   {128, 0},     {160, 0},
        {160, 0},  {224, 0},  {192, 0}, {192, 32}, {224, 32}};
    for (int i = 0; i < ButtonCount; ++i) {
      // The native atlas shares Select/PS and stick/push cells between actions;
      // they cannot truthfully carry side-specific keyboard legends.
      if (i == TouchLeft || i == TouchRight)
        continue;
      const float x = uv[i][0] + 16, y = uv[i][1] + 16;
      if (i == L3 || i == R3) {
        c.Dot(24, 104, 19);
        continue;
      }
      if (mode == Keyboard)
        c.Key(x, y, labels[i]);
      else if (i < 4)
        c.Face(x, y, i, mode);
      else
        c.Dot(x, y, 8);
    }
    c.Dot(176, 16, 6);
    c.Dot(176, 48, 6);
  }
  if (kind == MenuController) {
    // Independently drawn leader lines to the game's separate action-label
    // anchors.
    c.scale = 1;
    c.ox = c.oy = 0;
    c.Line(715, 308, 715, 255);
    c.Line(715, 255, 849, 255);
    c.Line(758, 344, 901, 344);
    c.Line(715, 381, 715, 460);
    c.Line(715, 460, 849, 460);
    c.Line(669, 344, 669, 551);
    c.Line(669, 551, 777, 551);
    c.Line(473, 453, 473, 554);
    c.Line(658, 453, 658, 586);
  }
  return std::move(c.p);
}

// BC7 mode 6, two RGBA endpoints with 4-bit interpolation; no proprietary
// encoder.
std::vector<uint8_t> EncodeBc7(const Picture &p) {
  if (!p.width || !p.height || p.width % 4 || p.height % 4 ||
      p.rgba.size() != size_t(p.width) * p.height * 4)
    return {};
  std::vector<uint8_t> out(size_t(p.width) * p.height);
  constexpr int weights[] = {0,  4,  9,  13, 17, 21, 26, 30,
                             34, 38, 43, 47, 51, 55, 60, 64};
  for (uint32_t by = 0; by < p.height / 4; ++by)
    for (uint32_t bx = 0; bx < p.width / 4; ++bx) {
      uint8_t lo[4] = {235, 235, 235, 0}, hi[4] = {235, 235, 235, 254};
      int index[16];
      for (int y = 0; y < 4; ++y)
        for (int x = 0; x < 4; ++x) {
          int a = p.rgba[((by * 4 + y) * p.width + bx * 4 + x) * 4 + 3],
              best = 0, error = 100000;
          for (int i = 0; i < 16; ++i) {
            const int diff = (weights[i] * 254 + 32) / 64 - a;
            if (diff * diff < error) {
              error = diff * diff;
              best = i;
            }
          }
          index[y * 4 + x] = best;
        }
      if (index[0] >= 8) {
        for (int k = 0; k < 4; ++k)
          std::swap(lo[k], hi[k]);
        for (int &i : index)
          i = 15 - i;
      }
      uint8_t *block = out.data() + (by * (p.width / 4) + bx) * 16;
      int bit = 0;
      const auto put = [&](uint32_t value, int count) {
        for (int i = 0; i < count; ++i, ++bit)
          block[bit / 8] |= ((value >> i) & 1) << (bit % 8);
      };
      put(64, 7);
      for (int k = 0; k < 4; ++k) {
        put(lo[k] >> 1, 7);
        put(hi[k] >> 1, 7);
      }
      put(0, 1);
      put(0, 1); // even endpoints, common p-bit 0
      put(index[0], 3);
      for (int i = 1; i < 16; ++i)
        put(index[i], 4);
    }
  return out;
}
std::shared_ptr<const std::vector<uint8_t>> Replacement(Kind kind,
                                                        uint64_t &epoch) {
  std::unique_lock lock{mutex};
  epoch = Generation();
  const Mode mode = Shown();
  if (mode == Original || kind == Unmatched)
    return {};
  const auto key = std::pair{int(kind), uint64_t(mode)};
  if (const auto it = cache.find(key); it != cache.end())
    return it->second;
  const auto labels = bindings;
  lock.unlock(); // never hold the input/selection mutex while drawing/encoding
  auto result = std::make_shared<const std::vector<uint8_t>>(
      EncodeBc7(Draw(kind, mode, labels)));
  lock.lock();
  if (Generation() == epoch && cache.size() < 9)
    cache[key] = result; // three textures x three devices
  return result;
}
} // namespace TlgPrompts

extern "C" void tlggpu_prompts_bindings(const char *const *labels, int count,
                                        int custom) {
  if (count == TlgPrompts::ButtonCount)
    TlgPrompts::Bindings(labels, count, custom != 0);
}

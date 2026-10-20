// SPDX-License-Identifier: GPL-2.0-or-later
#include "tlg_translations.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <set>
#include <string>
#include <string_view>
#include <tuple>
#include <xxhash.h>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace TlgTranslations {
namespace {
struct Entry {
  uint32_t width, height, source_bytes;
  uint64_t low, high;
  std::vector<uint8_t> bc7;
};
// Initialized on window creation, before GPU texture-cache use. Never
// hot-reloaded.
std::vector<Entry> entries;
constexpr size_t MaxBytes = 64 * 1024 * 1024;
constexpr std::array<uint8_t, 8> Magic{'T', 'L', 'G', 'T', 'R', 'N', '1', 0};
} // namespace

bool Parse(std::span<const uint8_t> bytes) {
  entries.clear();
  if (bytes.size() < 12 || bytes.size() > MaxBytes ||
      std::memcmp(bytes.data(), Magic.data(), Magic.size()))
    return false;
  size_t at = 8;
  auto read = [&](unsigned n) {
    uint64_t value = 0;
    for (unsigned i = 0; i < n; ++i)
      value |= uint64_t(bytes[at++]) << (8 * i);
    return value;
  };
  const auto count = read(4);
  if (!count || count > 512)
    return false;
  std::vector<Entry> pending;
  std::set<std::tuple<uint32_t, uint32_t, uint32_t, uint64_t, uint64_t>>
      identities;
  for (uint64_t i = 0; i < count; ++i) {
    if (bytes.size() - at < 32)
      return false;
    Entry e{};
    e.width = uint32_t(read(4));
    e.height = uint32_t(read(4));
    e.source_bytes = uint32_t(read(4));
    e.low = read(8);
    e.high = read(8);
    const auto length = read(4);
    // Initial profile is restricted to sampled single-level 512x128 tutorials.
    // Expanding the profile requires native review, not a translator-supplied
    // size.
    if (e.width != 512 || e.height != 128 || e.source_bytes != 65536 ||
        length != 65536 || length > bytes.size() - at ||
        !identities.emplace(e.width, e.height, e.source_bytes, e.low, e.high)
             .second)
      return false;
    // Compiler output uses mode 5, no channel rotation. Reject damaged block
    // prefixes before sending any replacement to a graphics driver.
    for (size_t block = 0; block < size_t(length); block += 16)
      if (bytes[at + block] != 32)
        return false;
    e.bc7.assign(bytes.begin() + at, bytes.begin() + at + size_t(length));
    at += size_t(length);
    pending.push_back(std::move(e));
  }
  if (at != bytes.size())
    return false;
  entries = std::move(pending);
  return true;
}

static bool LoadPath(const std::filesystem::path &path) {
  entries.clear();
  try {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    const auto length = stream.tellg();
    if (stream && length >= 12 && uint64_t(length) <= MaxBytes) {
      std::vector<uint8_t> data(static_cast<size_t>(length));
      stream.seekg(0);
      if (stream.read(reinterpret_cast<char *>(data.data()), length) &&
          Parse(data)) {
        std::printf("Translation: %zu exact English tutorial textures loaded "
                    "(host only; story/menu text unchanged)\n",
                    entries.size());
        return true;
      }
    }
  } catch (const std::exception &) {
    entries.clear();
  }
  std::puts(
      "Translation: pack invalid/unreadable; original game text retained");
  return false;
}

bool Load(const char *path) {
  entries.clear();
  if (!path || !*path)
    return false; // Default is a no-op, at both 30 and 60 FPS.
  try {
    const std::string_view utf8(path);
    return LoadPath(
        std::filesystem::path(std::u8string(utf8.begin(), utf8.end())));
  } catch (const std::exception &) {
    std::puts("Translation: invalid UTF-8 path; original game text retained");
    return false;
  }
}

bool LoadEnvironment() {
#ifdef _WIN32
  entries.clear();
  const DWORD needed =
      GetEnvironmentVariableW(L"TLG_TRANSLATION_PACK", nullptr, 0);
  if (!needed)
    return false;
  if (needed > 32768)
    return false;
  std::wstring path(needed, L'\0');
  const DWORD length =
      GetEnvironmentVariableW(L"TLG_TRANSLATION_PACK", path.data(), needed);
  if (!length || length >= needed)
    return false;
  path.resize(length);
  return LoadPath(std::filesystem::path(path));
#else
  return Load(std::getenv("TLG_TRANSLATION_PACK"));
#endif
}

bool Active() { return !entries.empty(); }

const std::vector<uint8_t> *Replacement(uint32_t width, uint32_t height,
                                        std::span<const uint8_t> original) {
  if (!Active() || width != 512 || height != 128 || original.size() != 65536)
    return nullptr;
  const auto hash = XXH3_128bits(original.data(), original.size());
  for (const auto &e : entries)
    if (e.width == width && e.height == height &&
        e.source_bytes == original.size() && e.low == hash.low64 &&
        e.high == hash.high64)
      return &e.bc7;
  return nullptr;
}
} // namespace TlgTranslations

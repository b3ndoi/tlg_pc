// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic pixels only. No GPU, SDL, process access, game files or timing
// hooks.
#include "tlg_translations.h"
#include <cassert>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <xxhash.h>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#endif

using Bytes = std::vector<uint8_t>;
static void Put(Bytes &out, uint64_t value, unsigned count) {
  for (unsigned i = 0; i < count; ++i)
    out.push_back(uint8_t(value >> (8 * i)));
}
static Bytes Pack(const Bytes &source) {
  Bytes data{'T', 'L', 'G', 'T', 'R', 'N', '1', 0};
  Put(data, 1, 4);
  Put(data, 512, 4);
  Put(data, 128, 4);
  Put(data, 65536, 4);
  const auto hash = XXH3_128bits(source.data(), source.size());
  Put(data, hash.low64, 8);
  Put(data, hash.high64, 8);
  Put(data, 65536, 4);
  for (unsigned n = 0; n < 4096; ++n) {
    data.push_back(32);
    data.insert(data.end(), 15, 0);
  }
  return data;
}
int main(int argc, char **argv) {
  namespace T = TlgTranslations;
  Bytes original(65536, 0x5a);
  const auto before = original, good = Pack(original);
  assert(!T::Active() && !T::Load(nullptr) && !T::Load(""));
  assert(T::Parse(good) && T::Active());
  const auto *replacement = T::Replacement(512, 128, original);
  assert(replacement && replacement->size() == 65536 &&
         replacement->front() == 32);
  assert(!T::Replacement(256, 256, original));
  assert(!T::Replacement(512, 128, {original.data(), original.size() - 1}));
  original[1024] ^= 1;
  assert(!T::Replacement(512, 128, original));
  original[1024] ^= 1;
  assert(original == before); // Matcher never changes source pixels.
  for (size_t length :
       {size_t(0), size_t(8), size_t(12), size_t(43), good.size() - 1}) {
    assert(!T::Parse({good.data(), length}) && !T::Active());
  }
  for (size_t offset : {size_t(0), size_t(8), size_t(12), size_t(16),
                        size_t(20), size_t(40), size_t(44)}) {
    auto bad = good;
    bad[offset] ^= 0xff;
    assert(!T::Parse(bad) && !T::Active());
  }
  auto bad = good;
  bad.push_back(0);
  assert(!T::Parse(bad));
  bad = good;
  bad[8] = 2;
  bad.insert(bad.end(), good.begin() + 12, good.end());
  assert(!T::Parse(bad)); // Duplicate identities rejected atomically.
  const auto file = std::filesystem::path(u8"čćžšđ-translation-fixture.tlgtrn");
  {
    std::ofstream out(file, std::ios::binary);
    out.write(reinterpret_cast<const char *>(good.data()), good.size());
  }
  const auto utf8 = file.u8string();
  assert(T::Load(reinterpret_cast<const char *>(utf8.c_str())));
  assert(T::Replacement(512, 128, original));
#ifdef _WIN32
  // Exercise the actual Python->wide Windows environment path, not just UTF-8
  // fopen.
  const DWORD needed =
      GetEnvironmentVariableW(L"TLG_TRANSLATION_PACK", nullptr, 0);
  std::wstring previous(needed, L'\0');
  if (needed)
    previous.resize(GetEnvironmentVariableW(L"TLG_TRANSLATION_PACK",
                                            previous.data(), needed));
  assert(SetEnvironmentVariableW(L"TLG_TRANSLATION_PACK", file.c_str()));
  assert(T::LoadEnvironment() && T::Replacement(512, 128, original));
  assert(SetEnvironmentVariableW(L"TLG_TRANSLATION_PACK",
                                 needed ? previous.c_str() : nullptr));
#endif
  std::filesystem::remove(file);
  assert(!T::Load("missing-translation-fixture.tlgtrn") && !T::Active());
  if (argc == 2)
    assert(T::Load(argv[1]) && T::Active()); // Optional locally compiled pack.
  std::puts("Translations: strict pack parsing, exact matches, Unicode paths "
            "and untouched source PASS");
}

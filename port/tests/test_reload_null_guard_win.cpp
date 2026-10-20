// Execute the production guard on synthetic state. The legacy NULL load must fault;
// guarded NULL entries advance without touching locals, and live entries are identical.
#include <array>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <vector>
#include <windows.h>
#include "reload_null_guard.h"

static unsigned char* legacy;
static unsigned char* missing;
static unsigned expected_faults;
static constexpr uintptr_t SavedSentinel = 0x1122334455667788ull;
static constexpr uintptr_t MissingResult = 0xdeadbeef;

static LONG CALLBACK catch_legacy(EXCEPTION_POINTERS* info) {
    const auto* record = info->ExceptionRecord;
    if (record->ExceptionCode == EXCEPTION_ACCESS_VIOLATION &&
        record->NumberParameters >= 2 && record->ExceptionInformation[0] == 0 &&
        record->ExceptionInformation[1] == 0x28 &&
        info->ContextRecord->Rip == reinterpret_cast<uintptr_t>(legacy)) {
        ++expected_faults;
        info->ContextRecord->Rip = reinterpret_cast<uintptr_t>(missing);
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

struct Result { uintptr_t value, saved; };
static Result Run(void* entry, uintptr_t object) {
    uintptr_t value, saved;
    asm volatile(
        "push %%rbp; sub $0x80, %%rsp; lea 0x80(%%rsp), %%rbp;"
        "movabs $0x1122334455667788, %%rax; mov %%rax, -0x68(%%rbp);"
        "mov %%rdx, %%rax; call *%%rcx; mov -0x68(%%rbp), %%rdx;"
        "add $0x80, %%rsp; pop %%rbp"
        : "=a"(value), "=d"(saved) : "c"(entry), "1"(object)
        : "r15", "memory", "cc");
    return {value, saved};
}

static void AbsJump(unsigned char* at, const unsigned char* target) {
    const unsigned char jump[] = {0xff,0x25,0,0,0,0};
    const uintptr_t address = reinterpret_cast<uintptr_t>(target);
    std::memcpy(at, jump, sizeof(jump));
    std::memcpy(at + sizeof(jump), &address, sizeof(address));
}

int main(int argc, char** argv) {
    std::vector<unsigned char> fixture(TLG_RELOAD_SPAN, 0xcc);
    const auto put = [&](size_t at, const auto& bytes) {
        std::memcpy(fixture.data() + at, bytes, sizeof(bytes));
    };
    put(0, tlg_reload_prologue);
    put(0x26, tlg_reload_reserve);
    put(0x70, tlg_reload_lookup);
    put(TLG_RELOAD_ADVANCE - TLG_RELOAD_FUNCTION, tlg_reload_advance);
    const auto matches = [&](const char* serial, const char* version, size_t size) {
        return tlg_reload_guard_matches(serial, version, fixture.data(), size);
    };
    assert(matches("CUSA03745", "01.00", fixture.size()));
    assert(!matches("CUSA03627", "01.03", fixture.size()));
    assert(!matches("CUSA03745", "01.01", fixture.size()));
    assert(!matches("CUSA03745", "01.00", fixture.size() - 1));
    assert(!tlg_reload_guard_matches(nullptr, "01.00", fixture.data(), fixture.size()));
    assert(!tlg_reload_guard_matches("CUSA03745", "01.00", nullptr, fixture.size()));
    // Every validated code byte must reject a mismatch, not install a partial hook.
    const std::array<std::pair<size_t, size_t>, 4> signatures{{
        {0, sizeof(tlg_reload_prologue)}, {0x26, sizeof(tlg_reload_reserve)},
        {0x70, sizeof(tlg_reload_lookup)},
        {TLG_RELOAD_ADVANCE - TLG_RELOAD_FUNCTION, sizeof(tlg_reload_advance)}
    }};
    for (const auto [start, length] : signatures) {
        for (size_t i = start; i < start + length; ++i) {
            fixture[i] ^= 1;
            assert(!matches("CUSA03745", "01.00", fixture.size()));
            fixture[i] ^= 1;
        }
    }
    if (argc > 1) {
        std::ifstream elf(argv[1], std::ios::binary);
        assert(elf);
        elf.seekg(0x4000 + TLG_RELOAD_FUNCTION);
        elf.read(reinterpret_cast<char*>(fixture.data()), fixture.size());
        assert(elf && matches("CUSA03745", "01.00", fixture.size()));
        std::puts("PASS: guard signatures match the real EU ELF");
    }

    auto* memory = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, 4096, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    assert(memory);
    legacy = memory + 256;
    auto* resume = memory + 512;
    missing = memory + 576;
    auto* guarded = memory + 768;
    std::memcpy(legacy, tlg_reload_original, TLG_RELOAD_LENGTH);
    AbsJump(legacy + TLG_RELOAD_LENGTH, resume);
    // Same immediate post-hook TEST; return the loaded field for observation.
    const unsigned char valid_tail[] = {0x4d,0x85,0xff,0x4c,0x89,0xf8,0xc3};
    const unsigned char skip_tail[] = {0xb8,0xef,0xbe,0xad,0xde,0xc3};
    std::memcpy(resume, valid_tail, sizeof(valid_tail));
    std::memcpy(missing, skip_tail, sizeof(skip_tail));
    assert(tlg_reload_guard_build_stub(guarded, reinterpret_cast<uintptr_t>(resume),
                                      reinterpret_cast<uintptr_t>(missing)) ==
           TLG_RELOAD_STUB_SIZE);
    DWORD old;
    assert(VirtualProtect(memory, 4096, PAGE_EXECUTE_READ, &old));
    assert(FlushInstructionCache(GetCurrentProcess(), memory, 4096));
    void* handler = AddVectoredExceptionHandler(1, catch_legacy);
    assert(handler);
    const auto original_null = Run(legacy, 0);
    assert(expected_faults == 1 && original_null.value == MissingResult &&
           original_null.saved == SavedSentinel);

    std::array<uintptr_t, 8> object{};
    object[5] = 0x123456789abcdef0ull;
    const auto address = reinterpret_cast<uintptr_t>(object.data());
    const auto original_live = Run(legacy, address);
    assert(original_live.value == object[5] && original_live.saved == address);

    // Exercise the real image-site 5-byte rel32 detour and NOP fill too.
    assert(VirtualProtect(memory, 4096, PAGE_READWRITE, &old));
    const int32_t delta = static_cast<int32_t>(guarded - (legacy + 5));
    legacy[0] = 0xe9;
    std::memcpy(legacy + 1, &delta, sizeof(delta));
    std::memset(legacy + 5, 0x90, TLG_RELOAD_LENGTH - 5);
    assert(VirtualProtect(memory, 4096, PAGE_EXECUTE_READ, &old));
    assert(FlushInstructionCache(GetCurrentProcess(), memory, 4096));
    for (unsigned i = 0; i < 10000; ++i) {
        const auto null_entry = Run(legacy, 0);
        assert(null_entry.value == MissingResult && null_entry.saved == SavedSentinel);
        object[5] = i % 2 ? 0 : 0x123456789abcdef0ull;
        const auto before = object;
        const auto live = Run(legacy, address);
        assert(live.value == object[5] && live.saved == address && object == before);
    }
    assert(expected_faults == 1); // none of the 20000 guarded runs trapped
    assert(RemoveVectoredExceptionHandler(handler));
    assert(VirtualFree(memory, 0, MEM_RELEASE));
    std::puts("PASS: original NULL read at 0x28 reproduced; 10000 missing and 10000 live "
              "entries execute the production guard without faults or local/data corruption");
}

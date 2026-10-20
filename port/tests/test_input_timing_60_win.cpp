// Offline only: executes the actual EU input counter loop on synthetic memory,
// plus the production SysV entry/copy hooks and trampoline. Never opens a game
// process, Vulkan, a controller, settings, saves or caches.
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <limits>
#include <vector>
#include <windows.h>
#include "input_timing_60.h"

using Sensor = std::array<unsigned char, 0x5500>;
using Copy = void *(TLG_INPUT_ABI *)(void *, const void *, size_t);
static TlgInputUpdate raw_loop, entry;
static TlgInputUpdate raw_stick_loop;
static unsigned stick_mask;
static Copy snapshot_copy;
static unsigned calls;
static Sensor nested_sensor;
static bool nest;

template<class T> static T Read(const Sensor& sensor, size_t offset) {
    T value; std::memcpy(&value, sensor.data() + offset, sizeof(value)); return value;
}
template<class T> static void Write(Sensor& sensor, size_t offset, T value) {
    std::memcpy(sensor.data() + offset, &value, sizeof(value));
}
static void TLG_INPUT_ABI NativeBody(void *object, float dt) {
    auto& sensor = *static_cast<Sensor *>(object);
    ++calls;
    raw_loop(object, dt);
    for (unsigned i=0; i<TLG_INPUT_STICKS; ++i) {
        const size_t live = TLG_INPUT_STICK_LIVE + i*TLG_INPUT_STICK_STRIDE;
        if (stick_mask & (1u<<i)) raw_stick_loop(sensor.data()+live,dt);
        else Write(sensor,live+TLG_INPUT_STICK_AGE,0u);
        std::memcpy(sensor.data()+TLG_INPUT_STICK_SNAPSHOT+i*TLG_INPUT_STICK_STRIDE,
                    sensor.data()+live,TLG_INPUT_STICK_STRIDE);
    }
    std::memcpy(sensor.data() + 0xe48, sensor.data() + 0xd20, 0x128);
    const auto invalid = Read<uint32_t>(sensor, 0xe5c);
    for (unsigned i = 0; i < TLG_INPUT_BUTTONS; ++i)
        if (invalid & (1u << i)) Write(sensor, TLG_INPUT_REMAP_COUNTS + 4*i, 0u);
    if (nest) {
        nest = false;
        Write(nested_sensor, TLG_INPUT_LIVE, 2u);
        entry(nested_sensor.data(), 1.0f / 30.0f);
    }
    std::array<unsigned char, TLG_INPUT_SNAPSHOT_SIZE> live;
    std::memcpy(live.data(), sensor.data() + TLG_INPUT_LIVE, live.size());
    void *result = snapshot_copy(sensor.data() + TLG_INPUT_SNAPSHOT,
                                sensor.data() + TLG_INPUT_LIVE, live.size());
    assert(result == sensor.data() + TLG_INPUT_SNAPSHOT);
    // Normalization must be complete before the original update returns/unlocks.
    assert(!std::memcmp(live.data(), sensor.data() + TLG_INPUT_LIVE, live.size()));
}
static void *TLG_INPUT_ABI NativeCopy(void *dest, const void *src, size_t length) {
    return std::memcpy(dest, src, length);
}
static void ExecutePermissions(void *memory, size_t size) {
    DWORD old;
    assert(VirtualProtect(memory, size, PAGE_EXECUTE_READWRITE, &old));
    assert(FlushInstructionCache(GetCurrentProcess(), memory, size));
}

static void Signatures(const char *elf_path) {
    std::vector<unsigned char> code(TLG_INPUT_SPAN, 0xcc);
    const auto put = [&](size_t offset, const auto& bytes) {
        std::memcpy(code.data() + offset, bytes, sizeof(bytes));
    };
    put(0, tlg_input_prologue);
    put(0x30, tlg_input_dt_capture);
    put(TLG_INPUT_LOOP - TLG_INPUT_UPDATE, tlg_input_loop);
    put(0x23a8, tlg_input_copy_setup);
    put(TLG_INPUT_COPY - TLG_INPUT_UPDATE, tlg_input_copy_call);
    for (unsigned i=0;i<TLG_INPUT_STICKS;++i) {
        unsigned char expected[19];
        const size_t length=tlg_input_stick_copy_setup(expected,i);
        std::memcpy(code.data()+0x2330+(i ? 16+(i-1)*19 : 0),expected,length);
    }
    std::array<unsigned char, 5> flip;
    std::array<unsigned char, 12> dt;
    std::memcpy(flip.data(), tlg_input_60_flip, flip.size());
    std::memcpy(dt.data(), tlg_input_60_dt, dt.size());
    const auto matches = [&](const char *id = "CUSA03745", const char *version = "01.00") {
        return tlg_input_60_matches(id, version, code.data(), code.size(), flip.data(), dt.data());
    };
    assert(matches());
    assert(!matches("CUSA01623"));
    assert(!matches("CUSA03745", "01.01"));
    assert(!matches(nullptr));
    assert(!tlg_input_60_matches("CUSA03745", "01.00", code.data(), code.size()-1, flip.data(), dt.data()));
    const std::array<std::pair<size_t, size_t>, 5> ranges{{
        {0,sizeof(tlg_input_prologue)}, {0x30,sizeof(tlg_input_dt_capture)},
        {TLG_INPUT_LOOP-TLG_INPUT_UPDATE,sizeof(tlg_input_loop)},
        {0x23a8,sizeof(tlg_input_copy_setup)},
        {TLG_INPUT_COPY-TLG_INPUT_UPDATE,sizeof(tlg_input_copy_call)}
    }};
    for (auto [at, length] : ranges) for (size_t i=at; i<at+length; ++i) {
        code[i] ^= 1; assert(!matches()); code[i] ^= 1;
    }
    for (auto& byte : flip) { byte ^= 1; assert(!matches()); byte ^= 1; }
    for (auto& byte : dt) { byte ^= 1; assert(!matches()); byte ^= 1; }
    for (unsigned i=0;i<111;++i) {
        code[0x2330+i]^=1; assert(!matches()); code[0x2330+i]^=1;
    }
    // Original 30 FPS flip, and flip-only/unlocked, MUST NOT enable the hook.
    flip[1] = 1; assert(!matches()); flip[1] = 0;
    const float original_dt[] = {0.035f, 1.0f/30.0f, 0.0316666663f};
    std::memcpy(dt.data(), original_dt, sizeof(original_dt));
    assert(!matches());
    if (elf_path) {
        std::ifstream elf(elf_path, std::ios::binary);
        assert(elf);
        elf.seekg(0x4000 + TLG_INPUT_UPDATE);
        elf.read(reinterpret_cast<char *>(code.data()), code.size());
        assert(elf);
        elf.seekg(0x4000 + TLG_INPUT_FLIP);
        elf.read(reinterpret_cast<char *>(flip.data()), flip.size());
        elf.seekg(0x4000 + TLG_INPUT_DT);
        elf.read(reinterpret_cast<char *>(dt.data()), dt.size());
        assert(elf && !matches()); // untouched real 30 FPS ELF
        std::memcpy(flip.data(), tlg_input_60_flip, flip.size());
        assert(!matches()); // even unlocked must remain untouched
        std::memcpy(dt.data(), tlg_input_60_dt, dt.size());
        assert(matches()); // all real code signatures, with 60 FPS bytes in RAM only
        std::vector<unsigned char> stick(TLG_INPUT_STICK_SPAN);
        elf.seekg(0x4000+TLG_INPUT_STICK_UPDATE);
        elf.read(reinterpret_cast<char *>(stick.data()),stick.size());
        assert(elf && tlg_input_stick_matches(stick.data(),stick.size()));
        const std::array<std::pair<size_t,size_t>,4> sites{{{0x70,sizeof(tlg_stick_age_load)},
            {0x12ad,sizeof(tlg_stick_age_step)},{0x13c5,sizeof(tlg_stick_age_store)},
            {0x1ab5,sizeof(tlg_stick_age_copy)}}};
        for (auto [offset,length] : sites) for (size_t i=offset;i<offset+length;++i) {
            stick[i]^=1; assert(!tlg_input_stick_matches(stick.data(),stick.size())); stick[i]^=1;
        }
        std::puts("PASS: real EU ELF signatures; 30 FPS/unlocked rejected; all guarded-byte mutations rejected");
    }
}

static void HoldArithmetic() {
    for (int fps : {30,45,60,120}) {
        TlgInputHold hold{};
        for (int frame=0; frame<fps*3; ++frame) {
            const int expected = 1 + static_cast<int>(std::floor(frame * 30.0 / fps + 0.00001));
            assert(tlg_input_hold_step(&hold, frame+1, 1.0f/fps) == expected);
        }
        assert(tlg_input_hold_step(&hold, 0, 1.0f/fps) == 0);
        assert(tlg_input_hold_step(&hold, 1, 1.0f/fps) == 1);
    }
    TlgInputHold variable{};
    double elapsed = 0;
    for (unsigned i=1; i<10000; ++i) {
        float dt = i%2 ? 1.0f/45.0f : 1.0f/60.0f;
        if (i>1) elapsed += dt;
        assert(tlg_input_hold_step(&variable,i,dt) == 1 + static_cast<int>(elapsed*30.0 + 0.00001));
    }
    TlgInputHold paused{};
    assert(tlg_input_hold_step(&paused, 1, 0) == 1);
    for (unsigned i=2; i<100; ++i) assert(tlg_input_hold_step(&paused,i,0) == 1);
    assert(tlg_input_hold_step(&paused,100,std::numeric_limits<float>::quiet_NaN()) == 1);
    assert(tlg_input_hold_step(&paused,101,std::numeric_limits<float>::infinity()) == 1);
    assert(tlg_input_hold_step(&paused,102,-1) == 1);
    assert(tlg_input_hold_step(&paused,103,1.0f/30) == 2);
    assert(tlg_input_hold_step(&paused,103,1.0f/30) == 2); // duplicate
    assert(tlg_input_hold_step(&paused,1,1.0f/30) == 1); // reset/reused instance
    assert(tlg_input_hold_step(&paused,2,std::numeric_limits<float>::max()) == INT32_MAX);
    assert(tlg_input_hold_step(&paused,3,1) == INT32_MAX);
    std::puts("PASS: 30/45/60/120 Hz and variable-dt replay, release/repress, pause, NaN/Inf, saturation");
}

static void NativeHooks() {
    auto *memory = static_cast<unsigned char *>(VirtualAlloc(nullptr,8192,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    assert(memory);
    // Real raw-counter loop. Set up exactly its R13/RSI/ECX/XMM1/EAX inputs;
    // skip the loop-back increment on the first button, as the original does.
    const unsigned char setup[] = {
        0x41,0x55,0x49,0x89,0xfd,0x48,0x8d,0xb7,0x20,0x0d,0,0,
        0x31,0xc9,0x0f,0x28,0xc8,0x8b,0x06,0xeb,0x05
    };
    auto *loop = memory+512;
    std::memcpy(loop,setup,sizeof(setup));
    std::memcpy(loop+sizeof(setup),tlg_input_loop,sizeof(tlg_input_loop));
    const unsigned char tail[] = {0x41,0x5d,0xc3};
    std::memcpy(loop+sizeof(setup)+sizeof(tlg_input_loop),tail,sizeof(tail));
    raw_loop = reinterpret_cast<TlgInputUpdate>(loop);
    // Native analog increment/store instructions, on a synthetic stick block.
    auto *stick_code = memory+4096;
    const unsigned char stick_setup[] = {0x55,0x48,0x89,0xe5,0x41,0x54,
        0x48,0x81,0xec,0x20,2,0,0,0x49,0x89,0xfc,
        0x41,0x8b,0x84,0x24,0xe0,1,0,0,0x89,0x85,0xec,0xfd,0xff,0xff};
    const unsigned char stick_tail[] = {0x48,0x81,0xc4,0x20,2,0,0,0x41,0x5c,0x5d,0xc3};
    size_t stick_at=0;
    const auto emit_stick = [&](const auto& bytes) {
        std::memcpy(stick_code+stick_at,bytes,sizeof(bytes)); stick_at+=sizeof(bytes);
    };
    emit_stick(stick_setup); emit_stick(tlg_stick_age_step);
    emit_stick(tlg_stick_age_store); emit_stick(stick_tail);
    raw_stick_loop = reinterpret_cast<TlgInputUpdate>(stick_code);

    // Full original prologue + body call + matching original epilogue.
    std::memcpy(memory,tlg_input_prologue,sizeof(tlg_input_prologue));
    auto *body = memory+sizeof(tlg_input_prologue);
    body[0]=0x48; body[1]=0xb8;
    const uintptr_t native = reinterpret_cast<uintptr_t>(NativeBody);
    std::memcpy(body+2,&native,8); body[10]=0xff; body[11]=0xd0;
    const unsigned char epilogue[] = {0x48,0x81,0xc4,0xb8,0x02,0,0,0x5b,0x41,0x5c,
        0x41,0x5d,0x41,0x5e,0x41,0x5f,0x5d,0xc3};
    std::memcpy(body+12,epilogue,sizeof(epilogue));
    entry = reinterpret_cast<TlgInputUpdate>(memory);

    // A separate original memcpy call with correct SysV stack alignment.
    auto *copy_bridge=memory+1024;
    const unsigned char sub[] = {0x48,0x83,0xec,0x08};
    const unsigned char ret[] = {0x48,0x83,0xc4,0x08,0xc3};
    std::memcpy(copy_bridge,sub,sizeof(sub));
    tlg_input_abs_jump(memory+1100,reinterpret_cast<uintptr_t>(NativeCopy));
    assert(tlg_input_rel_branch(copy_bridge+4,reinterpret_cast<uintptr_t>(copy_bridge+4),
                               reinterpret_cast<uintptr_t>(memory+1100),5,1));
    std::memcpy(copy_bridge+9,ret,sizeof(ret));
    snapshot_copy = reinterpret_cast<Copy>(copy_bridge);
    ExecutePermissions(memory,8192);
    Sensor sensor{};
    Write(sensor,TLG_INPUT_LIVE,1u);
    for (unsigned i=1; i<=60; ++i) entry(sensor.data(),1.0f/60);
    assert(Read<uint32_t>(sensor,TLG_INPUT_LIVE_COUNTS)==60);
    assert(Read<uint32_t>(sensor,TLG_INPUT_SNAPSHOT_COUNTS)==60);
    // Adjacent interval timer is already seconds-based in the real native loop.
    assert(std::fabs(Read<float>(sensor,0xdc0)-1.0f)<0.00001f);

    auto *stubs=memory+2048;
    tlg_input_build_stubs(stubs,reinterpret_cast<uintptr_t>(memory+TLG_INPUT_ENTRY_SIZE),
                         reinterpret_cast<uintptr_t>(tlg_input_60_update),
                         reinterpret_cast<uintptr_t>(tlg_input_60_copy));
    tlg_input_60_configure(reinterpret_cast<TlgInputUpdate>(stubs));
    assert(tlg_input_rel_branch(memory,reinterpret_cast<uintptr_t>(memory),
                               reinterpret_cast<uintptr_t>(stubs+TLG_INPUT_ENTRY_RELAY),8,0));
    assert(tlg_input_rel_branch(copy_bridge+4,reinterpret_cast<uintptr_t>(copy_bridge+4),
                               reinterpret_cast<uintptr_t>(stubs+TLG_INPUT_COPY_RELAY),5,1));
    ExecutePermissions(memory,8192);
    for (unsigned run=0; run<100; ++run) {
        sensor.fill(0);
        // Release first to reset history, then a full 17-button chord.
        entry(sensor.data(),1.0f/60);
        Write(sensor,TLG_INPUT_LIVE,0x1ffffu);
        for (unsigned i=1; i<=240; ++i) {
            if (i==35) Write(sensor,0xd34,2u); // remap invalid bit, copied to E5C
            if (i==45) Write(sensor,0xd34,0u);
            entry(sensor.data(),1.0f/60);
            for (unsigned button=0; button<TLG_INPUT_BUTTONS; ++button) {
                assert(Read<uint32_t>(sensor,TLG_INPUT_LIVE_COUNTS+4*button)==i);
                assert(Read<uint32_t>(sensor,TLG_INPUT_SNAPSHOT_COUNTS+4*button)==(i+1)/2);
                const bool invalid=button==1 && i>=35 && i<45;
                assert(Read<uint32_t>(sensor,TLG_INPUT_SNAPSHOT_REMAP+4*button)==(invalid?0:(i+1)/2));
            }
        }
    }
    // Nested update contexts retain separate dt and held histories.
    sensor.fill(0);
    entry(sensor.data(),1.0f/60);
    Write(sensor,TLG_INPUT_LIVE,1u);
    for (unsigned i=1; i<=60; ++i) {
        nest=true; entry(sensor.data(),1.0f/60);
        assert(Read<uint32_t>(sensor,TLG_INPUT_SNAPSHOT_COUNTS)==(i+1)/2);
        assert(Read<uint32_t>(nested_sensor,TLG_INPUT_SNAPSHOT_COUNTS+4)==i);
    }
    // Wrong-context copies retain standard memcpy semantics, no normalization.
    nest=false;
    for (unsigned fps : {30u,45u,60u,120u}) {
        stick_mask=0;
        sensor.fill(0);
        for (unsigned j=0;j<TLG_INPUT_STICKS;++j) {
            const size_t live=TLG_INPUT_STICK_LIVE+j*TLG_INPUT_STICK_STRIDE;
            for (size_t k=0;k<TLG_INPUT_STICK_STRIDE;++k) sensor[live+k]=(j*17+k)%251;
            Write(sensor,live+TLG_INPUT_STICK_AGE,0u);
        }
        entry(sensor.data(),1.0f/fps); // reset history
        stick_mask=0x3f;
        for (unsigned i=1;i<=fps*4;++i) {
            entry(sensor.data(),1.0f/fps);
            const unsigned expected=1+static_cast<unsigned>((i-1)*30.0/fps+0.00001);
            for (unsigned j=0;j<TLG_INPUT_STICKS;++j) {
                const size_t live=TLG_INPUT_STICK_LIVE+j*TLG_INPUT_STICK_STRIDE;
                const size_t snap=TLG_INPUT_STICK_SNAPSHOT+j*TLG_INPUT_STICK_STRIDE;
                assert(Read<uint32_t>(sensor,live+TLG_INPUT_STICK_AGE)==i);
                assert(Read<uint32_t>(sensor,snap+TLG_INPUT_STICK_AGE)==expected);
                for (size_t k=0;k<TLG_INPUT_STICK_STRIDE;++k)
                    if (k<TLG_INPUT_STICK_AGE || k>=TLG_INPUT_STICK_AGE+4)
                        assert(sensor[live+k]==sensor[snap+k]);
            }
        }
        // Pause must not age the published count, even when native counts advance.
        const unsigned before=Read<uint32_t>(sensor,TLG_INPUT_STICK_SNAPSHOT+TLG_INPUT_STICK_AGE);
        for (unsigned i=0;i<10;++i) entry(sensor.data(),0);
        assert(Read<uint32_t>(sensor,TLG_INPUT_STICK_SNAPSHOT+TLG_INPUT_STICK_AGE)==before);
        // A direction-change reset and a release/repress restart immediately.
        Write(sensor,TLG_INPUT_STICK_LIVE+TLG_INPUT_STICK_AGE,0u);
        entry(sensor.data(),1.0f/fps);
        assert(Read<uint32_t>(sensor,TLG_INPUT_STICK_SNAPSHOT+TLG_INPUT_STICK_AGE)==1);
        stick_mask=0; entry(sensor.data(),1.0f/fps);
        assert(Read<uint32_t>(sensor,TLG_INPUT_STICK_SNAPSHOT+TLG_INPUT_STICK_AGE)==0);
    }
    std::puts("PASS: six native analog hold counters, 30/45/60/120 Hz, release/direction reset/pause; all non-age stick bytes unchanged");
    std::array<unsigned char,32> src{}, dst{}; src[5]=77;
    assert(tlg_input_60_copy(dst.data(),src.data(),src.size())==dst.data());
    assert(src==dst);
    std::array<unsigned char,8> untouched{}; untouched.fill(0xa5);
    assert(!tlg_input_rel_branch(untouched.data(),0x1000,0x100000000ull,8,0));
    for (auto byte : untouched) assert(byte==0xa5);
    tlg_input_60_configure(nullptr);
    assert(VirtualFree(memory,0,MEM_RELEASE));
    std::printf("PASS: real native loop + production two-site SysV hooks, %u updates; live counters/timers unchanged; remap/nested contexts correct\n",calls);
}

int main(int argc,char **argv) {
    static_assert(sizeof(tlg_input_loop)==TLG_INPUT_LOOP_SIZE);
    Signatures(argc>1?argv[1]:nullptr);
    HoldArithmetic();
    NativeHooks();
}

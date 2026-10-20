/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TLG_INPUT_TIMING_60_H
#define TLG_INPUT_TIMING_60_H
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* CUSA03745 01.00 only. CharacterSensorExt::update increments DButtonInputFrame
 * once per update, unlike its adjacent interval timers, which already use dt.
 * The animation graph uses remapped hold counts for long-press/cancel/reach
 * conditions (Cross >4, Circle/R2 >6, R1 >10, among others).
 *
 * Keep live counters, axes, trigger/repeat bits, seconds-based timers and stamina
 * unchanged. Normalize published button and analog continuous-hold snapshots,
 * inside the original sensor lock, immediately after its snapshot memcpy.
 * These are input-timing corrections, not a verified fix for all climbing AI.
 */
enum {
    TLG_INPUT_UPDATE = 0x6d62b0,
    TLG_INPUT_COPY = 0x6d87b4,
    TLG_INPUT_LOOP = 0x6d7a70,
    TLG_INPUT_LOOP_SIZE = 0x68,
    TLG_INPUT_SPAN = 0x3af1,
    TLG_INPUT_ENTRY_SIZE = 8,
    TLG_INPUT_COPY_SIZE = 5,
    TLG_INPUT_BUTTONS = 17,
    TLG_INPUT_LIVE = 0xd20,
    TLG_INPUT_LIVE_COUNTS = 0xd38,
    TLG_INPUT_REMAP_COUNTS = 0xe60,
    TLG_INPUT_SNAPSHOT = 0x38b0,
    TLG_INPUT_SNAPSHOT_COUNTS = 0x38c8,
    TLG_INPUT_SNAPSHOT_REMAP = 0x39f0,
    TLG_INPUT_SNAPSHOT_SIZE = 0x268,
    TLG_INPUT_STICKS = 6,
    TLG_INPUT_STICK_LIVE = 0x50,
    TLG_INPUT_STICK_SNAPSHOT = 0x2be0,
    TLG_INPUT_STICK_STRIDE = 0x1f0,
    TLG_INPUT_STICK_AGE = 0x1e0,
    TLG_INPUT_STICK_UPDATE = 0x6dbf70,
    TLG_INPUT_STICK_SPAN = 0x1ac6,
    TLG_INPUT_TRAMPOLINE = 0,
    TLG_INPUT_ENTRY_RELAY = 32,
    TLG_INPUT_COPY_RELAY = 64,
    TLG_INPUT_STUB_SIZE = 78,
    TLG_INPUT_FLIP = 0xb8be7c,
    TLG_INPUT_DT = 0x14d9920
};

static const unsigned char tlg_input_prologue[] = {
    0x55,0x48,0x89,0xe5,0x41,0x57,0x41,0x56,0x41,0x55,0x41,0x54,
    0x53,0x48,0x81,0xec,0xb8,0x02,0x00,0x00
};
static const unsigned char tlg_input_loop[] = {
    0x8b,0x06,0x48,0xff,0xc1,0xba,0x01,0,0,0,0xd3,0xe2,0x0f,0xa3,0xc8,
    0xb8,0,0,0,0,0x73,0x0a,0x41,0x8b,0x84,0x8d,0x38,0x0d,0,0,0xff,0xc0,
    0x41,0x89,0x84,0x8d,0x38,0x0d,0,0,0x41,0x8b,0x84,0x8d,0xc0,0x0d,0,0,
    0x41,0x89,0x84,0x8d,0x04,0x0e,0,0,0x41,0x85,0x95,0x24,0x0d,0,0,
    0x74,0x0f,0xc5,0xf8,0x57,0xc0,0xeb,0x11,0x66,0x0f,0x1f,0x84,0,0,0,0,0,
    0xc5,0xf9,0x6e,0xc0,0xc5,0xfa,0x58,0xc1,0xc4,0xc1,0x7a,0x11,0x84,0x8d,
    0xc0,0x0d,0,0,0x48,0x83,0xf9,0x10,0x75,0x98
};
static const unsigned char tlg_input_copy_setup[] = {
    0x48,0x8b,0xb5,0x60,0xfd,0xff,0xff,0x49,0x8d,0xbd,0xb0,0x38,0,0,
    0xba,0x68,0x02,0,0
};
static const unsigned char tlg_input_copy_call[] = {0xe8,0xef,0x95,0xdd,0x00};
static const unsigned char tlg_input_dt_capture[] = {0xc5,0xf9,0x7f,0x85,0x20,0xfe,0xff,0xff};
static const unsigned char tlg_input_60_flip[] = {0xbe,0,0,0,0};
static const float tlg_input_60_dt[] = {0.0175f, 1.0f / 60.0f, 0.0158333331f};

/* Verify each original stick copy (including its exact source/destination and
 * callee), not merely the common helper. All six copies precede our memcpy hook.
 */
static inline size_t tlg_input_stick_copy_setup(unsigned char out[19], unsigned index) {
    uint32_t destination = TLG_INPUT_STICK_SNAPSHOT + index*TLG_INPUT_STICK_STRIDE;
    uint32_t source = TLG_INPUT_STICK_LIVE + index*TLG_INPUT_STICK_STRIDE;
    const unsigned char dest[] = {0x49,0x8d,0xbd};
    memcpy(out,dest,3); memcpy(out+3,&destination,4);
    size_t at=7;
    if (!index) { const unsigned char src[] = {0x49,0x8d,0x75,0x50}; memcpy(out+at,src,4); at+=4; }
    else { const unsigned char src[] = {0x49,0x8d,0xb5}; memcpy(out+at,src,3); memcpy(out+at+3,&source,4); at+=7; }
    uint32_t site = 0x6d85e0 + (index ? 16+(index-1)*19 : 0);
    int32_t relative = (int32_t)(0x6dd5f0-(site+at+5));
    out[at++]=0xe8; memcpy(out+at,&relative,4); return at+4;
}
static inline int tlg_input_stick_copies_match(const unsigned char *function) {
    for (unsigned i=0;i<TLG_INPUT_STICKS;++i) {
        unsigned char expected[19];
        size_t length=tlg_input_stick_copy_setup(expected,i);
        size_t offset=0x2330+(i ? 16+(i-1)*19 : 0);
        if (memcmp(function+offset,expected,length)) return 0;
    }
    return 1;
}

static const unsigned char tlg_stick_age_load[] = {0x41,0x8b,0x94,0x24,0xe0,1,0,0};
static const unsigned char tlg_stick_age_step[] = {0x8b,0xbd,0xec,0xfd,0xff,0xff,0xff,0xc7,0x41,0x89,0xf9};
static const unsigned char tlg_stick_age_store[] = {0x45,0x89,0x8c,0x24,0xe0,1,0,0};
static const unsigned char tlg_stick_age_copy[] = {
    0xc4,0xc1,0x7c,0x10,0x86,0xd0,1,0,0,0xc5,0xfc,0x11,0x83,0xd0,1,0,0
};
static inline int tlg_input_stick_matches(const unsigned char *code, size_t size) {
    return code && size >= TLG_INPUT_STICK_SPAN &&
        !memcmp(code + 0x70, tlg_stick_age_load, sizeof(tlg_stick_age_load)) &&
        !memcmp(code + 0x12ad, tlg_stick_age_step, sizeof(tlg_stick_age_step)) &&
        !memcmp(code + 0x13c5, tlg_stick_age_store, sizeof(tlg_stick_age_store)) &&
        !memcmp(code + 0x1ab5, tlg_stick_age_copy, sizeof(tlg_stick_age_copy));
}

/* Pass already-mapped ranges of these sizes. Actual patched bytes, not a launcher
 * preference or FPS overlay, gate the hook: 30 FPS and unlocked are untouched.
 */
static inline int tlg_input_60_matches(const char *serial, const char *version,
        const unsigned char *function, size_t size,
        const unsigned char *flip, const unsigned char *dt) {
    return serial && version && function && flip && dt &&
        !strcmp(serial, "CUSA03745") && !strcmp(version, "01.00") &&
        size >= TLG_INPUT_SPAN &&
        !memcmp(flip, tlg_input_60_flip, sizeof(tlg_input_60_flip)) &&
        !memcmp(dt, tlg_input_60_dt, sizeof(tlg_input_60_dt)) &&
        !memcmp(function, tlg_input_prologue, sizeof(tlg_input_prologue)) &&
        !memcmp(function + 0x30, tlg_input_dt_capture, sizeof(tlg_input_dt_capture)) &&
        tlg_input_stick_copies_match(function) &&
        !memcmp(function + TLG_INPUT_LOOP - TLG_INPUT_UPDATE,
                tlg_input_loop, sizeof(tlg_input_loop)) &&
        !memcmp(function + 0x23a8, tlg_input_copy_setup, sizeof(tlg_input_copy_setup)) &&
        !memcmp(function + TLG_INPUT_COPY - TLG_INPUT_UPDATE,
                tlg_input_copy_call, sizeof(tlg_input_copy_call));
}

typedef struct { uint32_t previous; double ticks; } TlgInputHold;

static inline int32_t tlg_input_hold_step(TlgInputHold *hold, uint32_t raw, float dt) {
    if (!raw) { hold->previous = 0; hold->ticks = 0; return 0; }
    /* A new press is immediately count 1 at BOTH rates. Subsequent intervals are
     * 30 Hz-equivalent elapsed time: 60 Hz produces 1,1,2,2,3,3... . Starting at
     * zero and clamping to 1 would incorrectly prolong the first hold count.
     * A duplicate update or dt=0 does not age a held input. NaN/Inf/negative dt
     * cannot overflow the output. No wall clock is used during paused gameplay.
     */
    if (!hold->previous || raw < hold->previous) hold->ticks = 1.0;
    else if (raw > hold->previous && dt > 0.0f && dt <= 3.402823466e38f) {
        hold->ticks += 30.0 * (double)dt;
        if (hold->ticks > INT32_MAX) hold->ticks = INT32_MAX;
    }
    hold->previous = raw;
    double rounded = hold->ticks + 0.00001; /* float(1/60) accumulated roundoff */
    return rounded >= INT32_MAX ? INT32_MAX : (int32_t)rounded;
}

static inline void tlg_input_abs_jump(unsigned char *out, uintptr_t target) {
    static const unsigned char jump[] = {0xff,0x25,0,0,0,0};
    memcpy(out, jump, sizeof(jump)); memcpy(out + sizeof(jump), &target, sizeof(target));
}
static inline void tlg_input_build_stubs(unsigned char *out, uintptr_t resume,
                                        uintptr_t entry, uintptr_t copy) {
    memset(out, 0xcc, TLG_INPUT_STUB_SIZE);
    memcpy(out, tlg_input_prologue, TLG_INPUT_ENTRY_SIZE);
    tlg_input_abs_jump(out + TLG_INPUT_ENTRY_SIZE, resume);
    tlg_input_abs_jump(out + TLG_INPUT_ENTRY_RELAY, entry);
    tlg_input_abs_jump(out + TLG_INPUT_COPY_RELAY, copy);
}
/* Build into temporary buffers first, so an out-of-range relay never leaves
 * either of the two guest sites partially patched. No scratch register clobber.
 */
static inline int tlg_input_rel_branch(unsigned char *out, uintptr_t from,
                                      uintptr_t to, size_t size, int call) {
    int64_t delta = (int64_t)to - (int64_t)(from + 5);
    if (size < 5 || delta < INT32_MIN || delta > INT32_MAX) return 0;
    int32_t relative = (int32_t)delta;
    out[0] = call ? 0xe8 : 0xe9;
    memcpy(out + 1, &relative, sizeof(relative));
    memset(out + 5, 0x90, size - 5);
    return 1;
}

#ifdef _WIN32
#define TLG_INPUT_ABI __attribute__((sysv_abi))
typedef void (TLG_INPUT_ABI *TlgInputUpdate)(void *, float);
#ifdef __cplusplus
extern "C" {
#endif
void tlg_input_60_configure(TlgInputUpdate original);
void TLG_INPUT_ABI tlg_input_60_update(void *sensor, float dt);
void *TLG_INPUT_ABI tlg_input_60_copy(void *destination, const void *source, size_t size);
#ifdef __cplusplus
}
#endif
#endif
#endif

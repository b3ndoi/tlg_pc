/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TLG_RELOAD_NULL_GUARD_H
#define TLG_RELOAD_NULL_GUARD_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* CUSA03745 EU 01.00, function +0x21e410. During checkpoint/scene reload the
 * object table lookup may return NULL. The original code reads [rax+0x28]
 * before testing the result. Skip that missing entry via the function's existing
 * degenerate-entry loop-advance path (+0x21e8dd).
 *
 * The output range was already reserved and default-initialized by +0x220c10.
 * Advance BOTH original loop indices; do not compact entries or return early.
 * Non-null entries replay both displaced instructions and resume at +0x21e4ad.
 * The next instruction there tests r15; the skip target also overwrites flags.
 * Thus the guard's TEST does not change any live flags, registers or stack state.
 * This is an exact-site compatibility guard, NOT general AV recovery.
 */
enum {
    TLG_RELOAD_FUNCTION = 0x21e410,
    TLG_RELOAD_SITE = 0x21e4a5,
    TLG_RELOAD_ADVANCE = 0x21e8dd,
    TLG_RELOAD_LENGTH = 8,
    TLG_RELOAD_SPAN = TLG_RELOAD_ADVANCE - TLG_RELOAD_FUNCTION + 15,
    TLG_RELOAD_STUB_SIZE = 41
};
static const unsigned char tlg_reload_prologue[] = {
    0x55,0x48,0x89,0xe5,0x41,0x57,0x41,0x56,0x41,0x55,0x41,0x54,0x53,0x48,0x83,0xec,0x68
};
static const unsigned char tlg_reload_reserve[] = {
    0x8b,0x71,0x50,0x85,0xf6,0x0f,0x84,0xab,0x04,0x00,0x00,0x44,0x8b,0x77,0x10,0x48,0x83,0xc7,0x08,0x48,0x89,0xcb,0x48,0x89,0xbd,0x78,0xff,0xff,0xff,0x48,0x89,0x5d,0x90,0xe8,0xb4,0x27,0x00,0x00
};
static const unsigned char tlg_reload_lookup[] = {
    0x49,0x8b,0x59,0x48,0x49,0x63,0xc4,0x49,0x8b,0x49,0x28,0x41,0xb8,0x00,0x00,0x00,0x00,0x4c,0x8d,0x2c,0x40,0x49,0xc1,0xe5,0x06,0x4a,0x63,0x84,0x2b,0xa0,0x00,0x00,0x00,0x48,0x8b,0x04,0xc1,0x4c,0x8b,0x78,0x28,0x48,0x89,0x45,0x98,0x4d,0x85,0xff,0x74,0x6f
};
static const unsigned char tlg_reload_advance[] = {
    0x41,0xff,0xc4,0xff,0xc7,0x45,0x3b,0x61,0x50,0x0f,0x82,0x94,0xfb,0xff,0xff
};
static const unsigned char tlg_reload_original[TLG_RELOAD_LENGTH] = {
    0x4c,0x8b,0x78,0x28, /* mov r15,[rax+0x28] */
    0x48,0x89,0x45,0x98  /* mov [rbp-0x68],rax */
};

static inline int tlg_reload_guard_matches(const char *serial, const char *version,
                                          const unsigned char *function, size_t size) {
    return serial && version && function && !strcmp(serial, "CUSA03745") &&
        !strcmp(version, "01.00") && size >= TLG_RELOAD_SPAN &&
        !memcmp(function, tlg_reload_prologue, sizeof(tlg_reload_prologue)) &&
        !memcmp(function + 0x26, tlg_reload_reserve, sizeof(tlg_reload_reserve)) &&
        !memcmp(function + 0x70, tlg_reload_lookup, sizeof(tlg_reload_lookup)) &&
        !memcmp(function + TLG_RELOAD_ADVANCE - TLG_RELOAD_FUNCTION,
                tlg_reload_advance, sizeof(tlg_reload_advance));
}

/* Absolute RIP-indirect jumps preserve every general register, including rax.
 * The only rel32 requirement is the image -> stub detour (checked by installer).
 * Branches go straight back to original code; no C call or exception is needed.
 */
static inline size_t tlg_reload_guard_build_stub(unsigned char *out, uintptr_t resume,
                                                uintptr_t advance) {
    static const unsigned char jump[] = {0xff,0x25,0,0,0,0};
    static const unsigned char test[] = {0x48,0x85,0xc0,0x75,0x0e}; /* test rax; jnz valid */
    size_t at = 0;
    memcpy(out + at, test, sizeof(test)); at += sizeof(test);
    memcpy(out + at, jump, sizeof(jump)); at += sizeof(jump);
    memcpy(out + at, &advance, sizeof(advance)); at += sizeof(advance);
    memcpy(out + at, tlg_reload_original, sizeof(tlg_reload_original));
    at += sizeof(tlg_reload_original);
    memcpy(out + at, jump, sizeof(jump)); at += sizeof(jump);
    memcpy(out + at, &resume, sizeof(resume)); at += sizeof(resume);
    return at;
}
#endif

/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TLG_CLOCK_SYNC_60_H
#define TLG_CLOCK_SYNC_60_H
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define TLG_CLOCK_ABI __attribute__((sysv_abi))
enum { TLG_CLOCK_SMOOTH = 0xc51940, TLG_CLOCK_SPAN = 0x25c,
       TLG_CLOCK_GRID = 0x14d9938, TLG_CLOCK_PHYSICS = 0xe99dd6,
       TLG_CLOCK_PHYSICS_ZERO = 0xe99d62, TLG_CLOCK_PHYSICS_CONSTANTS = 0x14da064,
       TLG_CLOCK_CALL = 0xcfeea5, TLG_CLOCK_VTABLE_A = 0x16b9d88,
       TLG_CLOCK_VTABLE_B = 0x16c8168, TLG_CLOCK_CALL_BYTES = 5 };

/* Fingerprints only: complete original game routines are not distributed. */
enum { TLG_CLOCK_PHYSICS_SPAN = 104, TLG_CLOCK_ZERO_SPAN = 19 };
#ifdef __cplusplus
extern "C" {
#endif
int tlg_clock_60_code_matches(const unsigned char *smooth,
    const unsigned char *physics, const unsigned char *physics_zero);
#ifdef __cplusplus
}
#endif
static const unsigned char tlg_clock_direct_call[] = {0xe8,0x96,0x2a,0xf5,0xff};

static inline int tlg_clock_60_matches(const char *serial, const char *version,
        const unsigned char *smooth, const unsigned char *physics,
        const unsigned char *physics_zero, const unsigned char *physics_constants,
        const unsigned char *flip, const unsigned char *snap, const unsigned char *grid,
        const unsigned char *direct_call, uintptr_t table_a, uintptr_t table_b, uintptr_t image_base) {
    const unsigned char expected_flip[] = {0xbe,0,0,0,0};
    const float expected_snap[] = {0.0175f,1.0f/60.0f,0.0158333331f};
    const float expected_grid[] = {36000000.0f,0.1f,1.0f/36000000.0f};
    const float expected_physics[] = {0.00001f,360.0f,0.1f,0.5f,1.0f/360.0f};
    return serial && version && smooth && physics && physics_zero && physics_constants && flip && snap && grid && direct_call &&
        !strcmp(serial,"CUSA03745") && !strcmp(version,"01.00") &&
        tlg_clock_60_code_matches(smooth,physics,physics_zero) &&
        !memcmp(physics_constants,expected_physics,sizeof(expected_physics)) &&
        !memcmp(flip,expected_flip,sizeof(expected_flip)) &&
        !memcmp(snap,expected_snap,sizeof(expected_snap)) &&
        !memcmp(grid,expected_grid,sizeof(expected_grid)) &&
        !memcmp(direct_call,tlg_clock_direct_call,sizeof(tlg_clock_direct_call)) &&
        table_a==image_base+TLG_CLOCK_SMOOTH && table_b==image_base+TLG_CLOCK_SMOOTH;
}

typedef struct { double residual; void *app, *timing; uint32_t frame; } TlgClockCarry;
typedef void (TLG_CLOCK_ABI *TlgClockSmooth)(void *,float,float);

/* Physics independently does floor(dt*360+0.1). Publish ONE shared grid value
 * to animation/AI AND physics, retaining fractional seconds across frames.
 * A zero tick is permitted; a positive slowdown cannot lock at zero forever.
 * No minimum-speed clamp, catch-volume change, wall clock, or extra solver work.
 */
static inline float tlg_clock_60_quantize(TlgClockCarry *state,float fine) {
    if (!(fine > 0.0f) || !isfinite(fine)) { state->residual=0; return 0; }
    double available=state->residual+(double)fine;
    double ticks=floor(available*360.0+0.1);
    if (ticks<0) ticks=0;
    float result=(float)ticks*(1.0f/360.0f);
    state->residual=available-(double)result;
    return result;
}

#ifdef __cplusplus
extern "C" {
#endif
void tlg_clock_60_configure(TlgClockSmooth original);
void TLG_CLOCK_ABI tlg_clock_60_smooth(void *app,float time,float dt);
#ifdef __cplusplus
}
#endif
#endif

/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TLG_CLIMB_DIAGNOSTICS_H
#define TLG_CLIMB_DIAGNOSTICS_H
#include <math.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

/* Exact EU 01.00 CharacterSensorExt schema, independently checked against its
 * native property registrations. No pointer chasing and no sensor writes.
 * Values are the latest published sensor state, not a trace of active graph
 * states. In particular "blocked" below is a zero Hang_Moveable scalar, not
 * proof that any particular animation transition was taken.
 */
typedef struct { uint32_t registration, field; } TlgClimbField;
static const TlgClimbField tlg_climb_fields[] = {
    {0x6a41dc,0x2ca0}, /* AnalogStickLeft_rawInput */
    {0x6a5246,0x2d44}, /* AnalogStickLeft_NormMagnitude */
    {0x69fff5,0x3b34}, /* TrackingPoint_Type */
    {0x6a059d,0x3b60}, /* TrackingPoint_SmoothAccelerationMS */
    {0x6a071b,0x3b70}, /* TrackingPoint_SmoothAccelerationNormXzMS */
    {0x6a2360,0x3ef0}, /* Collider_ReceiveImpulseNorm */
    {0x6b58f8,0x4090}, /* Hang_IsDetect */
    {0x6b6f0a,0x4160}, /* Hang_Moveable */
    {0x6b7088,0x4164}, /* Hang_TotalSlopeAngleOfMoveDirection */
};

static inline int tlg_climb_schema_matches(const unsigned char *image, size_t size) {
    const unsigned char prefix[] = {0xc7,0x85,0x50,0xff,0xff,0xff};
    if (!image) return 0;
    for (size_t n=0;n<sizeof(tlg_climb_fields)/sizeof(tlg_climb_fields[0]);++n) {
        const TlgClimbField f=tlg_climb_fields[n];
        if (f.registration>size || size-f.registration<220) return 0;
        int found=0;
        for (size_t at=0;at+sizeof(prefix)+4<=220;++at) {
            const unsigned char *p=image+f.registration+at;
            uint32_t field;
            memcpy(&field,p+sizeof(prefix),4);
            if (!memcmp(p,prefix,sizeof(prefix)) && field==f.field) { found=1; break; }
        }
        if (!found) return 0;
    }
    return 1;
}

typedef struct {
    uint32_t buttons, tracking, detected;
    float axis_x,axis_y,magnitude,moveable,slope,accel_x,accel_y,accel_z,accel_xz,impulse;
} TlgClimbSample;

static inline void tlg_climb_capture(const void *sensor,TlgClimbSample *s) {
    const unsigned char *p=(const unsigned char *)sensor;
    memcpy(&s->buttons,p+0x38b0,4);
    memcpy(&s->tracking,p+0x3b34,4);
    memcpy(&s->detected,p+0x4090,4);
    memcpy(&s->axis_x,p+0x2ca0,4); memcpy(&s->axis_y,p+0x2ca4,4);
    memcpy(&s->magnitude,p+0x2d44,4); memcpy(&s->moveable,p+0x4160,4);
    memcpy(&s->slope,p+0x4164,4);
    memcpy(&s->accel_x,p+0x3b60,4); memcpy(&s->accel_y,p+0x3b64,4);
    memcpy(&s->accel_z,p+0x3b68,4); memcpy(&s->accel_xz,p+0x3b70,4);
    memcpy(&s->impulse,p+0x3ef0,4);
}

typedef struct {
    uint32_t samples,held,detected,blocked,above_shake_threshold,invalid;
    float peak_accel_xz,peak_abs_accel_y,peak_impulse,minimum_moveable;
} TlgClimbSummary;

static inline void tlg_climb_accumulate(TlgClimbSummary *a,const TlgClimbSample *s) {
    ++a->samples;
    if (isfinite(s->magnitude) && s->magnitude>0.2f) ++a->held;
    if (s->detected==1) ++a->detected;
    if (!isfinite(s->moveable) || !isfinite(s->accel_xz) || !isfinite(s->accel_y) ||
            !isfinite(s->impulse)) { ++a->invalid; return; }
    if (s->detected==1 && s->moveable==0) ++a->blocked;
    if (s->accel_xz>12.5f) ++a->above_shake_threshold;
    if (s->accel_xz>a->peak_accel_xz) a->peak_accel_xz=s->accel_xz;
    if (fabsf(s->accel_y)>a->peak_abs_accel_y) a->peak_abs_accel_y=fabsf(s->accel_y);
    if (s->impulse>a->peak_impulse) a->peak_impulse=s->impulse;
    if (a->samples-a->invalid==1 || s->moveable<a->minimum_moveable)
        a->minimum_moveable=s->moveable;
}

#ifdef __cplusplus
extern "C" {
#endif
void tlg_climb_diagnostics_enable(void);
void tlg_climb_diagnostics_sample(const void *sensor,float dt);
#ifdef __cplusplus
}
#endif
#endif

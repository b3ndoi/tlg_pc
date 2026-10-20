/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <stdio.h>
#include "climb_diagnostics.h"

static int enabled;
static SRWLOCK diagnostic_lock=SRWLOCK_INIT;
typedef struct {
    const void *sensor;
    ULONGLONG last;
    TlgClimbSummary summary;
} History;
static History histories[16];

void tlg_climb_diagnostics_enable(void) { enabled=1; } /* before guest entry only */

void tlg_climb_diagnostics_sample(const void *sensor,float dt) {
    if (!enabled) return; /* zero data reads when the opt-in/schema gate is off */
    TlgClimbSample sample;
    tlg_climb_capture(sensor,&sample);
    const ULONGLONG now=GetTickCount64();
    TlgClimbSummary report={0};
    ULONGLONG span=0;
    AcquireSRWLockExclusive(&diagnostic_lock);
    History *h=NULL,*available=NULL;
    for (size_t i=0;i<sizeof(histories)/sizeof(histories[0]);++i) {
        if (histories[i].sensor==sensor) { h=&histories[i]; break; }
        if ((!histories[i].sensor || now-histories[i].last>10000) && !available)
            available=&histories[i];
    }
    /* Track active human input only; no slot shared across actors. This is not
     * a claim that any pointer is the Player. Log its identity for correlation.
     */
    if (!h && available && (sample.buttons || sample.magnitude>0.2f)) {
        h=available; memset(h,0,sizeof(*h)); h->sensor=sensor; h->last=now;
    }
    if (h) {
        tlg_climb_accumulate(&h->summary,&sample);
        span=now-h->last;
        if (span>=1000) {
            report=h->summary; memset(&h->summary,0,sizeof(h->summary)); h->last=now;
        }
    }
    ReleaseSRWLockExclusive(&diagnostic_lock);
    if (report.samples) {
        /* One report per second per active sensor, outside all sensor/history
         * locks. No controller calls, guest writes, sleeps or new threads.
         */
        printf("Climb diagnostic: sensor=%p uptime_ms=%llu window_ms=%llu n=%u dt=%.6f "
               "buttons=%#x stick=(%.3f,%.3f) magnitude=%.3f held=%u "
               "tracking=%u hang=%u detected=%u moveable=%.6g min=%.6g blocked=%u "
               "slope=%.3f accel=(%.3f,%.3f,%.3f) xz=%.3f peak_xz=%.3f "
               "above_12.5=%u peak_abs_y=%.3f impulse=%.3f peak_impulse=%.3f invalid=%u\n",
               sensor,(unsigned long long)now,(unsigned long long)span,report.samples,dt,
               sample.buttons,sample.axis_x,sample.axis_y,sample.magnitude,report.held,
               sample.tracking,sample.detected,report.detected,sample.moveable,
               report.minimum_moveable,report.blocked,sample.slope,
               sample.accel_x,sample.accel_y,sample.accel_z,sample.accel_xz,report.peak_accel_xz,
               report.above_shake_threshold,report.peak_abs_accel_y,sample.impulse,
               report.peak_impulse,report.invalid);
    }
}

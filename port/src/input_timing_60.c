/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include "input_timing_60.h"
#include "climb_diagnostics.h"

typedef struct TlgInputContext {
    void *sensor;
    float dt;
    struct TlgInputContext *previous;
} TlgInputContext;
typedef struct {
    void *sensor;
    unsigned active;
    TlgInputHold buttons[TLG_INPUT_BUTTONS];
    TlgInputHold sticks[TLG_INPUT_STICKS];
} TlgInputHistory;

static TlgInputUpdate original_update;
static __thread TlgInputContext *current_input;
static SRWLOCK history_lock = SRWLOCK_INIT;
static TlgInputHistory histories[128];

void tlg_input_60_configure(TlgInputUpdate original) {
    original_update = original; /* configured once, before entering guest code */
}

void TLG_INPUT_ABI tlg_input_60_update(void *sensor, float dt) {
    /* Preserve nested callbacks: the snapshot hook only accepts its own exact
     * sensor/source/destination tuple. Capture dt before the original function
     * reuses its saved-XMM stack slot during spinlock contention.
     */
    TlgInputContext context = {sensor, dt, current_input};
    current_input = &context;
    original_update(sensor, dt);
    current_input = context.previous;
    tlg_climb_diagnostics_sample(sensor,dt);
}

void *TLG_INPUT_ABI tlg_input_60_copy(void *destination, const void *source, size_t size) {
    memcpy(destination, source, size);
    const TlgInputContext *context = current_input;
    if (!context || size != TLG_INPUT_SNAPSHOT_SIZE ||
        destination != (unsigned char *)context->sensor + TLG_INPUT_SNAPSHOT ||
        source != (unsigned char *)context->sensor + TLG_INPUT_LIVE) return destination;

    unsigned char *sensor = context->sensor;
    uint32_t raw[TLG_INPUT_BUTTONS], remap[TLG_INPUT_BUTTONS], sticks[TLG_INPUT_STICKS];
    memcpy(raw, sensor + TLG_INPUT_LIVE_COUNTS, sizeof(raw));
    memcpy(remap, sensor + TLG_INPUT_REMAP_COUNTS, sizeof(remap));
    unsigned active = 0;
    for (unsigned i = 0; i < TLG_INPUT_BUTTONS; ++i) active |= raw[i];
    for (unsigned i = 0; i < TLG_INPUT_STICKS; ++i) {
        memcpy(&sticks[i], sensor + TLG_INPUT_STICK_LIVE +
            i * TLG_INPUT_STICK_STRIDE + TLG_INPUT_STICK_AGE, 4);
        active |= sticks[i];
    }

    /* Never hold a host lock while calling guest code. The snapshot correction
     * itself runs under the ORIGINAL sensor lock (the intercepted memcpy is
     * before its unlock), so graph readers cannot see a half-corrected snapshot.
     * Fixed storage avoids allocations/logging on the game's input path.
     */
    AcquireSRWLockExclusive(&history_lock);
    TlgInputHistory *history = NULL, *available = NULL;
    for (unsigned i = 0; i < sizeof(histories) / sizeof(histories[0]); ++i) {
        if (histories[i].sensor == sensor) { history = &histories[i]; break; }
        if (!histories[i].active && !available) available = &histories[i];
    }
    if (!history && active && available) {
        history = available;
        memset(history, 0, sizeof(*history));
        history->sensor = sensor;
    }
    /* Capacity exhaustion fails open to the original snapshot, not a crash or
     * shared history between actors. Non-player/inactive sensors need no slot.
     */
    if (history) {
        history->active = active;
        for (unsigned i = 0; i < TLG_INPUT_BUTTONS; ++i) {
            int32_t count = tlg_input_hold_step(&history->buttons[i], raw[i], context->dt);
            memcpy(sensor + TLG_INPUT_SNAPSHOT_COUNTS + i * 4, &count, 4);
            /* Native remapping copies raw counts, then zeros invalid buttons.
             * Re-enabling a held button must retain the same elapsed hold age.
             * An unexpected remap value is left unchanged, never guessed at.
             */
            if (remap[i] == raw[i])
                memcpy(sensor + TLG_INPUT_SNAPSHOT_REMAP + i * 4, &count, 4);
        }
        /* The six stick blocks were published by the original copy calls before
         * this memcpy, under the same lock. Change ONLY continuous-input age;
         * axes, velocities, direction bits, history and working ages stay native.
         */
        for (unsigned i = 0; i < TLG_INPUT_STICKS; ++i) {
            int32_t count = tlg_input_hold_step(&history->sticks[i], sticks[i], context->dt);
            memcpy(sensor + TLG_INPUT_STICK_SNAPSHOT +
                i * TLG_INPUT_STICK_STRIDE + TLG_INPUT_STICK_AGE, &count, 4);
        }
    }
    ReleaseSRWLockExclusive(&history_lock);
    return destination;
}

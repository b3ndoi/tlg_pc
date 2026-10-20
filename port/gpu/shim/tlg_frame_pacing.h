// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <chrono>
namespace TlgFramePacing {
inline std::chrono::steady_clock::time_point Next(
        std::chrono::steady_clock::time_point previous,
        std::chrono::nanoseconds period,
        std::chrono::steady_clock::time_point delivered,
        bool precise) {
    // Preserve phase across ordinary scheduler overshoot, rather than adding
    // its error to EVERY frame. If a whole slot was missed, discard the stale
    // catch-up schedule instead of immediately releasing several queued flips.
    // Vblank generation remains independent; this only schedules host delivery.
    const auto next = previous + period;
    return precise ? (next <= delivered ? delivered + period : next)
                   : std::max(next, delivered - period);
}
}

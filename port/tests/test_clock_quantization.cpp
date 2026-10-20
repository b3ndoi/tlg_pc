// SPDX-License-Identifier: GPL-2.0-or-later
// Asset-free arithmetic only; exact native/30-FPS comparison uses an optional local ELF.
#include <cassert>
#include <cmath>
#include <cstdio>
#include <initializer_list>
#include <limits>
#include "clock_sync_60.h"

int main() {
    for (double fps : {24., 30., 45., 60., 120.}) {
        for (double speed : {0.01, 0.10, 0.15, 0.5, 1., 2.}) {
            TlgClockCarry state{};
            double expected=0, actual=0;
            for (unsigned i=0;i<12000;++i) {
                const float fine=float(speed/fps*(1+0.02*std::sin(i*0.37)));
                const float step=tlg_clock_60_quantize(&state,fine);
                expected+=fine; actual+=step;
                assert(std::isfinite(step) && step>=0);
                assert(std::abs(actual-expected)<1./360.);
                assert(std::abs(step*360-std::round(step*360))<0.00001);
            }
            assert(tlg_clock_60_quantize(&state,0)==0 && state.residual==0);
            assert(tlg_clock_60_quantize(&state,-1)==0 && state.residual==0);
            assert(tlg_clock_60_quantize(&state,std::numeric_limits<float>::infinity())==0);
            assert(tlg_clock_60_quantize(&state,std::numeric_limits<float>::quiet_NaN())==0);
        }
    }
    std::puts("PASS: 360000 synthetic shared-clock steps, bounded error, pauses and invalid values");
}

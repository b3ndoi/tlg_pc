// SPDX-License-Identifier: GPL-2.0-or-later
#include <cassert>
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <thread>
#include <vector>
#include "tlg_win_pacing.h"
#include "tlg_frame_context.h"
#include "tlg_graphics.h"
#include "tlg_frame_pacing.h"

int main() {
    using namespace std::chrono;
    using namespace Common::WinPacing;
    assert(TlgGraphics::PresentLimit(60,60) == 60);
    assert(TlgGraphics::PresentLimit(0,60) == 0);
    const auto epoch = steady_clock::time_point{};
    const auto period = nanoseconds(1000000000/60);
    assert(TlgFramePacing::Next(epoch,period,epoch+1s,true) == epoch+1s+period);
    assert(TlgFramePacing::Next(epoch,period,epoch+1s,false) == epoch+1s-period);
    assert(TlgFramePacing::Next(epoch+period,period,epoch+period+500us,true) == epoch+period*2);
    // Same synthetic producer, short frames mixed with slightly late frames.
    // The old tick-only consumer quantizes late work to a second 60 Hz slot.
    auto tick_only = epoch, frame_ready = epoch, next_ready_slot = epoch+period;
    for(int i=0;i<240;++i) {
        const auto work = i%4 == 3 ? 17ms : 14ms;
        const auto ready = tick_only+work;
        const auto slots = (ready.time_since_epoch().count()+period.count()-1)/period.count();
        tick_only = epoch+period*slots;
        const auto ready_new = frame_ready+work;
        frame_ready = std::max(ready_new,next_ready_slot);
        next_ready_slot = TlgFramePacing::Next(next_ready_slot,period,frame_ready,true);
    }
    const double old_fps = 240/duration<double>(tick_only-epoch).count();
    const double ready_fps = 240/duration<double>(frame_ready-epoch).count();
    assert(ready_fps > old_fps && ready_fps <= 60.001);
    auto jitter_slot = epoch+period;
    for(int i=0;i<120;++i) {
        jitter_slot = TlgFramePacing::Next(jitter_slot,period,jitter_slot+500us,true);
    }
    assert(jitter_slot == epoch+period*121); // scheduler overshoot must not accumulate
    std::printf("Deterministic producer replay: tick-only %.2f vs frame-ready %.2f FPS (model, NOT live game)\n",old_fps,ready_fps);
    assert(TlgFrameContext::CanPresent(false,2560,1440));
    assert(!TlgFrameContext::CanPresent(true,2560,1440)); // SDL retains nonzero size
    assert(!TlgFrameContext::CanPresent(false,0,1440));
    assert(!TlgFrameContext::CanPresent(false,2560,0));
    TlgFrameContext::Window(true,true);
    TlgFrameContext::Flip();
    assert(TlgFrameContext::current == TlgFrameContext::Minimized);
    assert(TlgFrameContext::seen.exchange(0) == TlgFrameContext::Minimized);
    TlgFrameContext::Window(false,false);
    TlgFrameContext::Flip();
    TlgFrameContext::Window(false,true);
    TlgFrameContext::Flip();
    assert(TlgFrameContext::seen == (TlgFrameContext::Foreground | TlgFrameContext::Background));

    { std::jthread warmup([]{}); }
    DWORD handles_before{}, handles_after{};
    GetProcessHandleCount(GetCurrentProcess(), &handles_before);
    {
        Timer timer;
        std::printf("Windows precise timer: high_resolution=%d\n",timer.HighResolution());
        assert(timer.Wait(0ns) == Result::Deadline);
        assert(timer.Wait(-1ns) == Result::Deadline);
        assert(timer.Wait(1ns) == Result::Deadline); // never absolute zero / infinite wait
        Wakeup wake;
        assert(wake.Valid());
        assert(wake.WaitUntil(steady_clock::now()-1ms) == Result::Deadline);
        wake.Notify(); // notification before waiting must not be lost
        assert(wake.WaitUntil(steady_clock::now()+1s) == Result::Notified);
        const auto before = steady_clock::now();
        assert(wake.WaitUntil(before+2ms) == Result::Deadline);
        assert(steady_clock::now() >= before+2ms);

        // The production event/timer primitive: 200 producer handshakes, no UI,
        // no game, no lost frame-ready notifications or early deadline returns.
        std::atomic<int> requested{0}, acknowledged{0};
        std::jthread producer([&] {
            for(int i=1;i<=200;++i) {
                while(acknowledged.load(std::memory_order_acquire) != i-1) std::this_thread::yield();
                requested.store(i,std::memory_order_release);
                wake.Notify();
            }
        });
        for(int i=1;i<=200;++i) {
            const auto until = steady_clock::now()+2s;
            while(requested.load(std::memory_order_acquire) != i) {
                assert(wake.WaitUntil(until) == Result::Notified);
            }
            acknowledged.store(i,std::memory_order_release);
        }
        producer.join();
        // Clear a harmless coalesced notification after the final predicate hit.
        while(wake.WaitUntil(steady_clock::now()+1ms) == Result::Notified) {}
        std::vector<double> lateness;
        for(int i=0;i<120;++i) {
            const auto start = steady_clock::now();
            assert(timer.Wait(1ms) == Result::Deadline);
            const auto elapsed = duration<double,std::milli>(steady_clock::now()-start).count();
            assert(elapsed >= 1.0);
            lateness.push_back(elapsed-1.0);
        }
        std::sort(lateness.begin(),lateness.end());
        std::printf("1 ms waits: median overshoot %.3f ms, p99 %.3f ms (diagnostic, not a game benchmark)\n",
                    lateness[lateness.size()/2],lateness[lateness.size()*99/100]);
    }
    GetProcessHandleCount(GetCurrentProcess(), &handles_after);
    // The thread-local timer is intentionally retained until thread exit.
    assert(handles_after <= handles_before+1);
    std::puts("PASS: notification/deadline race, 200 handshakes, no early wakes/handle leaks; minimized display policy; 60 FPS limiter unchanged");
}

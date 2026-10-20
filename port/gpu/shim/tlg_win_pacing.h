// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#ifdef _WIN32
#include <windows.h>
#include <chrono>
#include <cstdlib>

namespace Common::WinPacing {
inline bool Enabled() {
    static const bool enabled = [] {
        const char* value = std::getenv("TLG_PRECISE_PACING");
        return value && value[0] == '1';
    }();
    return enabled;
}
enum class Result { Deadline, Notified, Interrupted, Failed };

// Per-thread, single-waiter timer. No timeBeginPeriod, process priorities, global
// timer policy or settings of another process are changed.
class Timer {
public:
    Timer() {
        timer = CreateWaitableTimerExW(nullptr, nullptr, 0x00000002, TIMER_ALL_ACCESS);
        high_resolution = timer != nullptr;
        if (!timer) timer = CreateWaitableTimerExW(nullptr, nullptr, 0, TIMER_ALL_ACCESS);
    }
    ~Timer() { if (timer) CloseHandle(timer); }
    Timer(const Timer&) = delete;
    Timer& operator=(const Timer&) = delete;
    bool HighResolution() const { return high_resolution; }
    Result Wait(std::chrono::nanoseconds duration, HANDLE notification = nullptr,
                bool alertable = false) {
        if (duration <= std::chrono::nanoseconds::zero()) return Result::Deadline;
        if (!timer) return Result::Failed;
        // Round UP to a relative 100 ns deadline; zero is an absolute 1601 date.
        LARGE_INTEGER due{.QuadPart = -((duration.count() / 100) + (duration.count() % 100 != 0))};
        if (!SetWaitableTimerEx(timer, &due, 0, nullptr, nullptr, nullptr, 0)) return Result::Failed;
        HANDLE handles[2]{notification ? notification : timer, timer};
        const DWORD count = notification ? 2 : 1;
        const DWORD result = WaitForMultipleObjectsEx(count, handles, FALSE, INFINITE, alertable);
        if (result == WAIT_OBJECT_0) return notification ? Result::Notified : Result::Deadline;
        if (notification && result == WAIT_OBJECT_0 + 1) return Result::Deadline;
        if (result == WAIT_IO_COMPLETION) return Result::Interrupted;
        return Result::Failed;
    }
private:
    HANDLE timer{};
    bool high_resolution{};
};
inline Timer& ThreadTimer() { static thread_local Timer timer; return timer; }

class Wakeup {
public:
    Wakeup() : event{CreateEventW(nullptr, FALSE, FALSE, nullptr)} {}
    ~Wakeup() { if (event) CloseHandle(event); }
    Wakeup(const Wakeup&) = delete;
    Wakeup& operator=(const Wakeup&) = delete;
    bool Valid() const { return event != nullptr; }
    void Notify() { if (event) SetEvent(event); }
    Result WaitUntil(std::chrono::steady_clock::time_point deadline) {
        if (!event) return Result::Failed;
        return ThreadTimer().Wait(deadline - std::chrono::steady_clock::now(), event);
    }
private:
    HANDLE event{};
};
} // namespace Common::WinPacing
#endif

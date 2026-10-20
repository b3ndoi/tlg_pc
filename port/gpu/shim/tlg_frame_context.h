// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <atomic>
#include <cstdint>
#include <cstdio>
namespace TlgFrameContext {
enum : unsigned { Foreground = 1, Background = 2, Minimized = 4 };
inline std::atomic<unsigned> current{Background}, seen{0};
inline std::atomic<uint64_t> presented{0}, skipped{0};
constexpr bool CanPresent(bool minimized, int width, int height) {
    return !minimized && width > 0 && height > 0;
}
inline void Window(bool minimized, bool focused) {
    current.store(minimized ? Minimized : focused ? Foreground : Background,
                  std::memory_order_relaxed);
}
inline void Flip() { seen.fetch_or(current.load(std::memory_order_relaxed), std::memory_order_relaxed); }
inline void Report(double seconds) {
    const auto states = seen.exchange(0);
    const auto shown = presented.exchange(0), hidden = skipped.exchange(0);
    std::printf("Frame context: foreground %d, background %d, minimized %d; "
                "successful surface presents %.1f/s, minimized/zero-size skips %.1f/s "
                "(flip FPS is not visible-display FPS)\n",
                !!(states & Foreground), !!(states & Background), !!(states & Minimized),
                shown / seconds, hidden / seconds);
}
} // namespace TlgFrameContext

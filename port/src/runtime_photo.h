/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TLG_RUNTIME_PHOTO_H
#define TLG_RUNTIME_PHOTO_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* All traffic is in memory, never a save/config file. The script runs on the
 * game's Lua thread; SDL and Vulkan never dereference guest camera objects. */
void runtime_photo_enable(int enabled);
int runtime_photo_enabled(void);
int runtime_photo_active(void);
int runtime_photo_captures_input(void);
void runtime_photo_release_inputs(void);
void runtime_photo_toggle(void);
void runtime_photo_cancel(void);
void runtime_photo_motion(float x, float y);
void runtime_photo_axes(float forward, float right, float up, float zoom, int fast);
size_t runtime_photo_control(char *output, size_t capacity);
size_t runtime_photo_peek_control(char *output, size_t capacity);
/* Unscaled render-thread time, independent of the paused game/editor clock. */
void runtime_photo_step(float seconds);
void runtime_photo_status(const char *data, size_t size);
void runtime_photo_capture(void);
int runtime_photo_take_capture(void);
const char *runtime_photo_script(size_t *size);
#ifdef __cplusplus
}
#endif
#endif

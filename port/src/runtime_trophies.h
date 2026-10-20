/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TLG_RUNTIME_TROPHIES_H
#define TLG_RUNTIME_TROPHIES_H
#include <stdint.h>
void runtime_trophies_configure(const char *title, const char *user_root);
int runtime_trophies_enabled(void);
/* Zero succeeds, one means already unlocked, negative means preserved-on-error. */
int runtime_trophies_unlock(int32_t user, int32_t id);
int runtime_trophies_read(int32_t user, uint32_t flags[4], uint32_t *count, uint64_t stamps[128]);
#endif

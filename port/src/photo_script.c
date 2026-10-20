/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "runtime_photo.h"
#ifndef TLG_PHOTO_SCRIPT_PATH
#define TLG_PHOTO_SCRIPT_PATH "src/photo_mode.lua"
#endif
#ifdef _WIN32
#define PHOTO_SECTION ".section .rdata,\"dr\"\n"
#else
#define PHOTO_SECTION ".section .rodata\n"
#endif
__asm__(PHOTO_SECTION ".global tlg_photo_lua\n"
    "tlg_photo_lua:\n.incbin \"" TLG_PHOTO_SCRIPT_PATH "\"\n"
    ".global tlg_photo_lua_end\ntlg_photo_lua_end:\n.text\n");
extern const char tlg_photo_lua[],tlg_photo_lua_end[];
const char *runtime_photo_script(size_t *size) {
    *size=(size_t)(tlg_photo_lua_end-tlg_photo_lua); return tlg_photo_lua;
}

/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef TLG_SCRIPT_TIMING_60_H
#define TLG_SCRIPT_TIMING_60_H
#include "input_timing_60.h"

enum { TLG_SCRIPT_LOAD = 0xdd4dd0, TLG_SCRIPT_CALLER = 0xc898e9 };
/* hksi_hksL_loadbuffer(L, compilerOptions, buffer, byteCount, chunkName).
 * Original engine caller at +0xc898fe verifies all five SysV argument registers.
 */
static const unsigned char tlg_script_load_code[] = {
    0x55,0x48,0x89,0xe5,0x41,0x57,0x41,0x56,0x41,0x55,0x41,0x54,0x53,
    0x48,0x81,0xec,0x58,1,0,0,0x4c,0x8b,0x3d,0xd5,0x32,0x90,0,
    0x4d,0x89,0xc4,0x49,0x89,0xfd,0x49,0x89,0xd0,0x48,0x89,0xb5,0xa8,0xfe,0xff,0xff
};
static const unsigned char tlg_script_caller_code[] = {
    0xbe,0x58,5,0,0,0x8b,0x4d,0xcc,0x4c,0x89,0xff,0x48,0x89,0xda,
    0x4d,0x89,0xe0,0x49,3,0x77,0x10,0xe8,0xcd,0xb4,0x14,0
};
static inline int tlg_script_60_matches(const char *serial, const char *version,
        const unsigned char *code, const unsigned char *caller,
        const unsigned char *flip, const unsigned char *dt) {
    return serial && version && code && caller && flip && dt &&
        !strcmp(serial,"CUSA03745") && !strcmp(version,"01.00") &&
        !memcmp(flip,tlg_input_60_flip,sizeof(tlg_input_60_flip)) &&
        !memcmp(dt,tlg_input_60_dt,sizeof(tlg_input_60_dt)) &&
        !memcmp(code,tlg_script_load_code,sizeof(tlg_script_load_code)) &&
        !memcmp(caller,tlg_script_caller_code,sizeof(tlg_script_caller_code));
}

typedef int (TLG_INPUT_ABI *TlgScriptLoad)(void *, void *, const char *, size_t, const char *);
#ifdef __cplusplus
extern "C" {
#endif
void tlg_script_60_configure(TlgScriptLoad original);
void tlg_script_60_enable(int enabled);
char *tlg_script_60_transform(const char *source, size_t size, size_t *output_size, const char **path);
char *tlg_photo_append(const char *source,size_t size,size_t *output_size);
int TLG_INPUT_ABI tlg_script_60_load(void *vm, void *options, const char *source, size_t size, const char *name);
#ifdef __cplusplus
}
#endif
#endif

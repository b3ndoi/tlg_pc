/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <bcrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include "script_timing_60.h"
#include "runtime_photo.h"

typedef struct { size_t offset, length, replacement_size; const char *replacement; } TlgScriptEdit;
typedef struct {
    const char *path;
    size_t size;
    unsigned char sha256[32];
    const TlgScriptEdit *edits;
    size_t count;
} TlgScriptRecord;
#include "script_timing_60_data.h"

static TlgScriptLoad original_load;
static int timing_enabled=1;
void tlg_script_60_configure(TlgScriptLoad original) { original_load = original; }
void tlg_script_60_enable(int enabled) { timing_enabled=enabled!=0; }

static int digest(const char *source, size_t size, unsigned char out[32]) {
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    if (size > ULONG_MAX || BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0) < 0)
        return 0;
    int ok = BCryptCreateHash(algorithm,&hash,NULL,0,NULL,0,0) >= 0;
    if (ok) ok = BCryptHashData(hash,(PUCHAR)source,(ULONG)size,0) >= 0;
    if (ok) ok = BCryptFinishHash(hash,out,32,0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm,0);
    return ok;
}

char *tlg_script_60_transform(const char *source, size_t size, size_t *output_size, const char **path) {
    if (output_size) *output_size = size;
    if (path) *path = NULL;
    if (!source) return NULL;
    int candidate = 0;
    size_t source_size = size;
    for (size_t i=0; i<sizeof(tlg_script_records)/sizeof(tlg_script_records[0]); ++i)
        if (size == tlg_script_records[i].size) candidate = 1;
        else if (size == tlg_script_records[i].size+1 && source[size-1] == 0) {
            candidate = 1;
            source_size = size-1; /* some loaders include the terminating NUL */
        }
    if (!candidate) return NULL;
    unsigned char sha256[32];
    if (!digest(source,source_size,sha256)) return NULL;
    for (size_t i=0; i<sizeof(tlg_script_records)/sizeof(tlg_script_records[0]); ++i) {
        const TlgScriptRecord *record = &tlg_script_records[i];
        if (source_size != record->size || memcmp(sha256,record->sha256,32)) continue;
        size_t total = size, end = 0;
        for (size_t j=0; j<record->count; ++j) {
            const TlgScriptEdit *edit = &record->edits[j];
            if (edit->offset < end || edit->offset > size || edit->length > size-edit->offset ||
                edit->replacement_size > SIZE_MAX-total) return NULL;
            total += edit->replacement_size;
            total -= edit->length;
            end = edit->offset+edit->length;
        }
        if (total == SIZE_MAX) return NULL;
        char *output = malloc(total+1);
        if (!output) return NULL;
        size_t read_at = 0, write_at = 0;
        for (size_t j=0; j<record->count; ++j) {
            const TlgScriptEdit *edit = &record->edits[j];
            size_t untouched = edit->offset-read_at;
            memcpy(output+write_at,source+read_at,untouched);
            write_at += untouched;
            memcpy(output+write_at,edit->replacement,edit->replacement_size);
            write_at += edit->replacement_size;
            read_at = edit->offset+edit->length;
        }
        memcpy(output+write_at,source+read_at,size-read_at);
        output[total] = 0;
        if (output_size) *output_size = total;
        if (path) *path = record->path;
        return output;
    }
    /* Modified/unknown scripts are left byte-for-byte original, not guessed at. */
    return NULL;
}

static const char *known_chunk(const char *name) {
    if (!name) return NULL;
    if (*name=='@' || *name=='=') ++name;
    char path[512];
    size_t n=strlen(name);
    if (n>=sizeof(path)) return NULL;
    for (size_t i=0;i<=n;++i) path[i]=name[i]=='\\' ? '/' : name[i];
    for (size_t i=0;i<sizeof(tlg_script_records)/sizeof(tlg_script_records[0]);++i) {
        const char *wanted=tlg_script_records[i].path;
        size_t length=strlen(wanted);
        if (!_stricmp(path,wanted) || (n+4==length && !_strnicmp(path,wanted,n))) return wanted;
    }
    return NULL;
}

/* Metadata only: no original game source. Mutated/modded/other-version chunks
 * are not guessed at, and 30-FPS processes never enable this transformer. */
char *tlg_photo_append(const char *source,size_t size,size_t *out_size) {
    static const char expected[]="b61524ce828141deb8e68cf22b9308c4f09e1dacabf6ae74069a9ba3869b3f7a";
    if (!runtime_photo_enabled() || !source || !out_size) return NULL;
    size_t n=size;
    if (n==23495 && source[n-1]==0) --n;
    if (n!=23494) return NULL;
    unsigned char hash[32];
    if (!digest(source,n,hash)) return NULL;
    static const char hex[]="0123456789abcdef";
    for (size_t i=0;i<32;++i)
        if (hex[hash[i]>>4]!=expected[i*2] || hex[hash[i]&15]!=expected[i*2+1]) return NULL;
    size_t addition; const char *lua=runtime_photo_script(&addition);
    if (addition>SIZE_MAX-n-2) return NULL;
    char *out=malloc(n+addition+2);
    if (!out) return NULL;
    memcpy(out,source,n); out[n]='\n'; memcpy(out+n+1,lua,addition); out[n+addition+1]=0;
    *out_size=n+addition+1;
    printf("Photo mode: source-verified EU bootstrap; experimental backend loaded\n");
    return out;
}

int TLG_INPUT_ABI tlg_script_60_load(void *vm, void *options, const char *source, size_t size, const char *name) {
    size_t changed_size;
    const char *path;
    path=NULL;
    char *changed = timing_enabled ? tlg_script_60_transform(source,size,&changed_size,&path) : NULL;
    if (changed) printf("60 FPS script timing: source-verified %s\n",path);
    else if (timing_enabled && (path=known_chunk(name)))
        printf("60 FPS script timing: NOT applied to %s (source fingerprint mismatch or allocation/hash failure)\n",path);
    size_t photo_size=0;
    char *photo=tlg_photo_append(source,size,&photo_size);
    int result = original_load(vm,options,photo ? photo : changed ? changed : source,
                              photo ? photo_size : changed ? changed_size : size,name);
    if (photo && result) runtime_photo_enable(0);
    free(photo);
    if (changed && result) printf("60 FPS script timing: compiler returned %d for %s\n",result,path);
    free(changed);
    return result;
}

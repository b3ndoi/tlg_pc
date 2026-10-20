/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <bcrypt.h>
#include <stdio.h>
#include <stdlib.h>
#include "script_timing_60.h"

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
void tlg_script_60_configure(TlgScriptLoad original) { original_load = original; }

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

int TLG_INPUT_ABI tlg_script_60_load(void *vm, void *options, const char *source, size_t size, const char *name) {
    size_t changed_size;
    const char *path;
    char *changed = tlg_script_60_transform(source,size,&changed_size,&path);
    if (changed) printf("60 FPS script timing: source-verified %s\n",path);
    else if ((path=known_chunk(name)))
        printf("60 FPS script timing: NOT applied to %s (source fingerprint mismatch or allocation/hash failure)\n",path);
    int result = original_load(vm,options,changed ? changed : source,changed ? changed_size : size,name);
    if (changed && result) printf("60 FPS script timing: compiler returned %d for %s\n",result,path);
    free(changed);
    return result;
}

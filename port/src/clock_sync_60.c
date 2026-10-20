/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "clock_sync_60.h"
#include <windows.h>
#include <bcrypt.h>

/* Match the same complete functions as the private fixture, without embedding
 * their original machine code in a public source tree or release binary. */
static int matches_digest(const unsigned char *code, ULONG length, const char *expected) {
    BCRYPT_ALG_HANDLE algorithm = NULL;
    BCRYPT_HASH_HANDLE hash = NULL;
    unsigned char digest[32];
    if (!code || BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,NULL,0) < 0)
        return 0;
    int ok = BCryptCreateHash(algorithm,&hash,NULL,0,NULL,0,0) >= 0;
    if (ok) ok = BCryptHashData(hash,(PUCHAR)code,length,0) >= 0;
    if (ok) ok = BCryptFinishHash(hash,digest,sizeof(digest),0) >= 0;
    if (hash) BCryptDestroyHash(hash);
    BCryptCloseAlgorithmProvider(algorithm,0);
    static const char hex[] = "0123456789abcdef";
    for (unsigned i=0;ok && i<sizeof(digest);++i)
        if (hex[digest[i]>>4] != expected[2*i] || hex[digest[i]&15] != expected[2*i+1]) ok=0;
    return ok;
}

int tlg_clock_60_code_matches(const unsigned char *smooth,
        const unsigned char *physics, const unsigned char *physics_zero) {
    return matches_digest(smooth,TLG_CLOCK_SPAN,
               "5f28f8bb83aee536321a336d4b330bbf8a491f9bc2dffd2af70e860bce594855") &&
           matches_digest(physics,TLG_CLOCK_PHYSICS_SPAN,
               "fd597a7cc30f217c2bcf48116abe9bb161165faa89b01e037fff9f7dd68ecef1") &&
           matches_digest(physics_zero,TLG_CLOCK_ZERO_SPAN,
               "25ad249787a2898cb62490257821a87127ab87b3faab83fade6531c773915ba3");
}

static TlgClockSmooth original_smooth;
static __thread TlgClockCarry carry;

void tlg_clock_60_configure(TlgClockSmooth original) {
    original_smooth=original; /* installed once, before guest execution */
}

void TLG_CLOCK_ABI tlg_clock_60_smooth(void *object,float time,float dt) {
    /* Retain the original v6 filter, feedback, fine precision, speed curves and
     * pause gates. Only its final published step is synchronized with physics.
     * This runs before returning to the native main-loop/worker dispatch.
     */
    original_smooth(object,time,dt);
    unsigned char *app=object,*timing=NULL;
    uint32_t frame,paused,overlay;
    float fine;
    memcpy(&timing,app+0xb0,sizeof(timing));
    memcpy(&frame,app+0x1a8,sizeof(frame));
    memcpy(&paused,app+0x1c0,sizeof(paused));
    memcpy(&overlay,app+0x20,sizeof(overlay));
    memcpy(&fine,app+0x19c,sizeof(fine));
    if (carry.app!=object || carry.timing!=timing || frame<carry.frame) carry.residual=0;
    carry.app=object; carry.timing=timing; carry.frame=frame;
    if (!timing) { carry.residual=0; return; }
    if (paused || overlay || !(fine>0) || !isfinite(fine)) {
        carry.residual=0; return; /* intentional pause: no debt, no catch-up */
    }
    float shared=tlg_clock_60_quantize(&carry,fine);
    memcpy(app+0x19c,&shared,sizeof(shared));
    memcpy(timing+0x39c,&shared,sizeof(shared));
    /* Do not overwrite the continuous filter at +3a0/+3a4, the native feedback
     * accumulator, or the unscaled/audio timestep channels at App +194/+198.
     */
}

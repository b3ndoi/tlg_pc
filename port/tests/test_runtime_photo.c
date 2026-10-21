/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "runtime_photo.h"
static unsigned sequence(char *line) {
    assert(runtime_photo_control(line,256)>0);
    unsigned seq; assert(sscanf(line,"2 %u",&seq)==1); return seq;
}
static void reply(unsigned seq,int state) {
    char line[64]; int n=snprintf(line,sizeof(line),"2 %u %d\n",seq,state);
    runtime_photo_status(line,(size_t)n);
}
int main(void) {
    char line[256];
    assert(!runtime_photo_enabled() && !runtime_photo_active());
    runtime_photo_toggle(); runtime_photo_capture(); assert(!runtime_photo_take_capture());
    runtime_photo_enable(1); runtime_photo_toggle(); unsigned seq=sequence(line);
    assert(runtime_photo_captures_input()); /* activation chord never reaches gameplay */
    assert(!runtime_photo_active());
    reply(seq-1,1); assert(!runtime_photo_active());
    reply(seq,1); assert(runtime_photo_active());
    runtime_photo_motion(INFINITY,NAN); runtime_photo_axes(100,-100,NAN,1,1);
    sequence(line); assert(!strstr(line,"nan") && !strstr(line,"inf"));
    runtime_photo_capture(); assert(runtime_photo_take_capture()); assert(!runtime_photo_take_capture());
    runtime_photo_capture(); runtime_photo_cancel(); assert(!runtime_photo_take_capture());
    unsigned next=sequence(line); reply(seq,0); assert(runtime_photo_active());
    reply(next,0); assert(!runtime_photo_active());
    assert(runtime_photo_captures_input());
    runtime_photo_release_inputs();assert(!runtime_photo_captures_input());
    runtime_photo_toggle(); next=sequence(line); reply(next,2); assert(!runtime_photo_active());
    runtime_photo_status("garbage",7); assert(!runtime_photo_active());
    runtime_photo_release_inputs();
    runtime_photo_toggle(); next=sequence(line);
    for (int i=0;i<30;++i) runtime_photo_step(0.05f);
    unsigned cancelled=sequence(line); assert(cancelled!=next && runtime_photo_captures_input());
    reply(next,1); assert(!runtime_photo_active()); /* timed-out acknowledgement cannot enter */
    runtime_photo_release_inputs(); assert(!runtime_photo_captures_input());
    runtime_photo_step(INFINITY);runtime_photo_step(NAN);sequence(line);
    assert(!strstr(line,"nan") && !strstr(line,"inf"));
    runtime_photo_enable(0); runtime_photo_toggle(); assert(!runtime_photo_active());
    puts("PASS: photo opt-in, acknowledgement, stale replies, finite inputs, cancellation and capture coalescing");
}

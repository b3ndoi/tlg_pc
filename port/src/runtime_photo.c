/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "runtime_photo.h"
#include <math.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>

static pthread_mutex_t photo_lock=PTHREAD_MUTEX_INITIALIZER;
static int enabled, active, wanted, capture, release_gate;
static float dx, dy, forward, right, up, zoom;
static unsigned sequence;
static int fast;
static int backend_ready;
static float host_step, pending_seconds;

void runtime_photo_enable(int value) {
    pthread_mutex_lock(&photo_lock);
    enabled=value!=0; active=wanted=capture=release_gate=0;
    dx=dy=forward=right=up=zoom=0; fast=0; ++sequence;
    host_step=pending_seconds=0;
    backend_ready=0;
    pthread_mutex_unlock(&photo_lock);
}
int runtime_photo_enabled(void) {
    pthread_mutex_lock(&photo_lock); int result=enabled;
    pthread_mutex_unlock(&photo_lock); return result;
}
int runtime_photo_active(void) {
    pthread_mutex_lock(&photo_lock); int result=enabled && active;
    pthread_mutex_unlock(&photo_lock); return result;
}
int runtime_photo_captures_input(void) {
    pthread_mutex_lock(&photo_lock); int result=enabled && (active || wanted || release_gate);
    pthread_mutex_unlock(&photo_lock); return result;
}
void runtime_photo_release_inputs(void) {
    pthread_mutex_lock(&photo_lock); release_gate=0;
    pthread_mutex_unlock(&photo_lock);
}
void runtime_photo_toggle(void) {
    pthread_mutex_lock(&photo_lock);
    if (enabled) {
        wanted=!wanted; ++sequence; pending_seconds=0; release_gate=1;
        /* SDL state polling bypasses event consumption: shield the activation
         * chord before acknowledgement as well as held controls after exit. */
    }
    pthread_mutex_unlock(&photo_lock);
}
void runtime_photo_cancel(void) {
    pthread_mutex_lock(&photo_lock);
    if (wanted) { wanted=0; ++sequence; }
    if (enabled && active) release_gate=1;
    pending_seconds=0;
    dx=dy=forward=right=up=zoom=0; fast=0; capture=0;
    pthread_mutex_unlock(&photo_lock);
}
static float bounded(float value,float limit) {
    return !isfinite(value) ? 0 : value>limit ? limit : value < -limit ? -limit : value;
}
void runtime_photo_motion(float x,float y) {
    pthread_mutex_lock(&photo_lock);
    if (enabled && active) { dx=bounded(dx+x,500); dy=bounded(dy+y,500); }
    pthread_mutex_unlock(&photo_lock);
}
void runtime_photo_axes(float f,float r,float u,float z,int speed) {
    pthread_mutex_lock(&photo_lock);
    if (enabled && active) {
        forward=bounded(f,1); right=bounded(r,1); up=bounded(u,1); zoom=bounded(z,1); fast=speed!=0;
    }
    pthread_mutex_unlock(&photo_lock);
}
void runtime_photo_step(float seconds) {
    pthread_mutex_lock(&photo_lock);
    host_step=isfinite(seconds) && seconds>0 ? (seconds>0.05f ? 0.05f : seconds) : 0;
    if (enabled && wanted && !active) {
        pending_seconds+=host_step;
        if (pending_seconds>=1) {
            wanted=0; ++sequence; release_gate=1; pending_seconds=0;
            printf("Photo mode: entry cancelled (backend did not acknowledge); release controls to resume input\n");
        }
    }
    pthread_mutex_unlock(&photo_lock);
}
static size_t control(char *out,size_t capacity,int consume) {
    if (!out || !capacity) return 0;
    pthread_mutex_lock(&photo_lock);
    int n=snprintf(out,capacity,"2 %u %d %.6f %.6f %.6f %.6f %.6f %.6f %d %.6f\n",
                   sequence,enabled && wanted,dx,dy,forward,right,up,zoom,fast,host_step);
    if (consume) dx=dy=0;
    pthread_mutex_unlock(&photo_lock);
    return n<0 || (size_t)n>=capacity ? 0 : (size_t)n;
}
size_t runtime_photo_control(char *out,size_t capacity) { return control(out,capacity,1); }
size_t runtime_photo_peek_control(char *out,size_t capacity) { return control(out,capacity,0); }
void runtime_photo_status(const char *data,size_t size) {
    if (!data || !size || size>127 || memchr(data,0,size)) return;
    char text[128], extra;
    memcpy(text,data,size); text[size]=0;
    unsigned reply; int version, state;
    if (sscanf(text,"%d %u %d %c",&version,&reply,&state,&extra)!=3 || version!=2 ||
        (state!=0 && state!=1 && state!=2)) return;
    pthread_mutex_lock(&photo_lock);
    if (enabled && reply==sequence) {
        if (!backend_ready) { backend_ready=1; printf("Photo mode: backend mailbox ready\n"); }
        if (active && state!=1) release_gate=1;
        if ((state==1)!=active || (state==2 && wanted))
            printf("Photo mode: %s\n",state==1 ? "active (native pause acquired)" :
                state==2 ? "refused or restored (unsafe/unknown scene or backend error)" : "camera restored; owned pause released");
        active=state==1;
        pending_seconds=0;
        if (state==2) wanted=0; /* refused/automatic restore; a fresh press is required */
        if (!active) capture=0;
    }
    pthread_mutex_unlock(&photo_lock);
}
void runtime_photo_capture(void) {
    pthread_mutex_lock(&photo_lock);
    if (enabled && active && wanted) capture=1;
    pthread_mutex_unlock(&photo_lock);
}
int runtime_photo_take_capture(void) {
    pthread_mutex_lock(&photo_lock);
    int result=enabled && active && wanted && capture;
    capture=0;
    pthread_mutex_unlock(&photo_lock); return result;
}

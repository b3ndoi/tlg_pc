/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "../src/runtime_file.c"
#include <assert.h>
static int32_t photo_errno;
int32_t *runtime_errno(void) { return &photo_errno; }
int32_t runtime_guest_errno(int e) { return e; }
void runtime_wait_begin(const char *k,const void *o,const char *n,const void *const *owner,uintptr_t f) {
    (void)k;(void)o;(void)n;(void)owner;(void)f;
}
void runtime_wait_end(void) {}
uintptr_t runtime_lookup(const RuntimeExport *table,size_t count,const char *name) {
    (void)table;(void)count;(void)name;return 0;
}
int main(void) {
    assert(do_open("/tlg-photo/control",0,0)==-ENOENT);
    runtime_photo_enable(1);runtime_photo_toggle();
    assert(do_open("/tlg-photo/control",1,0)==-EACCES);
    assert(do_open("/tlg-photo/status",0,0)==-EACCES);
    int fd=(int)do_open("/tlg-photo/control",0,0);assert(fd>=3);
    GuestStat st;assert(!do_fstat(fd,&st) && st.size>0 && st.size<256);
    char request[256]={0};assert(do_read(fd,request,1)==1);
    assert(do_read(fd,request+1,255)==st.size-1);
    assert(do_read(fd,request,1)==0);
    assert(do_write(fd,"x",1)==-EBADF && do_lseek(fd,0,0)==-ESPIPE);
    assert(!do_close(fd));
    unsigned seq;assert(sscanf(request,"1 %u",&seq)==1);
    char reply[64];int n=snprintf(reply,sizeof(reply),"1 %u 1\n",seq);
    fd=(int)do_open("/tlg-photo/status",1|0x200|0x400,0600);assert(fd>=3);
    assert(do_write(fd,reply,2)==2 && !runtime_photo_active());
    assert(do_write(fd,reply+2,(uint64_t)n-2)==n-2 && !runtime_photo_active());
    assert(!do_close(fd) && runtime_photo_active());
    fd=(int)do_open("/tlg-photo/status",1,0);assert(fd>=3);
    char large[257]={0};assert(do_write(fd,large,sizeof(large))==-EFBIG);
    assert(!do_close(fd));
    runtime_photo_cancel();runtime_photo_enable(0);
    assert(do_open("/tlg-photo/control",0,0)==-ENOENT);
    puts("PASS: actual guest descriptors, fragmented I/O, bounded mailbox and disabled paths; no host files");
}

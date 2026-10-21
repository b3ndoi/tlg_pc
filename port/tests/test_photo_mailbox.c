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
    GuestStat st;
    assert(do_open("/tlg-photo/control",0,0)==-ENOENT);
    assert(do_stat("/tlg-photo/control",&st)==-ENOENT);
    assert(do_access("/tlg-photo/status",0)==-ENOENT);
    runtime_photo_enable(1);runtime_photo_toggle();
    runtime_photo_step(1.f/60);
    /* Reproduce retail stdio's metadata/reachability preflight before open. */
    assert(!do_stat("/tlg-photo/control",&st) && st.size>0 && st.mode==0100400);
    assert(!do_access("/tlg-photo/control",4));
    assert(!sce_check_reachability("/tlg-photo/control"));
    assert(!do_stat("/tlg-photo/status",&st) && st.mode==0100200);
    assert(!do_access("/tlg-photo/status",2));
    assert(do_access("/tlg-photo/control",2)==-EACCES);
    assert(do_access("/tlg-photo/status",4)==-EACCES);
    assert(do_access("/tlg-photo/control",1)==-EACCES);
    assert(do_access("/tlg-photo/control",8)==-EINVAL);
    assert(do_stat("/tlg-photo/control",NULL)==-EFAULT);
    assert(!mount_count && !opens && !reads && !writes);
    assert(do_open("/tlg-photo/control",1,0)==-EACCES);
    assert(do_open("/tlg-photo/status",0,0)==-EACCES);
    int fd=(int)do_open("/tlg-photo/control",0,0);assert(fd>=3);
    assert(!do_fstat(fd,&st) && st.size>0 && st.size<256);
    char request[256]={0};assert(do_read(fd,request,1)==1);
    assert(do_read(fd,request+1,255)==st.size-1);
    assert(do_read(fd,request,1)==0);
    assert(do_write(fd,"x",1)==-EBADF);
    assert(do_lseek(fd,0,2)==st.size && do_lseek(fd,0,0)==0);
    assert(do_lseek(fd,INT64_MAX,1)==-EINVAL && do_lseek(fd,INT64_MIN,2)==-EINVAL);
    char positioned[256]={0};
    assert(do_pread(fd,positioned,255,0)==st.size && !strcmp(request,positioned));
    assert(do_lseek(fd,0,1)==0); /* pread does not advance the snapshot position */
    assert(do_pread(fd,positioned,1,-1)==-EINVAL);
    assert(!do_close(fd));
    unsigned seq;assert(sscanf(request,"2 %u",&seq)==1);
    char reply[64];int n=snprintf(reply,sizeof(reply),"2 %u 1\n",seq);
    fd=(int)do_open("/tlg-photo/status",1|0x200|0x400,0600);assert(fd>=3);
    assert(do_write(fd,reply,2)==2 && !runtime_photo_active());
    assert(do_write(fd,reply+2,(uint64_t)n-2)==n-2 && !runtime_photo_active());
    assert(!do_close(fd) && runtime_photo_active());
    runtime_photo_motion(7,0);
    assert(!do_stat("/tlg-photo/control",&st) && !do_stat("/tlg-photo/control",&st));
    fd=(int)do_open("/tlg-photo/control",0,0);assert(fd>=3);
    memset(positioned,0,sizeof(positioned));assert(do_read(fd,positioned,255)>0);
    assert(strstr(positioned,"7.000000")); /* metadata preflight preserved the delta */
    assert(!do_close(fd));
    fd=(int)do_open("/tlg-photo/status",1,0);assert(fd>=3);
    char large[257]={0};assert(do_write(fd,large,sizeof(large))==-EFBIG);
    assert(!do_close(fd));
    runtime_photo_cancel();runtime_photo_enable(0);
    assert(do_open("/tlg-photo/control",0,0)==-ENOENT);
    assert(do_stat("/tlg-photo/control",&st)==-ENOENT && do_access("/tlg-photo/control",0)==-ENOENT);
    assert(!mount_count && !opens && !reads && !writes);
    puts("PASS: retail stdio path preflight, seek/pread, fragmented I/O and disabled paths; no host files");
}

/* SPDX-License-Identifier: GPL-2.0-or-later
 * Opt-in local trophy state, separate from gameplay saves. No frame/time hooks.
 * Binary wire format is shared with launcher/native_trophies.py. Writers are
 * locked across processes, merge existing state, fsync and replace atomically.
 */
#define _GNU_SOURCE
#include "runtime_trophies.h"
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#ifdef _WIN32
#include <io.h>
#include <direct.h>
#include <sys/locking.h>
#include <windows.h>
#else
#include <sys/file.h>
#endif

#define STATE_SIZE 1064
static pthread_mutex_t state_mutex=PTHREAD_MUTEX_INITIALIZER;
static char title_id[16], root_dir[3072];
static int enabled;
static uint64_t get64(const unsigned char *p) {
    uint64_t value=0; for (int i=7;i>=0;--i) value=(value<<8)|p[i]; return value;
}
static void put64(unsigned char *p,uint64_t value) {
    for (int i=0;i<8;++i) { p[i]=(unsigned char)value; value>>=8; }
}
static uint64_t digest(const unsigned char *p,size_t size) {
    uint64_t value=UINT64_C(0xcbf29ce484222325);
    for (size_t i=0;i<size;++i) value=(value^p[i])*UINT64_C(0x100000001b3);
    return value;
}
static void header(unsigned char data[STATE_SIZE],int32_t user) {
    memset(data,0,STATE_SIZE); memcpy(data,"TLGTRO1",7); data[8]=1;
    for (int i=0;i<4;++i) data[12+i]=(unsigned char)((uint32_t)user>>(8*i));
    memcpy(data+16,title_id,strlen(title_id));
}
void runtime_trophies_configure(const char *title,const char *user_root) {
    pthread_mutex_lock(&state_mutex);
    enabled=0; title_id[0]=root_dir[0]=0;
    const char *option=getenv("TLG_TROPHY_STATE");
    if (option && !strcmp(option,"1") && title &&
        (!strcmp(title,"CUSA03745") || !strcmp(title,"CUSA03627")) && user_root && *user_root &&
        strlen(user_root)<sizeof(root_dir)) {
        snprintf(title_id,sizeof(title_id),"%s",title);
        snprintf(root_dir,sizeof(root_dir),"%s",user_root);
        /* Normalize separators before bounded recursive mkdir. */
        for (char *p=root_dir;*p;++p) if (*p=='\\') *p='/';
        enabled=1;
    }
    pthread_mutex_unlock(&state_mutex);
}
int runtime_trophies_enabled(void) { return enabled; }
static int paths(int32_t user,char folder[3200],char path[3264]) {
    if (!enabled || user<=0) return -1;
    snprintf(folder,3200,"%s/achievements/user-%d",root_dir,user);
    snprintf(path,3264,"%s/%s.bin",folder,title_id); return 0;
}
static int make_dirs(char *path) {
    for (char *p=path+1;;++p) {
        if (*p!='/' && *p) continue;
        if (*p=='/' && p==path+2 && path[1]==':') continue;
        char saved=*p; *p=0;
#ifdef _WIN32
        int result=_mkdir(path);
#else
        int result=mkdir(path,0700);
#endif
        *p=saved;
        if (result && errno!=EEXIST) return -1;
        if (!saved) break;
    }
    return 0;
}
static int load(const char *path,int32_t user,unsigned char data[STATE_SIZE]) {
    unsigned char expected[STATE_SIZE]; header(expected,user);
    FILE *input=fopen(path,"rb");
    if (!input) { if (errno!=ENOENT) return -1; memcpy(data,expected,STATE_SIZE); return 0; }
    size_t size=fread(data,1,STATE_SIZE,input);
    int extra=fgetc(input), bad=ferror(input); fclose(input);
    if (size!=STATE_SIZE || extra!=EOF || bad || memcmp(data,expected,32) ||
        get64(data+STATE_SIZE-8)!=digest(data,STATE_SIZE-8)) return -1;
    for (int i=0;i<128;++i) if (get64(data+32+8*i)>UINT64_C(253402300799)) return -1;
    return 0;
}
static int disk_lock(const char *path) {
    char name[3300]; snprintf(name,sizeof(name),"%.*s.lock",(int)strlen(path)-4,path);
    int fd=open(name,O_RDWR|O_CREAT
#ifdef _WIN32
                |O_BINARY|O_NOINHERIT
#else
                |O_CLOEXEC
#endif
                ,0600);
    if (fd<0) return -1;
    /* Python msvcrt.locking and the CRT _locking lock the same first byte. */
    if (lseek(fd,0,SEEK_END)==0 && write(fd,"\0",1)!=1) { close(fd); return -1; }
    for (int i=0;i<50;++i) {
#ifdef _WIN32
        lseek(fd,0,SEEK_SET);
        if (!_locking(fd,_LK_NBLCK,1)) return fd;
        Sleep(20);
#else
        if (!flock(fd,LOCK_EX|LOCK_NB)) return fd;
        struct timespec delay={0,20000000}; nanosleep(&delay,NULL);
#endif
    }
    close(fd); return -1;
}
static void disk_unlock(int fd) {
#ifdef _WIN32
    lseek(fd,0,SEEK_SET); (void)_locking(fd,_LK_UNLCK,1);
#else
    (void)flock(fd,LOCK_UN);
#endif
    close(fd);
}
static int store(const char *path,unsigned char data[STATE_SIZE]) {
    char temporary[3320];
    put64(data+STATE_SIZE-8,digest(data,STATE_SIZE-8));
#ifdef _WIN32
    snprintf(temporary,sizeof(temporary),"%s.tmp-%lu",path,(unsigned long)GetCurrentProcessId());
#else
    snprintf(temporary,sizeof(temporary),"%s.tmp-%ld",path,(long)getpid());
#endif
    /* O_EXCL never overwrites somebody else's stale/foreign temporary. */
    int fd=open(temporary,O_WRONLY|O_CREAT|O_EXCL
#ifdef _WIN32
                |O_BINARY|O_NOINHERIT
#else
                |O_CLOEXEC
#endif
                ,0600);
    if (fd<0) return -1;
    size_t done=0;
    while (done<STATE_SIZE) {
        int n=(int)write(fd,data+done,STATE_SIZE-done);
        if (n<=0) { close(fd); unlink(temporary); return -1; }
        done+=(size_t)n;
    }
#ifdef _WIN32
    int result=_commit(fd);
#else
    int result=fsync(fd);
#endif
    if (close(fd)) result=-1;
    if (!result) {
#ifdef _WIN32
        result=-1;
        /* A lock-free UI reader can briefly hold a Windows handle without
         * delete sharing. Retry that transient condition; never discard old state. */
        for (int attempt=0;attempt<50;++attempt) {
            if (MoveFileExA(temporary,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)) { result=0; break; }
            DWORD error=GetLastError();
            if (error!=ERROR_SHARING_VIOLATION && error!=ERROR_ACCESS_DENIED && error!=ERROR_LOCK_VIOLATION) break;
            Sleep(20);
        }
#else
        result=rename(temporary,path);
#endif
    }
    if (result) unlink(temporary);
    return result;
}
int runtime_trophies_read(int32_t user,uint32_t flags[4],uint32_t *count,uint64_t stamps[128]) {
    if (!flags || !count) return -1;
    char folder[3200], path[3264]; unsigned char data[STATE_SIZE];
    pthread_mutex_lock(&state_mutex);
    int result=paths(user,folder,path);
    if (!result) result=load(path,user,data);
    if (!result) {
        memset(flags,0,16); *count=0;
        for (int i=0;i<128;++i) {
            uint64_t stamp=get64(data+32+8*i);
            if (stamps) stamps[i]=stamp;
            if (stamp) { flags[i/32]|=UINT32_C(1)<<(i%32); ++*count; }
        }
    }
    pthread_mutex_unlock(&state_mutex); return result;
}
int runtime_trophies_unlock(int32_t user,int32_t id) {
    if (id<0 || id>=128) return -1;
    char folder[3200],path[3264]; unsigned char data[STATE_SIZE];
    pthread_mutex_lock(&state_mutex);
    int result=paths(user,folder,path), fd=-1;
    if (!result) result=make_dirs(folder);
    if (!result) { fd=disk_lock(path); if (fd<0) result=-1; }
    if (!result) result=load(path,user,data);
    if (!result) {
        if (get64(data+32+8*id)) result=1;
        else {
            time_t now=time(NULL);
            if (now<=0 || (uint64_t)now>UINT64_C(253402300799)) result=-1;
            else { put64(data+32+8*id,(uint64_t)now); result=store(path,data); }
        }
    }
    if (fd>=0) disk_unlock(fd);
    pthread_mutex_unlock(&state_mutex); return result;
}

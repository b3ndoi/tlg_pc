/* SPDX-License-Identifier: GPL-2.0-or-later
 * Native state fixtures. argv[1] is a newly created temporary test directory.
 * This fixture never starts a game or touches a real save/user directory.
 */
#define _GNU_SOURCE
#undef NDEBUG
#include "runtime_trophies.h"
#ifdef _WIN32
#include "compat_win.h"
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc,char **argv) {
    assert(argc==2 || argc==4);
    uint32_t flags[4],count; uint64_t stamps[128];
#ifdef _WIN32
    assert(!_putenv_s("TLG_TROPHY_STATE","0"));
#else
    assert(!setenv("TLG_TROPHY_STATE","0",1));
#endif
    runtime_trophies_configure("CUSA03745",argv[1]);
    assert(!runtime_trophies_enabled());
    assert(runtime_trophies_unlock(1,4)<0);
#ifdef _WIN32
    assert(!_putenv_s("TLG_TROPHY_STATE","1"));
#else
    assert(!setenv("TLG_TROPHY_STATE","1",1));
#endif
    runtime_trophies_configure("../escape",argv[1]);
    assert(!runtime_trophies_enabled());
    runtime_trophies_configure("CUSA03745",argv[1]);
    assert(runtime_trophies_enabled());
    if (argc==4) {
        assert(!strcmp(argv[2],"parallel"));
        int id=atoi(argv[3]); assert(id>=0 && id<128);
        assert(runtime_trophies_unlock(4,id)>=0);
        return 0;
    }
    assert(!runtime_trophies_read(1,flags,&count,stamps) && !count);
    assert(runtime_trophies_unlock(1,-1)<0 && runtime_trophies_unlock(1,128)<0);
    assert(runtime_trophies_unlock(0,1)<0);
    const int ids[]={0,31,32,127};
    for (unsigned i=0;i<4;++i) assert(runtime_trophies_unlock(1,ids[i])==0);
    assert(runtime_trophies_unlock(1,31)==1);
    assert(!runtime_trophies_read(1,flags,&count,stamps) && count==4);
    assert(flags[0]==0x80000001u && flags[1]==1 && flags[2]==0 && flags[3]==0x80000000u);
    uint64_t before=stamps[31];
    runtime_trophies_configure("CUSA03745",argv[1]); /* cold reload */
    assert(!runtime_trophies_read(1,flags,&count,stamps) && count==4 && stamps[31]==before);
    assert(!runtime_trophies_read(2,flags,&count,stamps) && !count);
    runtime_trophies_configure("CUSA03627",argv[1]);
    assert(!runtime_trophies_read(1,flags,&count,stamps) && !count);
    runtime_trophies_configure("CUSA03745",argv[1]);
    char path[4096]; snprintf(path,sizeof(path),"%s/achievements/user-1/CUSA03745.bin",argv[1]);
    FILE *file=fopen(path,"wb"); assert(file); assert(fwrite("corrupt fixture",1,15,file)==15); fclose(file);
    assert(runtime_trophies_read(1,flags,&count,stamps)<0 && runtime_trophies_unlock(1,2)<0);
    char bytes[16]={0}; file=fopen(path,"rb"); assert(file); assert(fread(bytes,1,16,file)==15); fclose(file);
    assert(!memcmp(bytes,"corrupt fixture",15));
    /* Python may seed user 3 before this process; native writes must merge it. */
    assert(!runtime_trophies_read(3,flags,&count,stamps));
    if (count) assert(count==1 && flags[0]==(1u<<9));
    assert(!runtime_trophies_unlock(3,10));
    puts("native trophy state: persistence, cold reload, dedup, bounds, title/user isolation, corruption and opt-in pass");
    return 0;
}

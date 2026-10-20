// Offline native-code fixtures only. No process attachment, game, GPU or saves.
#include <windows.h>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <string>
#include <vector>
#include "clock_sync_60.h"
#include "input_timing_60.h"

template<class T> static T Get(const unsigned char *p,size_t at){T v;std::memcpy(&v,p+at,sizeof v);return v;}
template<class T> static void Put(unsigned char *p,size_t at,T v){std::memcpy(p+at,&v,sizeof v);}
static std::string elf;
static size_t FileAt(size_t va,size_t n){
    auto ph=Get<uint64_t>((const unsigned char*)elf.data(),0x20);
    auto stride=Get<uint16_t>((const unsigned char*)elf.data(),0x36);
    auto count=Get<uint16_t>((const unsigned char*)elf.data(),0x38);
    for(unsigned i=0;i<count;++i){auto at=ph+i*stride;auto p=(const unsigned char*)elf.data()+at;
        auto kind=Get<uint32_t>(p,0);auto base=Get<uint64_t>(p,16),bytes=Get<uint64_t>(p,32);
        if((kind==1||kind==0x61000010)&&va>=base&&va+n<=base+bytes)return Get<uint64_t>(p,8)+va-base;}
    assert(false);return 0;
}
static void Exec(void *p,size_t n){DWORD old;assert(VirtualProtect(p,n,PAGE_EXECUTE_READ,&old));assert(FlushInstructionCache(GetCurrentProcess(),p,n));}

class Fixture {
    unsigned char *image{};
    bool sync{};
    TlgClockSmooth original{},entry{};
    using PhysicsTicks=int (TLG_CLOCK_ABI *)(void*);
    PhysicsTicks physics{};
    float time{};
public:
    alignas(16) std::array<unsigned char,0x200> app{};
    alignas(16) std::array<unsigned char,0x400> timing{};
    Fixture(bool fps60,bool fine,bool synchronized):sync(synchronized){
        image=(unsigned char*)VirtualAlloc(nullptr,0x6000000,MEM_RESERVE,PAGE_NOACCESS);assert(image);
        for(size_t page:{size_t(0x1000),size_t(0xc51000),size_t(0xcfe000),size_t(0xe99000),size_t(0x14d9000),size_t(0x14da000),size_t(0x16b9000),size_t(0x16c8000),size_t(0x5938000)})
            assert(VirtualAlloc(image+page,0x1000,MEM_COMMIT,PAGE_READWRITE));
        std::memcpy(image+TLG_CLOCK_SMOOTH,elf.data()+FileAt(TLG_CLOCK_SMOOTH,TLG_CLOCK_SPAN),TLG_CLOCK_SPAN);
        std::memcpy(image+0x14d9900,elf.data()+FileAt(0x14d9900,0x100),0x100);
        std::memcpy(image+0x14da064,elf.data()+FileAt(0x14da064,20),20);
        if(fps60){Put(image,0x14d9920,0.0175f);Put(image,0x14d9924,1.f/60);Put(image,0x14d9928,0.0158333331f);}
        if(fine){Put(image,TLG_CLOCK_GRID,36000000.f);Put(image,TLG_CLOCK_GRID+8,1.f/36000000);}
        Put(image,0x5938c40,app.data());
        entry=(TlgClockSmooth)(image+TLG_CLOCK_SMOOTH);original=entry;
        if(sync){
            // Exact direct call location/ABI plus both production vtable paths.
            // The complete original smoother is never patched by this hook.
            const unsigned char align[]={0x48,0x83,0xec,8};
            const unsigned char finish[]={0x48,0x83,0xc4,8,0xc3};
            std::memcpy(image+TLG_CLOCK_CALL-4,align,sizeof align);
            std::memcpy(image+TLG_CLOCK_CALL+5,finish,sizeof finish);
            tlg_input_abs_jump(image+0x1020,(uintptr_t)tlg_clock_60_smooth);
            assert(tlg_input_rel_branch(image+TLG_CLOCK_CALL,(uintptr_t)(image+TLG_CLOCK_CALL),(uintptr_t)(image+0x1020),5,1));
            Put(image,TLG_CLOCK_VTABLE_A,(TlgClockSmooth)tlg_clock_60_smooth);
            Put(image,TLG_CLOCK_VTABLE_B,(TlgClockSmooth)tlg_clock_60_smooth);
            entry=(TlgClockSmooth)(image+TLG_CLOCK_CALL-4);
            assert(!std::memcmp(image+TLG_CLOCK_SMOOTH,
                elf.data()+FileAt(TLG_CLOCK_SMOOTH,TLG_CLOCK_SPAN),TLG_CLOCK_SPAN));
        }
        // Actual physics quantizer instructions, with only a test return after
        // conversion. The production physics function is NEVER patched.
        std::memcpy(image+TLG_CLOCK_PHYSICS,elf.data()+FileAt(TLG_CLOCK_PHYSICS,0x23),0x23);
        const unsigned char result[]={0x44,0x89,0xf8,0xc3}; // mov eax,r15d; ret
        std::memcpy(image+TLG_CLOCK_PHYSICS+0x23,result,sizeof result);
        unsigned char call[]={0x41,0x56,0x41,0x57,0x49,0x89,0xfe,0x48,0x83,0xec,8,0x48,0xb8,
            0,0,0,0,0,0,0,0,0xff,0xd0,0x48,0x83,0xc4,8,0x41,0x5f,0x41,0x5e,0xc3};
        auto target=(uintptr_t)(image+TLG_CLOCK_PHYSICS);std::memcpy(call+13,&target,8);
        std::memcpy(image+0x1080,call,sizeof call);physics=(PhysicsTicks)(image+0x1080);
        Exec(image+0x1000,0x1000);Exec(image+0xc51000,0x1000);Exec(image+0xcfe000,0x1000);Exec(image+0xe99000,0x1000);
        Reset(fps60?60.f:30.f);
    }
    ~Fixture(){VirtualFree(image,0,MEM_RELEASE);}
    void Reset(float fps){app.fill(0);timing.fill(0);time=0;
        Put(app.data(),0xb0,timing.data());Put(app.data(),0x188,0.05f);
        Put(app.data(),0x1b0,1.f);Put(app.data(),0x1b4,1.f);Put(app.data(),0x1b8,1.f);
        Put(timing.data(),0x3a0,1.f/fps);Put(timing.data(),0x3a8,1.f/fps);
    }
    void Recorded(){Reset(60);Put(app.data(),0x1a4,-0.09479793906211853f);
        Put(timing.data(),0x3a0,0.002025047317147255f);
        Put(timing.data(),0x3a4,-0.000031409326766151935f);
        Put(timing.data(),0x3a8,0.01787496544420719f);}
    float Step(float real,float speed,int pause=0){
        time+=real;Put(app.data(),0x1b8,speed);Put(app.data(),0x20,pause);
        Put(app.data(),0x1a8,Get<uint32_t>(app.data(),0x1a8)+1);
        if(sync)tlg_clock_60_configure(original);
        auto dispatch=entry;
        if(sync){unsigned route=Get<uint32_t>(app.data(),0x1a8)%3;
            if(route)dispatch=Get<TlgClockSmooth>(image,route==1?TLG_CLOCK_VTABLE_A:TLG_CLOCK_VTABLE_B);}
        dispatch(app.data(),time,real);
        float value=Get<float>(app.data(),0x19c);
        assert(value==Get<float>(timing.data(),0x39c));return value;
    }
    int Ticks(){return physics(timing.data());}
    float Filter(){return Get<float>(timing.data(),0x3a0);}
};

static void Guards(){
    const auto at=[&](size_t va,size_t n){return (const unsigned char*)elf.data()+FileAt(va,n);};
    std::vector<unsigned char> smooth(at(TLG_CLOCK_SMOOTH,TLG_CLOCK_SPAN),at(TLG_CLOCK_SMOOTH,TLG_CLOCK_SPAN)+TLG_CLOCK_SPAN);
    std::vector<unsigned char> phys(at(TLG_CLOCK_PHYSICS,0x68),at(TLG_CLOCK_PHYSICS,0x68)+0x68);
    std::vector<unsigned char> zero(at(TLG_CLOCK_PHYSICS_ZERO,19),at(TLG_CLOCK_PHYSICS_ZERO,19)+19);
    std::vector<unsigned char> constants(at(TLG_CLOCK_PHYSICS_CONSTANTS,20),at(TLG_CLOCK_PHYSICS_CONSTANTS,20)+20);
    const float snaps[]={0.0175f,1.f/60,0.0158333331f},fine[]={36000000.f,0.1f,1.f/36000000};
    std::vector<unsigned char> snap((const unsigned char*)snaps,(const unsigned char*)snaps+12),grid((const unsigned char*)fine,(const unsigned char*)fine+12);
    std::vector<unsigned char> flip{0xbe,0,0,0,0};
    std::vector<unsigned char> call(at(TLG_CLOCK_CALL,5),at(TLG_CLOCK_CALL,5)+5);
    uintptr_t table_a=0x800000000ull+TLG_CLOCK_SMOOTH,table_b=table_a;
    const auto matches=[&](const char* serial="CUSA03745",const char* version="01.00"){
        return tlg_clock_60_matches(serial,version,smooth.data(),phys.data(),zero.data(),constants.data(),flip.data(),snap.data(),grid.data(),call.data(),table_a,table_b,0x800000000ull);};
    assert(matches());assert(!matches("CUSA03627"));assert(!matches("CUSA03745","01.03"));assert(!matches(nullptr));
    unsigned mutations=0;
    for(auto *v:{&smooth,&phys,&zero,&constants,&flip,&snap,&grid,&call})for(auto& b:*v){b^=1;assert(!matches());b^=1;++mutations;}
    for(unsigned i=0;i<64;++i){table_a^=uintptr_t(1)<<i;assert(!matches());table_a^=uintptr_t(1)<<i;
        table_b^=uintptr_t(1)<<i;assert(!matches());table_b^=uintptr_t(1)<<i;mutations+=2;}
    flip[1]=1;assert(!matches());flip[1]=0;
    std::memcpy(snap.data(),at(0x14d9920,12),12);assert(!matches()); // 30/unlocked
    std::printf("PASS exact native EU guards: %u byte/pointer mutations; 30/unlocked/unknown profiles rejected\n",mutations);
}

int main(int argc,char **argv){
    std::setbuf(stdout,nullptr);assert(argc==2);std::ifstream f(argv[1],std::ios::binary);assert(f);
    elf.assign(std::istreambuf_iterator<char>(f),{});Guards();
    Fixture old(true,true,false),fixed(true,true,true),legacy(false,false,false),control(false,false,false);
    old.Recorded();fixed.Recorded();
    double old_anim=0,old_physics=0,new_anim=0,new_physics=0,fine_total=0;
    unsigned advances=0,zero_run=0,max_zero_run=0;
    for(unsigned i=0;i<1200;++i){float dt=(1.f/60)*(1+0.02f*std::sin(i*0.73f));
        float a=old.Step(dt,0.15f),b=fixed.Step(dt,0.15f);
        assert(old.Filter()==fixed.Filter());
        assert(Get<float>(old.app.data(),0x1a4)==Get<float>(fixed.app.data(),0x1a4));
        old_anim+=a;old_physics+=(float)old.Ticks()*(1.f/360);
        new_anim+=b;new_physics+=(float)fixed.Ticks()*(1.f/360);fine_total+=a;
        if(b>0){++advances;zero_run=0;}else{++zero_run;if(zero_run>max_zero_run)max_zero_run=zero_run;}
        assert(std::abs(new_anim-new_physics)<1e-7);
        assert(std::abs(new_anim-fine_total)<1.f/360);
    }
    assert(old_anim-old_physics>0.1);assert(advances>600);assert(max_zero_run<4);
    std::printf("PASS recorded catch: v6 animation %.6fs vs physics %.6fs; v7 animation/physics %.6fs/%.6fs; max zero run %u frames\n",old_anim,old_physics,new_anim,new_physics,max_zero_run);
    unsigned samples=0;double worst_error=0;
    for(float fps:{24.f,30.f,45.f,48.f,50.f,55.f,59.f,60.f,61.f,75.f,90.f,120.f})
    for(float speed:{0.1f,0.15f,0.2f,0.25f,0.3f,0.4f,0.5f,0.66f,0.7f,0.75f,0.8f,0.85f,0.95f,1.f,1.5f}){
        old.Reset(fps);fixed.Reset(fps);
        // Reset the production TLS carry through a real intentional pause.
        old.Step(1/fps,0);fixed.Step(1/fps,0);
        double expected=0,got=0,physical=0;
        for(unsigned i=0;i<1500;++i){float dt=(1/fps)*(1+0.035f*std::sin(i*0.31f));
            float scale=i<90?1+(speed-1)*(i+1)/90:speed;
            float fine=old.Step(dt,scale),shared=fixed.Step(dt,scale);
            assert(old.Filter()==fixed.Filter());assert(std::isfinite(shared)&&shared>=0);
            expected+=fine;got+=shared;physical+=(float)fixed.Ticks()*(1.f/360);
            double error=std::abs(got-expected);if(error>worst_error)worst_error=error;
            assert(error<1.f/360);assert(std::abs(got-physical)<1e-6);++samples;
        }
        for(unsigned i=0;i<30;++i){assert(fixed.Step(1/fps,0)==0);assert(fixed.Step(1/fps,speed,1)==0);samples+=2;}
        unsigned resumed=0;for(unsigned i=0;i<60;++i){if(fixed.Step(1/fps,speed)>0)++resumed;++samples;}
        assert(resumed>5);
    }
    TlgClockCarry carry{};
    assert(tlg_clock_60_quantize(&carry,std::numeric_limits<float>::quiet_NaN())==0);
    assert(tlg_clock_60_quantize(&carry,std::numeric_limits<float>::infinity())==0);
    for(float value:{-1.f,0.f,-0.f})assert(tlg_clock_60_quantize(&carry,value)==0&&carry.residual==0);
    // The gated-out 30-FPS path still executes the exact original routine.
    for(unsigned i=0;i<30000;++i){float speed=i%1000<100?0.f:i%1000<400?0.15f:1.f;
        float dt=(1.f/30)*(1+0.025f*std::sin(i*0.71f));int pause=i%701==0;
        float a=legacy.Step(dt,speed,pause),b=control.Step(dt,speed,pause);assert(std::memcmp(&a,&b,4)==0);
        auto sa=legacy.app,sb=control.app;Put(sa.data(),0xb0,(void*)nullptr);Put(sb.data(),0xb0,(void*)nullptr);
        assert(sa==sb);assert(legacy.timing==control.timing);
    }
    std::printf("PASS %u native synchronized updates, 24-120Hz, slow/ramp/fast/pause/resume; worst accumulated error %.9fs (<1/360s)\n",samples,worst_error);
    std::puts("PASS 30000 30-FPS original updates bit-identical; actual SysV direct-call relay/both vtables and native physics quantizer exercised");
}

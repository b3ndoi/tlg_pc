// Offline execution of the EXACT EU leaf smoother, not a replacement model.
// No game/window, remote process handle, GPU, inputs or source-package writes.
#include <windows.h>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

using Smooth = void (__attribute__((sysv_abi)) *)(void*, float, float);
static constexpr size_t Function=0xc51940, Constants=0x14d9900, AppGlobal=0x5938c40;
static uint16_t U16(const std::string& s,size_t p){uint16_t n;std::memcpy(&n,s.data()+p,2);return n;}
static uint32_t U32(const std::string& s,size_t p){uint32_t n;std::memcpy(&n,s.data()+p,4);return n;}
static uint64_t U64(const std::string& s,size_t p){uint64_t n;std::memcpy(&n,s.data()+p,8);return n;}
static size_t FileAt(const std::string& elf,size_t va,size_t length){
    const auto ph=U64(elf,0x20);const auto stride=U16(elf,0x36),count=U16(elf,0x38);
    for(unsigned i=0;i<count;++i){auto at=ph+i*stride;auto kind=U32(elf,at);
        auto off=U64(elf,at+8),base=U64(elf,at+16),bytes=U64(elf,at+32);
        if((kind==1||kind==0x61000010)&&va>=base&&va+length<=base+bytes){
            assert(off+va-base+length<=elf.size());return off+va-base;}}
    assert(false);return 0;
}
template<class T> static void Put(unsigned char* p,size_t off,T value){std::memcpy(p+off,&value,sizeof value);}
static float Float(const unsigned char* p,size_t off){float value;std::memcpy(&value,p+off,4);return value;}

class Fixture {
    unsigned char* image{};
    alignas(16) std::array<unsigned char,0x200> app{};
    alignas(16) std::array<unsigned char,0x400> timing{};
    Smooth run{};
    float time{};
public:
    Fixture(const std::string& elf,bool fps60,bool fine,bool unquantized_reference=false){
        image=static_cast<unsigned char*>(VirtualAlloc(nullptr,0x6000000,MEM_RESERVE,PAGE_NOACCESS));assert(image);
        for(auto page: {size_t(0xc51000),size_t(0x14d9000),size_t(0x5938000)})
            assert(VirtualAlloc(image+page,0x1000,MEM_COMMIT,PAGE_READWRITE)==image+page);
        std::memcpy(image+Function,elf.data()+FileAt(elf,Function,0x25c),0x25c);
        std::memcpy(image+Constants,elf.data()+FileAt(elf,Constants,0x100),0x100);
        // The existing EU 60-FPS snap constants, plus only v6's two data writes.
        if(fps60){Put(image,0x14d9920,0.0175f);Put(image,0x14d9924,1.0f/60);Put(image,0x14d9928,0.0158333331f);}
        if(fine){assert(fps60);Put(image,0x14d9938,36000000.0f);Put(image,0x14d9940,1.0f/36000000);}
        // TEST-ONLY reference: original filter without the four quantizer
        // operations. Production never changes these instructions.
        if(unquantized_reference)std::memset(image+0xc51ae8,0x90,30);
        Put(image,AppGlobal,app.data());
        DWORD previous;assert(VirtualProtect(image+0xc51000,0x1000,PAGE_EXECUTE_READ,&previous));
        assert(FlushInstructionCache(GetCurrentProcess(),image+Function,0x25c));
        run=reinterpret_cast<Smooth>(image+Function);Reset(fps60?60:30);
    }
    ~Fixture(){VirtualFree(image,0,MEM_RELEASE);}
    void Reset(float fps){app.fill(0);timing.fill(0);time=0;
        Put(app.data(),0xb0,timing.data());Put(app.data(),0x188,0.05f);
        Put(app.data(),0x1b0,1.0f);Put(app.data(),0x1b4,1.0f);Put(app.data(),0x1b8,1.0f);
        Put(timing.data(),0x3a0,1.0f/fps);Put(timing.data(),0x3a8,1.0f/fps);
    }
    void Recorded(){Reset(60);Put(app.data(),0x1a4,-0.09479793906211853f);
        Put(timing.data(),0x3a0,0.002025047317147255f);
        Put(timing.data(),0x3a4,-0.000031409326766151935f);
        Put(timing.data(),0x3a8,0.01787496544420719f);}
    float Step(float real,float speed,int pause=0){
        time+=real;Put(app.data(),0x1b8,speed);Put(app.data(),0x20,pause);
        run(app.data(),time,real);return Float(app.data(),0x19c);
    }
    const auto& State() const{return app;}
    const auto& Timing() const{return timing;}
};

int main(int argc,char** argv){std::setbuf(stdout,nullptr);assert(argc==2);std::ifstream f(argv[1],std::ios::binary);assert(f);
    std::string elf{std::istreambuf_iterator<char>(f),{}};
    assert(elf.substr(0,4)==std::string("\x7f" "ELF",4));
    Fixture old(elf,true,false),fixed(elf,true,true),reference(elf,true,false,true),legacy(elf,false,false),legacy_control(elf,false,false);
    old.Recorded();fixed.Recorded();
    unsigned old_zero=0,fixed_zero=0;double fixed_progress=0;
    for(unsigned i=0;i<1200;++i){float real=(1.0f/60)*(1.0f+0.02f*std::sin(i*0.73f));
        if(old.Step(real,0.15f)==0)++old_zero;auto dt=fixed.Step(real,0.15f);
        assert(std::isfinite(dt)&&dt>0);fixed_progress+=dt;}
    assert(old_zero>1100);
    std::printf("PASS recorded freeze: old %u/1200 zero steps; v6 %u/1200 zero, %.6f s gameplay progress\n",old_zero,fixed_zero,fixed_progress);
    unsigned samples=0;double worst_relative=0;
    for(float fps:{48.f,50.f,55.f,59.f,60.f,61.f,65.f,75.f,90.f,120.f})
    for(float speed:{0.001f,0.005f,0.01f,0.025f,0.05f,0.1f,0.15f,0.2f,0.25f,0.3f,0.4f,0.5f,0.66f,0.7f,0.75f,0.8f,0.85f,0.95f,1.f}){
        if(speed/fps*0.8f<0.000012f)continue; // retain native intentional near-zero gate
        fixed.Reset(fps);reference.Reset(fps);
        for(unsigned i=0;i<300;++i){fixed.Step(1.0f/fps,1);reference.Step(1.0f/fps,1);}
        for(unsigned i=0;i<90;++i){float rate=1+(speed-1)*(i+1)/90;fixed.Step(1.0f/fps,rate);reference.Step(1.0f/fps,rate);}
        double wanted=0,got=0;
        for(unsigned i=0;i<900;++i){float real=(1.0f/fps)*(1.0f+0.025f*std::sin(i*0.31f));
            float dt=fixed.Step(real,speed);assert(std::isfinite(dt)&&dt>0);++samples;
            float ref=reference.Step(real,speed);
            if(i>=300){wanted+=ref;got+=dt;}}
        double relative=std::abs(got/wanted-1);if(relative>worst_relative)worst_relative=relative;
        if(relative>=0.003)std::fprintf(stderr,"RATE DETAIL fps=%.1f speed=%.6f native_reference=%.8f got=%.8f relative=%.5f\n",fps,speed,wanted,got,relative);
        assert(relative<0.003);
        // Real zero-speed and host overlay pauses must still be exactly zero.
        for(unsigned i=0;i<60;++i){assert(fixed.Step(1/fps,0)==0);assert(fixed.Step(1/fps,speed,1)==0);samples+=2;}
        for(unsigned i=0;i<120;++i){auto dt=fixed.Step(1/fps,speed);assert(std::isfinite(dt)&&dt>=0);++samples;}
        assert(fixed.Step(1/fps,speed)>0);
    }
    std::printf("PASS real routine sweep: %u updates; speed/fps/jitter/ramp/pause/resume; worst time error vs native unquantized filter %.4f%%\n",samples,worst_relative*100);
    // The 30-FPS path never calls the v6 patch helper; compare original native
    // routine state/output bit-for-bit over ordinary, slow and paused updates.
    for(unsigned i=0;i<30000;++i){float speed=i%1000<100?0.f:i%1000<400?0.15f:i%1000<600?0.05f:1.f;
        float real=(1.f/30)*(1+0.025f*std::sin(i*0.71f));int pause=i%701==0;
        float a=legacy.Step(real,speed,pause),b=legacy_control.Step(real,speed,pause);
        assert(std::memcmp(&a,&b,4)==0);auto sa=legacy.State(),sb=legacy_control.State();
        std::memset(sa.data()+0xb0,0,sizeof(void*));std::memset(sb.data()+0xb0,0,sizeof(void*));
        assert(sa==sb);assert(legacy.Timing()==legacy_control.Timing());}
    std::puts("PASS 30 FPS: 30000 original-routine updates bit-identical, including pauses and slow motion");
}

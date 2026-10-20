// Offline only: exact ELF property-schema guards and read-only synthetic sensors.
// No game process/window, GPU, controller, save, or setting is opened.
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
#include "climb_diagnostics.h"

template<class T> static T Get(const unsigned char *p,size_t at) {
    T v; std::memcpy(&v,p+at,sizeof(v)); return v;
}
template<class T> static void Put(unsigned char *p,size_t at,T value) {
    std::memcpy(p+at,&value,sizeof(value));
}
static size_t FileAt(const std::string& elf,size_t va,size_t n) {
    const auto *p=(const unsigned char*)elf.data();
    auto ph=Get<uint64_t>(p,0x20);
    auto stride=Get<uint16_t>(p,0x36),count=Get<uint16_t>(p,0x38);
    for (unsigned i=0;i<count;++i) {
        auto q=p+ph+i*stride; auto kind=Get<uint32_t>(q,0);
        auto base=Get<uint64_t>(q,16),bytes=Get<uint64_t>(q,32);
        if ((kind==1||kind==0x61000010)&&va>=base&&va+n<=base+bytes)
            return Get<uint64_t>(q,8)+va-base;
    }
    assert(false); return 0;
}
int main(int argc,char **argv) {
    assert(argc==2);
    tlg_climb_diagnostics_sample(nullptr,0); // disabled: not even a sensor read
    std::ifstream stream(argv[1],std::ios::binary);
    std::string elf((std::istreambuf_iterator<char>(stream)),{});
    assert(elf.size()>0x700000);
    std::vector<unsigned char> image(0x6c0000,0);
    for (auto f:tlg_climb_fields)
        std::memcpy(image.data()+f.registration,elf.data()+FileAt(elf,f.registration,220),220);
    assert(tlg_climb_schema_matches(image.data(),image.size()));
    assert(!tlg_climb_schema_matches(nullptr,image.size()));
    assert(!tlg_climb_schema_matches(image.data(),0x6b7000));
    unsigned mutations=0;
    for (auto f:tlg_climb_fields) {
        bool tested=false;
        for (size_t at=0;at+10<=220;++at) {
            auto *p=image.data()+f.registration+at;
            const unsigned char prefix[]={0xc7,0x85,0x50,0xff,0xff,0xff};
            if (std::memcmp(p,prefix,6)||Get<uint32_t>(p,6)!=f.field) continue;
            for (unsigned j=0;j<10;++j) {
                p[j]^=1; assert(!tlg_climb_schema_matches(image.data(),image.size()));
                p[j]^=1; ++mutations;
            }
            tested=true;break;
        }
        assert(tested);
    }
    std::array<unsigned char,0x5500> sensor{};
    auto *p=sensor.data();
    Put(p,0x38b0,0x200u); Put(p,0x3b34,2u); Put(p,0x4090,1u);
    Put(p,0x2ca0,0.25f); Put(p,0x2ca4,-1.f); Put(p,0x2d44,1.f);
    Put(p,0x4160,0.f); Put(p,0x4164,45.f);
    Put(p,0x3b60,18.f); Put(p,0x3b64,-35.f); Put(p,0x3b68,24.f);
    Put(p,0x3b70,30.f); Put(p,0x3ef0,2.5f);
    const auto before=sensor;
    TlgClimbSummary a{};
    tlg_climb_diagnostics_enable();
    for (unsigned i=0;i<10000;++i) {
        TlgClimbSample s{}; tlg_climb_capture(p,&s);
        assert(s.buttons==0x200&&s.tracking==2&&s.detected==1);
        assert(s.axis_x==0.25f&&s.axis_y==-1.f&&s.magnitude==1);
        assert(s.moveable==0&&s.slope==45&&s.accel_x==18&&s.accel_y==-35);
        assert(s.accel_z==24&&s.accel_xz==30&&s.impulse==2.5f);
        tlg_climb_accumulate(&a,&s);
        tlg_climb_diagnostics_sample(p,1.f/60);
        assert(sensor==before);
    }
    assert(a.samples==10000&&a.held==10000&&a.detected==10000&&a.blocked==10000);
    assert(a.above_shake_threshold==10000&&a.peak_accel_xz==30&&a.peak_abs_accel_y==35);
    assert(a.peak_impulse==2.5f&&a.minimum_moveable==0&&a.invalid==0);
    TlgClimbSummary b{};
    TlgClimbSample invalid{}; invalid.moveable=std::numeric_limits<float>::quiet_NaN();
    tlg_climb_accumulate(&b,&invalid); assert(b.invalid==1);
    TlgClimbSample valid{}; valid.moveable=1; tlg_climb_accumulate(&b,&valid);
    assert(b.minimum_moveable==1&&b.blocked==0&&b.held==0&&b.above_shake_threshold==0);
    std::printf("PASS: %u EU schema byte mutations rejected; 10000 diagnostic samples leave all sensor bytes unchanged; disabled path reads nothing; invalid/idle summaries safe.\n",mutations);
}

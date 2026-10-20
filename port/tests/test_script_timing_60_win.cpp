// Offline only. Production transformer + native SysV detour, no game launch.
#include <array>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>
#include <windows.h>
#include "script_timing_60.h"
#include "runtime_photo.h"

static const char *expected_source, *expected_name;
static void *expected_vm, *expected_options;
static size_t expected_size;
static bool expect_change;
static int TLG_INPUT_ABI CompilerStub(void *vm, void *options, const char *source, size_t size, const char *name) {
    assert(vm==expected_vm && options==expected_options && name==expected_name);
    if (expect_change) {
        assert(source!=expected_source && size>expected_size);
        assert(!std::memcmp(source,"-- TLG experimental",19));
    } else assert(source==expected_source && size==expected_size);
    return 37; // return/error value must survive the host/guest ABI boundary
}

static std::string Read(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary); assert(file);
    return {std::istreambuf_iterator<char>(file),std::istreambuf_iterator<char>()};
}

static void Signatures(const std::filesystem::path& path) {
    auto elf=Read(path);
    auto *bytes=reinterpret_cast<unsigned char *>(elf.data());
    auto *code=bytes+0x4000+TLG_SCRIPT_LOAD;
    auto *caller=bytes+0x4000+TLG_SCRIPT_CALLER;
    auto *flip=bytes+0x4000+TLG_INPUT_FLIP;
    auto *dt=bytes+0x4000+TLG_INPUT_DT;
    const auto matches=[&](const char *id="CUSA03745",const char *version="01.00") {
        return tlg_script_60_matches(id,version,code,caller,flip,dt);
    };
    assert(!matches()); // real 30 FPS original
    std::memcpy(flip,tlg_input_60_flip,5);
    assert(!matches()); // flip-only unlocked
    std::memcpy(dt,tlg_input_60_dt,12);
    assert(matches());
    assert(!matches("CUSA01623") && !matches("CUSA03745","01.01"));
    for (auto [ptr,length] : {std::pair{code,sizeof(tlg_script_load_code)},
                             {caller,sizeof(tlg_script_caller_code)},{flip,size_t(5)},{dt,size_t(12)}})
        for (size_t i=0;i<length;++i) { ptr[i]^=1; assert(!matches()); ptr[i]^=1; }
    std::puts("PASS: real EU loader/caller signatures; 30/unlocked/unknown/mutated code rejected");
}

int main(int argc,char **argv) {
    assert(argc==4); // original ELF, extracted assets, Python-generated expected files
    Signatures(argv[1]);
    auto *memory=static_cast<unsigned char *>(VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_EXECUTE_READWRITE));
    assert(memory);
    std::memcpy(memory,tlg_script_load_code,8);
    // Complete the synthetic prologue, then jump to the compiler test stub.
    const unsigned char pop[] = {0x41,0x5e,0x41,0x5f,0x5d};
    std::memcpy(memory+8,pop,sizeof(pop));
    tlg_input_abs_jump(memory+13,reinterpret_cast<uintptr_t>(CompilerStub));
    std::memcpy(memory+128,tlg_script_load_code,8);
    tlg_input_abs_jump(memory+136,reinterpret_cast<uintptr_t>(memory+8));
    tlg_input_abs_jump(memory+160,reinterpret_cast<uintptr_t>(tlg_script_60_load));
    tlg_script_60_configure(reinterpret_cast<TlgScriptLoad>(memory+128));
    assert(tlg_input_rel_branch(memory,reinterpret_cast<uintptr_t>(memory),reinterpret_cast<uintptr_t>(memory+160),8,0));
    assert(FlushInstructionCache(GetCurrentProcess(),memory,4096));
    auto load=reinterpret_cast<TlgScriptLoad>(memory);
    unsigned transformed=0,unchanged=0;
    const auto assets=std::filesystem::path(argv[2]);
    {
        auto source=Read(assets/"game/scripts/common/gamesetup.lua");
        const auto original=source;
        size_t length=0;
        assert(!tlg_photo_append(source.data(),source.size(),&length));
        runtime_photo_enable(1);
        char* photo=tlg_photo_append(source.data(),source.size(),&length);
        assert(photo && length>source.size() && !std::memcmp(photo,source.data(),source.size()));
        assert(source==original && photo[length]==0);
        free(photo);
        source[0]^=1;
        assert(!tlg_photo_append(source.data(),source.size(),&length));
        source=original;source.push_back(0);
        photo=tlg_photo_append(source.data(),source.size(),&length);assert(photo);free(photo);
        runtime_photo_enable(0);
        puts("PASS: exact EU photo bootstrap, opt-in, modified-source refusal and trailing NUL");
    }
    for (const auto& entry : std::filesystem::recursive_directory_iterator(assets)) {
        if (!entry.is_regular_file() || entry.path().extension()!=".lua") continue;
        auto source=Read(entry.path());
        auto before=source;
        auto relative=std::filesystem::relative(entry.path(),assets);
        auto expected_path=std::filesystem::path(argv[3])/relative;
        size_t output_size=0;
        const char *path=nullptr;
        char *result=tlg_script_60_transform(source.data(),source.size(),&output_size,&path);
        const bool selected=std::filesystem::exists(expected_path);
        assert(bool(result)==selected);
        if (selected) {
            auto expected=Read(expected_path);
            assert(path && output_size==expected.size());
            assert(!std::memcmp(result,expected.data(),expected.size()) && result[output_size]==0);
            ++transformed;
        } else { assert(!path && output_size==source.size()); ++unchanged; }
        free(result);
        expected_source=source.data(); expected_size=source.size(); expect_change=selected;
        expected_vm=reinterpret_cast<void *>(uintptr_t(0x1234));
        expected_options=reinterpret_cast<void *>(uintptr_t(0x5678));
        expected_name="@filename-is-preserved";
        assert(load(expected_vm,expected_options,source.data(),source.size(),expected_name)==37);
        assert(source==before);
        if (selected) {
            auto terminated=source+char(0);
            size_t terminated_size;
            char *terminated_result=tlg_script_60_transform(terminated.data(),terminated.size(),&terminated_size,&path);
            auto expected=Read(expected_path);
            assert(terminated_result && terminated_size==expected.size()+1);
            assert(!std::memcmp(terminated_result,expected.data(),expected.size()) && terminated_result[expected.size()]==0);
            free(terminated_result);
            source[0]^=1;
            result=tlg_script_60_transform(source.data(),source.size(),&output_size,&path);
            assert(!result && !path && output_size==source.size());
            expect_change=false;
            assert(load(expected_vm,expected_options,source.data(),source.size(),expected_name)==37);
            // Truncated, appended, pre-patched sources must never match.
            assert(!tlg_script_60_transform(source.data(),source.size()-1,&output_size,&path));
        }
    }
    assert(transformed==8 && unchanged>=600);
    assert(VirtualFree(memory,0,MEM_RELEASE));
    std::printf("PASS: %u exact scripts transformed identically to Python; %u untouched; mutations rejected; real detour/5-argument SysV ABI/return/source immutability\n",transformed,unchanged);
}

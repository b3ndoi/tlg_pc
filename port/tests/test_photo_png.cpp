// SPDX-License-Identifier: GPL-2.0-or-later
#include "tlg_photo_png.h"
#include "tlg_png.h"
#include <cassert>
#include <fstream>
#include <iterator>
#include <vector>
int main(int argc,char** argv) {
    assert(argc==2);
    auto folder=std::filesystem::path(argv[1])/std::filesystem::path(u8"фото-čćžšđ");
    std::filesystem::create_directories(folder);
    auto path=folder/"native-1440p.png";
    std::vector<uint8_t> pixels(2560ull*1440*4);
    for(size_t i=0;i<pixels.size();i+=4) {
        pixels[i]=uint8_t(i/4);pixels[i+1]=uint8_t(i/(2560*4));pixels[i+2]=123;pixels[i+3]=255;
    }
    assert(!TlgPhoto::WritePng(path,std::span(pixels).first(12)));
    assert(!std::filesystem::exists(path));
    assert(TlgPhoto::WritePng(path,pixels));
    assert(!TlgPhoto::WritePng(path,pixels));
    std::ifstream file(path,std::ios::binary);
    std::vector<unsigned char> bytes{std::istreambuf_iterator<char>(file),{}};
    TlgPng::Image decoded;
    assert(TlgPng::DecodeRgba(bytes.data(),bytes.size(),decoded));
    assert(decoded.width==2560 && decoded.height==1440 && decoded.rgba==pixels);
    puts("PASS: exact 2560x1440 lossless RGBA PNG, Unicode path and exclusive creation");
}

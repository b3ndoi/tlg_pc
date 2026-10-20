// SPDX-License-Identifier: GPL-2.0-or-later
#include "tlg_photo_png.h"
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#ifdef _WIN32
#include <io.h>
#include <sys/stat.h>
#else
#include <unistd.h>
#endif
extern "C" {
#include <libavcodec/avcodec.h>
}
namespace TlgPhoto {
bool WritePng(const std::filesystem::path& path,std::span<const uint8_t> rgba) {
    constexpr int width=2560,height=1440;
    if (rgba.size()!=size_t(width)*height*4) return false;
    const AVCodec* codec=avcodec_find_encoder(AV_CODEC_ID_PNG);
    AVCodecContext* context=codec ? avcodec_alloc_context3(codec) : nullptr;
    AVFrame* frame=av_frame_alloc(); AVPacket* packet=av_packet_alloc();
    bool ok=context && frame && packet;
    if (ok) {
        context->width=width; context->height=height;
        context->pix_fmt=AV_PIX_FMT_RGBA; context->time_base={1,1};
        frame->width=width; frame->height=height; frame->format=AV_PIX_FMT_RGBA;
        ok=avcodec_open2(context,codec,nullptr)==0 && av_frame_get_buffer(frame,32)==0;
    }
    if (ok) {
        for(int y=0;y<height;++y) std::memcpy(frame->data[0]+y*frame->linesize[0],
                                            rgba.data()+size_t(y)*width*4,width*4);
        ok=avcodec_send_frame(context,frame)==0 && avcodec_receive_packet(context,packet)==0;
    }
    if (ok) {
#ifdef _WIN32
        int fd=_wopen(path.c_str(),_O_WRONLY|_O_CREAT|_O_EXCL|_O_BINARY,_S_IREAD|_S_IWRITE);
        FILE* file=fd>=0 ? _fdopen(fd,"wb") : nullptr;
#else
        int fd=open(path.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
        FILE* file=fd>=0 ? fdopen(fd,"wb") : nullptr;
#endif
        ok=file!=nullptr;
        if (file) {
            ok=std::fwrite(packet->data,1,size_t(packet->size),file)==size_t(packet->size);
            if (std::fclose(file)!=0) ok=false;
        } else if (fd>=0) {
#ifdef _WIN32
            _close(fd);
#else
            close(fd);
#endif
        }
    }
    av_packet_free(&packet); av_frame_free(&frame); avcodec_free_context(&context);
    return ok;
}
}

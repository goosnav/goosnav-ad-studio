#!/bin/bash
# graded frames + type + mix -> master and web versions
cd /home/goosnav/goosnav-sessions/B_how_it_is_made
OUT=deliver/LIGHTS_OUT_Goosnav_1080p.mp4
mkdir -p deliver
# timings (s): title 3.8-8.8; prices 81.0/81.9/82.8 -> out 84.95; end card from 85.9; fade out 89.55
ffmpeg -y -v warning -framerate 24 -i graded/f_%05d.png \
  -loop 1 -framerate 24 -t 90 -i ov/title.png \
  -loop 1 -framerate 24 -t 90 -i ov/price0.png \
  -loop 1 -framerate 24 -t 90 -i ov/price1.png \
  -loop 1 -framerate 24 -t 90 -i ov/price2.png \
  -loop 1 -framerate 24 -t 90 -i ov/end.png \
  -i mix.wav \
  -filter_complex "\
[0:v]tpad=stop_mode=clone:stop_duration=5,trim=duration=90,setpts=PTS-STARTPTS,format=rgba[base];\
[1:v]format=rgba,fade=t=in:st=3.8:d=0.7:alpha=1,fade=t=out:st=8.4:d=0.8:alpha=1[ti];\
[2:v]format=rgba,fade=t=in:st=81.0:d=0.45:alpha=1,fade=t=out:st=84.75:d=0.3:alpha=1[p0];\
[3:v]format=rgba,fade=t=in:st=81.9:d=0.45:alpha=1,fade=t=out:st=84.75:d=0.3:alpha=1[p1];\
[4:v]format=rgba,fade=t=in:st=82.8:d=0.45:alpha=1,fade=t=out:st=84.75:d=0.3:alpha=1[p2];\
[5:v]format=rgba,fade=t=in:st=85.9:d=0.3:alpha=1[en];\
[base][ti]overlay=0:0[b1];[b1][p0]overlay=0:0[b2];[b2][p1]overlay=0:0[b3];[b3][p2]overlay=0:0[b4];[b4][en]overlay=0:0,\
fade=t=out:st=89.55:d=0.45,format=yuv420p[v]" \
  -map "[v]" -map 6:a -c:v libx264 -preset slow -crf 17 -profile:v high -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 320k -ar 48000 -t 90 "$OUT"
echo "wrote $OUT"
# web version (~35 MB): 2-pass at ~3 Mbit/s
ffmpeg -y -v warning -i "$OUT" -c:v libx264 -preset slow -b:v 2900k -pass 1 -an -f mp4 /dev/null && \
ffmpeg -y -v warning -i "$OUT" -c:v libx264 -preset slow -b:v 2900k -pass 2 -c:a aac -b:a 160k -movflags +faststart deliver/LIGHTS_OUT_Goosnav_1080p_web.mp4
rm -f ffmpeg2pass-0.log ffmpeg2pass-0.log.mbtree
ls -la deliver

#!/bin/bash
# final render: frames 0..2072 (the white end card covers everything after 85.9 s)
cd /home/goosnav/goosnav-sessions/B_how_it_is_made
blender -b --factory-startup -P film.py -- --start 0 --end 2072 --resume --out frames >> logs/render.log 2>&1
echo "RENDER EXIT $?" >> logs/render.log

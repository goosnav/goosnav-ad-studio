#!/bin/bash
cd /home/goosnav/goosnav-sessions/B_how_it_is_made
flock /tmp/goosnav-render.lock blender -b --factory-startup -P film.py -- --portrait --start 0 --end 2072 --resume --out frames45 >> logs/render45.log 2>&1
echo "RENDER EXIT $?" >> logs/render45.log

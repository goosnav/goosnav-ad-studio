#!/bin/bash
cd /home/goosnav/goosnav-sessions/B_how_it_is_made
while ! grep -q "RENDER EXIT" logs/render45.log; do
  n=$(ls frames45 | wc -l)
  printf 'PHASE: RENDERING\nPROGRESS: %d\nUPDATED: %s\nNOTE: 4:5 final render %d/2073 frames; 16:9 already delivered to agent-exchange:deliverables/claude/%s\n' $((n*100/2073)) "$(date -Is)" $n "$(cat deliver_dir.txt)" > STATUS.md
  sleep 300
done

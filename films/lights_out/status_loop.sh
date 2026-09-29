#!/bin/bash
cd /home/goosnav/goosnav-sessions/B_how_it_is_made
while ! grep -q "RENDER EXIT" logs/render.log; do
  n=$(ls frames | wc -l)
  if grep -q '^PHASE: RENDERING' STATUS.md; then
    printf 'PHASE: RENDERING\nPROGRESS: %d/2073\nUPDATED: %s\nNOTE: final 1080p Eevee render running (~5 s/frame); grading and sound done in parallel\n' "$n" "$(date -Is)" > STATUS.md
  fi
  sleep 300
done

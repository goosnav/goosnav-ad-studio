"""Captions from the narration placement."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timing import VO_AT
durs = json.load(open('vo/durations.json'))
lines = dict(l.rstrip('\n').split('|', 1) for l in open('vo/lines.txt'))
def ts(x):
    h = int(x // 3600); m = int(x % 3600 // 60); s = x % 60
    return '%02d:%02d:%06.3f' % (h, m, s)
out = []
order = sorted(VO_AT.items(), key=lambda kv: kv[1])
nxt = {k: (order[i + 1][1] if i + 1 < len(order) else 90.0) for i, (k, _) in enumerate(order)}
for i, (k, at) in enumerate(order, 1):
    text = lines[k].replace(' ... ', ' ').replace('...', '').replace(' ,', ',')
    if k == '20':
        text = 'www.goosnav.shop'
    out.append('%d\n%s --> %s\n%s\n' % (i, ts(at).replace('.', ','), ts(min(at + durs[k] + 0.2, nxt[k] - 0.05)).replace('.', ','), text))
open('LIGHTS_OUT_Goosnav.srt', 'w').write('\n'.join(out))
print(open('LIGHTS_OUT_Goosnav.srt').read()[:900])

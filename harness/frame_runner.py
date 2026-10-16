"""Executed in Frame's environment, not in the harness interpreter.

Frame renders every framed segment (its own layout, fonts, link style and retro
effects) plus a still of the card for review. The harness splices the segments and
keeps the ad's audio.
"""
import json
from pathlib import Path
import sys

# Frame's defaults are its house style at 1080 wide; these are the geometry to scale.
GEOMETRY = {'canvas': ('side_margin',), 'title': ('size', 'top'),
            'link': ('size', 'bottom', 'underline_thickness'), 'media': ('gap',)}


def main():
    request=json.loads(Path(sys.argv[1]).read_text())
    sys.path.insert(0,str(Path(request['root'])/'app/src'))
    from goosnav_frame.core import export,settings
    k=request.get('scale',1); d=settings.defaults()
    for job in request['jobs']:
        raw=job['settings']
        for group,keys in GEOMETRY.items():
            for key in keys:
                raw.setdefault(group,{}).setdefault(key,max(1,round(d[group][key]*k)))
        retro=raw.get('retro',{})
        if retro.get('enabled'):
            # Frame draws the underline in retro pixels; thinner than one pixel inverts the box.
            raw['link']['underline_thickness']=max(raw['link']['underline_thickness'],retro.get('pixel',d['retro']['pixel']))
        export.export_mp4(settings.normalize(raw),request['input'],Path(job['output']))
        if job.get('still'):
            still=settings.normalize({**raw,'export':{**raw['export'],'time':job['still_time']}})
            export.export_png(still,request['input'],Path(job['still']))


if __name__ == '__main__':main()

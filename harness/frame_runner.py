"""Executed in Frame's environment, not in the harness interpreter.

Frame renders the framed picture (its own layout, fonts and link style) plus a
still of the card for review. The harness splices it in and keeps the ad's audio.
"""
import json
from pathlib import Path
import sys


def main():
    request=json.loads(Path(sys.argv[1]).read_text())
    sys.path.insert(0,str(Path(request['root'])/'app/src'))
    from goosnav_frame.core import export,settings
    raw=request['settings']; k=request.get('scale',1)
    # Frame's defaults are its house style at 1080 wide; scale the geometry, keep everything else.
    d=settings.defaults()
    for group,keys in {'canvas':('side_margin',),'title':('size','top'),
                       'link':('size','bottom','underline_thickness'),'media':('gap',)}.items():
        for key in keys:
            raw.setdefault(group,{}).setdefault(key,max(1,round(d[group][key]*k)))
    s=settings.normalize(raw)
    export.export_mp4(s,request['input'],Path(request['output']))
    still=settings.normalize({**raw,'export':{**raw['export'],'time':request['still_time']}})
    export.export_png(still,request['input'],Path(request['still']))


if __name__ == '__main__':main()

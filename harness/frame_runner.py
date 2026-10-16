"""Executed in Frame's environment, not in the harness interpreter."""
import json
from pathlib import Path
import sys
import subprocess


def main():
    request=json.loads(Path(sys.argv[1]).read_text())
    sys.path.insert(0,str(Path(request['root'])/'app/src'))
    from goosnav_frame.core import export,settings
    from goosnav_frame.core import media
    output=Path(request['output'])
    framed=output.with_name('framed-full.mp4')
    export.export_mp4(settings.normalize(request['settings']),request['input'],framed)
    duration=media.probe(request['input']).duration
    start=max(0, duration-2)
    # Keep the original picture until the final CTA hold; retain its audio throughout.
    subprocess.run([media.ffmpeg(),'-v','error','-y','-i',request['input'],'-i',str(framed),
        '-filter_complex',f"[0:v][1:v]overlay=enable='gte(t,{start})'[v]",
        '-map','[v]','-map','0:a:0','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',
        '-c:a','copy','-movflags','+faststart',str(output)],check=True)
    framed.unlink()


if __name__ == '__main__':main()

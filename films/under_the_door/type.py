"""UNDER THE DOOR: overlays for any format -> <work>/under_the_door/<fmt>/ov/"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config, typeset

ap = argparse.ArgumentParser(); ap.add_argument('--format', default='4x5'); a = ap.parse_args()
W, H, _ = config.FORMATS[a.format]
out = config.path('work', 'under_the_door', a.format, 'ov'); out.mkdir(parents=True, exist_ok=True)
# the Patreon leads
typeset.lines_overlay(W, H, ['The Patreon. $3 a month.', 'Goosnav Book 2. $19.95.', 'Goosklerf. From $13.95.'],
                      out / 'ov_lines.png', url='www.patreon.com/goosnav')
typeset.end_card(W, H, out / 'ov_end.png', 'Goosnav continues.', ['www.patreon.com/goosnav', 'www.goosnav.shop'])
print('overlays ->', out)

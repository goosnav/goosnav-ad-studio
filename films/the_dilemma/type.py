"""THE DILEMMA: overlays for any format -> <work>/the_dilemma/<fmt>/ov/"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config, typeset

ap = argparse.ArgumentParser(); ap.add_argument('--format', default='16x9'); a = ap.parse_args()
W, H, _ = config.FORMATS[a.format]
out = config.path('work', 'the_dilemma', a.format, 'ov'); out.mkdir(parents=True, exist_ok=True)
typeset.lines_overlay(W, H, ['Goosnav Book 2. $19.95.', 'Goosklerf. From $13.95.', 'The Patreon. $3 a month.'],
                      out / 'ov_lines.png', url='www.goosnav.shop')
typeset.end_card(W, H, out / 'ov_end.png', 'Goosnav continues.', ['www.goosnav.shop', 'www.patreon.com/goosnav'])
print('overlays ->', out)

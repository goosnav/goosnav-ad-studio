"""delayed: end card (9:16 frame, 4:5-safe)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config, typeset
out = config.path('work', 'delayed', 'lpv', 'ov'); out.mkdir(parents=True, exist_ok=True)
typeset.vignette_card(1080, 1920, out / 'ov_end.png', 'Goosklerf.', 'The trading card game. From $13.95.', 'www.goosnav.shop')

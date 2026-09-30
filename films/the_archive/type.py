"""THE ARCHIVE: end card (9:16 frame, 4:5-safe)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config, typeset
out = config.path('work', 'the_archive', 'lpv', 'ov'); out.mkdir(parents=True, exist_ok=True)
typeset.vignette_card(1080, 1920, out / 'ov_end.png', 'Paper remains compatible.', 'Goosnav Book 2. $19.95.', 'www.goosnav.shop')
print(out)

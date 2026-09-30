"""continuation_department: end card (9:16 frame, 4:5-safe)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config, typeset
out = config.path('work', 'continuation_department', 'lpv', 'ov'); out.mkdir(parents=True, exist_ok=True)
typeset.vignette_card(1080, 1920, out / 'ov_end.png', 'Goosnav continues.', 'The Goosnav Patreon. $3 a month.', 'www.patreon.com/goosnav')

"""WHAT WE SENT narration: a warm, awestruck cosmic-science presenter in a small planetarium dome.
  python3 films/the_probe/vo.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config, vo
HERE = os.path.dirname(os.path.abspath(__file__))
vo.build(os.path.join(HERE, 'lines.txt'), config.path('work', 'the_probe', 'vo'),
         voice='en_US-ryan-high', slow=0.96, length=1.14, pause=0.62, reverb=0.2,
         warmth=0.4, room_seconds=1.6, room_decay=4.2)

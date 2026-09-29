"""UNDER THE DOOR narration: close, intimate, a small soft room (studio.vo.build with a short room).
  python3 films/under_the_door/vo.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from studio import config, vo
HERE = os.path.dirname(os.path.abspath(__file__))
vo.build(os.path.join(HERE, 'lines.txt'), config.path('work', 'under_the_door', 'vo'),
         voice='en_GB-jenny_dioco-medium', slow=0.97, length=1.18, pause=0.8, reverb=0.16,
         warmth=0.28, room_seconds=1.1, room_decay=5.5)

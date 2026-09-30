"""Cast voices for the vignettes. Commercially safe Piper voices only (see PLAYBOOK: voice licences)."""
import sys; sys.path.insert(0, '/home/goosnav/Desktop/code/goosnav-ad-studio')
from studio import vo, config
casts = {
 'show_and_tell': {'P1': dict(voice='en_US-john-medium', reverb=0.15, room_seconds=1.5, room_decay=4.0),
                   'P2': dict(voice='en_US-bryce-medium', reverb=0.15, room_seconds=1.5, room_decay=4.0),
                   'P3': dict(voice='en_US-norman-medium', slow=0.97, reverb=0.15, room_seconds=1.5, room_decay=4.0, pause=0.7)},
 'the_archive': {'ARCHIVIST': dict(voice='en_US-norman-medium', slow=0.97, reverb=0.25, room_seconds=2.5, room_decay=2.2),
                 'ASSISTANT': dict(voice='en_GB-cori-medium', reverb=0.9, room_seconds=4.0, room_decay=1.2, warmth=0.0)},
 'continuation_department': {'CLERK': dict(voice='en_GB-jenny_dioco-medium', slow=0.98, reverb=0.1),
                             'VISITOR': dict(voice='en_US-joe-medium', reverb=0.35, room_seconds=3.0, room_decay=2.0)},
 'delayed': {'PA': dict(voice='en_US-kristin-medium', radio=True, reverb=0.7, room_seconds=3.5, room_decay=1.5, length=1.12),
             'A': dict(voice='en_US-john-medium', slow=1.0, reverb=0.3, room_seconds=2.5, room_decay=2.5),
             'B': dict(voice='en_US-ljspeech-high', reverb=0.3, room_seconds=2.5, room_decay=2.5)},
}
import sys
only = sys.argv[1:] or list(casts)
for film, cast in casts.items():
    if film not in only:
        continue
    print('==', film)
    vo.build_cast(config.REPO / 'films' / film / 'lines.txt', config.path('work', film, 'vo'), cast)

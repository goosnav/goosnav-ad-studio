"""Lay out a five-line Book Two reaction short from its measured voice takes.

python3 films/reaction_shorts/layout.py SLUG WORKDIR

Lines are r1 (reader reads the item), p1 (friend reacts), r2 (reader adds the detail, over
the page insert), p2 (friend's escalating want, seen from the book), then the book shuts
and r3 lands the closing line. The pattern is the one that passed scene_check in
DRAW YOUR OWN; films/draw_your_own/{scene,animate,sound,render,finish}.py perform it.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHORTS = {
    'brain_surgery': {'title': 'Get in line for Book Two', 'leaf': 31, 'insert': 'CAM_insert_L',
                      'page': 'interior page 62 (printed comic 60): BARGAIN BIN BRAIN SURGERY & BUTCHER BOT; SLEEP BOT with a JAR FOR THE BRAIN'},
    'littlest_librarian': {'title': 'Read Book Two quietly', 'leaf': 33, 'insert': 'CAM_insert_R', 'quiet': True,
                           'page': 'interior page 67 (printed comic 65): WISSORS; THE LITTLEST LIBRARIAN beside books taller than her'},
    'wissors': {'title': 'Get your own copy', 'leaf': 33, 'insert': 'CAM_insert_R',
                'page': 'interior page 67 (printed comic 65): WISSORS (scissors made of worms); THE LITTLEST LIBRARIAN'},
}
FPS, CARD = 24, 3.0


def frame(t):
    return math.ceil(t * FPS) / FPS


def main():
    slug, work = sys.argv[1], Path(sys.argv[2]).expanduser()
    spec = SHORTS[slug]
    manifest = json.loads((work / 'voice/manifest.json').read_text())
    lines = {l['id']: l for l in manifest['lines']}

    def dur(i):
        take = lines[i]['takes'][0]['polished']
        return (take['active_end_sample'] - take['active_start_sample']) / 48000 + 0.09

    def take(i):
        return f"voice:{i}:{lines[i]['takes'][0]['settings']['speed']}"

    starts, shots, events = {}, [], []
    turn = 1.75
    events.append({'name': 'page_turn', 'at': turn, 'leaf': spec['leaf']})
    shots += [{'camera': 'CAM_wide', 'start': 0.0, 'end': 1.6},
              {'camera': spec['insert'], 'start': 1.6, 'end': 3.2, 'hide_reader_body': True}]
    starts['r1'] = 3.3
    t = starts['r1'] + dur('r1')
    shots.append({'camera': 'CAM_reader', 'start': 3.2, 'end': round(t + 0.1, 3)})
    starts['p1'] = round(t + 0.3, 3)
    t = starts['p1'] + dur('p1')
    shots.append({'camera': 'CAM_pal_ecu', 'start': shots[-1]['end'], 'end': round(t + 0.15, 3)})
    starts['r2'] = round(t + 0.35, 3)
    t = starts['r2'] + dur('r2')
    cut_to_face = round(starts['r2'] + 0.55 * dur('r2'), 3)    # face on camera for 45% of the line
    shots += [{'camera': spec['insert'], 'start': shots[-1]['end'], 'end': cut_to_face, 'hide_reader_body': True},
              {'camera': 'CAM_reader', 'start': cut_to_face, 'end': round(t + 0.1, 3)}]
    starts['p2'] = round(t + 0.3, 3)
    t = starts['p2'] + dur('p2')
    shots.append({'camera': 'CAM_pal_lean', 'start': shots[-1]['end'], 'end': round(t + 0.1, 3)})
    if spec.get('quiet'):
        events.append({'name': 'shush', 'at': round(t + 0.45, 3), 'tiny': True, 'gain_db': 4})
        slam = round(t + 1.5, 3)
        events.append({'name': 'slam', 'at': slam, 'gain_db': -16})   # eased shut, not slammed
    else:
        slam = round(t + 0.4, 3)
        events.append({'name': 'slam', 'at': slam})
    starts['r3'] = round(slam + 0.3, 3)
    t = starts['r3'] + dur('r3')
    shots.append({'camera': 'CAM_two', 'start': shots[-1]['end'], 'end': round(t + 0.15, 3)})
    story_end = frame(t + 1.0)                                       # the friend's silent reaction
    shots.append({'camera': 'CAM_pal_ecu', 'start': shots[-1]['end'], 'end': story_end})
    cut = {'title': slug.replace('_', ' ').title(), 'slug': slug, 'fps': FPS,
           'duration': story_end + CARD,
           'book': {'model': 'props/hq/book2_goosnav_dilemma_openable_v2.blend',
                    'collection': 'Book Two — openable v2', 'open_through': spec['leaf'] - 1,
                    'turn_leaf': spec['leaf'], 'insert_page': spec['page']},
           'end_card': {'start': story_end, 'seconds': CARD, 'title': spec['title']},
           'lines': [{'id': i, 'speaker': lines[i]['speaker'], 'text': lines[i]['text'], 'take': take(i),
                      'start': starts[i]} for i in ('r1', 'p1', 'r2', 'p2', 'r3')],
           'events': events, 'shots': shots}
    (HERE / slug / 'cut.json').write_text(json.dumps(cut, indent=2, ensure_ascii=False) + '\n')
    print(slug, cut['duration'])


if __name__ == '__main__':
    main()

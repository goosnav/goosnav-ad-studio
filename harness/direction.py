"""The director's plan and the deterministic checks that hold production to it.

The director is a worker; these checks are controller code. They catch what
reviews kept missing: buried dialogue, a voice cast against its character,
lines crammed faster than anyone can hear them, and beats too short to read.
"""
import array
import math
import re
import wave

from .contracts import ContractError

GENDERS = ('male', 'female', 'neutral')
MAX_WORDS_PER_SECOND = 3.0   # spoken English is ~2.5 w/s; above 3 an ad feels gabbled
MIN_BEAT_SECONDS = 0.75      # a shot shorter than this rarely reads on a phone
START_TOLERANCE = 0.75       # measured takes may land this far from the planned start

# Mix gates, measured on the mixed WAV in dBFS. Calibrated on the RETURN SLOT failure
# (speech -27, wind bed -19.6, chute -9.7): every one of these rejects that mix.
SPEECH_FLOOR_DB = -24.0      # loud half of a line's 50 ms frames
SPEECH_OVER_BED_DB = 8.0     # line level above the median non-dialogue level
FX_OVER_SPEECH_DB = 3.0      # no 400 ms stretch outside dialogue louder than this over the loudest line


def words(text):
    return len(re.findall(r"[A-Za-z0-9']+", text))


def kokoro_gender(voice):
    # Kokoro voice IDs: <language><f|m>_<name>, e.g. af_heart, am_onyx, bm_george.
    m = re.fullmatch(r'[a-z]([fm])_[a-z0-9_]+', voice or '')
    return {'f': 'female', 'm': 'male'}[m.group(1)] if m else None


def _num(d, key, where):
    v = d.get(key)
    if type(v) not in (int, float) or not math.isfinite(v):
        raise ContractError(f'{where}.{key} must be a number of seconds')
    return float(v)


def _text(d, key, where):
    if not isinstance(d.get(key), str) or not d[key].strip():
        raise ContractError(f'{where}.{key} is required text')
    return d[key]


def check_direction(direction, config):
    """Validate the director's plan; return it with derived numbers filled in."""
    if not isinstance(direction, dict):
        raise ContractError('direction must be an object')
    o = config['output']; frame = 1 / o['fps'] + 1e-6
    duration = _num(direction, 'duration', 'direction')
    if not o['min_seconds'] <= duration <= o['max_seconds']:
        raise ContractError(f'direction.duration {duration} is outside {o["min_seconds"]}-{o["max_seconds"]} s')
    story_end = duration
    card = direction.get('end_card')
    if config['output']['cta']:
        if not isinstance(card, dict):
            raise ContractError('direction.end_card is required: Frame sets the end text')
        seconds = _num(card, 'seconds', 'end_card')
        if not min(o['end_card_seconds'], duration / 2) - .05 <= seconds <= duration / 2:
            raise ContractError(f'end_card.seconds must be at least {o["end_card_seconds"]} and at most half the ad')
        title = _text(card, 'title', 'end_card')
        if len(title) > 60 or re.search(r'https?://|www\.|\.\w{2,4}\b/?$', title, re.I):
            raise ContractError('end_card.title is short copy (60 chars max) without the web address')
        _text(card, 'picture', 'end_card')
        story_end = duration - seconds
    beats = direction.get('beats')
    if not isinstance(beats, list) or not beats:
        raise ContractError('direction.beats must list the shots')
    cursor = 0.0
    for i, b in enumerate(beats):
        where = f'beats[{i}]'
        if not isinstance(b, dict):
            raise ContractError(f'{where} must be an object')
        start, end = _num(b, 'start', where), _num(b, 'end', where)
        for key in ('shot', 'picture', 'sound'):
            _text(b, key, where)
        if not isinstance(b.get('faces'), list) or not all(isinstance(f, str) for f in b['faces']):
            raise ContractError(f'{where}.faces must list the speakers whose faces are visible (may be empty)')
        if abs(start - cursor) > frame:
            raise ContractError(f'{where} starts at {start}; beats must be contiguous from 0 (expected {cursor:.3f})')
        if end - start < MIN_BEAT_SECONDS - 1e-6:
            raise ContractError(f'{where} lasts {end - start:.2f} s; hold a beat at least {MIN_BEAT_SECONDS} s')
        cursor = end
    if abs(cursor - story_end) > frame:
        raise ContractError(f'beats end at {cursor}; they must end where the end card starts ({story_end:.3f})')
    cast = direction.get('cast')
    if not isinstance(cast, list):
        raise ContractError('direction.cast must be a list (empty for a film without voices)')
    voices = {}
    for i, c in enumerate(cast):
        where = f'cast[{i}]'
        if not isinstance(c, dict):
            raise ContractError(f'{where} must be an object')
        speaker = _text(c, 'speaker', where); _text(c, 'character', where); _text(c, 'performance', where)
        voice = _text(c, 'voice', where)
        if c.get('gender') not in GENDERS:
            raise ContractError(f'{where}.gender must be one of {", ".join(GENDERS)}')
        if config['audio']['voice_provider'] == 'kokoro':
            heard = kokoro_gender(voice)
            if heard is None:
                raise ContractError(f'{where}.voice {voice!r} is not a Kokoro voice ID (af_heart, am_onyx, ...)')
            if c['gender'] != 'neutral' and heard != c['gender']:
                raise ContractError(f'{where}: {c["character"]} is {c["gender"]} but {voice} is a {heard} voice')
        if speaker in voices:
            raise ContractError(f'Speaker {speaker} is cast twice')
        voices[speaker] = voice
    lines = direction.get('lines')
    if not isinstance(lines, list):
        raise ContractError('direction.lines must be a list (empty for a film without dialogue)')
    previous = 0.0
    for i, line in enumerate(lines):
        where = f'lines[{i}]'
        if not isinstance(line, dict):
            raise ContractError(f'{where} must be an object')
        speaker = _text(line, 'speaker', where); text = _text(line, 'text', where)
        _text(line, 'delivery', where)
        start, end = _num(line, 'start', where), _num(line, 'end', where)
        if speaker not in voices:
            raise ContractError(f'{where}: speaker {speaker} is not in the cast')
        # The audience has to see who is talking: the speaker's face is in a beat the line
        # overlaps, unless the plan says why the voice is off screen.
        seen = any(speaker in b['faces'] for b in beats if b['start'] < end and b['end'] > start)
        if not seen and not (isinstance(line.get('offscreen'), str) and line['offscreen'].strip()):
            raise ContractError(f'{where}: no beat during "{text}" shows {speaker}\'s face; '
                                'show the speaker while they talk or give an offscreen reason')
        if not 0 <= start < end <= duration:
            raise ContractError(f'{where} timing is outside the ad')
        if start < previous - 1e-6:
            raise ContractError(f'{where} starts before the previous line; lines are listed in order')
        rate = words(text) / (end - start)
        if rate > MAX_WORDS_PER_SECOND:
            raise ContractError(f'{where} needs {rate:.1f} words/s; give it more time or cut words '
                                f'(max {MAX_WORDS_PER_SECOND})')
        previous = start
    return direction


def _mono(path):
    with wave.open(str(path)) as w:
        rate, channels, n = w.getframerate(), w.getnchannels(), w.getnframes()
        if w.getsampwidth() != 2:
            raise ContractError('Mix must be PCM16')
        raw = array.array('h', w.readframes(n))
    if channels == 1:
        return rate, raw
    return rate, [sum(raw[i:i + channels]) / channels for i in range(0, len(raw), channels)]


def _db(samples):
    if not samples:
        return -120.0
    power = sum(v * v for v in samples) / len(samples)
    return 10 * math.log10(power / 32768 ** 2 + 1e-12)


def mix_levels(path, dialogue):
    """Speech, bed and loudest-effect levels (dBFS) of a mix with timed dialogue."""
    rate, x = _mono(path)
    step = rate // 20  # 50 ms
    speech = []
    for line in dialogue:
        a, b = line['start_sample'], min(line['end_sample'], len(x))
        frames = sorted((_db(x[i:i + step]) for i in range(a, max(a + 1, b - step + 1), step)), reverse=True)
        loud = frames[:max(1, len(frames) // 2)]
        speech.append({'text': line['text'], 'speaker': line['speaker'],
                       'db': 10 * math.log10(sum(10 ** (f / 10) for f in loud) / len(loud))})
    inside = bytearray(len(x))
    for line in dialogue:
        inside[line['start_sample']:line['end_sample']] = b'\x01' * (min(line['end_sample'], len(x)) - line['start_sample'])
    window = rate * 2 // 5  # 400 ms
    outside = [_db(x[i:i + window]) for i in range(0, max(1, len(x) - window), rate // 10)
               if not any(inside[i:i + window])]
    outside = [v for v in outside if v > -90]  # true digital silence is not a bed
    bed = sorted(outside)[len(outside) // 2] if outside else -120.0
    return {'speech': speech, 'bed_db': bed, 'loudest_outside_db': max(outside, default=-120.0)}


def check_mix(path, timeline):
    """Dialogue has to be the lead. Returns the measurements; raises with a mixing brief."""
    dialogue = timeline.get('dialogue') or []
    if not dialogue:
        return {'speech': [], 'note': 'no dialogue'}
    m = mix_levels(path, dialogue)
    problems = []
    for s in m['speech']:
        if s['db'] < SPEECH_FLOOR_DB:
            problems.append(f'"{s["text"]}" is {s["db"]:.1f} dBFS; raise speech to at least {SPEECH_FLOOR_DB}')
        if s['db'] - m['bed_db'] < SPEECH_OVER_BED_DB:
            problems.append(f'"{s["text"]}" is only {s["db"] - m["bed_db"]:.1f} dB over the bed '
                            f'({m["bed_db"]:.1f} dBFS); need {SPEECH_OVER_BED_DB}')
    loudest = max(s['db'] for s in m['speech'])
    if m['loudest_outside_db'] - loudest > FX_OVER_SPEECH_DB:
        problems.append(f'an effect/bed passage reaches {m["loudest_outside_db"]:.1f} dBFS, '
                        f'{m["loudest_outside_db"] - loudest:.1f} dB over the loudest line; '
                        f'keep effects within {FX_OVER_SPEECH_DB} dB of speech')
    if problems:
        raise ContractError('Dialogue is not the lead of the mix: ' + '; '.join(problems))
    return m


def check_cast(timeline, direction):
    """Every planned line is voiced, in order, by its cast voice, near its planned time."""
    sample_rate = timeline['sample_rate']
    voices = {c['speaker']: c['voice'] for c in direction.get('cast', [])}
    planned, heard = direction.get('lines', []), timeline.get('dialogue', [])
    if len(planned) != len(heard):
        raise ContractError(f'The direction has {len(planned)} lines; the timeline has {len(heard)}')
    for plan, line in zip(planned, heard):
        if line.get('speaker') != plan['speaker']:
            raise ContractError(f'Line "{plan["text"]}" belongs to {plan["speaker"]}, got {line.get("speaker")}')
        if line.get('voice') != voices[plan['speaker']]:
            raise ContractError(f'{plan["speaker"]} is cast as {voices[plan["speaker"]]}; '
                                f'timeline says voice {line.get("voice")!r}')
        start = line['start_sample'] / sample_rate
        if abs(start - plan['start']) > START_TOLERANCE:
            raise ContractError(f'"{plan["text"]}" starts at {start:.2f} s; the direction places it at {plan["start"]} s')

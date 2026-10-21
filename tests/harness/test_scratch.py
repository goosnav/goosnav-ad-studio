import json
from pathlib import Path

import pytest

from harness.contracts import ContractError, promote
from tests.harness.test_voice import FakeSession


def test_direction_requires_real_declared_measured_takes(tmp_path):
    from harness.direction import check_scratch_takes
    direction = {'lines': [{'speaker':'A','text':'Hello.','start':0,'end':1}],
                 'cast': [{'speaker':'A','voice':'am_michael'}]}
    with pytest.raises(ContractError, match='scratch_takes'):
        check_scratch_takes({'direction':direction,'files':[]}, tmp_path)
    from harness.voice import run_batch
    run_batch({'lines':[{'speaker':'A','text':'Hello.','voice':'am_michael'}]},
              tmp_path/'scratch', session=FakeSession())
    files = [{'path':str(p.relative_to(tmp_path)), 'kind':'audio' if p.suffix=='.wav' else 'manifest'}
             for p in (tmp_path/'scratch').rglob('*') if p.is_file() and '.voice-cache' not in p.parts]
    data = {'summary':'fixture','direction':direction,'scratch_takes':'scratch/manifest.json','files':files}
    check_scratch_takes(data, tmp_path)
    accepted = promote(data, tmp_path, tmp_path/'accepted')
    assert Path(accepted['scratch_takes']).is_file()
    direction['lines'][0]['text'] = 'Different line.'
    with pytest.raises(ContractError, match='match'):
        check_scratch_takes(data, tmp_path)
    direction['lines'][0]['text'] = 'Hello.'
    direction['lines'][0]['end'] = .01
    with pytest.raises(ContractError, match='fit'):
        check_scratch_takes(data, tmp_path)


def test_scratch_audio_must_be_declared_and_hash_verified(tmp_path):
    from harness.direction import check_scratch_takes
    from harness.voice import run_batch
    run_batch({'lines':[{'speaker':'A','text':'Hello.','voice':'am_michael'}]},
              tmp_path/'scratch', session=FakeSession())
    data = {'direction': {'lines':[{'speaker':'A','text':'Hello.','start':0,'end':1}],
                          'cast':[{'speaker':'A','voice':'am_michael'}]},
            'scratch_takes':'scratch/manifest.json', 'files':[{'path':'scratch/manifest.json','kind':'manifest'}]}
    with pytest.raises(ContractError, match='declared'):
        check_scratch_takes(data, tmp_path)
    data['files'] += [{'path':str(p.relative_to(tmp_path)), 'kind':'audio'}
                      for p in (tmp_path/'scratch/takes').rglob('*.wav')]
    m=json.loads((tmp_path/'scratch/manifest.json').read_text())
    wave_path=tmp_path/'scratch'/m['lines'][0]['takes'][0]['polished']['path']
    wave_path.write_bytes(b'corrupt')
    with pytest.raises(ContractError, match='hash'):
        check_scratch_takes(data,tmp_path)


@pytest.mark.parametrize('quiet_tail', [False, True])
def test_full_wav_gate_acceptance_assembles_and_overslot_is_rejected(tmp_path, quiet_tail):
    import array
    import wave
    from harness.direction import check_scratch_takes
    from harness.voice import run_batch
    from harness.mix import assemble

    class MeasuredSession(FakeSession):
        def synthesize(self, request, output):
            # 400 ms full WAV; quiet nonzero tails are NOT removable digital silence.
            samples = [4000, -4000] * 9600
            if quiet_tail:
                samples[-4800:] = [1, -1] * 2400
            with wave.open(str(output), 'wb') as stream:
                stream.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
                stream.writeframes(array.array('h', samples).tobytes())
            return {'wall_seconds': 0}

    manifest = run_batch({'provider':'kokoro','polish':False,
                          'lines':[{'id':'hello','speaker':'A','text':'Hello.','voice':'am_michael'}]},
                         tmp_path/'scratch', session=MeasuredSession())
    take = manifest['lines'][0]['takes'][0]
    data = {'summary':'Authored timing', 'scratch_takes':'scratch/manifest.json',
            'direction': {'duration':2, 'lines':[{'id':'hello','speaker':'A','text':'Hello.',
                                                 'start':.3,'end':.7}],
                          'cast':[{'speaker':'A','voice':'am_michael'}]},
            'files':[{'path':'scratch/manifest.json','kind':'voice_manifest'}]}
    data['files'] += [{'path':'scratch/'+take[k]['path'],'kind':'audio'} for k in ('raw','polished')]
    measurement = check_scratch_takes(data, tmp_path)
    promote(data,tmp_path,tmp_path/'accepted')
    result = assemble(tmp_path/'accepted/accepted.json',tmp_path/'audio',no_bed=True,fps=24)
    assert (tmp_path/'audio'/result['mix']).is_file()
    audit = json.loads((tmp_path/'audio/audit.json').read_text())
    assert audit['lines'][0]['trim_start_samples'] == audit['lines'][0]['trim_end_samples'] == 0
    data['direction']['lines'][0]['end'] = .69
    with pytest.raises(ContractError,match='fit'):
        check_scratch_takes(data,tmp_path)
    assert measurement[0]['duration_seconds'] == .4


@pytest.fixture
def repeated_scratch(tmp_path):
    from harness.voice import run_batch
    manifest = run_batch({'provider':'kokoro', 'polish':False, 'lines':[
        {'id':'short', 'speaker':'A', 'text':'Hello.', 'voice':'am_michael', 'speed':1},
        {'id':'long', 'speaker':'A', 'text':'Hello.', 'voice':'am_michael', 'speed':.5},
    ]}, tmp_path/'scratch', session=FakeSession())
    data = {'summary':'Repeated words, distinct measured takes',
            'scratch_takes':'scratch/manifest.json',
            'direction': {'duration':2, 'cast':[{'speaker':'A','voice':'am_michael'}],
                          'lines':[
                              {'id':'long','speaker':'A','text':'Hello.','start':0,'end':.5},
                              {'id':'short','speaker':'A','text':'Hello.','start':1,'end':1.25},
                          ]},
            'files':[{'path':'scratch/manifest.json','kind':'voice_manifest'}]}
    data['files'] += [{'path':'scratch/'+entry['takes'][0][kind]['path'],'kind':'audio'}
                     for entry in manifest['lines'] for kind in ('raw','polished')]
    return data, manifest


@pytest.mark.parametrize('explicit_ids', [True, False])
def test_repeated_lines_use_distinct_matching_takes_and_assemble(tmp_path, repeated_scratch, explicit_ids):
    from harness.direction import check_scratch_takes
    from harness.mix import assemble
    data, manifest = repeated_scratch
    if not explicit_ids:
        # Without IDs, both consumers must consume entries in manifest order.
        for line in data['direction']['lines']:
            del line['id']
        data['direction']['lines'][0]['end'] = .25
        data['direction']['lines'][1]['end'] = 1.5
    long_line = data['direction']['lines'][0 if explicit_ids else 1]
    proper_end = long_line['end']
    long_line['end'] = long_line['start'] + .3
    with pytest.raises(ContractError, match='fit'):
        check_scratch_takes(data, tmp_path)
    long_line['end'] = proper_end
    measurements = check_scratch_takes(data, tmp_path)
    assert [m['duration_seconds'] for m in measurements] == (
        [.5, .25] if explicit_ids else [.25, .5])
    expected_entries = list(reversed(manifest['lines'])) if explicit_ids else manifest['lines']
    assert [m['take_id'] for m in measurements] == [e['selected_take_id'] for e in expected_entries]
    promote(data, tmp_path, tmp_path/'accepted')
    result = assemble(tmp_path/'accepted/accepted.json', tmp_path/'audio', no_bed=True, fps=24)
    assert (tmp_path/'audio'/result['mix']).is_file()
    audit = json.loads((tmp_path/'audio/audit.json').read_text())
    assert all(line['trim_start_samples'] == line['trim_end_samples'] == 0 for line in audit['lines'])


@pytest.mark.parametrize('invalid', [
    'duplicate_line_id', 'duplicate_selected_take', 'missing_selected_take',
    'wrong_line_id', 'manifest_voice', 'line_voice', 'duplicate_cast', 'reused_entry',
])
def test_scratch_selection_rejects_ambiguous_or_mismatched_inputs(tmp_path, repeated_scratch, invalid):
    from harness.direction import check_scratch_takes
    data, manifest = repeated_scratch
    # Generous slots isolate matching from duration checks.
    for line in data['direction']['lines']:
        line['end'] = line['start'] + .75
    if invalid == 'duplicate_line_id':
        manifest['lines'][1]['id'] = manifest['lines'][0]['id']
    elif invalid == 'duplicate_selected_take':
        manifest['lines'][1]['takes'].append(manifest['lines'][1]['takes'][0])
    elif invalid == 'missing_selected_take':
        manifest['lines'][1]['selected_take_id'] = 'nonexistent'
    elif invalid == 'wrong_line_id':
        data['direction']['lines'][0]['id'] = 'nonexistent'
    elif invalid == 'manifest_voice':
        manifest['lines'][1]['voice'] = 'af_heart'
    elif invalid == 'line_voice':
        data['direction']['lines'][0]['voice'] = 'af_heart'
    elif invalid == 'duplicate_cast':
        data['direction']['cast'].append(dict(data['direction']['cast'][0]))
    elif invalid == 'reused_entry':
        data['direction']['lines'][1]['id'] = 'long'
    (tmp_path/'scratch/manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ContractError):
        check_scratch_takes(data, tmp_path)

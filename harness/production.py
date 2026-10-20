"""Concise script -> animator -> editor workflow for new CLI runs.

Legacy snapshots retain their original graphs. Mechanical audio/render/edit helpers
are tools of the creative worker, not additional agent jobs or approval gates.
"""
import copy
import json
from pathlib import Path
import shlex
import sys

from .contracts import ContractError, digest

REPO = Path(__file__).resolve().parents[1]


def compact_run(state):
    return any(t['stage'] == 'script' for t in state.get('tasks', []))


def selected_script(state, ad):
    task = next(t for t in state['tasks'] if t['stage'] == 'script')
    return task['result']['scripts'][ad]


def animation_result(state, ad):
    return next(t['result'] for t in state['tasks']
                if t['ad'] == ad and t['stage'] == 'animate' and t['status'] == 'succeeded')


SCRIPT_JOB = '''Write one concise, chosen script guide per requested ad, in array order.
Use the supplied product facts and active character names. No research, file exploration,
voice synthesis, Blender, storyboard rendering, alternative candidates or separate plan.
Choose an interesting concrete situation with a clear turn/payoff and a reason the product
is present. Do not repeat a recent premise from past_results_reference_only unless the
user explicitly asks for a variation; reuse successful techniques, not the same story.
Write short, natural dialogue that fits the STORY_SECONDS; aim for at most
two spoken words per story second and leave a reaction. One or two characters and a
readable product are enough. Describe the action and 1-3 shots briefly. The animator owns
actual staging, measured timing and technical choices. Keep each entire guide under 120 words.
Immediately write result.json: {"summary":"...","files":[],"scripts":[
{"id":"unique-id","title":"short unique title","premise":"one sentence",
"script":"brief shots and exact dialogue/action","visual_direction":"setting and key visual",
"product":"exact supplied product name","cta":"short product CTA"}]}.
Return exactly COUNT guides, no surrounding report.'''

ANIMATOR_JOB = '''Make the complete animated ad from SCRIPT. You own staging, scene construction,
voice takes, timing, action and the finished render. Keep one working scene and build script;
inspect a few useful frames yourself. No separate storyboard submission or board-review agent.
Reuse active assets from active-assets.json. Start with a suitable existing environment and
real character/product models; author scenery and action when they materially help the story.
Work within the requested effort: low uses a simple existing setup, medium a distinctive
variation, high can develop more ambitious staging. Give the film early-game atmosphere and
clear action. Do not build photorealistic detail, invent rig capabilities or redraw product art.

1. Write plan.json: {summary,direction:{duration:TARGET_SECONDS,cast,lines,beats?,end_card,mix}}.
cast entries: {speaker,character,model:active character path,gender,voice,performance}.
lines: {speaker,text,delivery,start?}; keep text short. Male Kokoro voices include am_michael,
bm_lewis; female voices bf_emma, af_heart. Distinct characters should sound distinct.
end_card: {seconds,title,picture,product}; reserve CARD_SECONDS at the end, with no speech.
mix explains sound. Optional beats describe contiguous shots before the card:
{start,end,shot,picture,sound,faces:[speaker IDs]}. The audio helper generates measured line
times, a default two-shot when beats are omitted, mix/timeline/mouths, and a portable receipt.
If dialogue doesn't fit, shorten the lines and use a new audio folder; reuse verified takes.
Use the AUDIO command below. Its audio/production.json is the authoritative measured plan.
2. Build scene.blend and reproducible build.py in this workspace. The repo's docs/worlds.md
documents blender.staging.import_actor and frame_subjects. Read only the relevant recipe
and chosen asset metadata once, not the entire repository.
For static product imports prefer the tested worlds builder --product-blend/--product-size
options. Hand-written normalization must include each object's matrix_world, not raw
bounding boxes under an already-scaled parent. Inspect a small EEVEE frame before the
full render and correct obvious product scale, occlusion and face orientation first.
Use actual armature names from imported actors. Put these in rigs.json: {speaker:armature}.
Use blender/performance.py apply(timeline,mouths,rigs,models={speaker:source_model}) for measured
speech, idle and blinks. Preserve intentional poses/actions. Apply verified library motions
where useful. Show faces and the product clearly at phone size; inspect the payoff.
3. Pack resources, save the scene, then use RENDER below. It checks speaking faces/rigs
before expensive frames. Fix a reported staging defect in the existing scene and retry.
Set scene duration/fps to the
measured plan. Width/height in RENDER are DELIVERY dimensions: the helper chooses its native
low-resolution size and upscales once. Save progress early and reuse its frame cache on retry.
Do not rebuild the closing product clip: Frame inserts the configured existing clip during
the last CARD_SECONDS. Keep a full-duration picture/audio master; a short closing window
can hold the final story composition for Frame to replace. Never replace the story with a card.
4. Write used-assets.json as an array of catalog IDs actually used. Run SUBMIT with your
actual audio receipt, scene, source, preview and rig map. This writes the complete result.json.
Keep the full dialogue, story action, reaction and payoff. Report any timing/staging adaptation
in summary so the editor judges this measured version. Finish the first usable cut promptly;
spend remaining effort on meaningful action and readability, not extra process documents.'''

EDITOR_JOB = '''Inspect the animator's actual video across its story and transitions. Edit picture
and sound for clear action, natural response timing, readable faces/product and a convincing
payoff. The animator's measured direction and dialogue are authoritative: the earlier SCRIPT
is a guide, not an obligation to restore lines deliberately shortened for timing. Preserve the
central premise/product. Listen only if your tools support it; do not claim listening otherwise.
Keep a good cut unchanged. Cut only dead time or improve an actual issue; no compulsory second
render. Use measured timeline entries to keep spoken lines intact. Do not add captions/URLs;
Frame supplies the short product end card afterwards. Judge the complete story, not perfection
of minor décor. Low-resolution early-game art is intentional. A brief held reaction
shot is not automatically a defect: use the picture freeze diagnostics with the
actual video to judge its purpose. A mostly frozen movie is not animation.

Write cut-plan.json: {segments:[{start,end,reason}],removed_lines:[{index,reason}],
sound_plan:"...",review:{verdict:"pass",summary:"specific observations",findings:[]}}.
For an unchanged cut use one story segment [0,story_end] and a separate complete card segment
[story_end,duration]. If CARD_SECONDS is zero, use just [0,duration]; never add a zero-length
segment. Meaningful trims may use more ordered segments. Then run EDIT below;
it assembles matching master/timeline and result.json without resynthesizing voices or rendering
Blender again. Minor shortcomings can be noted in review.findings with severity minor.
If a concrete defect in the actual scene prevents a coherent ad and cannot be edited around,
write result.json {summary,files:[],verdict:"revise",restart:"animate",
findings:[{target:"time/shot",severity:"blocking",problem:"observed defect",fix:"focused change"}]}.
Only one targeted return to the same animator workspace is available. Preserve the existing
scene, voices and good shots; do not request a new script or a general rebuild.'''


def production_brief(state, task, work, timeout, home, store=None):
    c = state['config']; out = c['output']; stage = task['stage']
    card = min(out['end_card_seconds'], out['target_seconds'] / 2) if out['cta'] else 0
    project = {'COUNT': c['count'], 'TARGET_SECONDS': out['target_seconds'],
               'STORY_SECONDS': out['target_seconds'] - card, 'CARD_SECONDS': card,
               'EFFORT': c['generation']['effort'], 'ATTEMPT_SECONDS': round(timeout, 1),
               'WORKSPACE': str(work), 'products': c['products'], 'concept': c['concept'],
               'brand': c['brand']['direction'], 'look': out['look']}
    prefix = ('cd ' + shlex.quote(str(work)) + ' && env PYTHONPATH=' + shlex.quote(str(REPO)) + ' ')
    controller = prefix + shlex.quote(sys.executable)
    audio_python = prefix + shlex.quote(c['audio']['python'] or sys.executable)
    common = ('Complete this one production job in WORKSPACE. Use that absolute cwd on every shell call. '
              'Repository/shared assets are read-only; never use archived assets or modify originals. '
              'Other runs may be active: keep temporary scripts/media inside WORKSPACE too. '
              'Do not launch agents, publish, install services or access secrets. Write result.json in '
              'WORKSPACE; a prose completion message is not a submission. Save reusable work early.\n')
    if stage == 'script':
        project['characters'] = [Path(p).stem for p in c['sources']['characters']]
        job = SCRIPT_JOB
        effort = c['generation']['effort']
        if effort == 'low':
            job += ('\nLOW SCOPE: at most two actors, one existing setting, one shot, short dialogue '
                    'and a clear reaction using simple existing motion. No custom weather, '
                    'complex hand/prop contact, page rigs or new simulations. Make the idea compelling '
                    'through the exchange and visual contrast, not expensive construction.')
        elif effort == 'medium':
            job += ('\nMEDIUM SCOPE: at most two actors and two shots for this short ad. '
                    'One distinctive situation and readable action; keep the scene inexpensive to stage.')
    else:
        project['SCRIPT'] = selected_script(state, task['ad'])
        # A complete local index stays available without flooding every model prompt.
        (work/'active-assets.json').write_text(json.dumps(state.get('asset_catalog', []), indent=2))
        local_config = copy.deepcopy(c); local_config['delivery']['drive'] = ''
        (work/'production-config.json').write_text(json.dumps(local_config, indent=2))
        project.update(repo=str(REPO), active_characters=c['sources']['characters'],
                       format={k: out[k] for k in ('width', 'height', 'fps')})
        if stage == 'animate':
            project['AUDIO'] = (audio_python + ' -m harness.production_tools audio plan.json '
                '--config production-config.json --output audio --cache-dir ' + shlex.quote(str(home/'cache'/'voices')))
            project['RENDER'] = (controller + ' -m harness.render --scene scene.blend --production audio/production.json --rigs rigs.json '
                '--output preview.mp4 --width ' + str(out['width']) + ' --height ' + str(out['height']) +
                ' --fps ' + str(out['fps']) + ' --seconds ' + str(out['target_seconds']) +
                ' --effort ' + c['generation']['effort'] + (' --fast' if c['generation']['fast'] else '') +
                ' --blender ' + shlex.quote(c['tools']['blender']) + ' --ffmpeg ' + shlex.quote(c['tools']['ffmpeg']) +
                ' --timeout ' + str(max(1, round(timeout * .65))))
            project['SUBMIT'] = (controller + ' -m harness.production_tools submit audio/production.json '
                '--scene scene.blend --source build.py --preview preview.mp4 --rigs rigs.json '
                '--assets used-assets.json --catalog active-assets.json --output result.json')
            job = ANIMATOR_JOB
            project['publication_id'] = state['id'] + ':' + task['id']
            job += ('\nIf you create a genuinely reusable asset, optionally declare candidate_manifest '
                    'and all its dependencies in result.json following repo docs/library.md. Use '
                    'publication_id as run_id. The controller validates/publishes after the ad is done. '
                    'Never modify or push the shared asset checkout yourself; do not delay the film '
                    'to invent assets it does not need.')
        else:
            animation = animation_result(state, task['ad'])
            accepted = next(t['accepted_manifest'] for t in state['tasks']
                            if t['stage'] == 'animate' and t['ad'] == task['ad'])
            project['ANIMATION'] = {k: animation[k] for k in
                ('summary', 'direction', 'preview', 'mix', 'timeline', 'scene', 'picture') if k in animation}
            project['EDIT'] = (controller + ' -m harness.production_tools edit ' + shlex.quote(accepted) +
                ' --plan cut-plan.json --config production-config.json --output result.json')
            job = EDITOR_JOB
    if store is not None and stage in ('script', 'animate'):
        from .learning import lessons, character_voices
        memory = lessons(store, c, limit=3)
        project['past_results_reference_only'] = [{
            'status': row['status'], 'premises': [p[:200] for p in row['premises']],
            'feedback': [{'rating': f['rating'], 'note': f['note'][:220]} for f in row['user_feedback']],
            'observed_issues': [f['problem'][:160] for f in row['review_findings'][:2]]
        } for row in memory]
        if stage == 'animate':
            project['previous_voices_by_asset_id'] = character_voices(store, c)
    feedback = task.get('feedback', '')
    return common + '\nJOB\n' + job + '\nPROJECT\n' + json.dumps(project, separators=(',', ':')) + (
        '\nREPAIR: Continue existing local files; resubmit a complete result.json.\n' + feedback[:2200] if feedback else '')


def validate_production_media(engine, state, task, data, work, config):
    stage = task['stage']
    if stage == 'script':
        names = {p['name'] for p in config['products']}
        if names and any(s['product'] not in names for s in data['scripts']):
            raise ContractError('Script product must name one of the configured products')
        return
    if stage == 'edit':
        if data['verdict'] == 'revise':
            return
        from .media import check_video
        from .editing import validate_conformance
        source = animation_result(state, task['ad'])
        media = check_video(work/data['master'], config)
        validate_conformance(work/data['timeline'], data['plan'], json.loads(Path(source['timeline']).read_text()),
                             config, source['direction'], media['duration'])
        data['reviewed_preview_sha256'] = digest(source['preview'])
        return
    if stage != 'animate':
        return
    from .direction import check_direction, check_scratch_takes
    from .media import check_audio, check_video, check_picture, check_scene
    from .speech import check_presence
    paths = {f['path'] for f in data['files']}
    for key in ('scene', 'mix', 'timeline', 'dialogue_stem', 'mouths'):
        if data.get(key) not in paths:
            raise ContractError(f'Animator {key} must name a declared local file')
    check_direction(data.get('direction'), config)
    data['measured_scratch'] = check_scratch_takes(data, work)
    check_audio(work/data['mix'], work/data['timeline'], config, data['direction'])
    timeline = json.loads((work/data['timeline']).read_text())
    if timeline['dialogue']:
        data['speech_presence'] = check_presence(work/data['dialogue_stem'], timeline)
        speakers = {line['speaker'] for line in timeline['dialogue']}
        if not isinstance(data.get('rigs'), dict) or not speakers <= set(data['rigs']):
            raise ContractError('Animator rigs must map every speaker to its actual armature')
        planned = data['direction']['lines']; rate = timeline['sample_rate']
        lines = [{'speaker': line['speaker'], 'text': line['text'],
                  'start': line['start_sample']/rate, 'end': line['end_sample']/rate,
                  'offscreen': bool(planned[i].get('offscreen'))} for i, line in enumerate(timeline['dialogue'])]
        models = {actor['speaker']: actor['model'] for actor in data['direction']['cast'] if actor.get('model')}
        data['talking'] = check_scene(work/data['scene'], data['rigs'], lines, config['output']['fps'], models)
    check_video(work/data['preview'], config, preview=True)
    story_end = data['direction']['duration'] - data['direction'].get('end_card', {}).get('seconds', 0)
    data['picture'] = check_picture(work/data['preview'], config, story_end, max_frozen_fraction=.5)

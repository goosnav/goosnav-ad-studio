"""Production scope is independent of model tier; reliability constrains capabilities, not ideas."""

WORLD = '''LOOK: an inhabited early-3D game world, inspired by the atmosphere and impressionistic
detail of early Half-Life, Halo and Minecraft, with original Goosnav art and characters.
It should feel encountered on the internet of 2002: an uncanny little game-world film,
not a glossy contemporary commercial or a random neon "retro" filter. The deterministic
end card supplies the blue underlined Times browser link and dithered computer-screen finish.
Low-poly silhouettes, tactile small textures, a purposeful palette, pools of light, depth,
and a few specific objects imply a life beyond the camera. Avoid an empty grey studio unless
the joke requires it. Detail should reward looking without obscuring the face or product.
Use economical EEVEE lighting, shadows and modest ambient occlusion where helpful. No need
for photorealism, ray tracing, compulsory dithering or deliberately stiff movement.
The world supports character comedy: a concrete want, a reaction, a turn, a product connection.
Keep authentic product artwork readable. Never imitate the user's drawings or copy game assets.
Render at a sensible native size (at least 540x675 for 1080x1350 delivery), then upscale once;
sample a few frames to estimate render cost before committing to the whole movie.
'''


def scope(config):
    g = config.get('generation', {})
    effort = g.get('effort', 'medium')
    fast = g.get('fast', False)
    choices = {
        'low': 'Reuse a tested environment and existing camera/gesture setups. One set, 1-2 actors, 2-3 shots. No new asset construction.',
        'medium': 'Reuse an environment with a meaningful variation; at most one new simple prop. 2-4 shots and one tested action.',
        'high': 'Create a distinctive setting or substantial reusable extension. Use motivated camera movement, environmental reveals and tested action sequences when they serve the joke. 2-5 shots, never a shot-count quota.',
    }
    return ('CREATIVE SCOPE\n' + choices[effort] +
            (' Fast mode: reuse a finished set; no optional builds; one voice take per line; one focused correction.' if fast else '') +
            '\nEvery proposed action needs a known clip/capability or a short successful test before production. '
            'Provide a simpler staging of the SAME joke if its action cannot be verified. '
            'A recovery execution policy takes precedence over optional scope: reuse, fewer shots, no auditions. '
            'Do not simplify by deleting the causal reaction or product connection. '
            'A product/end-card video is ONLY the short closing segment, never a substitute for the story.\n')


# These notes stay stage-local: no extra agents, schema fields or source sweeps.
PRODUCT_TASTE = {
    'research': """Within the existing two-source budget, prioritize an actual product sample over
brand prose: a comic/page, card/rule, design detail or demonstrated function. In
creative_directions include a compact 'Taste:' note: product/edition; exact source
path or URL plus page/card ID; observed detail; evidence it belongs to that product.
Inspect only enough supplied material to choose 1-2 useful details, then stop.
A model's texture folder or a drawing's date alone does not prove edition membership.
If unverified, say so; use another verified product detail or report the missing
sample. Never invent book contents, card rules, exclusivity or purchase benefits.""",
    'write': """Give a small taste of the actual product BEFORE the CTA. Build the humor from a
verified excerpt, game interaction or distinctive feature, not generic praise or
people merely saying the product's name. One good sample is enough; no montage quota.
Carry the research Taste note (source, edition, specific detail) in visual_direction
so selection and production retain it. The script must say what the audience actually
sees/hears and how the reaction or riff follows. An original riff is not a quote or
claim about printed content. No verified sample? Use an evidenced product experience
or flag the gap, never manufacture an excerpt. Reference films are not story templates.""",
    'select': """As part of this same short check, identify the candidate's sourced product taste
and the response it causes. A generic cover shot, 'this is funny', or a random sketch followed
by a logo is not a taste. Read the source/edition note in visual_direction; reject
unsupported content claims or an absent product experience. No new research pass.
Do not require the reference film's setting, cast count, lines, shot count or length.""",
    'direct': """Carry the chosen source/edition/detail into the relevant beat.picture. Stage a
legible sample and its motivated reaction, not just characters explaining the brand.
A source-art insert or supported static spread can do the job; book opening, page
turning and hand IK are optional verified capabilities, not requirements. Preserve
the SAME content-based joke when simplifying staging. Let measured speech and sample
readability determine beat lengths within configured delivery bounds; don't copy a
reference runtime, rush the excerpt or add empty seconds to imitate its pacing.""",
    'assets': """Verify the chosen sample belongs to the advertised product/edition, not merely
to the asset library. Use and pack the original source art; preserve exact words and
images. A faithful crop/insert is preferable to inventing art or a complicated prop
interaction. Lettering printed on a real page/card IS product content, not a banned
promotional overlay. Check the relevant detail at phone size: crop/angle/light it so
the joke reads. Do not make a tiny washed-out full spread count as product exposure.""",
    'animate': """Preserve the sourced content insert and the reaction it motivates. Real lettering
on the product is allowed; invented captions/marketing overlays still belong to Frame.
Use the approved rigs and supported actions. If simplifying motion, keep the same
sample visible/readable rather than replacing it with a generic cover shot.""",
    'edit': """Protect the content-to-reaction connection when trimming: leave enough time to
perceive the actual excerpt/interaction, then cut once it lands. Remove empty time,
not the only product sample or the setup that makes the reply intelligible. Match
spoken references to the visible sample; use motivated sound, not canned laughter to
assert a joke worked. The CTA should follow the scene, without copying the reference
line or unverified offers. No mandatory music, page turn, sample count or runtime.""",
    'creative_qa': """During this existing review, identify the exact pre-CTA moment where the viewer
experiences a real product detail. Check it against the source/edition note and the
spoken reference: recognizable at phone size, coherent reaction, no fabricated art
or benefits. Cite that moment briefly in summary/findings, not a new report. A product
name or cover alone cannot stand in for the promised taste. Judge entertainment and
clarity, not resemblance to GET YOUR OWN. Report unsupported observations honestly.""",
}


def job(stage, original):
    """Add only the relevant product-content instruction to the existing worker job."""
    assignment = _production_job(stage, original)
    note = PRODUCT_TASTE.get(stage)
    return assignment + '\n\nPRODUCT TASTE\n' + note if note else assignment


def _production_job(stage, original):
    if stage == 'write':
        return '''Write TWO distinct candidate scripts per ad. Character comedy is central: a specific
want, causally connected exchange/action, readable reaction and payoff that leads to the real
product. Use the available world/capability catalog; vary recent premises and settings.
Work from the supplied facts and catalog. Do not browse the repository, inspect Blender files,
or research past campaigns; the director verifies exact motion capabilities. Write result.json
promptly. Each candidate should fit within 160 words including stage directions.
Atmosphere can be mysterious; the joke must be comprehensible. Keep dialogue brief enough for
natural delivery and a reaction before the reserved end card. Include shot timing, staging,
speaker lines, sound and an alternate simpler staging in each script.
Return scripts:[{id,title,premise,script,visual_direction,product,cta}], all fields plain text.'''
    if stage == 'direct':
        return '''Direct a short character comedy in a convincing small world. Let framing, reactions,
sound and a verified action carry part of the idea; do not force everything into spoken exposition.
Follow DIRECTOR QUICKSTART and PROJECT.director_tools below. Generate or verify/reuse measured
scratch takes BEFORE finalizing direction; never estimate durations or invent capability evidence.
Keep the selected joke; choose its simpler staging when an action cannot be verified cheaply.
Read only the selected script, supplied catalog and relevant predecessor files. Do not survey
the repository or read the whole worker guide. Run one batch for all needed lines, not one
model process per line. One take normally suffices; audition caps are maxima, not targets.
Use PREVIOUS CHARACTER VOICES by asset ID. Reserve natural reply gaps and a visible reaction.
After measurements, write direction.md and COMPLETE result.json promptly. No scene building,
board rendering, mixing, lip-sync generation or full speech animation belongs in this stage.
Return scratch_takes: the workspace-relative portable harness.voice manifest path, declared
in files with every raw/polished WAV dependency. A prose claim or measurements-only JSON is
not scratch_takes. Never skip real measured takes to finish before a deadline.
Schema reminders: beat.shot is ONE TEXT STRING, not an object. Each line must fit entirely
before duration - end_card.seconds and allow at most 3 words/second; allocate at least its
selected full WAV duration. Shorten/re-record text when needed, never falsify measurements.
''' + original[original.index('Plan the whole ad second by second'):]
    if stage == 'assets':
        return '''Build the real blocked Blender scene from the accepted direction. Use the active
asset catalog and existing sets before constructing anything; paths come from config/catalog.
The reusable world builder is <repo>/blender/worlds.py (see docs/worlds.md).
Use <repo>/blender/staging.py: import_actor(sourceblend,name,location,height_m) preserves
the rig under a measured placement root; frame_subjects(camera,subjects,margin,view_direction)
fits actual geometry at YOUR chosen angle. Select rig_name explicitly for multi-rig sources.
Do not append every character or guess unit scales. Save the projected report, then inspect
boards for face visibility/occlusion: frame containment alone is not a visual approval.
Use original textures, useful depth and lighting, and verified character rigs. Preserve accurate
product art. Test any new interaction cheaply; use the simpler staging if it fails.
Render one phone-readable still per beat and an end-card hero. Save a self-contained .blend,
rebuild script, and manifest of dependencies/provenance/capabilities. Assets are shared read-only.
New reusable objects/sets may be submitted as a candidate manifest following docs/library.md;
return candidate_manifest:relative_path and declare it and every candidate source in files.
Use RUN CONTEXT.publication_id for the manifest and provenance run_id.
the controller alone validates, promotes and publishes them after final approval.
Return assets:[{name,source,rights,proxy:false}], boards:[{beat:index or "end_card",image:path}],
used_asset_ids:[catalog IDs actually reused], and declare the manifest, boards, scene and source
files. No unresolved proxies. Copy the exact catalogue IDs; do not invent IDs for new assets.

ASSETS QUICKSTART
PROJECT.accepted_inputs contains the plan and measured-media paths; the complete authoritative
results remain at RUN CONTEXT.accepted_manifests. Read them only when more detail is needed.
Read only the relevant staging/world helper documentation. Do not read the entire worker guide
or unrelated audio/publication internals. Author the scene, render the required boards, then
submit before optional polish so a timeout does not lose a complete handoff. This does NOT
waive board review: report known defects honestly, never label unfinished proxies complete.
Write asset-plan.json containing summary, assets, boards, used_asset_ids, scene (local .blend),
source (local rebuild script), manifest (local authored provenance file), and optional files
[{path,kind}] for additional required local dependencies. All artifact paths are relative to
PROJECT.workspace. Do not invent rights, capabilities or observations. Optional candidate_manifest
must also be local and all of its dependencies explicitly listed in files.
With REPO=PROJECT.repo_read_only and CONTROLLER_PYTHON=PROJECT.controller_python, run from
PROJECT.workspace:
env PYTHONPATH="$REPO" "$CONTROLLER_PYTHON" -m harness.submission asset-plan.json --output result.json
The helper only verifies/declaratively stages existing local artifacts; it does not inspect
images, open Blender, discover undeclared dependencies, approve quality, or change the plan.
On repair preserve the prior result and submit to a fresh filename; only the completed
current submission should become result.json. Keep all controller/board-review gates.'''
    if stage == 'audio':
        return '''Produce sound from the director's accepted, measured takes. Preserve exact cast,
words and planned starts; dialogue stays the lead. Do not regenerate accepted speech or
engineer a mixer by reading helper source. Use PROJECT.audio_tools.assemble when supplied,
with DIRECT_RESULT set to RUN CONTEXT.accepted_manifests.direct. Otherwise:

AUDIO QUICKSTART
1. Read RUN CONTEXT.accepted_manifests.direct. This is the actual accepted director RESULT
   JSON, not direction.md or a voice manifest. Never infer an attempt path. If this mapping
   is absent on a legacy run, use the existing audio workflow in PROJECT.tool_guide and
   accepted_inputs instead; still return the complete audio contract below.
2. Bind STAGE_WORKSPACE to this stage's absolute TASK.md directory, AUDIO_PYTHON to
   PROJECT.config.audio.python, REPO to PROJECT.repo_read_only, DIRECT_RESULT to that
   accepted manifest path, and OUTPUT_FPS to PROJECT.config.output.fps. Quote paths.
   Keep cwd in the workspace on EVERY shell call, not the repository. Missing configured
   Python is a blocker, not permission to guess an interpreter or invent audio.
3. Decide sound creatively: supply a real WAV bed at quiet gain when ambience/music serves
   the accepted scene. Optional creative stems/effects remain allowed; record provenance.
   Only when no ambience is appropriate, explicitly choose --no-bed and run:

   cd "$STAGE_WORKSPACE" && test -f TASK.md && env PYTHONPATH="$REPO" "$AUDIO_PYTHON" -m harness.mix "$DIRECT_RESULT" generated-audio --fps "$OUTPUT_FPS" --no-bed --stage-result result.json

   For a supplied bed, replace --no-bed with --bed "actual-local-bed.wav" --bed-gain-db -30
   (choose a quiet gain appropriate to the recording). Never silently omit required ambience
   just to make the command run. The helper aligns selected takes deterministically; it does
   not compose sound, synthesize speech, or establish artistic quality.
4. --stage-result writes the COMPLETE workspace result.json, with correctly prefixed
   declared files plus mix, timeline and dialogue_stem. Preserve those fields and all
   dependencies; do not replace it with a prose summary or a partial custom JSON. Add any
   additional real source/stem/provenance artifacts to files. On retry reuse finished work;
   never overwrite accepted outputs or repeat synthesis. Use a fresh output folder for repairs.
5. Inspect/listen with available tools and report honestly; no fabricated listening claims.
   The controller still runs ASR and mix checks. Do not repeat those expensive checks in
   the worker unless repairing a specific finding. A successful helper exit is assembly,
   not ASR, acting approval, or permission to bypass controller validation.

Return summary, files, mix, timeline, dialogue_stem; all artifact paths must be relative to
this workspace and declared in files. Timeline uses delivery fps and 48000-Hz sample timing;
mix and dialogue_stem share full planned duration/alignment. Preserve provider/source rights
and report any real blocker instead of manufacturing a completed contract.'''
    if stage == 'animate':
        return '''Continue from the accepted blocked scene and measured audio. Use blender/performance.py:
performance.apply(timeline_path, mouths_path, {speaker:armature}, models={speaker:source_model})
for speech, idle and blinks; apply verified clips with performance.play_clip when directed.
Preserve product art and the scene's established staging. Allow motivated camera moves and
verified action; never invent rig capabilities or hide a broken interaction with a cut.
Save an economical animatic with audio, inspect speech/reaction windows and product visibility,
and save a resumable render command and animated .blend. Render a small frame sample first
to estimate cost. If it cannot finish within the remaining budget, reduce optional complexity.
Use python -m harness.render --scene scene.blend --audio mix.wav --output preview.mp4
--seconds TARGET --effort EFFORT [--fast] --timeout REMAINING_SECONDS (see CLI --help).
It caches verified frames and resumes after interruption; pack resources before calling it.
Use the finished animatic as the final picture when it already meets delivery requirements;
do not render twice merely because stages have different names.
Return scene, rigs:{speaker:armature}, preview, source and files declaring all dependencies.
No text overlays: the deterministic Frame stage handles them. It reuses a configured product
item-drop video for the end card when available; do not rebuild that clip. Without a matching
clip, use the actual product model for a slow bob/rotation in the final hero window. Preserve
original textures and leave enough air around its silhouette.'''
    if stage == 'board_review':
        return '''Review each storyboard and the measured dialogue performance together, once, before
animation. Check the causal joke, reaction timing, faces/product at phone size, environment,
and whether the proposed action was actually tested. Fixed features of an approved character
(including its built-in smile) are capabilities to stage around, not defects by themselves.
Evaluate the causal reaction in context; never require unsupported expressions or new face art.
PROJECT.frame_policy is authoritative over style prose in upstream picture descriptions.
Listen only if your tools support listening;
otherwise clearly mark acting quality unverified. Intelligibility does not prove good acting.
Reject concrete blockers or important defects, not differences in personal taste. Do not demand
more motion just to fill a frame. Return summary, files:[], verdict:pass|revise,
findings:[{target,severity:blocking|important|minor,problem,fix}],
and put unverified observations that are not defects in summary rather than inventing a severity.
and restart:direct|assets|audio for the actual cause. Give a focused correction preserving good work.'''
    if stage == 'edit':
        return original.replace('then render the original scene at\n full delivery quality.',
                                'reuse the accepted render when it meets delivery requirements. Render only when necessary.')
    if stage == 'creative_qa':
        return original.replace('(direct, assets, audio, animate or edit)', '(direct, assets, audio, animate, edit or frame)').replace(
            'a wording fix there means restart direct.', 'a card-only wording/style fix means restart frame; provide end_card_patch:{title:correct copy} when needed.')
    return original


DIRECTOR_QUICKSTART = '''
DIRECTOR QUICKSTART
1. Use PROJECT.director_tools commands in PROJECT.workspace (contains this TASK.md).
   Bind STAGE_WORKSPACE on EVERY shell call: login shells may reset cwd. Commands set
   PYTHONPATH and configured interpreters; never cd into the read-only repo or use bare python.
2. Retry: inspect result.previous-*.json, direction.md, motion.json and scratch-measurements.json.
   Verify existing scratch/manifest.json, takes/manifest.json or scratch/takes/manifest.json
   with takes BEFORE synthesis. For a known external predecessor use reuse: copies verified
   selections into a NEW local directory, without models/cache. Never overwrite completed
   manifests, modify predecessors or search unrelated runs. Choose new summary names on retry.
3. Use catalog-evidenced clips or run motion ONCE for chosen active character models.
   It opens them in Blender and inventories real armatures/clips. Never import bpy in the
   audio interpreter or guess rig names. Preserve motion.json. Clips do not prove hand/prop
   contact; use simpler staging for unverified interactions, not invented capability evidence.
4. Adapt request_template into scratch-request.json; set cache_dir=RUN CONTEXT.voice_cache.
   Batch missing/changed lines with voice --summary ONCE, then takes; read selected-take
   metadata in the compact summary, not
   the huge manifest. Retain unchanged lines via selected_take:{manifest,line_id,take_id},
   with no auditions/defect_retry or conflicting synthesis controls. Speaker/text/voice/provider
   must match exactly. Caps are maxima: low=1, medium<=2, high<=3, fast/recovery=1.
5. Schedule full selected polished WAV duration plus reply/reaction gaps. Active bounds
   are NOT word timing or permission to trim. If over budget, shorten and remeasure ONLY
   changed words; keep other takes. Never fake durations or skip measured speech.
6. Write a SMALL plan.json containing {summary,direction}; author every shot and timestamp.
   Optional files:[{path,kind}] lists only extra local notes/inventory/request files.
   Avoid manually transcribing long hashed WAV paths. Bind AUDIO_PYTHON to the actual
   PROJECT.config.audio.python value and REPO to PROJECT.repo_read_only, then run:
   cd "$STAGE_WORKSPACE" && env PYTHONPATH="$REPO" "$AUDIO_PYTHON" -m harness.creative submit-direction plan.json scratch/manifest.json --output result.json --direction-md direction.md
   Use the configured interpreter, never a guessed bare python. Omit
   --direction-md only if no notes file was authored. The helper verifies real WAVs and
   writes complete declarations plus scratch_takes; it NEVER invents/repairs the plan or
   timing. Inputs/output must stay local; output must not exist. Controller gates still run.
   Preserve provisional acceptance: hashes/WAV measurements do NOT verify acting, ASR or
   listening. State unverified listening. A checkpoint/prose reply is not a submission.
'''


def _read_selected(manifest):
    """Read and verify every dependency; return selected takes without model loading."""
    import json
    from pathlib import Path
    from .voice import verify_take
    path = Path(manifest).resolve()
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or data.get('sample_rate') != 48000 or not data.get('lines'):
        raise ValueError('Expected a measured 48 kHz voice manifest')
    rows, ids = [], set()
    for line in data['lines']:
        if line['id'] in ids:
            raise ValueError('Duplicate voice line ID')
        ids.add(line['id'])
        for take in line['takes']:
            verify_take(take, path.parent)
            if any(take['settings'][key] != line[key] for key in ('text', 'voice')):
                raise ValueError('Manifest line does not match measured take')
        selected = [t for t in line['takes'] if t['id'] == line['selected_take_id']]
        if len(selected) != 1:
            raise ValueError('Missing or ambiguous selected take')
        rows.append((line, selected[0]))
    return path, data, rows


def summarize_takes(manifest, workspace):
    """Compact measurements and complete file declarations, never an acting verdict."""
    from pathlib import Path
    work = Path(workspace).resolve()
    path, data, rows = _read_selected(manifest)
    def relative(file):
        return Path(file).resolve().relative_to(work).as_posix()
    files = {relative(path): 'voice_manifest'}
    lines = []
    for line, selected in rows:
        for take in line['takes']:
            for kind in ('raw', 'polished'):
                files[relative(path.parent / take[kind]['path'])] = 'audio'
        measured = selected['polished']
        lines.append({**{k: line[k] for k in ('id', 'speaker', 'text', 'voice', 'delivery')},
                      'duration': measured['duration'],
                      'active_start_seconds': measured['active_start_sample'] / 48000,
                      'active_end_seconds': measured['active_end_sample'] / 48000,
                      'polished_path': relative(path.parent / measured['path']),
                      'selected_take': {'manifest': relative(path), 'line_id': line['id'],
                                        'take_id': selected['id']},
                      'acceptance': line.get('acceptance', 'unverified')})
    return {'scratch_takes': relative(path), 'lines': lines,
            'total_wav_seconds': sum(line['duration'] for line in lines),
            'validation': 'SHA-256 and WAV measurements verified; no listening, ASR or acting assessment',
            'files': [{'path': p, 'kind': k} for p, k in sorted(files.items())]}


def reuse_takes(manifest, output_dir, workspace):
    """Copy exact predecessor selections through voice's verified reuse contract."""
    from pathlib import Path
    from .voice import run_batch
    destination = Path(output_dir).resolve()
    destination.relative_to(Path(workspace).resolve())
    path, data, rows = _read_selected(manifest)
    providers = {take['settings']['provider'] for _, take in rows}
    if len(providers) != 1:
        raise ValueError('Predecessor selections must use one voice provider')
    request = {'provider': providers.pop(), 'effort': 'low', 'fast': True, 'lines': [
        {**{k: line[k] for k in ('id', 'speaker', 'text', 'voice', 'delivery')},
         'selected_take': {'manifest': str(path), 'line_id': line['id'], 'take_id': take['id']}}
        for line, take in rows]}
    result = run_batch(request, destination)
    # Mechanical reuse is not a new artistic approval or a listening claim.
    for entry, (source, _) in zip(result['lines'], rows):
        entry['acceptance'] = source.get('acceptance', 'unverified')
    import json
    (destination / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    return summarize_takes(destination / 'manifest.json', workspace)


def submit_direction(plan, manifest, output, workspace, direction_md=None):
    """Serialize an authored plan and verified local dependencies, not an approval.

    Never change a line, timestamp, take selection, or source artifact. Declare all
    WAVs referenced by the supplied manifest (including retained alternate takes)
    so the unchanged manifest stays portable after promotion. No cache/model needed.
    """
    import json
    from pathlib import Path
    work = Path(workspace).resolve()

    def local(value, *, new=False):
        raw = Path(value)
        if '..' in raw.parts:
            raise ValueError('Submission paths must not contain parent traversal')
        path = raw if raw.is_absolute() else work / raw
        path.relative_to(work)
        for part in (path, *path.parents):
            if part == work.parent:
                break
            if part.is_symlink():
                raise ValueError('Submission paths must not use symlinks')
        if new:
            if path.exists():
                raise FileExistsError('Submission output already exists; preserve previous work')
        elif not path.is_file() or not path.stat().st_size:
            raise ValueError(f'Missing or empty submission artifact: {value}')
        return path

    destination = local(output, new=True)
    plan_path, manifest_path = local(plan), local(manifest)
    authored = json.loads(plan_path.read_text())
    if (not isinstance(authored, dict) or not isinstance(authored.get('summary'), str)
            or not authored['summary'].strip() or not isinstance(authored.get('direction'), dict)):
        raise ValueError('PLAN needs an authored summary and direction object')
    direction = authored['direction']
    if not isinstance(direction.get('lines'), list) or not isinstance(direction.get('cast'), list):
        raise ValueError('Direction needs authored lines and cast lists')
    files = {}

    def declare(value, kind):
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError('File kind must be nonempty text')
        path = local(value)
        files[path.relative_to(work).as_posix()] = kind

    declare(plan_path, 'direction_source')
    if direction_md is not None:
        declare(direction_md, 'direction_notes')
    extra = authored.get('files', [])
    if not isinstance(extra, list):
        raise ValueError('Optional plan.files must be a list')
    for entry in extra:
        declare(entry['path'], entry['kind'])
    # Check every referenced path before verify_take reads any audio bytes.
    raw_manifest = json.loads(manifest_path.read_text())
    for line in raw_manifest['lines']:
        for take in line['takes']:
            for kind in ('raw', 'polished'):
                relative = Path(take[kind]['path'])
                if relative.is_absolute():
                    raise ValueError('Voice manifest paths must remain relative')
                declare(manifest_path.parent / relative, 'audio')
    _, _, rows = _read_selected(manifest_path)  # SHA-256, recipe and measured WAV verification.
    declare(manifest_path, 'voice_manifest')
    cast = {}
    for actor in direction['cast']:
        if actor['speaker'] in cast:
            raise ValueError('Duplicate speaker in authored cast')
        cast[actor['speaker']] = actor['voice']
    used = set()
    normal = lambda text: ' '.join(text.split())
    for line in direction['lines']:
        candidates = [i for i, (entry, _) in enumerate(rows) if i not in used
                      and entry['speaker'] == line['speaker']
                      and normal(entry['text']) == normal(line['text'])
                      and entry['voice'] == cast.get(line['speaker'])
                      and ('id' not in line or line['id'] == entry['id'])]
        if not candidates:
            raise ValueError('Authored line has no matching unused measured take (speaker/text/voice/id)')
        used.add(candidates[0])
    result = {'summary': authored['summary'], 'direction': direction,
              'scratch_takes': manifest_path.relative_to(work).as_posix(),
              'files': [{'path': path, 'kind': kind} for path, kind in sorted(files.items())]}
    encoded = json.dumps(result, indent=2, allow_nan=False) + '\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x') as stream:
        stream.write(encoded)
    return result


def motion_inventory(models):
    """Inspect models without scripts; clip tags are temporary in-memory changes only.

    Never save the opened sources. The CLI writes only its workspace summary.
    """
    import bpy
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'blender'))
    import performance
    records = []
    for model in dict.fromkeys(str(Path(p).resolve()) for p in models):
        bpy.ops.wm.open_mainfile(filepath=model, use_scripts=False)
        records.append({'model': model, 'armatures': [
            {'name': rig.name, 'clips': performance.available_clips(rig, model=model)}
            for rig in sorted(bpy.context.scene.objects, key=lambda o: o.name) if rig.type == 'ARMATURE']})
    return {'models': records, 'validation': 'Embedded clip inventory only; interactions not tested'}


def main(argv=None):
    import argparse
    import json
    from pathlib import Path
    import sys
    parser = argparse.ArgumentParser(description='Director measurements/reuse and Blender clip inventory; no speech synthesis')
    parser.add_argument('command', choices=('takes', 'reuse', 'motion', 'submit-direction'))
    parser.add_argument('inputs', nargs='+')
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True, help='New workspace-relative summary JSON')
    parser.add_argument('--direction-md', type=Path, help='Existing local authored direction notes (submit-direction only)')
    args = parser.parse_args(argv)
    work = args.workspace.resolve()
    if args.command == 'submit-direction':
        if len(args.inputs) != 2:
            parser.error('submit-direction needs PLAN.json VOICE_MANIFEST')
        result = submit_direction(*args.inputs, args.output, work, args.direction_md)
        print(json.dumps({'output': str(args.output), 'files': len(result['files']),
                          'scratch_takes': result['scratch_takes'], 'lines': len(result['direction']['lines']),
                          'validation': 'WAVs verified; authored plan unchanged; controller gates still required'}))
        return
    if args.direction_md is not None:
        parser.error('--direction-md is only for submit-direction')
    output = (work / args.output).resolve()
    output.relative_to(work)
    if output.exists():
        raise FileExistsError('Preserve predecessor summaries; choose a new --output filename')
    def source(value):
        return (work / value).resolve()
    if args.command == 'motion':
        result = motion_inventory([source(p) for p in args.inputs])
    elif args.command == 'reuse' and len(args.inputs) == 2:
        result = reuse_takes(source(args.inputs[0]), source(args.inputs[1]), work)
    elif args.command == 'takes' and len(args.inputs) == 1:
        result = summarize_takes(source(args.inputs[0]), work)
    else:
        parser.error('takes needs MANIFEST; reuse needs MANIFEST NEW_DIRECTORY; motion needs MODEL [MODEL ...]')
    if 'files' in result:
        result['files'].append({'path': output.relative_to(work).as_posix(), 'kind': 'voice_measurements'})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, separators=(',', ':')))


if __name__ == '__main__':
    import sys
    main(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else None)

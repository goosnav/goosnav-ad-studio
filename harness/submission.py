"""Stage explicitly authored asset results without inventing content or approval."""
import argparse
import json
from pathlib import Path

from .contracts import contained, validate


def submit_assets(plan, output, workspace):
    """Declare local artifacts; controller still validates boards/media/asset identities.

    No filesystem discovery, image inspection, Blender execution, provenance inference,
    source modification, or automatic dependency claim. Only authored paths are read.
    """
    work = Path(workspace).resolve()

    def local(value, *, new=False):
        raw = Path(value)
        if '..' in raw.parts:
            raise ValueError('Submission paths must not contain parent traversal')
        path = raw if raw.is_absolute() else work / raw
        relative = path.relative_to(work).as_posix()
        for part in (path, *path.parents):
            if part == work.parent:
                break
            if part.is_symlink():
                raise ValueError('Submission paths must not use symlinks')
        if new:
            if path.exists():
                raise FileExistsError('Submission output exists; preserve previous work')
            return path
        return contained(work, relative)

    destination = local(output, new=True)
    plan_path = local(plan)
    authored = json.loads(plan_path.read_text())
    if not isinstance(authored, dict):
        raise ValueError('Asset plan must be an object')
    result = dict(authored)
    files = {}

    def declare(value, kind):
        # Artifacts follow the same relative-path contract as result.json.
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError('File kind must be nonempty text')
        path = contained(work, value, allow_empty=kind == 'notes' and isinstance(value, str)
                         and Path(value).suffix == '.log')
        relative = path.relative_to(work).as_posix()
        if path == destination:
            raise ValueError('Submission output cannot be an input dependency')
        files.setdefault(relative, kind)
        return relative

    extras = result.get('files', [])
    if not isinstance(extras, list):
        raise ValueError('Optional files must be a list of {path,kind}')
    for entry in extras:
        if not isinstance(entry, dict):
            raise ValueError('File entries must be objects')
        declare(entry.get('path'), entry.get('kind'))
    for key, kind in [('scene', 'scene'), ('source', 'source'), ('manifest', 'asset_manifest')]:
        result[key] = declare(result.get(key), kind)
    if Path(result['scene']).suffix.lower() != '.blend':
        raise ValueError('scene must name the authored Blender .blend file')
    boards = result.get('boards')
    if not isinstance(boards, list) or not boards:
        raise ValueError('boards must be a nonempty list of {beat,image}')
    seen = set()
    for board in boards:
        if not isinstance(board, dict):
            raise ValueError('Board entries must be objects')
        beat = board.get('beat')
        if not ((type(beat) is int and beat >= 0) or beat == 'end_card'):
            raise ValueError('Board beat must be a nonnegative integer or end_card')
        if beat in seen:
            raise ValueError('Duplicate board beat')
        seen.add(beat)
        board['image'] = declare(board.get('image'), 'storyboard')
        if Path(board['image']).suffix.lower() not in ('.png', '.jpg', '.jpeg'):
            raise ValueError('Board image must be PNG or JPEG')
    ids = result.get('used_asset_ids', [])
    if not isinstance(ids, list) or any(not isinstance(i, str) or not i.strip() for i in ids):
        raise ValueError('used_asset_ids must contain exact catalog ID strings')
    if 'candidate_manifest' in result:
        result['candidate_manifest'] = declare(result['candidate_manifest'], 'candidate_manifest')
    declare(plan_path.relative_to(work).as_posix(), 'asset_plan')
    result['files'] = [{'path': path, 'kind': kind} for path, kind in files.items()]
    validate('assets', result, work, {})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', help='Authored asset plan JSON; no automatic discovery')
    parser.add_argument('--output', default='result.json', help='New workspace-local result JSON')
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    result = submit_assets(args.plan, args.output, args.workspace)
    print(json.dumps({'output': args.output, 'files': len(result['files']),
                      'validation': 'Local declarations only; controller media and creative review still required'}))


if __name__ == '__main__':
    main()

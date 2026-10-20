"""Run the six real production presets in an isolated state directory (uses CLI model quota).

python3 tools/benchmark_production.py --config harness.local.json --home .local/benchmarks/worlds
No existing job/config is modified. Asset publication and Drive delivery are disabled.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from harness.config import load_config
from harness.learning import metrics
from harness.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True); parser.add_argument('--home', required=True)
    parser.add_argument('--library', help='Optional clean asset checkout for reproducible benchmarks during artist edits')
    parser.add_argument('--cases', nargs='+', choices=[e+s for e in ('low','medium','high') for s in ('','-fast')],
                        default=['low-fast','low','medium-fast','medium','high-fast','high'])
    args = parser.parse_args()
    folder = Path(args.home).resolve(); folder.mkdir(parents=True, exist_ok=True)
    summary = folder / 'results.json'
    results = json.loads(summary.read_text()) if summary.exists() else []
    for case in args.cases:
        config = load_config(args.config)
        if args.library:
            from harness.sources import reconcile_sources
            from harness.library import library_root, catalog
            from harness.contracts import digest
            reconcile_sources(config)
            previous_root = library_root(config)
            allowed = {digest(path) for path in config['sources']['characters']}
            root = Path(args.library).resolve()
            config['library']['root'] = str(root)
            config['sources']['assets'] = [str(root)] + [p for p in config['sources']['assets']
                                                        if not Path(p).is_relative_to(previous_root)]
            # Transfer the same whitelist by content, never by guessed filenames.
            config['sources']['characters'] = [e['path'] for e in catalog(config)
                                                if e['kind']=='character' and e['sha256'] in allowed]
            if len(config['sources']['characters']) != len(allowed):
                raise ValueError('Benchmark checkout does not contain the complete approved character whitelist')
        config['count'] = 1
        config['concept'] = ('A short character comedy selling Goosklerf. Two characters disagree about a small '
                             'practical problem in an inhabited retro game world; a visible reaction makes the joke. '
                             'Use a reusable set, real product artwork, natural brief dialogue and a clear CTA.')
        config['output'].update(target_seconds=9, min_seconds=9, max_seconds=9, look='retro_world', folder=str(folder/'videos'))
        config['generation'].update(effort=case.split('-')[0], provider='auto', fast=case.endswith('-fast'))
        # Rebuild routes from this preset rather than retain the config loader's previous routes.
        config.pop('workers')
        config['delivery']['drive'] = ''
        config['library']['publish'] = False
        path = folder / f'{case}.json'; path.write_text(json.dumps(config, indent=2))
        started = time.monotonic()
        with (folder / f'{case}.log').open('w') as output:
            result = subprocess.run([sys.executable, '-m', 'harness', '--home', str(folder/'state'), 'make',
                                     '--config', str(path), '--no-wait'], cwd=REPO, stdout=output, stderr=output)
        runs = Store(folder/'state').list()
        if runs:
            record = {'case': case, 'elapsed_seconds': round(time.monotonic()-started, 2),
                      'exit_code': result.returncode, **metrics(runs[0])}
        else:
            record = {'case': case, 'status': 'startup_failed', 'exit_code': result.returncode}
        results.append(record)
        (folder/'results.json').write_text(json.dumps(results, indent=2))
        print(case, record['status'], record.get('elapsed_seconds'), flush=True)


if __name__ == '__main__':
    main()

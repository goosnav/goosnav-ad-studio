"""One-command production with inspectable, recoverable jobs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from .config import load_config
from .delivery import upload_run
from .models import resolve_workers
from .store import Busy, Store
from .workflow import Engine, build_tasks
from .workers import subscription_status

REPO=Path(__file__).resolve().parents[1]


def default_config():
    path=REPO/'harness.local.json'
    return str(path) if path.exists() else None


def doctor(config):
    checks={}
    for tool in ('ffmpeg','ffprobe','blender'):
        checks[tool]=shutil.which(config['tools'][tool]) or 'MISSING'
    for provider in ('codex','claude'):
        checks[provider]={'executable':shutil.which(provider),'subscription_login':subscription_status(provider)}
    checks['frame']={'root_exists':bool(config['tools']['frame_root']) and
                    (Path(config['tools']['frame_root'])/'app/src/goosnav_frame').is_dir(),
                    'interpreter_exists':Path(config['tools']['frame_python']).is_file()}
    checks['audio_python']=config['audio']['python'] or 'Not configured'
    checks['missing_sources']=[v for values in [config['brand']['documents'],config['sources']['scripts'],
                             config['sources']['assets'],config['sources']['characters'],config['sources']['inspiration']] for v in values if not v.startswith(('http://','https://')) and not Path(v).exists()]
    from .preflight import check_dependencies
    checks['run_blockers']=check_dependencies(config) or 'none'
    checks['drive']={'destination':config['delivery']['drive'] or 'disabled (local-only)',
                     'rclone':shutil.which('rclone') or 'MISSING (only needed if Drive is enabled)'}
    return checks


def drive(engine, store, run_id, wait=True, max_steps=None, sleep=time.sleep):
    """Run; while every provider is cooling down, sleep to the earliest reset and continue."""
    queued=False
    while True:
        try:
            result=engine.run(run_id,max_steps=max_steps)
        except Busy:
            # Another ad is being made: wait our turn instead of failing (pause/cancel still apply).
            if store.control_value(run_id)=='cancel':
                state=store.get(run_id);state['status']='cancelled';store.save(state,'cancelled_in_queue');return state
            if not queued:
                print('Another run is in progress; this one is queued and starts when it finishes.',file=sys.stderr,flush=True)
                queued=True
            # Check the cancellation flag quickly for controllers queued behind the lock.
            sleep(1);continue
        delay=min([c for c in (store.cooldown(p) for p in ('codex','claude')) if c] or [0])
        if not wait or result.get('status')!='waiting_provider' or not delay:
            return result
        print(f'All providers are at their usage limits; waiting {delay/60:.0f} min, then continuing '
              f'(pause/cancel still work).',file=sys.stderr,flush=True)
        while delay>0:
            if store.control_value(run_id)!='run':
                return store.get(run_id)
            # A bulk cancel should wake quota-waiting controllers promptly.
            step=min(1,delay);sleep(step);delay-=step


def main(argv=None):
    p=argparse.ArgumentParser(prog='python -m harness',description='Hands-off animated ads using your installed CLI agents.')
    p.add_argument('--home',default=os.environ.get('STUDIO_HARNESS_HOME',str(Path.home()/'.local/share/goosnav-ad-studio')))
    sub=p.add_subparsers(dest='cmd',required=True)
    for name in ('make','new'):
        q=sub.add_parser(name);q.add_argument('--config',default=default_config())
        q.add_argument('--concept');q.add_argument('--website');q.add_argument('--count',type=int)
        q.add_argument('--seconds',type=int,help='Target length per ad (default 10)')
        q.add_argument('--plan',action='store_true',help='Create the run without starting any agents')
        q.add_argument('--no-wait',action='store_true',help='Stop instead of waiting out provider usage limits')
    for name in ('run','resume'):
        q=sub.add_parser(name);q.add_argument('id');q.add_argument('--steps',type=int)
        q.add_argument('--no-wait',action='store_true',help='Stop instead of waiting out provider usage limits')
    for name in ('status','events','pause'):
        q=sub.add_parser(name);q.add_argument('id')
    q=sub.add_parser('cancel',help='Cancel one run or every unfinished run')
    q.add_argument('id',nargs='?')
    q.add_argument('-a','--all',action='store_true',help='Cancel all active, queued, and paused runs')
    q=sub.add_parser('retry');q.add_argument('id');q.add_argument('--task',required=True)
    q=sub.add_parser('upload',help='Upload packaged ads to configured Drive (or retry a failed upload)')
    q.add_argument('id')
    q=sub.add_parser('cooldown',help='Inspect or clear cached provider quota cooldowns')
    q.add_argument('action',choices=('status','clear'))
    q.add_argument('provider',nargs='?',choices=('codex','claude','all'),default='all')
    sub.add_parser('list')
    for name in ('doctor','models'):
        q=sub.add_parser(name);q.add_argument('--config',default=default_config())
    q=sub.add_parser('gui',help='Local browser page for runs, config and controls')
    q.add_argument('--host',default='0.0.0.0',help='default: every interface (reachable on the LAN); 127.0.0.1 = this computer only')
    q.add_argument('--port',type=int,default=8788)
    q.add_argument('--no-browser',action='store_true')
    a=p.parse_args(argv)
    try:
        if a.cmd=='gui':
            from .gui import serve
            serve(a.home,a.host,a.port,not a.no_browser);return 0
        if a.cmd in ('doctor','models'):
            c=load_config(a.config)
            result=doctor(c) if a.cmd=='doctor' else resolve_workers(c['workers'])
        else:
            store=Store(a.home)
            if a.cmd in ('make','new'):
                overrides={k:getattr(a,k) for k in ('concept','website','count') if getattr(a,k) is not None}
                if a.seconds is not None:overrides['output']={'target_seconds':a.seconds}
                result=store.create(load_config(a.config,overrides));result['tasks']=build_tasks(result['config']['count'])
                store.save(result,'planned')
                if a.cmd=='make' and not a.plan:
                    print(f'Run {result["id"]} — inspect with: python -m harness --home {str(store.root)!r} status {result["id"]}',file=sys.stderr,flush=True)
                    result=drive(Engine(store),store,result['id'],not a.no_wait)
            elif a.cmd in ('run','resume'):
                if a.steps is not None and a.steps<0:raise ValueError('steps must be nonnegative')
                if a.cmd=='resume':
                    with store.worker_lock():
                        result=store.get(a.id)
                        for task in result['tasks']:
                            if task['status']=='cancelled':task['status']='pending'
                        store.save(result,'resumed')
                        store.control(a.id,'run')
                result=drive(Engine(store),store,a.id,not a.no_wait,a.steps)
            elif a.cmd=='retry':
                cancelled=False
                while True:
                    if store.control_value(a.id)=='cancel':
                        # A queued retry must not silently restart after cancel-all.
                        cancelled=True
                        break
                    try:
                        Engine(store).prepare_retry(a.id,a.task)
                        break
                    except Busy:
                        time.sleep(1)
                result=store.get(a.id) if cancelled else drive(Engine(store),store,a.id)
            elif a.cmd=='upload':
                result=upload_run(store,store.get(a.id))
            elif a.cmd=='cooldown':
                if a.action=='clear':
                    store.clear_cooldowns(None if a.provider=='all' else a.provider)
                    result={'cleared':a.provider}
                else:
                    result={p:round(store.cooldown(p)) for p in ('codex','claude')
                            if a.provider in ('all',p)}
            elif a.cmd=='cancel':
                if a.all or a.id=='all':
                    if a.all and a.id is not None:
                        raise ValueError('Use cancel --all OR cancel RUN_ID, not both')
                    ids=store.cancel_all()
                    result={'requested':'cancel_all','count':len(ids),'runs':ids}
                elif a.id:
                    store.control(a.id,'cancel');result={'id':a.id,'requested':'cancel'}
                else:
                    raise ValueError('Supply RUN_ID or use cancel --all')
            elif a.cmd=='pause':
                store.control(a.id,'pause');result={'id':a.id,'requested':'pause'}
            elif a.cmd=='status':result=store.get(a.id)
            elif a.cmd=='events':result=store.events(a.id)
            else:result=[{'id':r['id'],'status':r['status'],'created':r['created']} for r in store.list()]
            # Delivery is a post-render side effect. A Drive outage must never
            # turn a successfully rendered ad into a failed render.
            if (a.cmd in ('make','run','resume','retry') and result.get('status') in ('complete','partial')
                    and result['config'].get('delivery', {}).get('drive')):
                result=upload_run(store,result)
                if result['delivery']['status']=='failed':
                    print('Drive delivery failed (local videos remain safe): '
                          + result['delivery']['error'] + '\nRetry: ./ad upload ' + result['id'],
                          file=sys.stderr,flush=True)
        print(json.dumps(result,indent=2))
        if a.cmd=='upload' and result['delivery']['status']!='uploaded':
            return 1
        if isinstance(result,dict) and result.get('status') in ('failed','partial','needs_review','waiting_provider','cancelled','interrupted'):
            return 1
        return 0
    except KeyboardInterrupt:
        print('Interrupted. Work is saved; use resume RUN_ID.',file=sys.stderr);return 130
    except Exception as e:
        print(json.dumps({'error':str(e),'type':type(e).__name__}),file=sys.stderr);return 2


def _interrupt(signum, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM,_interrupt)

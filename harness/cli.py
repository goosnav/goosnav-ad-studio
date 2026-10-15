"""One-command production with inspectable, recoverable jobs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

from .config import load_config
from .models import resolve_workers
from .store import Store
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
                             config['sources']['assets']] for v in values if not v.startswith(('http://','https://')) and not Path(v).exists()]
    return checks


def main(argv=None):
    p=argparse.ArgumentParser(prog='python -m harness',description='Hands-off animated ads using your installed CLI agents.')
    p.add_argument('--home',default=os.environ.get('STUDIO_HARNESS_HOME',str(Path.home()/'.local/share/goosnav-ad-studio')))
    sub=p.add_subparsers(dest='cmd',required=True)
    for name in ('make','new'):
        q=sub.add_parser(name);q.add_argument('--config',default=default_config())
        q.add_argument('--concept');q.add_argument('--website');q.add_argument('--count',type=int)
        q.add_argument('--seconds',type=int,help='Target length per ad (default 10)')
        q.add_argument('--plan',action='store_true',help='Create the run without starting any agents')
    for name in ('run','resume'):
        q=sub.add_parser(name);q.add_argument('id');q.add_argument('--steps',type=int)
    for name in ('status','events','pause','cancel'):
        q=sub.add_parser(name);q.add_argument('id')
    q=sub.add_parser('retry');q.add_argument('id');q.add_argument('--task',required=True)
    sub.add_parser('list')
    for name in ('doctor','models'):
        q=sub.add_parser(name);q.add_argument('--config',default=default_config())
    q=sub.add_parser('gui',help='Local browser page for runs, config and controls')
    q.add_argument('--host',default='127.0.0.1',help='0.0.0.0 to reach it from the LAN');q.add_argument('--port',type=int,default=8788)
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
                    result=Engine(store).run(result['id'])
            elif a.cmd in ('run','resume'):
                if a.steps is not None and a.steps<0:raise ValueError('steps must be nonnegative')
                if a.cmd=='resume':
                    with store.worker_lock():
                        result=store.get(a.id)
                        for task in result['tasks']:
                            if task['status']=='cancelled':task['status']='pending'
                        store.save(result,'resumed')
                        store.control(a.id,'run')
                result=Engine(store).run(a.id,max_steps=a.steps)
            elif a.cmd=='retry':
                Engine(store).prepare_retry(a.id,a.task)
                result=Engine(store).run(a.id)
            elif a.cmd in ('pause','cancel'):
                store.control(a.id,a.cmd);result={'id':a.id,'requested':a.cmd}
            elif a.cmd=='status':result=store.get(a.id)
            elif a.cmd=='events':result=store.events(a.id)
            else:result=[{'id':r['id'],'status':r['status'],'created':r['created']} for r in store.list()]
        print(json.dumps(result,indent=2))
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

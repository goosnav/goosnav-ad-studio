import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def cli(tmp_path,*args):
    return subprocess.run([sys.executable,'-m','harness','--home',str(tmp_path),*args],
                          cwd=ROOT,capture_output=True,text=True)


def test_cli_minimal_plan_and_status(tmp_path):
    cfg=tmp_path/'blank.json';cfg.write_text('{}')
    r=cli(tmp_path,'make','--config',str(cfg),'--website','example.com','--count','2','--plan')
    assert r.returncode==0,r.stderr
    d=json.loads(r.stdout)
    assert d['status']=='ready' and len(d['tasks'])==24
    s=cli(tmp_path,'status',d['id'])
    assert json.loads(s.stdout)['config']['website']=='https://example.com'


def test_cli_unknown_run_and_invalid_input_are_clean_errors(tmp_path):
    r=cli(tmp_path,'status','../../escape')
    assert r.returncode!=0 and 'Traceback' not in r.stderr
    r=cli(tmp_path,'make','--count','0','--plan')
    assert r.returncode!=0 and 'count' in r.stderr

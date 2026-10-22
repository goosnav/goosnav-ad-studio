import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {prepareAudio,writeMix} from '../src/audio.mjs';
import {run} from '../src/process.mjs';
import {ROOT} from '../src/library.mjs';
test('offline local voice installation resolves the required files without demanding unrelated repository files',{skip:!process.env.THEATRE_PYTHON},async()=>{
 const output=await run(process.env.THEATRE_PYTHON,[path.join(ROOT,'voices/kokoro_worker.py'),'--identity'],{env:{...process.env,HF_HUB_OFFLINE:'1'}});
 const identity=JSON.parse(output);assert.equal(Object.keys(identity.files).length,4);assert.match(identity.files['kokoro-v1_0.pth'],/^[a-f0-9]{64}$/);
});
test('recorded audio measures real time and mouth activity, then reuses verified cache',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'theatre-audio-'));
 try{execFileSync('ffmpeg',['-v','error','-f','lavfi','-i','sine=frequency=330:duration=0.75','-ar','48000',path.join(root,'take.wav')]);
 const script={seed:1,cast:[{id:'reader',voice:'am_onyx'}],lines:[{id:'a',speaker:'reader',text:'Test',audio:'take.wav'}]};
 const options={mode:'recorded',inputRoot:root,cacheRoot:path.join(root,'cache')};
 const takes=await prepareAudio(script,options);assert.equal(takes.a.duration,.75);assert.ok(takes.a.mouth.some(p=>p.value>0));
 assert.equal((await prepareAudio(script,options)).a.sha256,takes.a.sha256);
 const out=path.join(root,'mix.wav');await writeMix({duration:1.5,events:[{id:'a',type:'line',start:.5,end:1.25}]},takes,out);
 const duration=execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',out],{encoding:'utf8'});assert.equal(Number(duration),1.5);
 }finally{await fs.rm(root,{recursive:true});}
});
test('missing recorded take errors rather than synthesizing or inserting silence',async()=>{
 await assert.rejects(prepareAudio({cast:[],lines:[{id:'a',speaker:'reader',text:'Hi'}]},{mode:'recorded'}),/audio|recorded/i);
});

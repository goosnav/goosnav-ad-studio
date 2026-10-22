import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {chromium} from 'playwright';
import {withDeadline,run} from '../src/process.mjs';
import {createJob,processJob,readJob} from '../src/jobs.mjs';

test('a hung real browser evaluation is closed by the watchdog',async()=>{
 const browser=await chromium.launch({headless:true});let closed=false;
 try{
  const page=await browser.newPage();
  await assert.rejects(withDeadline(page.evaluate(()=>new Promise(()=>{})),50,'Frame watchdog',async()=>{await browser.close();closed=true;}),/timed out/);
  await withDeadline((async()=>{while(!closed)await new Promise(r=>setTimeout(r,10));})(),5000,'Watchdog cleanup');
  assert.equal(browser.isConnected(),false);
 }finally{await browser.close();}
});

test('real capture verifies full video, recovers missing delivery, and replaces corrupt checkpoints',{timeout:180000},async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'theatre-capture-'));
 try{
  // A generated tone is a technical fixture only, never a purported voice demo.
  await run(process.env.FFMPEG??'ffmpeg',['-nostdin','-v','error','-f','lavfi','-i','sine=frequency=240:duration=0.2','-y',path.join(root,'take.wav')]);
  const job=await createJob({template:'book-duet',title:'Capture regression',comics:['book2-036'],seed:4,output:{width:128,height:128,fps:12},lines:[{speaker:'reader',text:'Fixture',audio:'take.wav'}]},{outputRoot:root,inputRoot:root,voice:'recorded'});
  const done=await processJob(job.id,{outputRoot:root});assert.equal(done.status,'complete');assert.ok(done.verification.frames>=40);assert.equal(done.verification.width,128);
  const dir=path.join(root,job.id),video=path.join(dir,job.id+'.mp4');
  await fs.unlink(video);assert.equal((await readJob(job.id,root)).status,'interrupted');
  const reused=[];assert.equal((await processJob(job.id,{outputRoot:root,progress:s=>reused.push(s)})).status,'complete');
  assert.equal(reused.some(s=>s.startsWith('Rendering frame')),false,'valid checkpoints reused');
  await fs.unlink(video);await fs.writeFile(path.join(dir,'segments','segment-0000.mp4'),'corrupt');
  const repaired=[];assert.equal((await processJob(job.id,{outputRoot:root,progress:s=>repaired.push(s)})).status,'complete');
  assert.ok(repaired.some(s=>s.startsWith('Rendering frame')),'corrupt checkpoint rerendered');
 }finally{await fs.rm(root,{recursive:true});}
});

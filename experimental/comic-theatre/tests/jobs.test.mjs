import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {segmentRanges,atomicJSON,readJob,processJob} from '../src/jobs.mjs';
import lockfile from 'proper-lockfile';
test('segment boundaries cover every frame exactly once, including short final part',()=>{
 assert.deepEqual(segmentRanges(125,24,2),[[0,48],[48,96],[96,125]]);
 assert.deepEqual(segmentRanges(1,24,2),[[0,1]]);
});
test('attempting a duplicate resume cannot mark a live run failed',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'theatre-active-')),dir=path.join(root,'active');await fs.mkdir(dir);
 await atomicJSON(path.join(dir,'job.json'),{id:'active',status:'rendering',pid:process.pid});const release=await lockfile.lock(dir);
 try{await assert.rejects(processJob('active',{outputRoot:root}),/lock/i);assert.equal((await readJob('active',root)).status,'rendering');}
 finally{await release();await fs.rm(root,{recursive:true});}
});
test('receipt writes are atomic and job IDs cannot escape output directory',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'theatre-jobs-'));try{await fs.mkdir(path.join(root,'run-1'));await atomicJSON(path.join(root,'run-1','job.json'),{id:'run-1',status:'failed',error:'Encoder stopped'});assert.equal((await readJob('run-1',root)).status,'failed');await assert.rejects(readJob('../run-1',root),/ID/i);}finally{await fs.rm(root,{recursive:true});}
});
test('complete jobs are not reported as delivered when their video is missing or changed',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'theatre-delivery-')),dir=path.join(root,'done');await fs.mkdir(dir);
 try{
  await atomicJSON(path.join(dir,'job.json'),{id:'done',status:'complete',verification:{sha256:'invalid'}});
  assert.equal((await readJob('done',root)).status,'interrupted');
  await fs.writeFile(path.join(dir,'done.mp4'),'changed');assert.equal((await readJob('done',root)).status,'interrupted');
 }finally{await fs.rm(root,{recursive:true});}
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {safePath,verifyCatalog,loadCatalog,ROOT,freezeAssets,digest} from '../src/library.mjs';
test('bundled assets are present and match provenance hashes',async()=>{const c=await loadCatalog();assert.equal((await verifyCatalog(c)).length,7);});
test('path escapes and archived material cannot become active sources',async()=>{
 for(const p of ['../package.json','/etc/passwd','assets/archive/bad.glb'])await assert.rejects(safePath(ROOT,p),/outside|relative|archive/i);
 const d=await fs.mkdtemp(path.join(os.tmpdir(),'theatre-path-'));try{await fs.symlink(os.tmpdir(),path.join(d,'escape'));await assert.rejects(safePath(d,'escape/test'),/outside|ENOENT/);}finally{await fs.rm(d,{recursive:true});}
});
test('wrong content hash fails verification before expensive work',async()=>{const c=await loadCatalog();c.comics[0].sha256='0'.repeat(64);await assert.rejects(verifyCatalog(c),/hash/i);});
test('a valid image cannot be mislabeled as another physical book page',async()=>{const c=await loadCatalog();c.comics[0].pdfPage=40;await assert.rejects(verifyCatalog(c),/book page|embedded/i);});
test('render assets are immutable snapshots of the verified bytes',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'theatre-freeze-'));try{
  await fs.cp(path.join(ROOT,'assets'),path.join(root,'assets'),{recursive:true});const c=await loadCatalog(root),frozen=await freezeAssets(c,root),entry=c.comics[0];
  await fs.writeFile(path.join(root,entry.path),'edited during render');
  assert.equal(digest(frozen.get('/'+entry.path)),entry.sha256);
  await assert.rejects(freezeAssets(c,root),/hash/i);
 }finally{await fs.rm(root,{recursive:true});}
});

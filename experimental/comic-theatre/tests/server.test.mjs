import test from 'node:test';
import assert from 'node:assert/strict';
import {startServer} from '../src/server.mjs';
test('local GUI rejects cross-origin mutations and exposes only approved source assets',async()=>{
 const s=await startServer({port:0});try{
  const c=await (await fetch(s.url+'/api/catalog')).json();assert.ok(c.comics.length>=3);
  const video=await fetch(s.url+'/'+c.assets.endCardVideo.path);
  assert.equal(video.status,200);assert.equal(video.headers.get('content-type'),'video/mp4');
  assert.equal((await video.arrayBuffer()).byteLength,Number(video.headers.get('content-length')));
  assert.equal((await fetch(s.url+'/src/endcard-video.mjs')).status,200);
  let r=await fetch(s.url+'/api/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({template:'book-duet'})});assert.equal(r.status,403);
  const {token}=await (await fetch(s.url+'/api/session')).json();
  r=await fetch(s.url+'/api/select',{method:'POST',headers:{'Content-Type':'application/json','X-Theatre-Token':token},body:JSON.stringify({template:'book-duet',seed:4})});assert.equal(r.status,200);assert.equal((await r.json()).script.comics.length,1);
  r=await fetch(s.url+'/api/select',{method:'POST',headers:{'Content-Type':'application/json','X-Theatre-Token':token,Origin:'https://evil.example'},body:'{}'});assert.equal(r.status,403);
  assert.equal((await fetch(s.url+'/writer.local.json')).status,404);assert.equal((await fetch(s.url+'/assets/catalog.json')).status,404);
 }finally{await s.close();}
});

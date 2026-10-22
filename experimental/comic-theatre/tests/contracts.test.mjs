import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveScript,selectScript} from '../src/contracts.mjs';
const catalog={edition:{id:'book',pdfSha256:'a'.repeat(64)},templates:[{id:'book-duet',minComics:1,maxComics:1,speakers:['reader','friend'],scenes:['library','fireside']}],comics:[{id:'p1',sha256:'b'.repeat(64),pdfPage:5,verified:true},{id:'p2',sha256:'c'.repeat(64),pdfPage:6,verified:true}]};
const input=()=>({template:'book-duet',title:'Test',comics:['p1'],lines:[{speaker:'reader',text:'Hello.'}]});
test('simple script locks exact pages and deterministic defaults',()=>{
 const a=resolveScript({...input(),seed:12},catalog),b=resolveScript({...input(),seed:12},catalog);
 assert.deepEqual(a,b);assert.equal(a.sourceLock[0].sha256,'b'.repeat(64));assert.equal(a.lines[0].comic,'p1');assert.equal(a.lines[0].emotion,'neutral');
});
test('cannot substitute a different source under a saved lock',()=>{
 const a=resolveScript(input(),catalog); a.comics=['p2'];a.lines[0].comic='p2';assert.throws(()=>resolveScript(a,catalog),/lock|changed/i);
});
test('typos and unsupported facial fields fail with helpful options',()=>{
 assert.throws(()=>resolveScript({...input(),lines:[{speaker:'reader',text:'Hi',emotion:'smuggg'}]},catalog),/emotion.*neutral/i);
 assert.throws(()=>resolveScript({...input(),lines:[{speaker:'reader',text:'Hi',face:{jaw:9}}]},catalog),/face/i);
});
test('template restrictions and undeclared pages are enforced',()=>{
 assert.throws(()=>resolveScript({...input(),comics:['p1','p2']},catalog),/comic/i);
 assert.throws(()=>resolveScript({...input(),lines:[{speaker:'reader',text:'Hi',comic:'p2'}]},catalog),/selected|declared/i);
 assert.throws(()=>resolveScript({...input(),lines:[{speaker:'ghost',text:'Hi'}]},catalog),/speaker/i);
});
test('random selection is seeded and excludes unverified material',()=>{
 const c={...catalog,comics:[...catalog.comics,{id:'bad',verified:false}]};
 const a=selectScript('book-duet',3,c);assert.deepEqual(a,selectScript('book-duet',3,c));assert.ok(!a.comics.includes('bad'));
});
test('book rails reject impossible hand state and incomplete selected content',()=>{
 assert.throws(()=>resolveScript({...input(),lines:[{action:'place'},{speaker:'reader',text:'Hi'}]},catalog),/held|state/i);
 assert.throws(()=>resolveScript({...input(),lines:[{action:'close'}]},catalog),/dialogue|line/i);
});
test('held book constrains listener hands too, and turn requires a target',()=>{
 assert.throws(()=>resolveScript({...input(),lines:[{action:'hold'},{speaker:'friend',text:'Hi',reaction:{actor:'reader',gesture:'shrug'}}]},catalog),/hands|held/i);
 assert.throws(()=>resolveScript({...input(),lines:[{action:'turn'},{speaker:'reader',text:'Hi'}]},catalog),/target|comic/i);
});
test('adjacent turns use the actual book spread numbering',()=>{
 const c={...catalog,templates:[{...catalog.templates[0],maxComics:3}],comics:[{...catalog.comics[0],id:'p4',pdfPage:4},{...catalog.comics[0],id:'p5',pdfPage:5},{...catalog.comics[0],id:'p6',pdfPage:6}]};
 const script=(a,b)=>({...input(),comics:[a,b],lines:[{speaker:'reader',text:'First',comic:a},{action:'turn',comic:b},{speaker:'friend',text:'Next',comic:b}]});
 assert.throws(()=>resolveScript(script('p4','p5'),c),/adjacent/i);
 assert.doesNotThrow(()=>resolveScript(script('p5','p6'),c));
});

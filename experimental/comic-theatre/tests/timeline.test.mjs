import test from 'node:test';
import assert from 'node:assert/strict';
import {compileTimeline} from '../src/timeline.mjs';
const script={seed:1,scene:'library',template:'book-duet',comics:['p'],cast:[{id:'reader'},{id:'friend'}],output:{width:540,height:675,fps:24},lines:[{id:'a',speaker:'reader',text:'First',comic:'p',pause:.4,reaction:{actor:'friend',at:'line_end',duration:.8}},{id:'b',speaker:'friend',text:'Last',comic:'p',pause:.2}]};
test('timeline includes source, every measured take and full final reaction',()=>{
 const t=compileTimeline(script,{a:{duration:2,mouth:[]},b:{duration:1,mouth:[]}});
 assert.equal(t.events[0].type,'source');assert.equal(t.events[0].end,3);
 assert.equal(t.events.find(e=>e.id==='a').start,3);assert.equal(t.events.find(e=>e.id==='b').start,5.8);
 assert.equal(t.duration,7);assert.equal(t.frames,168);
});
test('missing or nonfinite takes cannot be replaced with filler',()=>{
 assert.throws(()=>compileTimeline(script,{a:{duration:2}}),/Missing|take/i);
 assert.throws(()=>compileTimeline(script,{a:{duration:NaN},b:{duration:1}}),/duration|take/i);
});
test('each source change inserts the selected page without deleting lines',()=>{
 const s=structuredClone(script);s.lines[1].comic='q';s.comics.push('q');const t=compileTimeline(s,{a:{duration:2},b:{duration:1}});
 assert.deepEqual(t.events.filter(e=>e.type==='source').map(e=>e.comic),['p','q']);assert.equal(t.events.filter(e=>e.type==='line').length,2);
});

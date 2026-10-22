import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveScript} from '../src/contracts.mjs';
import {compileTimeline} from '../src/timeline.mjs';
import {loadCatalog} from '../src/library.mjs';
import {acceptDraft} from '../src/writer.mjs';
const c=await loadCatalog();
const raw=()=>({template:'book-duet',title:'Test',seed:17,comics:['book2-036'],lines:Array.from({length:6},(_,i)=>({speaker:i%2?'friend':'reader',text:'A line.'}))});
const takes=s=>Object.fromEntries(s.lines.map(l=>[l.id,{duration:1,mouth:[]} ]));
test('minimal inputs get distinct clothing and a product-specific editable closing card',()=>{
 const s=resolveScript(raw(),c);assert.notEqual(s.characters.reader,s.characters.friend);assert.equal(s.product,'book2');assert.equal(s.endCard.title,'Goosnav Book Two');assert.equal(s.endCard.url,'www.goosnav.shop');
 const custom=resolveScript({...raw(),characters:{reader:'olive',friend:'blue'},endCard:{title:'Keep reading',text:'Another page.',seconds:4}},c);
 assert.equal(custom.endCard.title,'Keep reading');assert.equal(custom.characters.reader,'olive');assert.deepEqual(resolveScript(custom,c),custom);
 assert.throws(()=>resolveScript({...raw(),characters:{reader:'astronaut'}},c),/blue|rust|olive/);
 assert.throws(()=>resolveScript({...raw(),endCard:{seconds:0}},c),/seconds/);
 assert.throws(()=>resolveScript({...raw(),endCard:{title:'a'.repeat(121)}},c),/title/);
 const beady=resolveScript({...raw(),characters:{reader:'blue-beady',friend:'olive'}},c);
 assert.equal(beady.characters.reader,'blue-beady');assert.deepEqual(resolveScript(beady,c),beady);
});
test('seeded auto shots provide a two-shot and varied compositions while explicit choices win',()=>{
 const s=resolveScript(raw(),c),a=compileTimeline(s,takes(s)),b=compileTimeline(s,takes(s));assert.deepEqual(a,b);
 const shots=a.events.filter(e=>e.type==='line').map(e=>e.shot);assert.equal(shots[0],'two-shot');assert.ok(new Set(shots).size>=3);assert.ok(!shots.includes('auto'));
 const changed=compileTimeline({...s,seed:333},takes(s));assert.notDeepEqual(changed.events.filter(e=>e.type==='line').map(e=>e.shot),shots);
 s.lines[0].shot='source';assert.equal(compileTimeline(s,takes(s)).events.find(e=>e.type==='line').shot,'source');
 assert.equal(a.events[0].shot,'book');
});
test('solo templates retain clothing choices for inactive known roles without adding actors',()=>{
 const s=resolveScript({...raw(),template:'fireside-reader',characters:{reader:'olive',friend:'blue'},lines:[{speaker:'reader',text:'A line.'}]},c);
 assert.deepEqual(s.characters,{reader:'olive',friend:'blue'});assert.equal(s.cast.length,1);
 assert.deepEqual(resolveScript(s,c),s);
 assert.throws(()=>resolveScript({...raw(),characters:{intruder:'blue'}},c),/unknown field/);
});
test('end card follows every measured take and reaction without replacing dialogue',()=>{
 const s=resolveScript(raw(),c),t=compileTimeline(s,takes(s));assert.equal(t.events.filter(e=>e.type==='line').length,6);assert.equal(t.events.at(-1).type,'endcard');assert.equal(t.events.at(-1).end-t.events.at(-1).start,3);
 const no=compileTimeline({...s,endCard:{...s.endCard,enabled:false}},takes(s));assert.equal(t.duration-no.duration,3);assert.ok(no.events.every(e=>e.type!=='endcard'));
});
test('optional writer cannot overwrite chosen cast colors or end card',()=>{
 const s=resolveScript(raw(),c),draft={title:'Draft',lines:s.lines};assert.deepEqual(acceptDraft(draft,s,c).endCard,s.endCard);
 assert.throws(()=>acceptDraft({...draft,characters:{reader:'olive',friend:'blue'}},s,c),/locked/);
 assert.throws(()=>acceptDraft({...draft,endCard:{...s.endCard,title:'Wrong'}},s,c),/locked/);
});

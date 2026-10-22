import {randomInt} from 'node:crypto';
import {bookSpread} from './book-pages.mjs';
export const EMOTIONS=['neutral','thoughtful','curious','skeptical','dry','pleased','concerned','exasperated'];
export const GESTURES=['none','explain','nod','head_tilt','shrug','page_glance'];
const ACTIONS=['open','turn','hold','read','place','close','slam'];
const fail=(s)=>{throw new Error(s);};
const object=(v,label)=>{if(!v||typeof v!=='object'||Array.isArray(v))fail(`${label} must be an object`);};
const keys=(v,allowed,label)=>{object(v,label);for(const k of Object.keys(v))if(!allowed.includes(k))fail(`${label}.${k}: unknown field. Options: ${allowed.join(', ')}`);};
const number=(v,lo,hi,label)=>{if(typeof v!=='number'||!Number.isFinite(v)||v<lo||v>hi)fail(`${label} must be ${lo}–${hi}`);return v;};
const choice=(v,options,label)=>{if(!options.includes(v))fail(`${label}: choose ${options.join(', ')}`);return v;};
export function seeded(seed){let x=seed>>>0;return()=>{x=(Math.imul(x,1664525)+1013904223)>>>0;return x/4294967296;};}
function face(v,label){if(v===undefined)return {};keys(v,['brow_left','brow_right','eye_open','mouth_curve','blink'],label);for(const [k,n]of Object.entries(v)){if(k==='blink')choice(n,['auto','once','off'],label+'.blink');else number(n,k==='eye_open'?0:-1,1,label+'.'+k);}return {...v};}
function selection(template,ids,catalog){
 const t=catalog.templates.find(t=>t.id===template);if(!t)fail(`template: choose ${catalog.templates.map(t=>t.id).join(', ')}`);
 if(!Array.isArray(ids)||ids.length<t.minComics||ids.length>t.maxComics||new Set(ids).size!==ids.length)fail(`${template} needs ${t.minComics}–${t.maxComics} distinct comic IDs`);
 const selected=ids.map(id=>{const c=catalog.comics.find(c=>c.id===id&&c.verified);if(!c)fail(`Unknown or unverified comic: ${id}`);return c;});return {t,selected};
}
export function resolveScript(raw,catalog){
 keys(raw,['version','template','title','comics','seed','scene','lines','output','sourceLock','cast'], 'script');
 if((raw.version??1)!==1)fail('version must be 1');
 if(typeof raw.title!=='string'||!raw.title.trim()||raw.title.length>160)fail('title must contain 1–160 characters');
 const {t,selected}=selection(raw.template,raw.comics,catalog);
 const seed=raw.seed??randomInt(0,2147483647);number(seed,0,4294967295,'seed');if(!Number.isInteger(seed))fail('seed must be an integer');
 const scene=raw.scene??t.scenes[Math.floor(seeded(seed)()*t.scenes.length)];choice(scene,t.scenes,'scene');
 const sourceLock=selected.map(c=>({id:c.id,sha256:c.sha256,pdfPage:c.pdfPage,pdfSha256:catalog.edition.pdfSha256}));
 if(raw.sourceLock&&JSON.stringify(raw.sourceLock)!==JSON.stringify(sourceLock))fail('Source lock changed. Re-select and review the source before creating a new script.');
 if(!Array.isArray(raw.lines)||!raw.lines.length||raw.lines.length>200)fail('lines must contain 1–200 entries');
 let state=raw.lines[0]?.action==='open'?'table-closed':'table-open',current=selected[0].id;
 const used=new Set();
 const lines=raw.lines.map((line,i)=>{
  const label=`lines[${i}]`;object(line,label);
  if(line.action!==undefined){
   keys(line,['action','comic','seconds','id','bookState'],label);choice(line.action,ACTIONS,label+'.action');
   if(line.action==='turn'&&!line.comic)fail(`${label}: turn needs an explicit target comic`);
   if(line.comic&&line.comic!==current&&!['open','turn'].includes(line.action))fail(`${label}: only open/turn actions may change the comic; use dialogue comic for a source cut`);
   const transitions={open:['table-closed','table-open'],turn:['table-open','table-open'],hold:['table-open','held-open'],read:[state,state],place:['held-open','table-open'],close:['table-open','table-closed'],slam:['table-open','table-closed']};
   const [from,to]=transitions[line.action];if(state!==from||line.action==='read'&&state==='table-closed')fail(`${label}: ${line.action} needs ${from==='table-closed'?'closed':from} book state, currently ${state}`);
   if(line.comic){if(!raw.comics.includes(line.comic))fail(`${label}: comic is not selected`);if(line.action==='turn'){const a=catalog.comics.find(c=>c.id===current),b=catalog.comics.find(c=>c.id===line.comic);if(bookSpread(a.pdfPage)===null||bookSpread(b.pdfPage)===null||Math.abs(bookSpread(a.pdfPage)-bookSpread(b.pdfPage))!==1)fail(`${label}: turn requires an adjacent spread; use a line's comic field for a deliberate source cut`);}current=line.comic;}
   state=to;return {...line,id:`beat-${i}`,seconds:number(line.seconds??({slam:.65,turn:1.2,open:1.3,hold:1,place:1,close:.9,read:1}[line.action]),.3,8,label+'.seconds'),comic:current,bookState:state};
  }
  keys(line,['speaker','text','comic','emotion','gesture','face','reaction','pause','shot','audio','id','bookState'],label);
  choice(line.speaker,t.speakers,label+'.speaker');if(typeof line.text!=='string'||!line.text.trim()||line.text.length>1000)fail(`${label}.text needs 1–1000 characters`);
  const comic=line.comic??current;if(!raw.comics.includes(comic))fail(`${label}: comic ${comic} is not selected/declared`);
  if(state==='table-closed')fail(`${label}: open the book before reading dialogue`);
  if(comic!==current&&state==='held-open')fail(`${label}: place the held book before switching comic`);
  current=comic;used.add(comic);const gesture=choice(line.gesture??'none',GESTURES,label+'.gesture');
  if(state==='held-open'&&line.speaker==='reader'&&['explain','shrug'].includes(gesture))fail(`${label}: held book reserves the reader's hands; choose nod, head_tilt, page_glance or none`);
  let reaction;if(line.reaction){keys(line.reaction,['actor','emotion','gesture','face','at','duration'],label+'.reaction');reaction={...line.reaction,actor:line.reaction.actor??t.speakers.find(s=>s!==line.speaker),emotion:choice(line.reaction.emotion??'neutral',EMOTIONS,label+'.reaction.emotion'),gesture:choice(line.reaction.gesture??'none',GESTURES,label+'.reaction.gesture'),face:face(line.reaction.face,label+'.reaction.face'),at:choice(line.reaction.at??'line_end',['line_start','line_end'],label+'.reaction.at'),duration:number(line.reaction.duration??.8,.1,5,label+'.reaction.duration')};if(!t.speakers.includes(reaction.actor)||reaction.actor===line.speaker)fail(`${label}: reaction needs a different cast actor`);}
  if(line.audio!==undefined&&(typeof line.audio!=='string'||!line.audio||line.audio.includes('\0')))fail(`${label}.audio must be a relative filename`);
  if(state==='held-open'&&reaction?.actor==='reader'&&['explain','shrug'].includes(reaction.gesture))fail(`${label}: held book reserves the reader's hands during reactions too`);
  return {...line,id:`beat-${i}`,comic,emotion:choice(line.emotion??'neutral',EMOTIONS,label+'.emotion'),gesture,face:face(line.face,label+'.face'),pause:number(line.pause??.4,0,5,label+'.pause'),shot:choice(line.shot??'speaker',['speaker','two-shot','source'],label+'.shot'),...(reaction?{reaction}:{}),bookState:state};
 });
 if(!used.size)fail('At least one dialogue line is required');for(const c of raw.comics)if(!used.has(c))fail(`Selected comic ${c} needs a dialogue line`);
 const output={width:1080,height:1350,fps:24,...raw.output};keys(output,['width','height','fps'],'output');for(const k of ['width','height']){number(output[k],128,1920,'output.'+k);if(output[k]%2)fail(`output.${k} must be an even integer`);}choice(output.fps,[12,24,30],'output.fps');
 return {version:1,template:t.id,title:raw.title.trim(),comics:[...raw.comics],seed,scene,lines,output,sourceLock,cast:t.speakers.map(id=>({id,voice:id==='reader'?'am_onyx':'am_puck'}))};
}
export function selectScript(template,seed=randomInt(0,2147483647),catalog){
 const t=catalog.templates.find(t=>t.id===template);if(!t)fail('Unknown template');number(seed,0,4294967295,'seed');const rand=seeded(seed);
 const pool=catalog.comics.filter(c=>c.verified);for(let i=pool.length-1;i>0;i--){const j=Math.floor(rand()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]];}
 if(pool.length<t.minComics)fail('Not enough verified comics for this template');
 const comics=pool.slice(0,t.minComics).map(c=>c.id);
 return resolveScript({template,title:'New comic conversation',comics,seed,lines:comics.map(comic=>({speaker:'reader',comic,text:'Write your commentary here.'}))},catalog);
}

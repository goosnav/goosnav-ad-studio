import {seeded} from './contracts.mjs';
const RATE=48000;
const ticks=s=>Math.round(s*RATE);
export function compileTimeline(script,takes){
 const events=[];let cursor=0,lastComic=null,established=false,previous=null,bag=[];
 const random=seeded((script.seed??0)^0x53c74);
 const shotFor=line=>{
  if(line.shot&&line.shot!=='auto'){if(line.shot==='two-shot')established=true;previous=line.shot;return line.shot;}
  if(!established&&script.cast.length>1){established=true;previous='two-shot';return previous;}
  if(!bag.length){bag=script.cast.length>1?['speaker','over-shoulder','two-shot']:['speaker','book'];for(let i=bag.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[bag[i],bag[j]]=[bag[j],bag[i]];}}
  let index=bag.findIndex(s=>s!==previous);if(index<0){bag=[];return shotFor(line);}
  previous=bag.splice(index,1)[0];return previous;
 };
 const add=(event,duration)=>{const start=cursor;cursor+=ticks(duration);events.push({...event,start:start/RATE,end:cursor/RATE});};
 for(const line of script.lines){
  if(line.action){add({...line,type:'action',rail:line.action},line.seconds);continue;}
  const take=takes[line.id];if(!take||!Number.isFinite(take.duration)||take.duration<=0)throw Error(`Missing or invalid take duration: ${line.id}`);
  if(lastComic!==line.comic){add({id:`source-${line.id}`,type:'source',shot:'book',comic:line.comic,bookState:line.bookState??'table-open'},3);lastComic=line.comic;}
  const shot=shotFor(line);
  add({...line,shot,type:'line',mouth:take.mouth??[],bookState:line.bookState??'table-open'},take.duration);
  const pause=Math.max(line.pause??.4,line.reaction?.at==='line_end'?line.reaction.duration:0);
  if(pause)add({...line,shot,id:`hold-${line.id}`,type:'hold',mouth:[],bookState:line.bookState??'table-open'},pause);
 }
 if(script.endCard?.enabled)add({...script.endCard,id:'end-card',type:'endcard'},script.endCard.seconds);
 return {version:1,...script.output,duration:cursor/RATE,frames:Math.ceil(cursor/RATE*script.output.fps),seed:script.seed,scene:script.scene,template:script.template,cast:script.cast.map(c=>c.id),characters:script.characters,product:script.product,endCard:script.endCard,sources:script.comics,events};
}

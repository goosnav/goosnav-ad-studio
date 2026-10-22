const RATE=48000;
const ticks=s=>Math.round(s*RATE);
export function compileTimeline(script,takes){
 const events=[];let cursor=0,lastComic=null;
 const add=(event,duration)=>{const start=cursor;cursor+=ticks(duration);events.push({...event,start:start/RATE,end:cursor/RATE});};
 for(const line of script.lines){
  if(line.action){add({...line,type:'action',rail:line.action},line.seconds);continue;}
  const take=takes[line.id];if(!take||!Number.isFinite(take.duration)||take.duration<=0)throw Error(`Missing or invalid take duration: ${line.id}`);
  if(lastComic!==line.comic){add({id:`source-${line.id}`,type:'source',comic:line.comic,bookState:line.bookState??'table-open'},3);lastComic=line.comic;}
  add({...line,type:'line',mouth:take.mouth??[],bookState:line.bookState??'table-open'},take.duration);
  const pause=Math.max(line.pause??.4,line.reaction?.at==='line_end'?line.reaction.duration:0);
  if(pause)add({...line,id:`hold-${line.id}`,type:'hold',mouth:[],bookState:line.bookState??'table-open'},pause);
 }
 return {version:1,...script.output,duration:cursor/RATE,frames:Math.ceil(cursor/RATE*script.output.fps),seed:script.seed,scene:script.scene,template:script.template,cast:script.cast.map(c=>c.id),sources:script.comics,events};
}

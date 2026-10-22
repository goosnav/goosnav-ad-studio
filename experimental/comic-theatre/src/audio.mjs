import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {ROOT,safePath,digest} from './library.mjs';
import {run} from './process.mjs';
export async function pythonCommand(){
 if(process.env.THEATRE_PYTHON)return process.env.THEATRE_PYTHON;
 const local=path.join(ROOT,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 try{await fs.access(local);return local;}catch{return process.platform==='win32'?'python':'python3';}
}
async function decode(file){return run(process.env.FFMPEG??'ffmpeg',['-nostdin','-v','error','-i',file,'-f','s16le','-ac','1','-ar','48000','pipe:1']);}
function measure(pcm){
 if(!pcm.length||pcm.length%2)throw Error('Empty/corrupt audio');let peak=0,clipped=0;const mouth=[];
 for(let off=0;off<pcm.length;off+=1920){let sum=0,n=0;for(let k=off;k<Math.min(off+1920,pcm.length);k+=2){const a=pcm.readInt16LE(k)/32768;peak=Math.max(peak,Math.abs(a));if(Math.abs(a)>.999)clipped++;sum+=a*a;n++;}mouth.push({t:off/96000,value:Math.min(1,Math.sqrt(sum/n)*12)});}
 if(peak<.0001)throw Error('Silent audio take');if(clipped>48)throw Error('Clipped audio take; supply a clean recording');
 const duration=pcm.length/96000;let level=0;
 // Filter in audio time, once per take—not renderer history—so seeking remains
 // deterministic. Soft onset/release avoids popping between a line and silence.
 for(const point of mouth){const target=point.value*.75,tau=target>level?.04:.07;level+=(target-level)*(1-Math.exp(-.02/tau));const edge=Math.min(1,point.t/.06,(duration-point.t)/.08);point.value=level*Math.max(0,edge);}
 mouth.push({t:duration,value:0});
 return {duration,mouth};
}
export async function prepareAudio(script,{mode='kokoro',inputRoot=ROOT,cacheRoot=path.join(ROOT,'.cache/audio'),progress=()=>{}}={}){
 if(!['recorded','kokoro'].includes(mode))throw Error('voice: choose kokoro or recorded');
 const lines=script.lines.filter(l=>l.text);if(mode==='recorded'&&lines.some(l=>!l.audio))throw Error('Recorded mode requires an audio filename on every dialogue line');
 await fs.mkdir(cacheRoot,{recursive:true});const tmp=await fs.mkdtemp(path.join(cacheRoot,'prepare-'));let identity=null;const result={},pending=[];
 try{
  if(lines.some(l=>!l.audio)){
   progress('Checking local voice model');const raw=await run(await pythonCommand(),[path.join(ROOT,'voices/kokoro_worker.py'),'--identity'],{timeout:60000,env:{...process.env,HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1'}});identity=JSON.parse(raw.toString());
  }
  for(const line of lines){
   let source=null;if(line.audio){if(!/\.(wav|flac|mp3|ogg|m4a)$/i.test(line.audio))throw Error('Recorded audio needs WAV, FLAC, MP3, OGG or M4A');source=await safePath(inputRoot,line.audio);}
   const voice=script.cast.find(c=>c.id===line.speaker)?.voice;if(!source&&!voice)throw Error('Missing voice profile');
   const key=digest(JSON.stringify({v:1,text:line.text,voice:source?null:voice,identity,source:source?digest(await fs.readFile(source)):null}));
   const file=path.join(cacheRoot,key+'.pcm'),receipt=path.join(cacheRoot,key+'.json');let pcm;
   try{const meta=JSON.parse(await fs.readFile(receipt));const b=await fs.readFile(file);if(meta.sha256===digest(b))pcm=b;}catch{}
   if(pcm){result[line.id]={path:file,sha256:digest(pcm),...measure(pcm)};continue;}
   const native=source??path.join(tmp,`${line.id}.wav`);pending.push({line,key,file,receipt,native,source,voice});
  }
  const synth=pending.filter(p=>!p.source);if(synth.length){
   progress(`Synthesizing ${synth.length} local voice takes`);const request=path.join(tmp,'request.json');await fs.writeFile(request,JSON.stringify(synth.map(p=>({text:p.line.text,voice:p.voice,output:p.native}))));
   await run(await pythonCommand(),[path.join(ROOT,'voices/kokoro_worker.py'),request],{timeout:600000,env:{...process.env,HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1'}});
  }
  for(const p of pending){const pcm=await decode(p.native),info=measure(pcm);const nonce=randomUUID();await fs.writeFile(p.file+'.'+nonce,pcm);await fs.rename(p.file+'.'+nonce,p.file);await fs.writeFile(p.receipt+'.'+nonce,JSON.stringify({sha256:digest(pcm),identity}));await fs.rename(p.receipt+'.'+nonce,p.receipt);result[p.line.id]={path:p.file,sha256:digest(pcm),...info};}
  return result;
 }finally{await fs.rm(tmp,{recursive:true,force:true});}
}
export async function writeMix(timeline,takes,output){
 if(timeline.duration>600)throw Error('Episode exceeds the 600-second resource safety bound; split into episodes. Prepared takes are cached.');
 const pcm=Buffer.alloc(Math.ceil(timeline.duration*48000)*2);
 for(const e of timeline.events.filter(e=>e.type==='line')){const t=takes[e.id],bytes=await fs.readFile(t.path);if(digest(bytes)!==t.sha256)throw Error('Take changed before mixing');bytes.copy(pcm,Math.round(e.start*48000)*2);}
 await run(process.env.FFMPEG??'ffmpeg',['-nostdin','-v','error','-y','-f','s16le','-ar','48000','-ac','1','-i','pipe:0','-c:a','pcm_s16le',output],{input:pcm,maxBytes:1024});
}

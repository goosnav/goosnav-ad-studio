import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';
import {digest} from './library.mjs';
import {atomicJSON,segmentRanges} from './jobs.mjs';
import {run,withDeadline} from './process.mjs';
import {startServer} from './server.mjs';
export async function probeVideo(file){return JSON.parse((await run(process.env.FFPROBE??'ffprobe',['-v','error','-count_frames','-show_streams','-show_format','-of','json',file])).toString());}
export async function captureVideo({dir,id,timeline,catalog,inputKey,progress=()=>{}}){
 const server=await startServer({outputRoot:path.dirname(dir),renderCatalog:catalog});let browser,page;
 const closeBrowser=async()=>{if(browser){const previous=browser;browser=null;await withDeadline(previous.close(),5000,'Browser shutdown').catch(()=>{});}};
 const segmentsDir=path.join(dir,'segments');await fs.mkdir(segmentsDir,{recursive:true});
 try{
  const load=async()=>{
   await closeBrowser();
   browser=await chromium.launch({headless:true,timeout:60000,...(process.env.THEATRE_BROWSER?{executablePath:process.env.THEATRE_BROWSER}:{}),args:['--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
   page=await withDeadline(browser.newPage({viewport:{width:timeline.width,height:timeline.height},deviceScaleFactor:1}),30000,'Browser page setup',closeBrowser);
   await page.route('**/*',route=>new URL(route.request().url()).origin===server.url?route.continue():route.abort());
   await page.goto(server.url+'/render/'+id);await page.waitForFunction(()=>window.renderReady||window.renderError,{},{timeout:60000});
   const error=await withDeadline(page.evaluate(()=>window.renderError),30000,'Renderer setup',closeBrowser);if(error)throw Error(error);
  };
  await load();const parts=[],ranges=segmentRanges(timeline.frames,timeline.fps);
  for(const [index,[start,end]]of ranges.entries()){
   const name=`segment-${String(index).padStart(4,'0')}`,mp4=path.join(segmentsDir,name+'.mp4'),receipt=path.join(segmentsDir,name+'.json');let valid=false;
   try{const r=JSON.parse(await fs.readFile(receipt));valid=r.inputKey===inputKey&&r.start===start&&r.end===end&&r.sha256===digest(await fs.readFile(mp4));}catch{}
   if(!valid){
    let error;for(let attempt=0;attempt<3;attempt++){
     const framesDir=path.join(segmentsDir,name+'-frames');await fs.mkdir(framesDir,{recursive:true});
     try{
      if(attempt){await progress(`Retry ${attempt}/2 of segment ${index+1}`);await load();}
      for(let f=start;f<end;f++){
       await withDeadline(page.evaluate(f=>window.player.renderAt(f),f),30000,`Frame ${f}`,closeBrowser);
       await page.locator('canvas').screenshot({path:path.join(framesDir,`frame-${String(f-start).padStart(6,'0')}.png`),timeout:30000});
       if((f-start)%timeline.fps===0)await progress(`Rendering frame ${f+1}/${timeline.frames} · segment ${index+1}/${ranges.length}`);
      }
      await run(process.env.FFMPEG??'ffmpeg',['-nostdin','-v','error','-y','-framerate',String(timeline.fps),'-i',path.join(framesDir,'frame-%06d.png'),'-frames:v',String(end-start),'-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-threads','2','-an',mp4]);
      const p=await probeVideo(mp4),v=p.streams.find(s=>s.codec_type==='video');if(Number(v?.nb_read_frames)!==end-start)throw Error('Segment frame count mismatch');
      await atomicJSON(receipt,{inputKey,start,end,sha256:digest(await fs.readFile(mp4))});await fs.rm(framesDir,{recursive:true});error=null;break;
     }catch(e){error=e;if(attempt<2)await new Promise(r=>setTimeout(r,500*(attempt+1)));}
    }
    if(error)throw error;
   }
   parts.push(`file '${name}.mp4'`);
  }
  await progress('Encoding and checking the complete video');const list=path.join(segmentsDir,'concat.txt');await fs.writeFile(list,parts.join('\n')+'\n');
  const dest=path.join(dir,id+'.mp4'),partial=path.join(dir,'final.partial.mp4');
  await run(process.env.FFMPEG??'ffmpeg',['-nostdin','-v','error','-y','-f','concat','-safe','1','-i',list,'-i',path.join(dir,'mix.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-af','apad','-t',String(timeline.frames/timeline.fps),'-movflags','+faststart',partial]);
  const p=await probeVideo(partial),v=p.streams.find(s=>s.codec_type==='video'),a=p.streams.find(s=>s.codec_type==='audio');
  if(!a||v?.width!==timeline.width||v?.height!==timeline.height||Number(v?.nb_read_frames)!==timeline.frames||Math.abs(Number(p.format.duration)-timeline.frames/timeline.fps)>.1)throw Error('Final audio/video verification failed');
  await run(process.env.FFMPEG??'ffmpeg',['-nostdin','-v','error','-i',partial,'-f','null','-'],{timeout:120000});
  await fs.rename(partial,dest);return {path:dest,sha256:digest(await fs.readFile(dest)),frames:timeline.frames,duration:Number(p.format.duration),width:v.width,height:v.height,sources:timeline.sources,sourceLock:catalog.comics.filter(c=>timeline.sources.includes(c.id)).map(c=>({id:c.id,sha256:c.sha256})),delivery:'local-only'};
 }finally{await closeBrowser();await server.close();}
}

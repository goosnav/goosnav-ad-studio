#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import {ROOT,loadCatalog,verifyCatalog} from '../src/library.mjs';
import {resolveScript,selectScript} from '../src/contracts.mjs';
import {createJob,processJob,listJobs,readJob,OUTPUT} from '../src/jobs.mjs';
import {startServer} from '../src/server.mjs';
import {draftScript} from '../src/writer.mjs';
import {run} from '../src/process.mjs';
const help=`Comic Theatre — local JSON-driven book cutscenes

  node bin/theatre.mjs gui [--port 8777]
  node bin/theatre.mjs select TEMPLATE [--seed NUMBER] [--out script.json]
  node bin/theatre.mjs validate script.json
  node bin/theatre.mjs render script.json [--voice kokoro|recorded] [--preview]
  node bin/theatre.mjs resume RUN_ID
  node bin/theatre.mjs status [RUN_ID]
  node bin/theatre.mjs draft script.json [--out draft.json]
  node bin/theatre.mjs draft --template TEMPLATE [--seed NUMBER] [--out draft.json]
  node bin/theatre.mjs assets
  node bin/theatre.mjs doctor

Templates: book-duet (1 comic), fireside-reader (1), page-tour (2–3).
Rendering never calls a paid API/agent. 'draft' explicitly enables optional AI.
--preview renders 432×540 at 12 fps. Normal default: 1080×1350 at 24 fps.
Outputs: ${OUTPUT}
Tutorial: TUTORIAL.md
`;
const args=process.argv.slice(2);const command=args.shift()??'help';
const positional=[],options={};
try{
 const allowed={gui:['port'],select:['seed','out'],validate:[],render:['voice','preview'],resume:[],status:[],draft:['out','template','seed'],assets:[],doctor:[],help:[]};
 if(command==='--help'||command==='-h'||command==='help'){console.log(help);process.exit(0);}
 if(!Object.hasOwn(allowed,command))throw Error(`Unknown command '${command}'. Choose ${Object.keys(allowed).join(', ')}`);
 for(let i=0;i<args.length;i++){const a=args[i];if(a==='--help'){console.log(help);process.exit(0);}if(a.startsWith('-')){const key=a.replace(/^--/,'');if(!allowed[command].includes(key))throw Error(`Unknown option ${a}. Options for ${command}: ${allowed[command].map(k=>'--'+k).join(', ')||'none'}`);if(key==='preview')options[key]=true;else{if(!args[i+1]||args[i+1].startsWith('--'))throw Error(`${a} needs a value`);options[key]=args[++i];}}else positional.push(a);}
 if(positional.length>1)throw Error('Too many positional arguments');
 const read=async()=>{if(!positional[0])throw Error('Supply an input JSON filename');return JSON.parse(await fs.readFile(path.resolve(positional[0]),'utf8'));};
 const save=async value=>{const text=JSON.stringify(value,null,2)+'\n';if(options.out){await fs.writeFile(path.resolve(options.out),text,{flag:'wx'});console.log(`Saved ${options.out}`);}else console.log(text);};
 if(command==='gui'){const port=options.port===undefined?8777:Number(options.port);if(!Number.isInteger(port)||port<0||port>65535)throw Error('--port must be 0–65535');const server=await startServer({port});console.log(`Comic Theatre: ${server.url}\nKeep this terminal open. Ctrl+C stops the GUI; interrupted jobs can be resumed.`);}
 else if(command==='assets'){console.log(`Verified ${(await verifyCatalog(await loadCatalog())).length} bundled assets.`);}
 else if(command==='select'){if(!positional[0])throw Error('Supply a template: book-duet, fireside-reader, page-tour');await save(selectScript(positional[0],options.seed===undefined?undefined:Number(options.seed),await loadCatalog()));}
 else if(command==='validate'){await verifyCatalog(await loadCatalog());const script=resolveScript(await read(),await loadCatalog());console.log(`Valid: ${script.title}; ${script.comics.join(', ')}; ${script.lines.length} beats; seed ${script.seed}.`);}
 else if(command==='draft'){if(options.template&&positional[0])throw Error('Choose either a saved script or --template');const catalog=await loadCatalog();const raw=options.template?selectScript(options.template,options.seed===undefined?undefined:Number(options.seed),catalog):await read();await save(await draftScript(raw,catalog));}
 else if(command==='render'){const raw=await read();if(options.preview)raw.output={width:432,height:540,fps:12};if(options.voice&&!['kokoro','recorded'].includes(options.voice))throw Error('--voice: choose kokoro or recorded');const job=await createJob(raw,{voice:options.voice??'kokoro',inputRoot:path.dirname(path.resolve(positional[0]))});console.log(`Run ${job.id}`);const finished=await processJob(job.id,{progress:console.log});console.log(finished.verification.path);}
 else if(command==='resume'){if(!positional[0])throw Error('Supply RUN_ID from status');const j=await processJob(positional[0],{progress:console.log});console.log(j.verification?.path??j.status);}
 else if(command==='status'){console.log(JSON.stringify(positional[0]?await readJob(positional[0]):await listJobs(),null,2));}
 else if(command==='doctor'){console.log(`Node ${process.version}; project ${ROOT}`);await run(process.env.FFMPEG??'ffmpeg',['-version']);await run(process.env.FFPROBE??'ffprobe',['-version']);await verifyCatalog(await loadCatalog());const {chromium}=await import('playwright');const b=await chromium.launch({headless:true,...(process.env.THEATRE_BROWSER?{executablePath:process.env.THEATRE_BROWSER}:{})});await b.close();console.log('FFmpeg, ffprobe, browser and bundled assets OK. Local voices: python tools/setup_voice.py (one-time), or --voice recorded.');}
}catch(e){console.error(`Error: ${e.message}\nUse --help for options. Completed run stages remain in output/.`);process.exitCode=1;}

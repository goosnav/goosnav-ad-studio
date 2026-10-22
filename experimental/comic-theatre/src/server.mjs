import http from 'node:http';
import fs from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import path from 'node:path';
import {randomBytes} from 'node:crypto';
import {ROOT,loadCatalog,safePath,freezeAssets} from './library.mjs';
import {resolveScript,selectScript} from './contracts.mjs';
import {draftScript} from './writer.mjs';
import {OUTPUT,listJobs,readJob,createJob,processJob} from './jobs.mjs';
const types={'.html':'text/html; charset=utf-8','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.json':'application/json','.jpg':'image/jpeg','.png':'image/png','.glb':'model/gltf-binary','.mp4':'video/mp4','.wav':'audio/wav'};
async function body(req){let size=0,parts=[];for await(const p of req){size+=p.length;if(size>256000)throw Error('Request too large');parts.push(p);}return JSON.parse(Buffer.concat(parts).toString());}
function json(res,status,value){res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(value));}
async function file(req,res,p){const stat=await fs.stat(p);if(!stat.isFile())return json(res,404,{error:'Not found'});const headers={'Content-Type':types[path.extname(p)]??'application/octet-stream','Accept-Ranges':'bytes','X-Content-Type-Options':'nosniff'};let start=0,end=stat.size-1,status=200;
 if(req.headers.range){const m=/^bytes=(\d+)-(\d*)$/.exec(req.headers.range);if(!m)return json(res,416,{error:'Invalid range'});start=Number(m[1]);end=m[2]?Math.min(Number(m[2]),end):end;if(start>end||start>=stat.size)return json(res,416,{error:'Invalid range'});status=206;headers['Content-Range']=`bytes ${start}-${end}/${stat.size}`;}
 res.writeHead(status,{...headers,'Content-Length':end-start+1});createReadStream(p,{start,end}).on('error',()=>res.destroy()).pipe(res);
}
function renderHTML(id){return `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#000}canvas{display:block}</style><canvas></canvas><script type="importmap">{"imports":{"three":"/node_modules/three/build/three.module.js","three/addons/":"/node_modules/three/examples/jsm/"}}</script><script type="module">import{createPlayer}from'/src/player.mjs';try{const[timeline,catalog]=await Promise.all([fetch('/api/jobs/${id}/timeline').then(r=>r.json()),fetch('/api/catalog').then(r=>r.json())]);window.player=await createPlayer(document.querySelector('canvas'),{timeline,catalog,assetBase:''});window.player.renderAt(0);window.renderReady=true;}catch(e){window.renderError=e.stack||String(e);}</script>`;}
export async function startServer({port=0,outputRoot=OUTPUT,renderCatalog}={}){
 const catalog=renderCatalog??await loadCatalog(),token=randomBytes(32).toString('hex');let origin;
 const assets=await freezeAssets(catalog);
 const server=http.createServer(async(req,res)=>{
  try{
   if(req.headers.host!==new URL(origin).host){json(res,403,{error:'Invalid Host'});return;}
   const url=new URL(req.url,origin),p=decodeURIComponent(url.pathname);
   if(req.method==='POST'){
    if((req.headers.origin&&req.headers.origin!==origin)||req.headers['x-theatre-token']!==token){json(res,403,{error:'Invalid local session. Reload the GUI.'});return;}
    const data=await body(req);
    if(p==='/api/select')return json(res,200,{script:selectScript(data.template,data.seed,catalog)});
    if(p==='/api/validate')return json(res,200,{script:resolveScript(data.script,catalog)});
    if(p==='/api/draft')return json(res,200,{script:await draftScript(data.script,catalog)});
    if(p==='/api/render'){const job=await createJob(data.script,{outputRoot,voice:data.voice??'kokoro'});json(res,202,{id:job.id,status:job.status});processJob(job.id,{outputRoot}).catch(e=>console.error(`Run ${job.id}: ${e.message}`));return;}
    return json(res,404,{error:'Unknown action'});
   }
   if(req.method!=='GET')return json(res,405,{error:'GET or POST required'});
   if(p==='/api/session')return json(res,200,{token});
   if(p==='/api/catalog')return json(res,200,catalog);
   if(p==='/api/jobs')return json(res,200,{jobs:await listJobs(outputRoot)});
   const match=/^\/api\/jobs\/([A-Za-z0-9_-]+)(\/timeline)?$/.exec(p);
   if(match){if(match[2])return file(req,res,await safePath(outputRoot,match[1]+'/timeline.json'));return json(res,200,await readJob(match[1],outputRoot));}
   const render=/^\/render\/([A-Za-z0-9_-]+)$/.exec(p);if(render){await readJob(render[1],outputRoot);res.writeHead(200,{'Content-Type':'text/html'});res.end(renderHTML(render[1]));return;}
   if(p.startsWith('/output/')){const m=/^\/output\/([A-Za-z0-9_-]+)\/([A-Za-z0-9_.-]+\.mp4)$/.exec(p);if(!m)return json(res,404,{error:'Not found'});const job=await readJob(m[1],outputRoot);if(job.status!=='complete'||job.video!==p)return json(res,404,{error:'Video not verified'});return file(req,res,await safePath(outputRoot,m[1]+'/'+m[2]));}
   if(assets.has(p)){res.writeHead(200,{'Content-Type':types[path.extname(p)]??'application/octet-stream','Content-Length':assets.get(p).length,'X-Content-Type-Options':'nosniff'});res.end(assets.get(p));return;}
   const web={'/':'web/index.html','/app.mjs':'web/app.mjs','/style.css':'web/style.css'};
   if(web[p])return file(req,res,await safePath(ROOT,web[p]));
   if(['/src/player.mjs','/src/actor.mjs','/src/book.mjs','/src/book-pages.mjs'].includes(p)||p.startsWith('/node_modules/three/')&&p.endsWith('.js'))return file(req,res,await safePath(ROOT,p.slice(1)));
   json(res,404,{error:'Not found'});
  }catch(e){if(!res.headersSent)json(res,e.code==='ENOENT'?404:400,{error:e.message});else res.destroy();}
 });
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',resolve);});origin=`http://127.0.0.1:${server.address().port}`;
 return {url:origin,close:()=>new Promise(resolve=>{server.close(resolve);server.closeIdleConnections();})};
}

import {spawn} from 'node:child_process';
export async function withDeadline(operation,ms,label,onTimeout=()=>{}){
 let timer;
 try{return await Promise.race([operation,new Promise((_,reject)=>{
  timer=setTimeout(()=>{reject(Error(`${label} timed out after ${ms/1000}s; verified checkpoints are preserved`));Promise.resolve().then(onTimeout).catch(()=>{});},ms);
 })]);}finally{clearTimeout(timer);}
}
export function run(command,args,{timeout=120000,env=process.env,cwd,input,maxBytes=32*1024*1024}={}){
 return new Promise((resolve,reject)=>{
  const child=spawn(command,args,{cwd,env,windowsHide:true,stdio:['pipe','pipe','pipe']});let chunks=[],errors=[],size=0,settled=false;
  const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(error):resolve(value);};
  const timer=setTimeout(()=>{child.kill('SIGKILL');finish(Error(`${command} stalled/timed out after ${timeout/1000}s; completed work is preserved`));},timeout);
  child.stdout.on('data',b=>{size+=b.length;if(size>maxBytes){child.kill('SIGKILL');finish(Error(`${command}: output exceeds safety bound`));}else chunks.push(b);});
  child.stderr.on('data',b=>{errors.push(b);if(errors.length>32)errors.shift();});
  child.on('error',e=>finish(Error(`${command}: ${e.message}. Check installation and PATH.`)));
  child.on('close',code=>finish(code===0?null:Error(`${command} exited ${code}: ${Buffer.concat(errors).toString().slice(-4000)}`),Buffer.concat(chunks)));
  child.stdin.on('error',()=>{});child.stdin.end(input);
 });
}

import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
export const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const digest=b=>createHash('sha256').update(b).digest('hex');
export async function safePath(root,relative){
 if(typeof relative!=='string'||!relative||path.isAbsolute(relative)||/^[a-z]:|\\|\0/i.test(relative))throw Error('Asset path must be relative');
 if(relative.split('/').some(p=>['archive','archives','archived'].includes(p.toLowerCase())))throw Error('Archived sources are not allowed');
 const base=await fs.realpath(root),candidate=path.resolve(base,relative);
 if(candidate===base||!candidate.startsWith(base+path.sep))throw Error('Path outside project');
 const real=await fs.realpath(candidate);if(!real.startsWith(base+path.sep))throw Error('Symlink outside project');
 if(real.split(path.sep).some(p=>['archive','archives','archived'].includes(p.toLowerCase())))throw Error('Archived sources are not allowed');return real;
}
export async function loadCatalog(root=ROOT){return JSON.parse(await fs.readFile(path.join(root,'assets/catalog.json'),'utf8'));}
export async function freezeAssets(catalog,root=ROOT){
 await verifyCatalog(catalog,root);const snapshot=new Map();
 for(const entry of [...Object.values(catalog.assets),...catalog.comics]){
  const bytes=await fs.readFile(await safePath(root,entry.path));
  if(digest(bytes)!==entry.sha256)throw Error(`${entry.path}: source hash changed while preparing render`);
  snapshot.set('/'+entry.path,bytes);
 }
 return snapshot;
}
export async function verifyCatalog(catalog,root=ROOT){
 if(catalog.version!==1||!catalog.edition?.pdfSha256||!Array.isArray(catalog.comics))throw Error('Invalid source catalog');
 if(catalog.variants!==undefined){
  const seen=new Set();
  if(!Array.isArray(catalog.variants)||!catalog.variants.length)throw Error('Variant catalog must contain at least one variant');
  for(const v of catalog.variants){
   if(!v||typeof v.id!=='string'||!v.id||seen.has(v.id)||!catalog.assets?.[v.asset]?.path?.endsWith('.glb'))throw Error('Invalid variant ID or missing GLB asset in catalog');
   seen.add(v.id);
  }
 }
 const entries=[...Object.values(catalog.assets),...catalog.comics],results=[];let book;
 for(const entry of entries){
  const p=await safePath(root,entry.path),b=await fs.readFile(p);
  if(b.subarray(0,80).toString().includes('version https://git-lfs.github.com'))throw Error(`${entry.path}: Git LFS pointer. Run git lfs pull.`);
  if(digest(b)!==entry.sha256)throw Error(`${entry.path}: source hash mismatch; restore the verified asset or review a new catalog version.`);
  if(p.endsWith('.glb')){if(b.readUInt32LE(0)!==0x46546c67||b.readUInt32LE(4)!==2||b.readUInt32LE(8)!==b.length)throw Error('Invalid GLB');const j=JSON.parse(b.subarray(20,20+b.readUInt32LE(12)).toString());for(const r of [...(j.buffers??[]),...(j.images??[])])if(r.uri)throw Error(`${entry.path}: external GLB dependencies are not allowed; pack the GLB`);if(entry===catalog.assets.book)book={j,b,offset:28+b.readUInt32LE(12)};}
  results.push(entry.path);
 }
 if(!book)throw Error('Missing verified book GLB');
 for(const comic of catalog.comics){
  const material=book.j.materials?.find(m=>m.name===`Comic page ${comic.pdfPage-2}`);
  const texture=book.j.textures?.[material?.pbrMetallicRoughness?.baseColorTexture?.index];
  const image=book.j.images?.[texture?.source],view=book.j.bufferViews?.[image?.bufferView];
  if(!view||digest(book.b.subarray(book.offset+(view.byteOffset??0),book.offset+(view.byteOffset??0)+view.byteLength))!==comic.sha256)throw Error(`${comic.id}: embedded book page does not match the catalog image and PDF page. Review the source mapping.`);
 }
 return results;
}

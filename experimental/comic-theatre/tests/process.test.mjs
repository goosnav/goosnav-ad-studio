import test from 'node:test';
import assert from 'node:assert/strict';
import {withDeadline} from '../src/process.mjs';
test('a stalled browser operation reaches cleanup instead of owning the queue forever',async()=>{
 let cleaned=0;
 await assert.rejects(withDeadline(new Promise(()=>{}),20,'Frame evaluation',()=>{cleaned++;}),/Frame evaluation.*timed out/i);
 assert.equal(cleaned,1);
 assert.equal(await withDeadline(Promise.resolve(42),100,'Healthy frame'),42);
});

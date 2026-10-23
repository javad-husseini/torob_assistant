// Exercise the actual TypeScript client without a microphone or provider.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require = createRequire(new URL('../frontend/package.json',import.meta.url));
const {transformWithOxc} = await import(pathToFileURL(require.resolve('vite')).href);
const source = fs.readFileSync(new URL('../frontend/src/lib/call-client.ts', import.meta.url), 'utf8');
const {code} = await transformWithOxc(source, 'call-client.ts');
const {CallClient} = await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
globalThis.WebSocket = {OPEN:1};
globalThis.AudioWorkletNode = class {
  port = {};
  connect() {}
  disconnect() {}
};
const sent = [];
const track = {enabled:true,stop(){}};
const client = new CallClient(async()=>({}), {status(){},active(){},transcript(){},result(){}});
client.mic = {getAudioTracks:()=>[track],getTracks:()=>[track]};
client.ctx = {createMediaStreamSource:()=>({connect(){}}),destination:{},close:()=>Promise.resolve()};
client.ws = {readyState:1,send:s=>sent.push(JSON.parse(s)),close(){}};
client.streaming = true;
await client.handle({type:'ready',turn_taking:'half_duplex'});
assert.equal(track.enabled,false);
const frame = {data:{pcm:new ArrayBuffer(4),rms:1}};
client.sources.add({}); // Speaker echo must not send audio or barge-in.
client.capture.port.onmessage(frame);
assert.equal(sent.length,0);
client.sources.clear();
await client.handle({type:'listening',enabled:true});
assert.equal(track.enabled,false);
await new Promise(r=>setTimeout(r,240));
assert.equal(track.enabled,true);
client.capture.port.onmessage(frame);
assert.equal(sent.filter(e=>e.type==='audio').length,1);
await client.handle({type:'listening',enabled:false});
assert.equal(track.enabled,false);
client.capture.port.onmessage(frame);
assert.equal(sent.filter(e=>e.type==='audio').length,1);
client.cleanup();
console.log('Audio turn checks passed: speaker echo blocked, capture waits for playback, turn transitions and cleanup. No network.');

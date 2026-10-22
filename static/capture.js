// Audio is streamed as PCM16 LE, mono 24 kHz; never recorded or persisted.
class PcmCapture extends AudioWorkletProcessor {
  constructor(){super();this.pending=[];this.phase=0;this.sum=0;this.count=0;}
  process(inputs){const input=inputs[0]?.[0];if(!input)return true;let energy=0;for(const sample of input){energy+=sample*sample;this.sum+=sample;this.count++;this.phase+=24000;if(this.phase>=sampleRate){this.phase-=sampleRate;this.pending.push(Math.max(-1,Math.min(1,this.sum/this.count)));this.sum=0;this.count=0;}}if(this.pending.length>=2400){const chunk=this.pending.splice(0,2400);const pcm=new ArrayBuffer(chunk.length*2);const view=new DataView(pcm);for(let i=0;i<chunk.length;i++)view.setInt16(i*2,Math.round(chunk[i]*32767),true);this.port.postMessage({pcm,rms:Math.sqrt(energy/input.length)},[pcm]);}return true;}
}
registerProcessor('pcm-capture',PcmCapture);

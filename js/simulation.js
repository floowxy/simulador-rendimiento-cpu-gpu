// Motor de eventos discreto. PRNG y reglas replican python/modelos.py.
export const RES = {"720p":[1280,720],"1080p":[1920,1080],"1440p":[2560,1440],"4K":[3840,2160]};
export const FACTOR = {"Baja":.7,"Media":1,"Alta":1.4,"Ultra":1.8};
function uniform(seed,stream){let x=(Number(seed)+Math.imul(0x9e3779b9,stream+1))>>>0;x=Math.imul(x^(x>>>16),0x85ebca6b)>>>0;x=Math.imul(x^(x>>>13),0xc2b2ae35)>>>0;x^=x>>>16;return ((x>>>0)+.5)/4294967296;}
function normal(seed,stream){const u1=Math.max(uniform(seed,stream*2),1e-15),u2=uniform(seed,stream*2+1);return Math.sqrt(-2*Math.log(u1))*Math.cos(2*Math.PI*u2);}
function sample(mean,cv,seed,stream){if(cv===0)return mean;const s=Math.sqrt(Math.log1p(cv*cv));return Math.exp(Math.log(mean)-s*s/2+s*normal(seed,stream));}
export function simulate(c){
 if(!(c.cpu_ms>=.1&&c.cpu_ms<=100&&c.gpu_ms>=.1&&c.gpu_ms<=200&&c.duracion_s>=.1&&c.duracion_s<=600)||!RES[c.resolucion]||!FACTOR[c.complejidad]||!Number.isInteger(c.cola)||c.cola<0||c.cola>100||c.limite_fps<0||c.limite_fps>1000||c.cv_cpu<0||c.cv_cpu>1||c.cv_gpu<0||c.cv_gpu>1||!Number.isInteger(c.semilla)||c.semilla<0||c.semilla>4294967295)throw Error('Revisa los rangos: CPU 0.1–100 ms, GPU 0.1–200 ms, duración 0.1–600 s, FPS 0–1000, cola entera 0–100, CV 0–1 y semilla entera de 32 bits.');
 const [w,h]=RES[c.resolucion],gm=c.gpu_ms*w*h/(1920*1080)*FACTOR[c.complejidad],frames=[],events=[],queue=[],completed=[];
 let now=0,cpuJob=null,gpuJob=null,cpuDone=Infinity,gpuDone=Infinity,blocked=null,nextAllowed=0,nextId=0,cpuBusy=0,gpuBusy=0,qArea=0,qMax=0;
 const end=c.duracion_s*1000;
 const ev=(t,type,id=null)=>events.push({time_ms:t,type,frame_id:id});
 function startGpu(t){if(gpuJob===null&&queue.length){gpuJob=queue.shift();const f=frames[gpuJob];f.gpu_start_ms=t;f.wait_ms=t-f.cpu_end_ms;gpuDone=t+f.gpu_ms;ev(t,'gpu_start',gpuJob);ev(gpuDone,'gpu_end',gpuJob);}}
 function startCpu(t){if(cpuJob!==null||blocked!==null||t>=end)return;t=Math.max(t,nextAllowed);if(t>=end)return;const id=nextId++,cm=sample(c.cpu_ms,c.cv_cpu,c.semilla,id*2),g=sample(gm,c.cv_gpu,c.semilla,id*2+1);frames.push({id,arrival_ms:t,cpu_start_ms:t,cpu_end_ms:null,gpu_start_ms:null,gpu_end_ms:null,cpu_ms:cm,gpu_ms:g,wait_ms:0});cpuJob=id;cpuDone=t+cm;nextAllowed=t+(c.limite_fps?1000/c.limite_fps:0);ev(t,'generated',id);ev(t,'cpu_start',id);ev(cpuDone,'cpu_end',id);}
 ev(0,'system_start');startCpu(0);
 for(let guard=0;guard<10000000;guard++){
  const candidates=[cpuDone,gpuDone];if(cpuJob===null&&blocked===null&&now<end)candidates.push(Math.max(now,nextAllowed));const t=Math.min(...candidates);if(!Number.isFinite(t))break;
  qArea+=queue.length*(t-now);now=t;
  if(gpuDone===t){const id=gpuJob,f=frames[id];f.gpu_end_ms=t;completed.push(id);ev(t,'completed',id);gpuBusy+=Math.max(0,Math.min(t,end)-f.gpu_start_ms);gpuJob=null;gpuDone=Infinity;}
  if(cpuDone===t){const id=cpuJob,f=frames[id];f.cpu_end_ms=t;cpuBusy+=Math.max(0,Math.min(t,end)-f.cpu_start_ms);ev(t,'cpu_processed',id);cpuJob=null;cpuDone=Infinity;if(queue.length<c.cola){queue.push(id);ev(t,'enqueued',id);}else{blocked=id;ev(t,'cpu_blocked',id);}}
  if(blocked!==null&&queue.length<c.cola){const id=blocked;blocked=null;queue.push(id);ev(t,'enqueued',id);}
  qMax=Math.max(qMax,queue.length);startGpu(t);
  if(cpuJob===null&&blocked===null)startCpu(t);
  if(c.cola===0&&gpuJob===null&&blocked!==null){const id=blocked;blocked=null;const f=frames[id];f.gpu_start_ms=t;f.wait_ms=0;gpuJob=id;gpuDone=t+f.gpu_ms;ev(t,'gpu_start',id);ev(gpuDone,'gpu_end',id);}
  if(t>=end&&cpuJob===null&&gpuJob===null&&!queue.length&&blocked===null)break;
 }
 const drain=Math.max(0,now-end),ct=completed.map(i=>frames[i].gpu_end_ms),ints=ct.slice(1).map((x,i)=>x-ct[i]),resp=completed.map(i=>frames[i].gpu_end_ms-frames[i].arrival_ms);
 const pct=(xs,p)=>{if(!xs.length)return 0;const a=[...xs].sort((x,y)=>x-y),pos=(a.length-1)*p,lo=Math.floor(pos),hi=Math.min(lo+1,a.length-1);return a[lo]+(a[hi]-a[lo])*(pos-lo);};
 const fps=ct.filter(t=>t<=end).length/c.duracion_s,cu=Math.min(100,cpuBusy/end*100),gu=Math.min(100,gpuBusy/end*100);
 let bottleneck;if(c.limite_fps&&fps>=.97*c.limite_fps&&cu<90&&gu<90)bottleneck='Limitado externamente por el límite de FPS';else if(cu>gu*1.15)bottleneck='Limitado principalmente por CPU';else if(gu>cu*1.15)bottleneck='Limitado principalmente por GPU';else bottleneck='Aproximadamente equilibrado';
 events.sort((a,b)=>a.time_ms-b.time_ms||a.type.localeCompare(b.type));
 return {config:c,frames,events,metrics:{fps,completed:completed.length,generated:frames.length,drain_ms:drain,cpu_util_pct:cu,gpu_util_pct:gu,response_mean_ms:resp.length?resp.reduce((a,b)=>a+b,0)/resp.length:0,frame_interval_mean_ms:ints.length?ints.reduce((a,b)=>a+b,0)/ints.length:0,frame_interval_median_ms:pct(ints,.5),frame_interval_p95_ms:pct(ints,.95),wait_mean_ms:completed.length?completed.reduce((a,i)=>a+frames[i].wait_ms,0)/completed.length:0,queue_mean:qArea/end,queue_max:qMax,bottleneck,pending_cpu:cpuJob===null?0:1,pending_queue:queue.length,pending_gpu:gpuJob===null?0:1,generation_window_s:end/1000,drain_s:drain/1000}};
}

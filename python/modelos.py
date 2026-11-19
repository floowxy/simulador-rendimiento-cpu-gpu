"""Modelo de fotogramas en pipeline con cola FIFO acotada.

Los tiempos aleatorios se generan por fotograma con hash entero + Box–Muller;
la fórmula se replica en js/simulation.js para mantener equivalencia.
"""
from dataclasses import dataclass
import math

RESOLUCIONES = {"720p": (1280, 720), "1080p": (1920, 1080), "1440p": (2560, 1440), "4K": (3840, 2160)}
COMPLEJIDAD = {"Baja": .7, "Media": 1., "Alta": 1.4, "Ultra": 1.8}

@dataclass
class Configuracion:
    cpu_ms: float = 5.0
    gpu_ms: float = 8.0
    resolucion: str = "1080p"
    complejidad: str = "Media"
    limite_fps: float = 0.0
    cola: int = 2
    duracion_s: float = 10.0
    semilla: int = 42
    cv_cpu: float = .15
    cv_gpu: float = .15

def _uniform(seed, stream):
    x = (int(seed) + 0x9E3779B9 * (stream + 1)) & 0xffffffff
    x = ((x ^ (x >> 16)) * 0x85EBCA6B) & 0xffffffff
    x = ((x ^ (x >> 13)) * 0xC2B2AE35) & 0xffffffff
    x ^= x >> 16
    return (x + .5) / 4294967296

def _normal(seed, stream):
    u1 = max(_uniform(seed, stream * 2), 1e-15)
    u2 = _uniform(seed, stream * 2 + 1)
    return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)

def _sample(mean, cv, seed, stream):
    if cv == 0: return mean
    sigma = math.sqrt(math.log1p(cv * cv))
    mu = math.log(mean) - sigma * sigma / 2
    return math.exp(mu + sigma * _normal(seed, stream))

def validar(c):
    if not (.1 <= c.cpu_ms <= 100 and .1 <= c.gpu_ms <= 200 and .1 <= c.duracion_s <= 600): raise ValueError("CPU debe estar entre 0.1–100 ms, GPU entre 0.1–200 ms y duración entre 0.1–600 s.")
    if c.resolucion not in RESOLUCIONES or c.complejidad not in COMPLEJIDAD: raise ValueError("Resolución o complejidad no válida.")
    if c.limite_fps < 0 or c.limite_fps > 1000 or c.cola < 0 or c.cola > 100 or int(c.cola) != c.cola: raise ValueError("Límite FPS debe ser 0–1000 y cola un entero 0–100.")
    if not (0 <= c.cv_cpu <= 1 and 0 <= c.cv_gpu <= 1): raise ValueError("El CV debe estar entre 0 y 1.")
    if int(c.semilla) != c.semilla or not (0 <= c.semilla <= 4294967295): raise ValueError("La semilla debe ser un entero sin signo de 32 bits.")

def simular(c: Configuracion):
    """Avanza el reloj por eventos; se detiene la admisión en duración y drena el pipeline."""
    validar(c)
    width, height = RESOLUCIONES[c.resolucion]
    gpu_mean = c.gpu_ms * (width * height / (1920 * 1080)) * COMPLEJIDAD[c.complejidad]
    frames, events, queue, completed = [], [], [], []
    now = cpu_start = 0.0
    cpu_job = gpu_job = None
    cpu_done = gpu_done = math.inf
    blocked_job = None
    next_allowed = 0.0
    generation_end = c.duracion_s * 1000
    next_id = 0
    cpu_busy = gpu_busy = q_area = 0.0
    q_max = 0

    def ev(t, kind, fid=None, **extra):
        events.append({"time_ms": t, "type": kind, "frame_id": fid, **extra})
    def start_gpu(t):
        nonlocal gpu_job, gpu_done
        if gpu_job is None and queue:
            gpu_job = queue.pop(0); f = frames[gpu_job]
            f["gpu_start_ms"] = t; f["wait_ms"] = t - f["cpu_end_ms"]
            gpu_done = t + f["gpu_ms"]; ev(t, "gpu_start", gpu_job); ev(gpu_done, "gpu_end", gpu_job)
    def start_cpu(t):
        nonlocal cpu_job, cpu_done, next_id, next_allowed
        if cpu_job is not None or blocked_job is not None or t >= generation_end: return
        t = max(t, next_allowed)
        if t >= generation_end: return
        fid = next_id; next_id += 1
        cpu_ms = _sample(c.cpu_ms, c.cv_cpu, c.semilla, fid * 2)
        gpu_ms = _sample(gpu_mean, c.cv_gpu, c.semilla, fid * 2 + 1)
        frames.append({"id": fid, "arrival_ms": t, "cpu_start_ms": t, "cpu_end_ms": None, "gpu_start_ms": None, "gpu_end_ms": None, "cpu_ms": cpu_ms, "gpu_ms": gpu_ms, "wait_ms": 0.0})
        cpu_job = fid; cpu_done = t + cpu_ms
        next_allowed = t + (1000 / c.limite_fps if c.limite_fps else 0)
        ev(t, "generated", fid); ev(t, "cpu_start", fid); ev(cpu_done, "cpu_end", fid)

    ev(0, "system_start")
    start_cpu(0)
    last = 0.0
    while True:
        candidates = [cpu_done, gpu_done]
        if cpu_job is None and blocked_job is None and now < generation_end:
            candidates.append(max(now, next_allowed))
        t = min(candidates)
        if math.isinf(t): break
        q_area += len(queue) * (t - now); now = t
        # Empates: GPU libera sitio primero, luego CPU transfiere; ambos finales son simultáneos.
        if gpu_done == t:
            fid = gpu_job; f = frames[fid]; f["gpu_end_ms"] = t; completed.append(fid); ev(t, "completed", fid)
            gpu_busy += max(0.0, min(t, generation_end) - f["gpu_start_ms"]); gpu_job = None; gpu_done = math.inf
        if cpu_done == t:
            fid = cpu_job; frames[fid]["cpu_end_ms"] = t; cpu_busy += max(0.0, min(t, generation_end) - frames[fid]["cpu_start_ms"])
            ev(t, "cpu_processed", fid); cpu_job = None; cpu_done = math.inf
            if len(queue) < c.cola:
                queue.append(fid); ev(t, "enqueued", fid)
            else:
                blocked_job = fid; ev(t, "cpu_blocked", fid)
        if blocked_job is not None and len(queue) < c.cola:
            fid = blocked_job; blocked_job = None; queue.append(fid); ev(t, "enqueued", fid)
        q_max = max(q_max, len(queue)); start_gpu(t)
        if cpu_job is None and blocked_job is None: start_cpu(t)
        # cola=0 implica transferencia directa a GPU al quedar libre
        if c.cola == 0 and gpu_job is None and blocked_job is not None:
            fid = blocked_job; blocked_job = None; frames[fid]["gpu_start_ms"] = t; frames[fid]["wait_ms"] = 0
            gpu_job = fid; gpu_done = t + frames[fid]["gpu_ms"]; ev(t, "gpu_start", fid); ev(gpu_done, "gpu_end", fid)
        if t >= generation_end and cpu_job is None and gpu_job is None and not queue and blocked_job is None: break
        if t == last and cpu_job is None and gpu_job is None and blocked_job is None and not queue:
            if t >= generation_end: break
        last = t
    drain = max(0.0, now - generation_end)
    generated = len(frames)
    completion_times = [frames[i]["gpu_end_ms"] for i in completed]
    observed = max(0.0, generation_end)
    intervals = [b-a for a,b in zip(completion_times, completion_times[1:])]
    def percentile(xs, p):
        if not xs: return 0.0
        s=sorted(xs); pos=(len(s)-1)*p; lo=int(pos); hi=min(lo+1,len(s)-1)
        return s[lo]+(s[hi]-s[lo])*(pos-lo)
    response = [frames[i]["gpu_end_ms"]-frames[i]["arrival_ms"] for i in completed]
    fps = len([x for x in completion_times if x <= generation_end]) / c.duracion_s
    utilization_cpu = min(100.0, cpu_busy / generation_end * 100)
    utilization_gpu = min(100.0, gpu_busy / generation_end * 100)
    # Distingue límite externo observando holgura; después usa utilización y demanda servida.
    cap_rate = c.limite_fps or math.inf
    if c.limite_fps and fps >= .97*c.limite_fps and utilization_cpu < 90 and utilization_gpu < 90: bottleneck="Limitado externamente por el límite de FPS"
    elif utilization_cpu > utilization_gpu * 1.15: bottleneck="Limitado principalmente por CPU"
    elif utilization_gpu > utilization_cpu * 1.15: bottleneck="Limitado principalmente por GPU"
    else: bottleneck="Aproximadamente equilibrado"
    return {"config": c.__dict__, "frames": frames, "events": sorted(events, key=lambda x:(x["time_ms"], x["type"])), "metrics": {
        "fps": fps, "completed": len(completed), "generated": generated, "drain_ms": drain,
        "cpu_util_pct": utilization_cpu, "gpu_util_pct": utilization_gpu,
        "response_mean_ms": sum(response)/len(response) if response else 0,
        "frame_interval_mean_ms": sum(intervals)/len(intervals) if intervals else 0,
        "frame_interval_median_ms": percentile(intervals,.5), "frame_interval_p95_ms": percentile(intervals,.95),
        "wait_mean_ms": sum(frames[i]["wait_ms"] for i in completed)/len(completed) if completed else 0,
        "queue_mean": q_area/generation_end, "queue_max": q_max, "bottleneck": bottleneck,
        "pending_cpu": 1 if cpu_job is not None else 0, "pending_queue": len(queue), "pending_gpu": 1 if gpu_job is not None else 0,
        "generation_window_s": observed/1000, "drain_s": drain/1000 }}

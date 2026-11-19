import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from python.modelos import Configuracion, simular

class SimulationTests(unittest.TestCase):
    def test_reproducible_and_valid(self):
        c=Configuracion(cpu_ms=5,gpu_ms=10,duracion_s=2,cv_cpu=0,cv_gpu=0)
        a,b=simular(c),simular(c)
        self.assertEqual(a,b)
        self.assertGreater(a['metrics']['fps'],95)
        self.assertLess(a['metrics']['fps'],105)
        for f in a['frames']:
            self.assertGreaterEqual(f['wait_ms'],0)
            self.assertGreaterEqual(f['gpu_start_ms'],f['cpu_end_ms'])
        for left,right in zip(a['frames'],a['frames'][1:]):
            self.assertGreaterEqual(right['cpu_start_ms'],left['cpu_end_ms'])
            self.assertGreaterEqual(right['gpu_start_ms'],left['gpu_end_ms'])
    def test_bounded_fifo_queue(self):
        r=simular(Configuracion(cpu_ms=1,gpu_ms=20,duracion_s=1,cola=1,cv_cpu=0,cv_gpu=0))
        self.assertLessEqual(r['metrics']['queue_max'],1)
        self.assertTrue(any(e['type']=='cpu_blocked' for e in r['events']))
        self.assertEqual(r['metrics']['generated'],r['metrics']['completed']+r['metrics']['pending_cpu']+r['metrics']['pending_queue']+r['metrics']['pending_gpu'])
    def test_zero_queue(self):
        r=simular(Configuracion(cpu_ms=5,gpu_ms=10,duracion_s=.1,cola=0,cv_cpu=0,cv_gpu=0))
        self.assertEqual(r['metrics']['queue_max'],0)
        self.assertGreater(r['metrics']['completed'],0)
    def test_resource_exclusion_frame_ids_and_queue_history(self):
        r=simular(Configuracion(cpu_ms=3,gpu_ms=7,duracion_s=.5,cola=2,cv_cpu=.2,cv_gpu=.2))
        cpu=sorted((f['cpu_start_ms'],f['cpu_end_ms']) for f in r['frames'])
        gpu=sorted((f['gpu_start_ms'],f['gpu_end_ms']) for f in r['frames'])
        self.assertTrue(all(b[0] >= a[1] for a,b in zip(cpu,cpu[1:])))
        self.assertTrue(all(b[0] >= a[1] for a,b in zip(gpu,gpu[1:])))
        self.assertTrue(all(f['id']==i and f['gpu_start_ms']>=f['cpu_end_ms'] and f['wait_ms']>=0 for i,f in enumerate(r['frames'])))
        self.assertTrue(all(e['frame_id'] is None or 0<=e['frame_id']<len(r['frames']) for e in r['events']))
        waiting=0; maximum=0
        for e in r['events']:
            if e['type']=='enqueued': waiting+=1
            elif e['type']=='gpu_start' and waiting: waiting-=1
            maximum=max(maximum,waiting)
        self.assertLessEqual(maximum,2)
    def test_validation(self):
        with self.assertRaises(ValueError): simular(Configuracion(cpu_ms=0))

if __name__=='__main__': unittest.main()

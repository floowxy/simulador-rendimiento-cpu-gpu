"""Prueba de paridad del contrato de eventos y métricas Python/JavaScript."""
import json, shutil, subprocess, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from python.modelos import Configuracion,simular

@unittest.skipUnless(shutil.which('node'),'Node.js no disponible')
class CrossRuntimeTests(unittest.TestCase):
 def test_same_seed_same_samples_and_metrics(self):
  c=Configuracion(cpu_ms=4.7,gpu_ms=7.3,resolucion='1440p',complejidad='Alta',limite_fps=60,cola=3,duracion_s=1.25,semilla=123,cv_cpu=.22,cv_gpu=.31)
  script="import {simulate} from './js/simulation.js';let s='';for await(const x of process.stdin)s+=x;console.log(JSON.stringify(simulate(JSON.parse(s))))"
  js=subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(c.__dict__),text=True,capture_output=True,cwd=ROOT,check=True)
  py=simular(c); web=json.loads(js.stdout)
  self.assertEqual(len(py['frames']),len(web['frames']))
  for a,b in zip(py['frames'],web['frames']):
   for key in ('cpu_ms','gpu_ms','arrival_ms','cpu_end_ms','gpu_start_ms','gpu_end_ms','wait_ms'):
    self.assertAlmostEqual(a[key],b[key],places=8)
  for key,value in py['metrics'].items():
   if isinstance(value,(int,float)): self.assertAlmostEqual(value,web['metrics'][key],places=7)
   else: self.assertEqual(value,web['metrics'][key])
  self.assertEqual([(e['type'],e['frame_id']) for e in py['events']],[(e['type'],e['frame_id']) for e in web['events']])

if __name__=='__main__': unittest.main()

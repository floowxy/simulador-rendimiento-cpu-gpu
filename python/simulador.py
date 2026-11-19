"""CLI sencilla para ejecutar el motor y guardar un resultado JSON."""
import argparse, json
from dataclasses import asdict
from modelos import Configuracion, simular

def main():
    p=argparse.ArgumentParser(description="Simulador CPU–GPU por eventos discretos")
    p.add_argument("--salida", default="resultado.json")
    p.add_argument("--duracion", type=float, default=10)
    p.add_argument("--cpu", type=float, default=5)
    p.add_argument("--gpu", type=float, default=8)
    a=p.parse_args(); c=Configuracion(cpu_ms=a.cpu,gpu_ms=a.gpu,duracion_s=a.duracion)
    with open(a.salida,"w",encoding="utf-8") as f: json.dump(simular(c),f,ensure_ascii=False,indent=2)
    print(f"Resultado escrito en {a.salida}")
if __name__=="__main__": main()

# Simulación del procesamiento de fotogramas en videojuegos

Proyecto académico para el curso **Modelos y Simulación**, Universidad Nacional Mayor de San Marcos. Modela mediante eventos discretos un pipeline de preparación CPU, cola FIFO acotada y renderizado GPU. El resultado es una abstracción didáctica y reproducible; no predice ni mide una computadora física.

## Problema y objetivos

Un videojuego prepara trabajos en CPU y los procesa en una etapa de renderizado GPU. Si sus demandas no coinciden, una etapa limita la tasa de finalización, puede crecer la espera y se acumula trabajo. El proyecto permite modificar los parámetros del sistema y estudiar FPS, respuesta de fotogramas, utilización, cola y contrapresión. Su objetivo general es implementar un simulador CPU–GPU de eventos discretos con una interfaz web sin backend.

## Estructura

```text
index.html                 Interfaz estática en español
css/styles.css              Tema oscuro y diseño adaptable
js/simulation.js           Motor de eventos para el navegador
js/app.js                   Controles, reproducción, gráficos y exportación
python/modelos.py           Motor de referencia y modelo probabilístico
python/simulador.py         CLI que guarda un resultado JSON
python/metricas.py          Acceso al resumen de métricas
tests/                      Pruebas de invariantes y paridad Python/JS
data/escenarios.json        Escenarios sintéticos de comparación
```

El proyecto usa solamente la biblioteca estándar de Python y JavaScript del navegador. No requiere SimPy, Chart.js, APIs, servidor de aplicación ni claves. Se implementó un calendario de eventos propio y explícito en ambos lenguajes para facilitar el análisis de reglas y la equivalencia. La aplicación publicada no requiere conexión a APIs externas. Para probar los módulos ES en local, utiliza un servidor estático; la publicación en Pages ya proporciona ese origen web.

## Publicación en GitHub Pages

El repositorio está preparado para GitHub Pages desde la rama `main` y la carpeta raíz `/`. `index.html` está en la raíz; las hojas de estilo y módulos JavaScript usan rutas relativas (`css/styles.css`, `js/app.js`, `js/simulation.js`). `.nojekyll` evita que Jekyll altere los archivos estáticos. La página no llama a `localhost`, no necesita un servidor Python ni un backend cuando está alojada en Pages.

Para publicar en la cuenta `floowxy`, crea un repositorio público vacío llamado `simulador-rendimiento-cpu-gpu` en GitHub (sin README, licencia ni `.gitignore` iniciales). En una copia local del proyecto con permisos normales de escritura, ejecuta:

```bash
git init -b main
git add .
git commit -m "Publica simulador de rendimiento CPU y GPU"
git remote add origin https://github.com/floowxy/simulador-rendimiento-cpu-gpu.git
git push -u origin main
```

En el espacio de trabajo usado para preparar esta copia, `.git/` está montado como solo lectura; por eso el repositorio Git debe inicializarse en tu copia local, donde Git pueda crear `.git/`.

Luego, en el repositorio de GitHub, abre **Settings → Pages** y en **Build and deployment** elige **Deploy from a branch**, rama **main** y carpeta **/(root)**; guarda los cambios. GitHub Pages publicará el sitio al completar el despliegue. Como la publicación aún no se ha completado desde esta copia del proyecto, no se indica aquí una URL pública como si ya estuviera activa. Para el nombre de repositorio solicitado, la URL esperada será `https://floowxy.github.io/simulador-rendimiento-cpu-gpu/`, una vez creado y publicado.

## Modelo conceptual y reglas

Cada unidad CPU y GPU es un servidor de capacidad uno y orden FIFO. Un fotograma se crea cuando puede empezar su preparación CPU. Si hay límite FPS, el inicio de generación de dos fotogramas sucesivos dista al menos `1000 / límite` milisegundos; ese intervalo no garantiza alcanzar dicho FPS. No se construye una cola de entrada ilimitada.

Al finalizar CPU, el trabajo se entrega a la cola si hay espacio. Si está llena, el trabajo queda retenido en el punto de entrega y la CPU no inicia otro fotograma hasta poder transferirlo. La cola cuenta exclusivamente los fotogramas que esperan GPU; no incluye el trabajo activo en CPU, el retenido por contrapresión ni el que procesa GPU. La capacidad cero representa entrega directa: CPU espera a que GPU quede libre. La GPU toma el siguiente trabajo disponible inmediatamente.

La simulación salta directamente al siguiente instante de finalización CPU/GPU o al próximo inicio permitido por el límite FPS. En empates, GPU completa primero y libera espacio; luego se procesa la entrega CPU y se inicia GPU; los nuevos trabajos CPU se admiten después de esas transferencias. Los empates tienen probabilidad cero con tiempos aleatorios continuos, pero esta regla hace determinista el caso sin variabilidad.

La ventana de generación es `[0, duración)`. Cuando termina, no se admiten más fotogramas, y los trabajos ingresados se completan. `drain_s` informa el tiempo transcurrido tras esa ventana hasta vaciar el sistema. FPS se calcula con las finalizaciones ocurridas dentro de la ventana de generación dividido entre su duración. La utilización acumula solo el trabajo de CPU/GPU que ocurrió dentro de esa misma ventana, dividido entre su duración. Las métricas de respuesta y los intervalos entre finalizaciones consideran los trabajos completados, incluso los que terminan durante el drenaje. Por ello las métricas de latencia y FPS se refieren a ventanas observacionales distintas.

## Parámetros y fórmulas

Valores iniciales: media CPU `5 ms`; base GPU `8 ms` en 1080p; resolución `1920 × 1080`; complejidad media (`1.0`); sin límite FPS; cola de dos; duración `10 s`; semilla `42`; coeficientes de variación CPU/GPU `0.15`.

El tiempo medio efectivo de GPU es:

```text
media_GPU = GPU_base × (ancho × alto / (1920 × 1080)) × factor_complejidad
```

Factores: Baja `0.7`, Media `1.0`, Alta `1.4`, Ultra `1.8`. La escala por cantidad de píxeles supone costo proporcional a píxeles y es una hipótesis simplificada, no una predicción exacta del hardware.

CPU y GPU usan distribuciones lognormales positivas. Dada media `m` y coeficiente de variación `cv`, se define `σ² = ln(1 + cv²)`, `μ = ln(m) − σ²/2`, y el servicio es `exp(μ + σZ)`, con `Z` normal estándar. Para `cv=0`, el servicio es exactamente la media. Un hash entero determinista de 32 bits y Box–Muller crean los valores por fotograma y recurso; ambas fórmulas están implementadas en los dos motores. Igual configuración, semilla e identificadores producen los mismos tiempos.

Métricas:

- **FPS promedio:** fotogramas GPU completados durante la ventana de generación / duración en segundos.
- **Intervalo de fotogramas:** diferencia entre tiempos de finalización GPU consecutivos; se reporta promedio, mediana y percentil 95 (interpolación lineal).
- **Respuesta:** finalización GPU menos instante de inicio/generación CPU.
- **Espera GPU:** inicio GPU menos fin CPU; no incluye el servicio GPU.
- **Utilización:** tiempo de procesamiento útil dentro de la ventana de generación / duración. El trabajo CPU bloqueado esperando transferencia no cuenta como procesamiento útil.
- **Longitud de cola:** área bajo la cantidad de trabajos en cola dividida entre la duración, además del máximo observado. Un trabajo retenido por contrapresión no se cuenta como elemento de cola.

La clasificación del cuello de botella combina las utilizaciones observadas: una etapa con utilización mayor por más de 15% que la otra se identifica como limitante. Si hay límite FPS, se comprueba primero si el ritmo observado está cerca del límite y ambas utilizaciones están por debajo de 90%; en ese caso se clasifica como límite externo. Los umbrales son una regla diagnóstica explícita del modelo, no una ley universal.

## Interfaz

La sección superior muestra el pipeline y el reproductor recorre el historial de eventos calculado por el motor. Ejecutar y luego reproducir/pausar, avanzar un evento o reiniciar permite inspeccionar la misma simulación. Las gráficas y la tabla de escenarios se calculan con los tiempos y métricas retornados, sin datos aleatorios de presentación. Los escenarios A–E son configuraciones sintéticas, no benchmarks reales. La exportación permite descargar métricas, fotogramas, eventos, configuración JSON y comparación CSV.

La utilización representa la fracción de tiempo útil del servidor abstracto. No equivale a lecturas de Windows, MSI Afterburner ni a una medición de hardware. Los factores de resolución tampoco modelan memoria, rasterización, shaders, cachés ni arquitectura de GPU.

## Ejecución

### Python

No hay paquetes externos que instalar. Desde la raíz:

```bash
python3 python/simulador.py --duracion 10 --cpu 5 --gpu 8 --salida resultado.json
```

El CLI guarda en JSON fotogramas, eventos y métricas. Para personalizar todos los parámetros, importa `Configuracion` y `simular` desde `python.modelos`.

### Web local (opcional)

La versión publicada en GitHub Pages se sirve como archivos estáticos y no depende de un servidor Python. Para probarla localmente, los navegadores requieren un origen HTTP para cargar módulos ES; se puede usar cualquier servidor estático. Por ejemplo:

```bash
npm run serve
```

Este servidor solo sirve para desarrollo local. No se necesita compilación ni backend para publicar. La aplicación evita dependencias externas.

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

Se verifican repetibilidad, orden CPU/GPU, exclusión mutua de cada servidor, capacidad FIFO, contrapresión, tiempos no negativos, cola de capacidad cero, caso determinista y comparación de muestras/métricas/eventos Python–JavaScript. La prueba cruzada usa Node.js cuando está disponible y se omite si no lo está.

En el pipeline ideal sin variabilidad CPU `5 ms` y GPU `10 ms`, la GPU limita el régimen estable a `100 fotogramas/s`. En una ventana finita, la tasa observada puede diferir por el transitorio inicial, el último fotograma que empieza antes del corte y termina durante el drenaje, y la convención de contar solo finalizaciones dentro de la ventana. En ventanas largas el efecto relativo del transitorio disminuye.

## Limitaciones

La generación bajo carga es *just in time*: se crea trabajo al empezar CPU disponible, salvo el espaciamiento impuesto por FPS. No modela un juego que produzca una cola ilimitada de simulación, descartes, sincronización vertical, paralelismo dentro de CPU/GPU, transferencia PCIe, CPU multinúcleo, clocks dinámicos, temperatura ni variación correlacionada. Una cola de render puede amortiguar diferencias y añadir latencia. El simulador sirve para explorar relaciones dentro de sus supuestos y comparar experimentos controlados, no para recomendar componentes reales.

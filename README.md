# GraphScope · Neo4j × TuringDB

Laboratorio local para presentar una comparativa reproducible con datos reales de relaciones empresariales. Backend Python/FastAPI, frontend HTML/JS, Neo4j Community y TuringDB. No contiene resultados de rendimiento inventados.

**Windows, instalación desde cero:** copia la carpeta y ejecuta `install.cmd`. Comprueba el PC, prepara Python/WSL2/Docker si faltan y después ejecuta el instalador del proyecto. Si Windows requiere reinicio, repite el mismo comando después de reiniciar. No configura inicio automático. `install.cmd -CheckOnly` realiza solo el diagnóstico. Instrucciones, permisos y límites en [INSTALL.md](INSTALL.md).

**Si Python y Docker ya existen, o en Linux/WSL:** `python create.py` (o `sh create.sh`). Adapta los recursos, prepara los datos, carga bases vacías y verifica el contenido. `python create.py --check` solo comprueba requisitos.

## Estado y requisitos

### Pestañas y datasets (20 de noviembre de 2026)

- **Offshore Leaks:** conserva el conjunto de 2.016.523 nodos y 3.339.267 relaciones.
- **Epinions:** red completa de Stanford SNAP con 75.879 usuarios y 508.837 relaciones dirigidas de confianza. Se eligió un dataset completo cercano a 70.000 nodos, sin muestrear ni recortar el grafo grande. Un enlace A → B significa que A confía en B. El archivo solo tiene IDs y enlaces; «Usuario N» es una etiqueta derivada, no un nombre real. No contiene países ni reseñas. [Fuente y cita original](https://snap.stanford.edu/data/soc-Epinions1.html).
- **Motores y tecnologías:** arquitectura, alcance de la comparativa y tecnologías del proyecto, con enlaces a documentación oficial.

Cada dataset tiene su propio par de servicios de bases de datos y volúmenes. Las consultas se ejecutan contra el par seleccionado, sin filtrar el grafo grande durante la medición. Las dos pestañas mantienen preguntas y resultados separados; la API comparte un bloqueo global para evitar comparaciones simultáneas. La estructura de los dos grafos es diferente: esta comparación no aísla únicamente el efecto del tamaño ni demuestra el rendimiento de los grafos de una empresa.

La página SNAP no declara una licencia específica para Epinions; revisar sus condiciones con el proveedor antes de redistribuir o reutilizar comercialmente. El manifiesto registra procedencia, conteos y hashes.

Para preparar el dataset nuevo en una instalación anterior, con Docker abierto:

```powershell
docker compose build
docker compose run --rm --no-deps api python -m tools.epinions
docker compose --profile ai up -d
docker compose exec api python -m tools.load neo4j --dataset small
docker compose exec api python -m tools.load turingdb --dataset small
docker compose exec api python -m tools.verify --dataset small
docker compose exec api python -m tools.benchmark --dataset small
```

En este equipo Epinions ya está preparado y cargado: no repitas las importaciones. El instalador `create.py` prepara y verifica automáticamente ambos datasets en equipos nuevos. Si los archivos ya están preparados, omite también `tools.epinions`. Los informes nuevos se guardan en `reports/verification-small.json` y `reports/benchmark-small.json`; los originales mantienen sus nombres.

La API admite `GET /api/status?dataset=full|small` y `POST /api/compare` con `dataset: full|small` (por defecto full). Los informes incluyen el selector y el manifiesto. Epinions tiene ranking de confianza y recorridos dirigidos; no admite el ranking de países de Offshore Leaks.

Hay cuatro servicios de bases de datos en lugar de dos. Cada motor mantiene el mismo límite de recursos, pero comparten la VM y pueden consumir más memoria total. No ejecutes importaciones ni verificaciones mientras mides. Los servicios conservan `restart: "no"` y su arranque es manual.

**Demo operativa en http://localhost:8000.** ICIJ completo está cargado en ambos motores: **2.016.523 nodos y 3.339.267 relaciones**, sin relaciones excluidas. La verificación íntegra ha pasado y las siete preguntas de ejemplo devuelven resultados equivalentes. Ollama interpreta las preguntas localmente por CPU. Consulta [el estado validado](docs/ESTADO.md) y [las mediciones reales](docs/RESULTADOS.md).

En este equipo basta con iniciar Docker Desktop y ejecutar `./scripts/start.ps1` si los servicios están detenidos. **No repitas las cargas** sobre las bases preparadas. Los pasos siguientes documentan una instalación nueva.

Windows: instala [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) con WSL2, inicia Docker y asigna unos 24 GB de RAM como máximo a su VM. Reiniciar Windows puede ser necesario. Linux con Docker Engine y Compose también sirve. Para uso empresarial, revisa los términos de Docker Desktop con tu organización.

Para 32 GB: ambos motores tienen el mismo límite de 8 GB y 4 CPU. Neo4j usa 3 GB de heap y 3 GB de page cache. Ollama tiene un límite de 5 GB y funciona por CPU por defecto; no se presupone compatibilidad con la AMD. Empieza por `medium` y pasa a `full` si la memoria lo permite. El muestreo produce un subgrafo inducido, con menos conexiones; para evaluar recorridos usa preferiblemente `full`.

## Arranque

Desde PowerShell, en esta carpeta:

```powershell
Copy-Item .env.example .env
# Edita .env: cambia la contraseña antes del primer arranque.
docker compose up -d --build
docker compose ps
```

También puedes ejecutar `./scripts/start.ps1`. Abre <http://localhost:8000>. El frontend muestra errores de conexión reales mientras no se hayan cargado datos. Los servicios están expuestos solamente en localhost; no publiques este laboratorio directamente en internet.

`DATA_DIR` controla los archivos fuente, NO los volúmenes internos. Para usar el M.2 E:, configura en Docker Desktop la ubicación de su disco virtual en E: antes de crear los volúmenes. Si quieres también los CSV/JSONL en E:, establece `DATA_DIR=E:/GraphScope/data` en `.env` y crea esa carpeta. La aplicación y Docker mantienen estos datos fuera de Git.

## Datos reales

Fuente: [ICIJ Offshore Leaks](https://offshoreleaks.icij.org/pages/database), archivo CSV oficial. Incluye entidades, personas, intermediarios, direcciones y relaciones. El perfil completo no aplica un límite artificial: el tamaño exacto se registra después de descargar la versión disponible, sin prometer un número fijo de relaciones. No se mezclan datos sintéticos.

```powershell
docker compose run --rm --no-deps api python -m tools.dataset --profile medium
# En una carpeta de datos nueva, para el conjunto completo:
# docker compose run --rm --no-deps api python -m tools.dataset --profile full
docker compose exec api python -m tools.load neo4j
docker compose exec api python -m tools.load turingdb
docker compose exec api python -m tools.verify
```

No ejecutes cargas simultáneas ni consultes durante la carga. Las cargas rechazan bases ya existentes para evitar duplicados. Si una carga falla puede dejar datos parciales: conserva el archivo canónico y vuelve a cargar en volúmenes de un proyecto Compose nuevo (`docker compose -p graphscope-retry ...`), sin borrar el original. El primer build necesita internet; descargar y normalizar el dataset puede tardar. El ZIP se lee sin extraer rutas externas. Se registra SHA-256 del ZIP y del grafo, perfil, fecha, conteos y relaciones excluidas.

Modelo común: `(:Record {uid, name, name_search, kind, country, jurisdiction, source})-[:LINK {uid, role, source}]->(:Record)`. `uid` es texto para conservar identidad. `country` conserva el campo de origen, que puede incluir varios países: el ranking agrupa ese campo, no descompone listas. La normalización no intenta resolver duplicados de personas ni inferir propiedad real. La restricción de unicidad en Neo4j crea un índice para búsquedas por ID; no se desactiva para favorecer al otro motor.

`tools.verify` recorre todas las propiedades normalizadas de nodos y aristas en orden y compara hashes entre bases, además de los conteos del manifiesto. Puede ser costoso en el perfil completo; se ejecuta antes de presentar, fuera del benchmark. Guarda `reports/verification.json`.

## Lenguaje natural local y proveedores

Por defecto `NL_PROVIDER=rules`: interpreta un catálogo limitado de preguntas sin descargar un modelo, con ejemplos visibles. No es un LLM general. Para interpretación con IA local:

```powershell
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
# En .env: NL_PROVIDER=ollama
docker compose up -d --force-recreate api
```

El modelo elige una intención y parámetros validados, y el backend compila una consulta de solo lectura. Admite conteos, ranking por país, nodos conectados, nombres, vecinos y alcance de 1 a 3 saltos. No ejecuta Cypher arbitrario ni inventa explicaciones de resultados. Revisa el plan y los parámetros mostrados cuando uses IA. Sin Ollama disponible, se muestra el error; no se cambia silenciosamente a otro proveedor.

Para una API futura: `NL_PROVIDER=openai-compatible`, `LLM_BASE_URL=https://tu-proveedor/v1`, `LLM_MODEL=...`, `LLM_API_KEY=...`; recrea `api`. No subas `.env` a Git. Esa opción enviará las preguntas al proveedor configurado.

## Qué se mide

- La interpretación se mide una vez, separada de las bases.
- Se crean y verifican conexiones y se carga el grafo fuera del cronómetro.
- Cada consulta se ejecuta secuencialmente, alternando el primer motor, con calentamientos configurables y 1–10 muestras. Se muestran mediana, p95 de rango más cercano y muestras crudas. Con pocas muestras p95 es casi el máximo, no una estimación robusta.
- Tiempo de cliente: consulta, transporte, decodificación y materialización completa. Neo4j usa Bolt y TuringDB su SDK nativo; las diferencias de drivers forman parte de la medición. No se etiqueta como tiempo interno del motor.
- Se comprueba igualdad como multiconjunto de filas y estabilidad entre repeticiones. Las consultas usan orden determinista y límites iguales. Rankings/búsquedas muestran solo la ventana indicada; igualdad de esa ventana no demuestra equivalencia global.
- No se vacían cachés del sistema ni del motor. Una primera ejecución sin calentamiento tampoco es una prueba garantizada de caché fría. No ejecutes importaciones ni otras comparaciones al medir. Los recorridos en grafos densos pueden costar mucho incluso a 3 saltos.

El objetivo es evaluar cargas concretas y explicar sus condiciones, no declarar un ganador universal. La UI permite descargar el informe JSON de cada pregunta.

Para repetir el catálogo completo y guardar `reports/benchmark.json`, ejecuta `docker compose exec api python -m tools.benchmark`. La tabla de esta ejecución está en [docs/RESULTADOS.md](docs/RESULTADOS.md). Neo4j mantiene además un índice de `LINK.uid` para la verificación completa. Las consultas de lectura tienen un límite de 30 segundos; en TuringDB es un timeout de transporte y no garantiza cancelar una consulta ya enviada al servidor.

## Trasladar a otro equipo

Ya hay un paquete real preparado en `data/portable/graphscope-icij.zip` (unos 129 MB). Cópialo junto con el código al destino y restáuralo mediante `tools.portable restore`; después carga las dos bases y verifica el contenido. El paquete contiene los datos normalizados y el manifiesto; el modelo local se descarga por separado.

La vía portable recomendada es reconstruir ambos motores desde el mismo archivo canónico, evitando formatos binarios dependientes de versión:

1. Detén las cargas. Copia el repositorio (sin `.env`, ni `.venv`), `data/canonical/graph.jsonl` y `manifest.json` al otro equipo. Incluye `reports/verification.json` para trazabilidad cuando exista. No necesitas volver a descargar ICIJ.
2. Instala Docker, crea `.env`, conserva las versiones del Compose/Dockerfiles y ajusta `DATA_DIR` a la nueva ubicación.
3. Inicia un proyecto con volúmenes vacíos y ejecuta las dos cargas y `tools.verify` de arriba.

Puedes empaquetar los datos con `.venv/Scripts/python -m tools.portable export backups/dataset.zip` y restaurarlos en el otro equipo con `.venv/Scripts/python -m tools.portable restore backups/dataset.zip`. La restauración exige una carpeta `canonical` vacía y comprueba el hash. Dentro del contenedor los mismos comandos empiezan por `docker compose run --rm --no-deps api python` y la salida debe estar en `/app/data` para persistirla.

Esta migración reconstruye las bases; no es una copia instantánea. Para conservar exactamente el entorno sin internet exporta además las imágenes con `docker image save` y cárgalas con `docker image load`. Para copias binarias, usa procedimientos oficiales de backup de cada motor con servicios detenidos y versiones idénticas; no copies carpetas de bases en ejecución. Las claves y contraseñas se configuran por separado.

## Interfaces nativas de los motores

Con los servicios arrancados, puedes explorar directamente las bases desde el navegador de Windows o Linux:

| Dataset | Neo4j Browser | Conexión Bolt | TuringDB Visualizer |
|---|---|---|---|
| Offshore Leaks | http://localhost:7474 | bolt://localhost:7687 | http://localhost:8080 |
| Epinions | http://localhost:7475 | bolt://localhost:7688 | http://localhost:8081 |

En Neo4j usa el usuario `neo4j`, la contraseña `NEO4J_PASSWORD` de tu `.env` y la conexión Bolt de la fila correspondiente. Comprueba el puerto del formulario: Browser puede recordar una conexión anterior. En TuringDB selecciona el grafo `offshore` y pulsa **Load offshore** si aparece: ambos servicios conservan ese nombre interno, pero cada uno contiene su dataset independiente. No es necesario importar de nuevo los datos.

Para ver un ejemplo de relaciones en cualquiera de las interfaces, ejecuta `MATCH (a:Record)-[r:LINK]->(b:Record) RETURN a, r, b LIMIT 25`. Son consolas nativas con capacidad de modificar datos; usa consultas de lectura para conservar la igualdad de la comparación. Las consultas ejecutadas allí también pueden calentar cachés o competir por recursos: finalízalas antes del benchmark.

Los puertos se publican exclusivamente en `127.0.0.1`. Puedes cambiarlos con las variables de `.env.example`, sin modificar los puertos internos. Tras actualizar una instalación existente, ejecuta `docker compose --profile ai up -d --build` (añade `-p` si usas un nombre de proyecto propio). No uses `down -v`: las bases permanecen en sus volúmenes.

La interfaz de TuringDB se inicia con `-ui`, según su [documentación oficial](https://docs.turingdb.ai/quickstart), y es independiente del visualizador común de nuestra aplicación.

## Visualización de resultados

Cada motor ofrece las vistas **Tabla / Grafo** en los dos datasets. Se utiliza un visualizador SVG común integrado en la aplicación, con flechas de dirección, colores por tipo, zoom, desplazamiento, arrastre e inspección de propiedades. No requiere servicios de visualización ni librerías externas. No es una integración de las interfaces nativas de los fabricantes.

Las consultas de vecinos dibujan las relaciones reales de las filas devueltas y el nodo consultado. Las búsquedas y rankings muestran sus nodos; **Explorar conexiones** añade un vecindario real identificado como exploración adicional. **Volver al resultado original** descarta esa ampliación. Los conteos y agregados permanecen como tablas; no se inventan conexiones para representarlos.

Las lecturas visuales se realizan después de las mediciones y usan el mismo bloqueo que las comparaciones para evitar solaparlas. Pueden calentar las cachés para ejecuciones posteriores. Los tiempos mostrados siguen incluyendo únicamente la consulta medida y su materialización, según la metodología existente.

La vista se limita a 150 nodos y 200 relaciones, con hasta 50 relaciones por expansión; avisa cuando está limitada. El servidor conserva hasta 20 comparaciones durante 15 minutos; si expira una, vuelve a ejecutar la consulta. El JSON descargado incluye las visualizaciones disponibles. El endpoint `/api/visualize` recibe un identificador de comparación y obtiene el dataset y los resultados del contexto guardado en el servidor.

Validación: pruebas unitarias con `python -m unittest discover -s tests -v`, distribución SVG con `node tests/test_graph_layout.cjs` y prueba integrada con ambos motores y datasets mediante `docker compose exec -T api python -m tools.graph_smoke`. Esta última guarda `reports/graph-smoke.json` y comprueba direcciones, igualdad de grafos, expansión, restablecimiento y agregados sin nodos ficticios.

## Desarrollo y pruebas sin Docker

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m unittest discover -s tests -v
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

TuringDB se instala en el contenedor Linux; el desarrollo Windows del frontend/API no requiere su paquete. Sin motores, la UI indica que no hay conexión. Las pruebas unitarias no sustituyen la prueba integrada con ambos motores y el dataset completo.

## Guion para la presentación

1. Muestra origen, tamaño y verificación del dataset; explica el modelo de grafo.
2. Cuenta nodos y relaciones, después ejecuta el ranking de países y nodos conectados.
3. Busca un nombre, copia un ID devuelto y consulta sus vecinos y alcance a 2/3 saltos.
4. Repite cinco veces con calentamiento, revisa igualdad y descarga JSON.
5. Explica memoria, protocolo, caché e índices antes de extraer conclusiones.

## Fuentes y atribución

- [ICIJ: descarga y licencias](https://offshoreleaks.icij.org/pages/database). Base ODbL; contenidos CC BY-SA. Cita siempre a ICIJ. Aparecer en los registros no implica una conducta ilegal; los datos son históricos.
- [TuringDB 3.1: protocolo y SDK](https://docs.turingdb.ai/releases/v3-1), [importación JSONL](https://docs.turingdb.ai/import_data/jsonl), [CLI](https://docs.turingdb.ai/commands). La documentación general contiene ejemplos previos a 3.1: se usa la conexión host/puerto de 3.1. Motor y SDK fijados juntos a 3.1; paquete Linux confirmado en PyPI y firmas del SDK inspeccionadas. La compatibilidad integrada se debe confirmar en el primer build.
- [Neo4j Docker](https://neo4j.com/docs/operations-manual/current/docker/), [memoria](https://neo4j.com/docs/operations-manual/current/docker/configuration/), [Ollama chat](https://docs.ollama.com/api/chat).

Las imágenes base usan tags explícitos; para una presentación auditada guarda también sus digests con `docker image inspect` y conserva el manifiesto, informe y configuración del equipo.

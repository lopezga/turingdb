# Estado del laboratorio · 20 de noviembre de 2026

## Actualización: dos datasets y tres pestañas

- Título simplificado a **Neo4j vs. TuringDB** y subtítulo **Demo de consultas y tiempos de respuesta**.
- Pestaña original de Offshore Leaks conservada, con 2.016.523 nodos y 3.339.267 relaciones.
- Nueva pestaña con el dataset **Epinions completo de Stanford SNAP**: 75.879 usuarios y 508.837 relaciones dirigidas de confianza. No es un subconjunto del grafo de ICIJ ni un recorte a 70.000 nodos.
- Cada conjunto utiliza su propio par de servicios y volúmenes. Los cuatro motores tienen el mismo límite por servicio y comparten la VM Docker. El consumo combinado observado después de los benchmarks fue aproximadamente 13,5 GiB, con ambos grafos cargados y el modelo local.
- Verificación completa de Epinions aprobada: todos los nodos, propiedades y extremos de relaciones coinciden entre motores. Evidencia en reports/verification-small.json.
- Catálogos de siete preguntas ejecutados en ambos datasets: catorce casos con interpretación esperada, resultados equivalentes y estables. Informes independientes en reports/benchmark.json y reports/benchmark-small.json; tablas en docs/RESULTADOS.md y docs/RESULTADOS-EPINIONS.md.
- Trece pruebas unitarias aprobadas. Navegador: título, pestañas, consulta real, conservación de resultados al cambiar de pestaña y exportación JSON con el selector correcto comprobados.
- Tercera pestaña con explicación de arquitecturas, límites de la comparación, fuentes oficiales y tecnologías utilizadas.
- Instalador actualizado para preparar, cargar y verificar los dos conjuntos. No se ha repetido una instalación completa desde cero en otro equipo físico.
- Las nuevas bases conservan restart: "no" y el arranque sigue siendo manual. El número de nodos no basta para extrapolar rendimiento: Epinions y Offshore Leaks tienen estructuras y semánticas distintas.

Capturas de la interfaz actualizada: reports/demo-epinions.jpg y reports/demo-tecnologias.jpg.

El proyecto funciona en **http://localhost:8000** con Neo4j, TuringDB y el modelo local Qwen2.5 3B mediante Ollama.

## Validado

- Docker Desktop/WSL2 operativo tras la instalación y el reinicio.
- Imágenes construidas y servicios arrancados; frontend revisado en navegador.
- ICIJ completo cargado en ambos motores: **2.016.523 nodos y 3.339.267 relaciones**, sin relaciones excluidas.
- Neo4j Community 5.26.0 y TuringDB 3.1: hashes iguales de todas las propiedades normalizadas de nodos y relaciones, incluidos sus extremos. Conteos coincidentes con el manifiesto.
- Contenedores recreados conservando los datos en sus volúmenes. Benchmark ejecutado después del reinicio.
- Modelo local descargado y activo por CPU. Siete preguntas de ejemplo interpretadas correctamente, con resultados equivalentes y estables en tres repeticiones tras un calentamiento.
- Seis pruebas unitarias aprobadas, incluyendo validación de parámetros y exportación/restauración con fixture. Sintaxis JavaScript comprobada.
- Consulta desde el frontend: 3.339.267 relaciones en ambos motores, tiempos separados e interpretación aparte. Captura en reports/demo.jpg.

## Evidencia

- reports/verification.json: conteos y hashes completos.
- reports/benchmark.json: preguntas, planes, consultas, parámetros, muestras y resultados.
- docs/RESULTADOS.md: tabla de medianas y condiciones.
- reports/runtime.json y reports/requirements-linux.lock: entorno y dependencias.
- data/canonical/manifest.json: origen, licencia y huella del grafo.
- data/portable/graphscope-icij.zip: paquete portable del grafo y manifiesto, unos 129 MB. No incluye contraseñas ni el modelo.

SHA-256 del grafo JSONL: 83161cd3b7aab6be5360b4db6e1bce3898cd5d80978eeb04ea927855b41067d6.

## Visualización integrada (20 de noviembre de 2026)

Disponibles las vistas Tabla/Grafo independientes para Neo4j y TuringDB en ambos datasets, con un visualizador SVG común, propiedades, zoom y expansión de conexiones. Se distinguen los resultados originales de la exploración adicional y se conservan los agregados como tablas. Las lecturas visuales se ejecutan después del benchmark y fuera de sus cronómetros.

Validación: 20 pruebas unitarias, prueba determinista de distribución en Node y prueba real con ambos motores sobre los dos datasets (`reports/graph-smoke.json`). Coinciden los grafos originales y ampliados, incluidas las direcciones; restablecimiento y agregados comprobados. Límites: 150 nodos, 200 relaciones, 50 relaciones por expansión; contexto de comparación de 15 minutos y hasta 20 entradas en memoria.

## Uso diario

Inicia Docker Desktop y ejecuta scripts/start.ps1 si los contenedores no están funcionando. El script activa Ollama cuando .env contiene NL_PROVIDER=ollama. No repitas las cargas sobre estas bases ya preparadas. Para detener los servicios conservando los volúmenes: docker compose --profile ai stop.

## Límites de esta validación

El lenguaje natural selecciona un catálogo de consultas de lectura; no es un asistente general sobre cualquier pregunta. Una formulación nueva puede interpretarse mal: revisa la consulta y los parámetros mostrados.

Las mediciones incluyen protocolo, driver y materialización. No son tiempos internos puros ni una comparación estadística definitiva: tres muestras por consulta y cachés sin vaciar. Cada motor tiene un límite de 8 GiB y 4 CPU; Docker dispone de aproximadamente 15,5 GiB. Consulta docs/RESULTADOS.md.

No se ha migrado a un segundo equipo físico. Se ha generado el paquete real y probado el mecanismo de exportación/restauración con un fixture y validación SHA-256. En el destino hay que reconstruir ambas bases y repetir tools.verify.

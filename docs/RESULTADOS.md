# Mediciones del laboratorio

Ejecución UTC: 2026-11-20T12:02:49.672402+00:00

Dataset: ICIJ Offshore Leaks. 2,016,523 nodos y 3,339,267 relaciones.

Tres muestras medidas por consulta, precedidas de un calentamiento por motor. Ejecución secuencial con orden alterno; cachés sin vaciar. Tiempo de cliente incluyendo transporte y materialización, con la interpretación de Ollama fuera del cronómetro.

| Pregunta | Neo4j, mediana ms | TuringDB, mediana ms | Resultados iguales |
|---|---:|---:|:---:|
| ¿Cuántos nodos hay? | 3.11 | 0.54 | Sí |
| ¿Cuántas relaciones hay? | 645.62 | 41.93 | Sí |
| ¿Qué países tienen más entidades? | 581.01 | 31.05 | Sí |
| ¿Cuáles son los nodos más conectados? | 7749.43 | 1891.27 | Sí |
| Busca entidades llamadas "MOSSACK" | 395.79 | 39.07 | Sí |
| Vecinos del nodo 10000001 | 3.90 | 19.56 | Sí |
| Alcance a 2 saltos del nodo 10000001 | 11.28 | 23.42 | Sí |

Configuración de esta ejecución: {"BENCH_ENGINE_MEMORY": "8g", "BENCH_ENGINE_CPUS": "4", "BENCH_NEO4J_HEAP": "3G", "BENCH_NEO4J_PAGECACHE": "3G", "NL_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen2.5:3b"}

La verificación íntegra compara todas las propiedades normalizadas y extremos de relaciones mediante SHA-256. Los siete casos del catálogo también comprueban estabilidad entre repeticiones y la intención interpretada.

Estos datos describen esta ejecución, este equipo y este catálogo. Las consultas de vecinos y alcance se anclan al nodo 10000001; no representan todos los grados ni profundidades del grafo. Tres muestras no bastan para conclusiones estadísticas generales. La igualdad de rankings y búsquedas se comprueba sobre la ventana limitada que devuelve cada consulta.

Neo4j mantiene su índice único de Record.uid y un índice de LINK.uid para verificación. La diferencia de protocolos y drivers forma parte del tiempo medido. Los números pueden cambiar entre ejecuciones y equipos.

Informes completos: `reports/benchmark.json`, `reports/verification.json`, `reports/runtime.json` y `reports/requirements-linux.lock`.

# Mediciones del laboratorio

Ejecución UTC: 2026-11-20T12:01:30.413611+00:00

Dataset: Stanford SNAP Epinions. 75,879 nodos y 508,837 relaciones.

Tres muestras medidas por consulta, precedidas de un calentamiento por motor. Ejecución secuencial con orden alterno; cachés sin vaciar. Tiempo de cliente incluyendo transporte y materialización, con la interpretación de Ollama fuera del cronómetro.

| Pregunta | Neo4j, mediana ms | TuringDB, mediana ms | Resultados iguales |
|---|---:|---:|:---:|
| ¿Cuántos nodos hay? | 1.68 | 0.97 | Sí |
| ¿Cuántas relaciones hay? | 70.26 | 4.56 | Sí |
| ¿Qué usuarios reciben más confianza? | 213.80 | 46.85 | Sí |
| ¿Cuáles son los nodos más conectados? | 728.12 | 84.37 | Sí |
| Busca usuarios llamados "Usuario 1" | 14.87 | 3.65 | Sí |
| Vecinos del nodo 0 | 3.36 | 1.79 | Sí |
| Alcance a 2 saltos del nodo 0 | 6.01 | 3.07 | Sí |

Configuración de esta ejecución: {"BENCH_ENGINE_MEMORY": "8g", "BENCH_ENGINE_CPUS": "4", "BENCH_NEO4J_HEAP": "3G", "BENCH_NEO4J_PAGECACHE": "3G", "NL_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen2.5:3b"}

La verificación íntegra compara todas las propiedades normalizadas y extremos de relaciones mediante SHA-256. Los siete casos del catálogo también comprueban estabilidad entre repeticiones y la intención interpretada.

Estos datos describen esta ejecución, este equipo y este catálogo. Las consultas de vecinos y alcance se anclan al nodo 0; no representan todos los grados ni profundidades del grafo. Tres muestras no bastan para conclusiones estadísticas generales. La igualdad de rankings y búsquedas se comprueba sobre la ventana limitada que devuelve cada consulta.

Neo4j mantiene su índice único de Record.uid y un índice de LINK.uid para verificación. La diferencia de protocolos y drivers forma parte del tiempo medido. Los números pueden cambiar entre ejecuciones y equipos.

Informes completos: `reports/benchmark-small.json`, `reports/verification-small.json`, `reports/runtime.json` y `reports/requirements-linux.lock`.

"""Create a concise presentation reference from an actual benchmark report."""
import json
import argparse
from pathlib import Path


def main(dataset='full'):
    benchmark = 'benchmark.json' if dataset == 'full' else 'benchmark-small.json'
    verification = 'verification.json' if dataset == 'full' else 'verification-small.json'
    data = json.loads((Path('reports') / benchmark).read_text(encoding='utf-8'))
    manifest = data['state']['dataset']
    seed = '10000001' if dataset == 'full' else '0'
    lines = ['# Mediciones del laboratorio', '',
        f"Ejecución UTC: {data['created_utc']}", '',
        f"Dataset: {'ICIJ Offshore Leaks' if dataset == 'full' else 'Stanford SNAP Epinions'}. {manifest['nodes']:,} nodos y {manifest['edges']:,} relaciones.", '',
        'Tres muestras medidas por consulta, precedidas de un calentamiento por motor. '
        'Ejecución secuencial con orden alterno; cachés sin vaciar. '
        'Tiempo de cliente incluyendo transporte y materialización, con la interpretación de Ollama fuera del cronómetro.', '',
        '| Pregunta | Neo4j, mediana ms | TuringDB, mediana ms | Resultados iguales |',
        '|---|---:|---:|:---:|']
    for row in data['queries']:
        a, b = row['engines']['Neo4j'], row['engines']['TuringDB']
        lines.append(f"| {row['question']} | {a.get('median_ms', float('nan')):.2f} | {b.get('median_ms', float('nan')):.2f} | {'Sí' if row['equivalent'] else 'No'} |")
    lines += ['', 'Configuración de esta ejecución: ' + json.dumps(data['state'].get('configuration',
        {'nota': 'No registrada por esta versión del informe; consulta el entorno de la ejecución original.'}), ensure_ascii=False), '',
        'La verificación íntegra compara todas las propiedades normalizadas y extremos de relaciones mediante SHA-256. '
        'Los siete casos del catálogo también comprueban estabilidad entre repeticiones y la intención interpretada.', '',
        'Estos datos describen esta ejecución, este equipo y este catálogo. Las consultas de vecinos y alcance '
        f'se anclan al nodo {seed}; no representan todos los grados ni profundidades del grafo. '
        'Tres muestras no bastan para conclusiones estadísticas generales. '
        'La igualdad de rankings y búsquedas se comprueba sobre la ventana limitada que devuelve cada consulta.', '',
        'Neo4j mantiene su índice único de Record.uid y un índice de LINK.uid para verificación. '
        'La diferencia de protocolos y drivers forma parte del tiempo medido. '
        'Los números pueden cambiar entre ejecuciones y equipos.', '',
        f'Informes completos: `reports/{benchmark}`, `reports/{verification}`, `reports/runtime.json` '
        'y `reports/requirements-linux.lock`.']
    Path('docs').mkdir(exist_ok=True)
    filename = 'RESULTADOS.md' if dataset == 'full' else 'RESULTADOS-EPINIONS.md'
    (Path('docs') / filename).write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dataset', choices=['full', 'small'], default='full')
    main(p.parse_args().dataset)

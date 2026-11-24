"""Full content digest (not just counts) for both stores, streamed in ID pages."""
import hashlib
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from app.engines import NeoEngine, TuringEngine
from app.datasets import dataset_config


def digest(engine, relationship=False):
    h = hashlib.sha256()
    last, count = '', 0
    if relationship:
        prefix = 'MATCH (a:Record)-[n:LINK]->(b:Record)'
        fields = 'n.uid AS uid, a.uid AS start, b.uid AS end, n.role AS role, n.source AS source'
    else:
        prefix = 'MATCH (n:Record)'
        fields = ', '.join(f'n.{key} AS {key}' for key in ['uid', 'name', 'name_search', 'kind', 'country', 'jurisdiction', 'source'])
    while True:
        rows = engine.query(f'{prefix} WHERE n.uid > $last RETURN {fields} ORDER BY uid LIMIT 50000', {'last': last})
        if not rows:
            return {'count': count, 'sha256': h.hexdigest()}
        for row in rows:
            h.update((json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n').encode())
        last = rows[-1]['uid']
        count += len(rows)
        print(f"{'Relaciones' if relationship else 'Nodos'} verificados: {count:,}", flush=True)


def verify(dataset='full'):
    report = {}
    for name, factory in [('neo4j', NeoEngine), ('turingdb', TuringEngine)]:
        engine = factory(dataset=dataset)
        try:
            report[name] = {'nodes': digest(engine), 'edges': digest(engine, True)}
        finally:
            engine.close()
    report['equal'] = report['neo4j'] == report['turingdb']
    manifest = json.loads((dataset_config(dataset)['directory'] / 'manifest.json').read_text(encoding='utf-8'))
    report['dataset_id'] = dataset
    report['dataset_sha256'] = manifest['graph_sha256']
    report['checked_utc'] = datetime.now(timezone.utc).isoformat()
    report['expected_counts'] = all(report[k][typ]['count'] == manifest[typ] for k in ['neo4j', 'turingdb'] for typ in ['nodes', 'edges'])
    Path('reports').mkdir(exist_ok=True)
    filename = 'verification.json' if dataset == 'full' else 'verification-small.json'
    (Path('reports') / filename).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if not report['equal'] or not report['expected_counts']:
        raise SystemExit(1)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dataset', choices=['full', 'small'], default='full')
    verify(p.parse_args().dataset)

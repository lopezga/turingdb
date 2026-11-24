"""Load the exact canonical file into empty databases; fail on pre-existing data."""
import argparse
import json
from pathlib import Path
from app.engines import NeoEngine, TuringEngine
from tools.dataset import sha256
from app.datasets import dataset_config


def batches(path, kind, size=5000):
    batch = []
    with path.open(encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            if row['type'] == kind:
                batch.append(row)
                if len(batch) == size:
                    yield batch
                    batch = []
    if batch:
        yield batch


def load(which, dataset='full'):
    root = dataset_config(dataset)['directory']
    path = root / 'graph.jsonl'
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if sha256(path) != manifest['graph_sha256']:
        raise ValueError('El hash del dataset no coincide.')
    if which == 'neo4j':
        engine = NeoEngine(dataset=dataset)
        try:
            if engine.query('MATCH (n) RETURN count(n) AS total')[0]['total']:
                raise ValueError('Neo4j contiene datos. No se sobrescribe: usa un proyecto Compose nuevo.')
            engine.query('CREATE CONSTRAINT record_uid IF NOT EXISTS FOR (n:Record) REQUIRE n.uid IS UNIQUE')
            for batch in batches(path, 'node'):
                engine.query('UNWIND $rows AS row CREATE (n:Record) SET n = row.properties', {'rows': batch})
                print(f"Nodos: lote de {len(batch)} cargado", flush=True)
            for batch in batches(path, 'relationship'):
                engine.query('UNWIND $rows AS row MATCH (a:Record {uid: row.start.id}), (b:Record {uid: row.end.id}) CREATE (a)-[r:LINK]->(b) SET r = row.properties', {'rows': batch})
                print(f"Relaciones: lote de {len(batch)} cargado", flush=True)
            engine.query('CREATE INDEX link_uid IF NOT EXISTS FOR ()-[r:LINK]-() ON (r.uid)')
            engine.query('CALL db.awaitIndexes(300)')
        finally:
            engine.close()
    else:
        engine = TuringEngine(graph=False, dataset=dataset)
        engine.query(f"LOAD JSONL 'graph.jsonl' AS {dataset_config(dataset)['graph']}")
        engine.close()
    print(f'{which}: carga terminada; ejecuta python -m tools.verify')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('engine', choices=['neo4j', 'turingdb'])
    p.add_argument('--dataset', choices=['full', 'small'], default='full')
    args = p.parse_args()
    load(args.engine, args.dataset)

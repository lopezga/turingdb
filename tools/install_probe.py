"""Bootstrap probe: missing graph means empty; every other connection error fails."""
import json
import argparse
import time
from app.engines import NeoEngine, TuringEngine
from app.datasets import dataset_config


def probe(dataset='full'):
    error = None
    for _ in range(90):
        neo = turing = None
        try:
            neo = NeoEngine(dataset=dataset)
            # Count every node, including data outside the demo schema.
            count = neo.query('MATCH (n) RETURN count(n) AS total')[0]['total']
            turing = TuringEngine(graph=False, dataset=dataset)
            available = turing.client.list_available_graphs()
            return {'neo4j': 'empty' if count == 0 else 'existing',
                    'turingdb': 'existing' if dataset_config(dataset)['graph'] in available else 'empty'}
        except Exception as exc:
            error = exc
            time.sleep(2)
        finally:
            if neo:
                neo.close()
            if turing:
                turing.close()
    raise RuntimeError(f'Los motores no están disponibles: {error}')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dataset', choices=['full', 'small'], default='full')
    print(json.dumps(probe(p.parse_args().dataset)))

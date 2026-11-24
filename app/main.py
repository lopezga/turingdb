import json
import math
import os
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.catalog import EXAMPLES, compile_plan
from app.planner import interpret
from app.engines import NeoEngine, TuringEngine, measure
from app.datasets import DatasetId, dataset_config
from app.catalog import dataset_examples
from typing import Literal
from app.graph import store, result_graph, expand_graph, GraphRequestError

app = FastAPI(title='GraphScope · Neo4j × TuringDB')
lock = threading.Lock()


def dataset_metadata(dataset='full'):
    manifest = dataset_config(dataset)['directory'] / 'manifest.json'
    return json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else None


def execution_config():
    return {key: os.getenv(key) for key in ['BENCH_ENGINE_MEMORY', 'BENCH_ENGINE_CPUS',
        'BENCH_NEO4J_HEAP', 'BENCH_NEO4J_PAGECACHE', 'NL_PROVIDER', 'OLLAMA_MODEL']}


class Ask(BaseModel):
    dataset: DatasetId = 'full'
    question: str = Field(min_length=3, max_length=500)
    repetitions: int = Field(default=3, ge=1, le=10)
    warmups: int = Field(default=1, ge=0, le=2)


class GraphRequest(BaseModel):
    comparison_id: str = Field(pattern=r'^[0-9a-f]{32}$')
    engine: Literal['Neo4j', 'TuringDB']
    action: Literal['result', 'expand', 'reset'] = 'result'
    node_id: str = Field(default='', pattern=r'^[0-9]{0,30}$')


def fingerprint(rows):
    # Multiset comparison preserves duplicates and ignores transport row order.
    return sorted(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) for row in rows)


@app.get('/api/status')
def status(dataset: DatasetId = 'full'):
    result = {}
    for name, factory in [('Neo4j', NeoEngine), ('TuringDB', TuringEngine)]:
        engine = None
        try:
            engine = factory(dataset=dataset)
            result[name] = {'ready': True, 'counts': engine.query('MATCH (n:Record) RETURN count(n) AS total')}
        except Exception as exc:
            result[name] = {'ready': False, 'error': str(exc)[:400]}
        finally:
            if engine:
                engine.close()
    return {'engines': result, 'dataset_id': dataset, 'dataset': dataset_metadata(dataset), 'examples': dataset_examples(dataset), 'configuration': execution_config()}


@app.post('/api/compare')
def compare(body: Ask):
    if not lock.acquire(blocking=False):
        raise HTTPException(409, 'Hay otra comparación en curso.')
    engines = {}
    try:
        start = time.perf_counter_ns()
        try:
            plan, provider = interpret(body.question, dataset=body.dataset)
            cypher, params = compile_plan(plan, dataset=body.dataset)
        except Exception as exc:
            raise HTTPException(422, str(exc)) from exc
        planning_ms = (time.perf_counter_ns() - start) / 1e6
        output = {}
        for name, factory in [('Neo4j', NeoEngine), ('TuringDB', TuringEngine)]:
            try:
                engines[name] = factory(dataset=body.dataset)
                output[name] = {'samples_ms': [], 'rows': [], 'stable': True}
            except Exception as exc:
                output[name] = {'error': str(exc)[:500]}
        previous = {}
        for iteration in range(body.warmups + body.repetitions):
            names = list(engines)
            if iteration % 2:
                names.reverse()
            for name in names:
                if 'error' in output[name]:
                    continue
                try:
                    sample = measure(engines[name], cypher, params)
                    if iteration >= body.warmups:
                        fp = fingerprint(sample['rows'])
                        if name in previous and previous[name] != fp:
                            output[name]['stable'] = False
                        previous[name] = fp
                        output[name]['samples_ms'].append(sample['ms'])
                        output[name]['rows'] = sample['rows']
                except Exception as exc:
                    output[name]['error'] = str(exc)[:500]
        for value in output.values():
            if 'error' not in value:
                samples = value['samples_ms']
                value['median_ms'] = statistics.median(samples)
                value['p95_ms'] = sorted(samples)[math.ceil(.95 * len(samples)) - 1]
                value['row_count'] = len(value['rows'])
        valid = all('error' not in v and v.get('stable') for v in output.values())
        equivalent = fingerprint(output['Neo4j']['rows']) == fingerprint(output['TuringDB']['rows']) if valid else None
        report = {'question': body.question, 'plan': plan.model_dump(), 'provider': provider,
            'created_utc': datetime.now(timezone.utc).isoformat(), 'dataset': dataset_metadata(body.dataset), 'dataset_id': body.dataset,
            'configuration': execution_config(),
            'planning_ms': planning_ms, 'cypher': cypher, 'parameters': params,
            'warmups': body.warmups, 'repetitions': body.repetitions,
            'equivalent': equivalent, 'engines': output,
            'method': 'Ejecución secuencial, orden alterno; tiempo de cliente con transporte y materialización. No es tiempo interno puro del motor.'}
        report['comparison_id'] = store.add(body.dataset, plan, output)
        return report
    finally:
        try:
            for engine in engines.values():
                engine.close()
        finally:
            lock.release()


@app.post('/api/visualize')
def visualize(body: GraphRequest):
    if not lock.acquire(blocking=False):
        raise HTTPException(409, 'Hay una medición o una lectura visual en curso. Espera y vuelve a intentarlo.')
    engine = None
    try:
        try:
            entry = store.get(body.comparison_id)
        except KeyError as exc:
            raise HTTPException(410, str(exc.args[0])) from exc
        # Aggregates need no extra database connection unless the user explicitly explores an anchor.
        cached = entry['graphs'].get(body.engine)
        if body.action == 'result' and cached is not None:
            return cached
        factory = NeoEngine if body.engine == 'Neo4j' else TuringEngine
        engine = factory(dataset=entry['dataset'])
        try:
            graph = result_graph(entry, body.engine, engine) if body.action in ('result', 'reset') else expand_graph(entry, body.engine, engine, body.node_id)
        except GraphRequestError as exc:
            raise HTTPException(422, str(exc)) from exc
        entry['graphs'][body.engine] = graph
        return graph
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, 'No se pudo obtener el grafo: ' + str(exc)[:400]) from exc
    finally:
        try:
            if engine:
                engine.close()
        finally:
            lock.release()


app.mount('/', StaticFiles(directory=Path(__file__).resolve().parent.parent / 'web', html=True), name='web')

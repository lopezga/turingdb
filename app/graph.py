"""Bounded graph reads derived from server-held comparison results, never arbitrary Cypher."""
import copy
import threading
import time
import uuid
from collections import OrderedDict

MAX_NODES = 150
MAX_EDGES = 200
EXPAND_EDGES = 50
GRAPH_INTENTS = {'neighbors', 'search', 'hubs', 'trusted'}
NODE_QUERY = ('MATCH (n:Record) WHERE n.uid IN $ids RETURN n.uid AS id, n.name AS name, '
              'n.kind AS kind, n.country AS country, n.jurisdiction AS jurisdiction, '
              'n.source AS source ORDER BY id LIMIT 151')
EDGE_FIELDS = ('a.uid AS source, b.uid AS target, r.uid AS id, '
               'r.role AS role, r.source AS origin')


class GraphRequestError(ValueError):
    pass


class ComparisonStore:
    def __init__(self, capacity=20, ttl=900):
        self.capacity, self.ttl = capacity, ttl
        self.entries = OrderedDict()
        self.lock = threading.RLock()

    def add(self, dataset, plan, results):
        with self.lock:
            now = time.monotonic()
            for key in list(self.entries):
                if now - self.entries[key]['created'] >= self.ttl:
                    del self.entries[key]
            key = uuid.uuid4().hex
            self.entries[key] = {'created': now, 'dataset': dataset, 'plan': plan.model_copy(deep=True),
                'results': copy.deepcopy(results), 'graphs': {}}
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
            return key

    def get(self, key):
        with self.lock:
            entry = self.entries.get(key)
            if entry is None or time.monotonic() - entry['created'] >= self.ttl:
                self.entries.pop(key, None)
                raise KeyError('La visualización ha caducado. Ejecuta de nuevo la consulta.')
            return entry


store = ComparisonStore()


def uid(value):
    value = str(value)
    if not value.isascii() or not value.isdigit() or len(value) > 30:
        raise GraphRequestError('Identificador de grafo inválido.')
    return value


def read_nodes(engine, ids):
    if not ids:
        return []
    return [{'id': uid(row['id']), 'label': row['name'] or str(row['id']), 'kind': row['kind'],
             'properties': {key: row.get(key) for key in ['name', 'kind', 'country', 'jurisdiction', 'source']}}
            for row in engine.query(NODE_QUERY, {'ids': sorted(ids)[:MAX_NODES]})]


def merge_graph(document, nodes, edges):
    node_map = {row['id']: row for row in document['nodes']}
    edge_map = {row['id']: row for row in document['edges']}
    for row in nodes:
        if row['id'] in node_map or len(node_map) < MAX_NODES:
            node_map[row['id']] = row
        else:
            document['limited'] = True
    for row in edges:
        edge = {'id': uid(row['id']), 'source': uid(row['source']), 'target': uid(row['target']),
                'label': row['role'] or 'LINK', 'properties': {'role': row['role'], 'source': row.get('origin', '')}}
        if edge['source'] not in node_map or edge['target'] not in node_map:
            document['limited'] = True
            continue
        if edge['id'] in edge_map or len(edge_map) < MAX_EDGES:
            edge_map[edge['id']] = edge
        else:
            document['limited'] = True
    document['nodes'] = sorted(node_map.values(), key=lambda row: row['id'])
    document['edges'] = sorted(edge_map.values(), key=lambda row: row['id'])
    return document


def base_document(entry, engine_name):
    plan = entry['plan']
    return {'dataset_id': entry['dataset'], 'engine': engine_name, 'nodes': [], 'edges': [],
        'scope': 'result', 'limited': False, 'available': plan.intent in GRAPH_INTENTS,
        'anchor': plan.node_id if plan.intent in ('neighbors', 'reach') else None,
        'limits': {'nodes': MAX_NODES, 'edges': MAX_EDGES, 'per_expansion': EXPAND_EDGES},
        'message': 'Vista posterior a la medición. Las flechas indican la dirección almacenada de cada relación.'}


def result_graph(entry, engine_name, engine):
    plan = entry['plan']
    result = entry['results'][engine_name]
    if 'error' in result:
        raise GraphRequestError('El motor no devolvió un resultado válido. Repite la comparación.')
    document = base_document(entry, engine_name)
    rows = result['rows']
    if not document['available']:
        document['message'] = ('Esta consulta devuelve valores agregados, no nodos ni relaciones. '
                               'Prueba una búsqueda o una consulta de vecinos para ver su grafo.')
        if plan.intent == 'reach':
            document['message'] += ' Puedes explorar aparte el vecindario del nodo de origen; no representa todos los caminos contados.'
        return document
    ids = {uid(row['id']) for row in rows}
    edge_rows = []
    if plan.intent == 'neighbors':
        ids.add(uid(plan.node_id))
        edge_ids = sorted({uid(row['edge_id']) for row in rows})
        if edge_ids:
            edge_rows = engine.query('MATCH (a:Record)-[r:LINK]->(b:Record) '
                'WHERE r.uid IN $edge_ids RETURN ' + EDGE_FIELDS + ' ORDER BY id LIMIT 51', {'edge_ids': edge_ids})
        document['message'] = ('Nodo de origen y relaciones de las filas devueltas (máximo 50). '
            'Las flechas muestran su dirección real, incluso si la búsqueda de vecinos era sin dirección.')
    else:
        document['message'] = ('Nodos de las filas devueltas. La consulta no devuelve relaciones; '
            'selecciona un nodo y explora sus conexiones por separado.')
    nodes = read_nodes(engine, ids)
    annotations = {uid(row['id']): {key: value for key, value in row.items()
                   if key not in ('id', 'name', 'kind', 'country', 'edge_id', 'role')} for row in rows}
    for node in nodes:
        node['in_result'] = node['id'] in annotations
        node['result_values'] = annotations.get(node['id'], {})
    return merge_graph(document, nodes, edge_rows)


def expand_graph(entry, engine_name, engine, node_id):
    node_id = uid(node_id)
    document = entry['graphs'].get(engine_name)
    if document is None:
        raise GraphRequestError('Carga primero el grafo del resultado.')
    allowed = {node['id'] for node in document['nodes']}
    if document['anchor']:
        allowed.add(document['anchor'])
    if node_id not in allowed:
        raise GraphRequestError('Solo puedes expandir nodos del grafo de esta comparación.')
    if len(document['nodes']) >= MAX_NODES or len(document['edges']) >= MAX_EDGES:
        document['limited'] = True
        document['message'] = 'Límite de exploración alcanzado. Ejecuta una consulta de vecinos más concreta.'
        return document
    pattern = '(n:Record)-[r:LINK]->(m:Record)' if entry['dataset'] == 'small' else '(n:Record)-[r:LINK]-(m:Record)'
    # Return physical endpoints, not traversal direction. Projection is supported by both engines.
    query = ('MATCH ' + pattern + ' WHERE n.uid = $id RETURN '
        'startNode(r).uid AS source, endNode(r).uid AS target, r.uid AS id, '
        'r.role AS role, r.source AS origin ORDER BY id LIMIT 51')
    rows = engine.query(query, {'id': node_id})
    document = copy.deepcopy(document)
    document['limited'] = document['limited'] or len(rows) > EXPAND_EDGES
    rows = rows[:EXPAND_EDGES]
    ids = {node_id}
    for row in rows:
        ids.update((uid(row['source']), uid(row['target'])))
    nodes = read_nodes(engine, ids)
    previous = {node['id']: node for node in document['nodes']}
    for node in nodes:
        if node['id'] in previous:
            node.update({key: previous[node['id']][key] for key in ['in_result', 'result_values'] if key in previous[node['id']]})
        else:
            node['in_result'] = False
    document['available'] = True
    document['scope'] = 'exploration'
    document['message'] = ('Exploración adicional, fuera del resultado y de los tiempos medidos. '
        'Máximo 50 relaciones por expansión; flechas con dirección real. '
        + ('En Epinions se siguen enlaces salientes de confianza.' if entry['dataset'] == 'small' else 'Se exploran conexiones entrantes y salientes.'))
    return merge_graph(document, nodes, rows)

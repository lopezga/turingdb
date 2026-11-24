"""Shared, bounded, read-only query plans. No generated Cypher is executed."""
import re
import unicodedata
from typing import Literal
from pydantic import BaseModel, Field


class Plan(BaseModel):
    intent: Literal['nodes', 'edges', 'countries', 'trusted', 'hubs', 'search', 'neighbors', 'reach', 'unsupported']
    term: str = Field(default='', max_length=120)
    node_id: str = Field(default='', pattern=r'^[0-9]*$')
    hops: int = Field(default=2, ge=1, le=3)


EXAMPLES = ['¿Cuántos nodos hay?', '¿Cuántas relaciones hay?',
            '¿Qué países tienen más entidades?', '¿Cuáles son los nodos más conectados?',
            'Busca entidades llamadas "MOSSACK"', 'Vecinos del nodo 10000001',
            'Alcance a 2 saltos del nodo 10000001']


def dataset_examples(dataset='full'):
    if dataset == 'full':
        return EXAMPLES
    return ['¿Cuántos nodos hay?', '¿Cuántas relaciones hay?',
            '¿Qué usuarios reciben más confianza?', '¿Cuáles son los nodos más conectados?',
            'Busca usuarios llamados "Usuario 1"', 'Vecinos del nodo 0',
            'Alcance a 2 saltos del nodo 0']


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn')


def rule_plan(question):
    q = normalize(question)
    ids = re.findall(r'\b[0-9]+\b', q)
    anchor = re.search(r'(?:nodo|usuario)\s+([0-9]+)\b', q)
    if anchor:
        ids = [anchor[1]]
    if 'alcance' in q or 'saltos' in q:
        if not ids:
            raise ValueError('Indica el ID del nodo; puedes obtenerlo con una búsqueda.')
        hops = re.search(r'\b(\d+)\s+saltos?', q)
        return Plan(intent='reach', node_id=ids[-1], hops=int(hops[1]) if hops else 2)
    if 'vecin' in q or ('conexiones' in q and ids):
        if not ids:
            raise ValueError('Indica el ID del nodo.')
        return Plan(intent='neighbors', node_id=ids[-1])
    if 'busca' in q or 'llamad' in q:
        term = re.search(r'["“](.+?)["”]', question)
        if not term:
            raise ValueError('Escribe el nombre entre comillas, por ejemplo: Busca "MOSSACK".')
        return Plan(intent='search', term=term[1])
    if 'pais' in q or 'countries' in q:
        return Plan(intent='countries')
    if 'reciben' in q and 'confianza' in q:
        return Plan(intent='trusted')
    if 'conectad' in q or 'intermediari' in q or 'ranking' in q:
        return Plan(intent='hubs')
    if 'relacion' in q or 'aristas' in q:
        return Plan(intent='edges')
    if 'cuantos' in q or 'total' in q:
        return Plan(intent='nodes')
    raise ValueError('Pregunta fuera del catálogo. Usa un ejemplo o activa Ollama para interpretar otras formulaciones.')


def compile_plan(plan, dataset='full'):
    if plan.intent == 'unsupported':
        raise ValueError('La pregunta no está cubierta por el catálogo. Prueba uno de los ejemplos disponibles.')
    if plan.intent in ('neighbors', 'reach') and not plan.node_id:
        raise ValueError('La consulta necesita un ID de nodo.')
    if plan.intent == 'search' and not plan.term.strip():
        raise ValueError('La búsqueda necesita un nombre.')
    if dataset == 'small' and plan.intent == 'countries':
        raise ValueError('Epinions no contiene países. Usa el ranking de confianza.')
    if dataset == 'full' and plan.intent == 'trusted':
        raise ValueError('El ranking de confianza corresponde al dataset Epinions.')
    queries = {
        'nodes': 'MATCH (n:Record) RETURN count(n) AS total',
        'edges': 'MATCH (:Record)-[r:LINK]->(:Record) RETURN count(r) AS total',
        'countries': "MATCH (n:Record) WHERE n.kind = 'Entity' RETURN n.country AS country, count(n) AS total ORDER BY total DESC, country ASC LIMIT 20",
        'hubs': 'MATCH (n:Record)-[r:LINK]-(:Record) RETURN n.uid AS id, n.name AS name, count(r) AS degree ORDER BY degree DESC, id ASC LIMIT 20',
        'search': 'MATCH (n:Record) WHERE n.name_search CONTAINS $term RETURN n.uid AS id, n.name AS name, n.kind AS kind, n.country AS country ORDER BY id LIMIT 50',
        'neighbors': 'MATCH (n:Record)-[r:LINK]-(m:Record) WHERE n.uid = $id RETURN m.uid AS id, m.name AS name, r.role AS role, r.uid AS edge_id ORDER BY id, edge_id LIMIT 50',
        'reach': f'MATCH (n:Record)-[:LINK*1..{plan.hops}]-(m:Record) WHERE n.uid = $id RETURN count(DISTINCT m.uid) AS total',
        'trusted': 'MATCH (:Record)-[r:LINK]->(n:Record) RETURN n.uid AS id, count(r) AS trust_count ORDER BY trust_count DESC, id ASC LIMIT 20',
    }
    if dataset == 'small':
        queries['neighbors'] = 'MATCH (n:Record)-[r:LINK]->(m:Record) WHERE n.uid = $id RETURN m.uid AS id, m.name AS name, r.role AS role, r.uid AS edge_id ORDER BY id, edge_id LIMIT 50'
        queries['reach'] = f'MATCH (n:Record)-[:LINK*1..{plan.hops}]->(m:Record) WHERE n.uid = $id RETURN count(DISTINCT m.uid) AS total'
    params = {'term': normalize(plan.term)} if plan.intent == 'search' else ({'id': plan.node_id} if plan.intent in ('neighbors', 'reach') else {})
    return queries[plan.intent], params

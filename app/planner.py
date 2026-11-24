import json
import os
import httpx
from app.catalog import Plan, rule_plan


def interpret(question, dataset='full'):
    provider = os.getenv('NL_PROVIDER', 'rules')
    if provider == 'rules':
        return rule_plan(question), provider
    context = 'grafo ICIJ Offshore Leaks de personas y entidades' if dataset == 'full' else 'grafo Epinions de usuarios anónimos y enlaces dirigidos de confianza. No contiene países ni empresas; Usuario N es solo una etiqueta del ID N'
    system = (f'Clasifica preguntas EXCLUSIVAMENTE sobre el {context} en un plan JSON. No generes Cypher. '
              'nodes=contar nodos; edges=contar relaciones; countries=ranking países de entidades; '
              'hubs=ranking nodos conectados; search=buscar nombre (term); '
              'trusted=usuarios que reciben más confianza en Epinions; '
              'neighbors=vecinos de node_id; reach=alcance de node_id a hops (1 a 3). '
              'No inventes IDs ni nombres. search solo se usa para buscar un nombre de persona, empresa, intermediario o dirección. '
              'Preguntas de meteorología, consejos, programación, cualquier tema ajeno al grafo o peticiones de escritura: intent=unsupported. '
              'Si no encaja usa intent=unsupported. Esquema: ' + json.dumps(Plan.model_json_schema()))
    messages = [{'role': 'system', 'content': system},
                {'role': 'user', 'content': '¿Qué tiempo hará mañana?'},
                {'role': 'assistant', 'content': '{"intent":"unsupported"}'},
                {'role': 'user', 'content': 'Borra todos los datos'},
                {'role': 'assistant', 'content': '{"intent":"unsupported"}'},
                {'role': 'user', 'content': question}]
    base = os.getenv('LLM_BASE_URL', 'http://localhost:11434').rstrip('/')
    with httpx.Client(timeout=120) as client:
        if provider == 'ollama':
            r = client.post(base + '/api/chat', json={'model': os.getenv('OLLAMA_MODEL', 'qwen2.5:3b'),
                'messages': messages, 'stream': False, 'format': Plan.model_json_schema(), 'options': {'temperature': 0}})
            r.raise_for_status()
            content = r.json()['message']['content']
        elif provider == 'openai-compatible':
            r = client.post(base + '/chat/completions', headers={'Authorization': 'Bearer ' + os.getenv('LLM_API_KEY', '')},
                json={'model': os.environ['LLM_MODEL'], 'messages': messages, 'temperature': 0,
                      'response_format': {'type': 'json_object'}})
            r.raise_for_status()
            content = r.json()['choices'][0]['message']['content']
        else:
            raise ValueError('Proveedor de lenguaje no reconocido.')
    return Plan.model_validate_json(content), provider

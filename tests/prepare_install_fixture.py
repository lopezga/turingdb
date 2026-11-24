"""Prepare an isolated tiny install for manual Docker integration testing."""
import json
import shutil
import secrets
from pathlib import Path
from tools.dataset import sha256


def main():
    root = Path(__file__).resolve().parent.parent
    target = root / '.installer-test'
    if target.exists():
        raise ValueError('La carpeta de prueba ya existe; se conserva sin cambios.')
    target.mkdir()
    for name in ['create.py', 'compose.yaml', 'Dockerfile', 'Dockerfile.turing', 'requirements.txt', '.dockerignore']:
        shutil.copy2(root / name, target / name)
    for name in ['app', 'tools', 'web']:
        shutil.copytree(root / name, target / name, ignore=shutil.ignore_patterns('__pycache__'))
    canonical = target / 'data/canonical'
    canonical.mkdir(parents=True)
    rows = [
        {'type': 'node', 'id': str(i), 'labels': ['Record'], 'properties': {
            'uid': str(i), 'name': name, 'name_search': name.lower(), 'kind': 'Entity',
            'country': 'Spain', 'jurisdiction': '', 'source': 'installer-test'}}
        for i, name in [(1, 'A'), (2, 'B')]]
    rows.append({'type': 'relationship', 'id': '0', 'label': 'LINK', 'start': {'id': '1'},
        'end': {'id': '2'}, 'properties': {'uid': '0', 'role': 'test', 'source': 'installer-test'}})
    graph = canonical / 'graph.jsonl'
    graph.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    (canonical / 'manifest.json').write_text(json.dumps({'nodes': 2, 'edges': 1, 'graph_sha256': sha256(graph)}))
    (target / '.env').write_text('NEO4J_PASSWORD=' + secrets.token_urlsafe(24) +
        '\nDATA_DIR=./data\nNL_PROVIDER=rules\nAPI_PORT=8011\nNEO4J_HTTP_PORT=7485\nNEO4J_BOLT_PORT=7698\n')
    print(target)


if __name__ == '__main__':
    main()

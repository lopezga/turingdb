"""Export the canonical dataset and manifest as one portable, verified ZIP."""
import argparse
import json
import zipfile
from pathlib import Path
from tools.dataset import sha256


def export(root, output):
    canonical = Path(root) / 'canonical'
    manifest = json.loads((canonical / 'manifest.json').read_text())
    if sha256(canonical / 'graph.jsonl') != manifest['graph_sha256']:
        raise ValueError('El grafo no coincide con el manifiesto')
    output = Path(output)
    if output.exists():
        raise ValueError('El archivo de destino ya existe')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for name in ['graph.jsonl', 'manifest.json']:
            archive.write(canonical / name, arcname=name)
    print(f'Exportado: {output}')


def restore(root, source):
    canonical = Path(root) / 'canonical'
    canonical.mkdir(parents=True, exist_ok=True)
    if any(canonical.iterdir()):
        raise ValueError('La carpeta canonical debe estar vacía')
    with zipfile.ZipFile(source) as archive:
        if set(archive.namelist()) != {'graph.jsonl', 'manifest.json'}:
            raise ValueError('Paquete no reconocido')
        manifest = json.loads(archive.read('manifest.json'))
        # Extract only fixed names; never use archive-supplied filesystem paths.
        import shutil
        for name in ['graph.jsonl', 'manifest.json']:
            with archive.open(name) as src, (canonical / name).open('wb') as dst:
                shutil.copyfileobj(src, dst)
    if sha256(canonical / 'graph.jsonl') != manifest['graph_sha256']:
        raise ValueError('El paquete está corrupto: no cargues estos datos')
    print('Restaurado y verificado. Ejecuta tools.load para cada motor y tools.verify.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['export', 'restore'])
    parser.add_argument('archive')
    parser.add_argument('--root', default='data')
    args = parser.parse_args()
    (export(args.root, args.archive) if args.action == 'export' else restore(args.root, args.archive))

#!/usr/bin/env python3
"""Prepare the demo using existing Docker + Compose; never install Docker or WSL."""
import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GIB = 1024 ** 3


def run(command, capture=False):
    result = subprocess.run(command, cwd=ROOT, text=True, encoding='utf-8', errors='replace',
                            stdout=subprocess.PIPE if capture else None, check=True)
    return result.stdout.strip() if capture else None


def docker_path():
    executable = shutil.which('docker')
    if not executable and os.name == 'nt':
        fallbacks = [Path('C:/Program Files/Docker/Docker/resources/bin/docker.exe'),
                     Path(os.getenv('LOCALAPPDATA', '')) / 'Programs/DockerDesktop/resources/bin/docker.exe']
        executable = next((str(path) for path in fallbacks if path.is_file()), None)
    if not executable:
        if os.name == 'nt':
            raise ValueError('No se encuentra Docker en Windows. Si utilizas Docker Engine dentro de WSL, ejecuta python3 create.py desde esa distribución WSL. Este script no instala Docker Desktop.')
        raise ValueError('No se encuentra docker en el PATH de Linux/WSL. Utiliza la distribución y el entorno donde funciona vuestro Docker Engine + Compose. Este script no instala Docker ni Docker Desktop.')
    return executable


def choose_profile(memory, requested):
    if memory < 12 * GIB:
        raise ValueError('Docker necesita al menos 12 GiB disponibles para este dataset completo. Aumenta la memoria de Docker/WSL o utiliza un equipo con más RAM.')
    selected = ('full' if memory >= 15 * GIB else 'compact') if requested == 'auto' else requested
    if selected == 'full' and memory < 15 * GIB:
        raise ValueError('El perfil full requiere al menos 15 GiB disponibles para Docker. Usa --profile compact.')
    return selected


def read_env(path):
    result = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                result[key.strip()] = value.strip().strip('\"\'')
    return result


def apply_resources(settings, profile, cpus):
    settings = dict(settings)
    settings.update({'ENGINE_MEMORY': '8g' if profile == 'full' else '5g',
        'ENGINE_CPUS': str(max(1, min(4, cpus))), 'NEO4J_HEAP_INITIAL': '1G',
        'NEO4J_HEAP_MAX': '3G' if profile == 'full' else '1536M',
        'NEO4J_PAGECACHE': '3G' if profile == 'full' else '1536M'})
    if profile == 'compact' and settings.get('NL_PROVIDER') == 'ollama':
        settings['NL_PROVIDER'] = 'rules'
    return settings


def main():
    parser = argparse.ArgumentParser(description='Prepara y arranca GraphScope con Docker + Compose existentes; no instala Docker Desktop ni modifica WSL. Conserva bases existentes.')
    parser.add_argument('--check', action='store_true', help='Solo comprobar requisitos; no modifica archivos ni servicios.')
    parser.add_argument('--profile', choices=['auto', 'full', 'compact'], default='auto')
    parser.add_argument('--project', default=None, help='Proyecto Compose nuevo para una instalación aislada, por ejemplo graphscope-demo.')
    args = parser.parse_args()
    docker = docker_path()
    try:
        info = json.loads(run([docker, 'info', '--format', '{{json .}}'], capture=True))
    except subprocess.CalledProcessError as exc:
        raise ValueError('No se puede acceder al motor Docker. Comprueba docker info en esta misma consola y el contexto/permisos autorizados por IT. No se instala ni inicia ningún motor automáticamente.') from exc
    if info.get('OSType') != 'linux':
        raise ValueError('Docker debe estar configurado para contenedores Linux.')
    run([docker, 'compose', 'version'], capture=True)
    memory = int(info['MemTotal'])
    envpath = ROOT / '.env'
    existing = read_env(envpath)
    # Keep credentials but adapt managed memory/CPU settings to this Docker VM.
    profile = choose_profile(memory, args.profile)
    datadir = Path(existing.get('DATA_DIR', './data'))
    if not datadir.is_absolute():
        datadir = ROOT / datadir
    if shutil.disk_usage(ROOT).free < 8 * GIB or (datadir.exists() and shutil.disk_usage(datadir).free < 8 * GIB):
        raise ValueError('Se necesitan al menos 8 GiB libres en las unidades de la carpeta y los datos. Docker necesita espacio adicional en su propio disco.')
    print(f'Docker: {memory/GIB:.1f} GiB RAM, {info.get("NCPU")} CPU. Perfil: {profile}.', flush=True)
    print('Disco recomendado: al menos 20 GiB libres para Docker y 8 GiB en la carpeta de datos.', flush=True)
    print('Se mantienen credenciales; se ajustan RAM/CPU al perfil. Compact usa el catálogo sin LLM local.' if envpath.exists() else 'Se generarán credenciales locales y ajustes por defecto.', flush=True)
    if args.check:
        print('Comprobación previa correcta. No se han modificado archivos ni servicios. La compatibilidad final se verifica durante la instalación.')
        return
    if not envpath.exists():
        settings = {'NEO4J_PASSWORD': secrets.token_urlsafe(24), 'DATA_DIR': './data',
            'NL_PROVIDER': 'ollama' if profile == 'full' else 'rules',
            'OLLAMA_MODEL': 'qwen2.5:3b', 'LLM_BASE_URL': 'http://ollama:11434'}
        with envpath.open('x', encoding='utf-8') as file:
            file.write('\n'.join(f'{k}={v}' for k, v in settings.items()) + '\n')
        if os.name != 'nt':
            envpath.chmod(0o600)
        existing = settings
    if not existing.get('NEO4J_PASSWORD'):
        raise ValueError('Falta NEO4J_PASSWORD en .env; no se cambia la contraseña de bases existentes automáticamente.')
    updated = apply_resources(existing, profile, int(info.get('NCPU', 4)))
    # Replace only managed keys; retain comments and unrelated settings verbatim.
    managed = ['ENGINE_MEMORY', 'ENGINE_CPUS', 'NEO4J_HEAP_INITIAL', 'NEO4J_HEAP_MAX', 'NEO4J_PAGECACHE', 'NL_PROVIDER']
    lines = envpath.read_text(encoding='utf-8-sig').splitlines()
    lines = [line for line in lines if line.split('=', 1)[0].strip() not in managed]
    lines += [f'{key}={updated[key]}' for key in managed if key in updated]
    envpath.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    existing = updated
    compose = [docker, 'compose']
    if args.project:
        compose += ['-p', args.project]
    if existing.get('NL_PROVIDER', 'rules') == 'ollama':
        compose += ['--profile', 'ai']
    run(compose + ['config', '--quiet'])
    run(compose + ['build'])
    def task(*arguments, capture=False):
        return run(compose + ['run', '--rm', '--no-deps', '-T', 'api', 'python', *arguments], capture=capture)
    # The image filesystem resides on Docker's disk, which can be a different drive.
    free = int(task('-c', 'import shutil; print(shutil.disk_usage("/").free)', capture=True))
    if free < 20 * GIB:
        raise ValueError('El disco de Docker tiene menos de 20 GiB libres. Libera espacio o cambia la ubicación de su disco virtual; no se han importado bases.')
    canonical = datadir / 'canonical'
    graph, manifest = canonical / 'graph.jsonl', canonical / 'manifest.json'
    if graph.exists() != manifest.exists():
        raise ValueError('Dataset parcial: falta graph.jsonl o manifest.json. Conserva esa carpeta y restaura el paquete en otra carpeta vacía.')
    if not graph.exists():
        archive = datadir / 'portable' / 'graphscope-icij.zip'
        if archive.exists():
            task('-m', 'tools.portable', 'restore', '/app/data/portable/graphscope-icij.zip')
        else:
            print('No hay dataset portable: se descargará ICIJ completo desde su fuente oficial.', flush=True)
            task('-m', 'tools.dataset', '--profile', 'full')
    # Validate the canonical artifact even when both stores already contain data.
    task('-c', 'import json; from pathlib import Path; from tools.dataset import sha256; p=Path("data/canonical"); m=json.loads((p/"manifest.json").read_text()); assert sha256(p/"graph.jsonl")==m["graph_sha256"], "Hash del grafo incorrecto"')
    small_graph = datadir / 'small' / 'graph.jsonl'
    small_manifest = datadir / 'small' / 'manifest.json'
    if small_graph.exists() != small_manifest.exists():
        raise ValueError('Dataset Epinions parcial. Conserva esa carpeta y prepara los archivos completos en otra carpeta vacía.')
    if not small_graph.exists():
        task('-m', 'tools.epinions')
    task('-c', 'import json; from pathlib import Path; from tools.dataset import sha256; p=Path("data/small"); m=json.loads((p/"manifest.json").read_text()); assert sha256(p/"graph.jsonl")==m["graph_sha256"], "Hash Epinions incorrecto"')
    run(compose + ['up', '-d', 'neo4j', 'turingdb', 'neo4j-small', 'turingdb-small'])
    if profile == 'compact':
        run(compose + ['--profile', 'ai', 'stop', 'ollama'])
    for dataset in ['full', 'small']:
        probe = task('-m', 'tools.install_probe', '--dataset', dataset, capture=True)
        state = json.loads(probe)
        for engine in ['neo4j', 'turingdb']:
            if state[engine] == 'empty':
                task('-m', 'tools.load', engine, '--dataset', dataset)
            else:
                print(f'{dataset}/{engine}: contiene datos; se conserva y se verificará íntegramente.', flush=True)
        task('-m', 'tools.verify', '--dataset', dataset)
    if existing.get('NL_PROVIDER') == 'ollama':
        run(compose + ['up', '-d', 'ollama'])
        run(compose + ['exec', '-T', 'ollama', 'ollama', 'pull', existing.get('OLLAMA_MODEL', 'qwen2.5:3b')])
    run(compose + ['up', '-d', 'api'])
    for _ in range(60):
        try:
            task('-c', 'import json,urllib.request; r=json.load(urllib.request.urlopen("http://api:8000/api/status",timeout=30)); assert all(e["ready"] and e["counts"][0]["total"]==r["dataset"]["nodes"] for e in r["engines"].values()), "Los motores no están listos"')
            break
        except subprocess.CalledProcessError:
            time.sleep(2)
    else:
        raise ValueError('La API no responde. Consulta docker compose logs api.')
    print(f'\nInstalación verificada. Abre http://localhost:{existing.get("API_PORT", "8000")}\nLas bases y el modelo quedan en volúmenes Docker. No se han borrado datos.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f'\nInstalación detenida: {exc}\nCorrige el problema y vuelve a ejecutar create.py. Las bases existentes se conservan.', file=sys.stderr)
        sys.exit(1)

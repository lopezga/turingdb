# Llevar GraphScope a otro ordenador

## Instalación desde Git

Publica el código en un repositorio privado autorizado por tu organización. `.gitignore` excluye las credenciales de `.env`, entornos locales, datasets, informes, archivos comprimidos y estado del instalador. `.env.example` contiene únicamente valores de ejemplo y sí debe versionarse.

En el PC de destino, con Git instalado o proporcionado por IT:

```powershell
git clone <URL-DEL-REPOSITORIO> GraphScope
cd GraphScope
.\install.cmd -CheckOnly
.\install.cmd
```

Sustituye `<URL-DEL-REPOSITORIO>` por la URL real. El instalador genera la configuración local y descarga y prepara los dos datasets si no existen. Después reconstruye y verifica las bases; no necesitas llevar los volúmenes de Docker del PC original. La primera ejecución puede tardar por las descargas y las importaciones.

Clonar el código no elimina las descargas necesarias para instalar dependencias, imágenes Docker, datasets y, si se utiliza, el modelo local. Si las políticas corporativas restringen esas fuentes, IT debe autorizarlas o proporcionar los recursos mediante sus canales internos. No ejecutes el instalador si la instalación de estos componentes no está autorizada.

Para futuras actualizaciones, detén los servicios, ejecuta `git pull --ff-only` y arranca con `.\scripts\start.ps1`. Los datos y `.env` locales se conservan. Si una actualización cambia el formato de datos o el esquema, consulta sus instrucciones de migración antes de aplicarla.

## Instalador completo para Windows

En un PC Windows x64, copia la carpeta a una unidad local y ejecuta **install.cmd** (doble clic, PowerShell o CMD). No necesita que Python ni Docker esten instalados previamente:

```powershell
.\install.cmd
```

Comprueba Windows, virtualizacion, CPU, memoria y disco; prepara WinGet si falta mediante el modulo oficial de Microsoft; instala Python 3.12 para el usuario actual, activa los componentes WSL2 y prepara Docker Desktop. Despues ejecuta create.py, que construye los servicios, prepara ambos datasets, carga las bases vacias, verifica el contenido y arranca la demo. Git, Java, Neo4j y Ollama no necesitan instalarse directamente en Windows: las dependencias de la aplicacion se ejecutan en contenedores.

Para revisar requisitos **sin instalar ni cambiar archivos o arrancar servicios**:

```powershell
.\install.cmd -CheckOnly
```

Para preparar solamente los requisitos del sistema, sin importar los datasets:

```powershell
.\install.cmd -PrerequisitesOnly
```

Tambien admite `-Profile compact` o `-Profile full`, que se pasan a create.py. Desde una consola PowerShell que ya permita scripts se puede invocar directamente `scripts/setup-windows.ps1` con las mismas opciones.

### Permisos, reinicios y politicas

- La fase principal permanece en la cuenta del usuario. Solo los componentes de Windows, WSL y el ajuste del servicio privilegiado pueden solicitar elevacion UAC. No instala Python ni configura Docker en el perfil de otra cuenta administradora.
- Si faltan componentes WSL2 y Windows exige reiniciar, termina con codigo 3010 y guarda el estado en .setup. **Guarda tu trabajo, reinicia y ejecuta install.cmd otra vez.** No reinicia Windows ni registra una tarea para reanudarse al iniciar sesion. Volver a ejecutarlo sin haber reiniciado detecta ese estado y evita repetir la fase.
- Si Docker pide aceptar sus condiciones o completar la configuracion inicial, hazlo en su ventana y repite el script si se detiene. La organizacion debe autorizar Docker Desktop y disponer de la licencia que corresponda. WinGet usa la fuente oficial y acepta los acuerdos de instalacion de los paquetes; no se pasan claves ni credenciales de empresa.
- No cambia la politica de ejecucion de PowerShell, no desactiva seguridad y no sortea restricciones de empresa. Si Windows bloquea scripts, Microsoft Store, WinGet, PSGallery o Docker, IT debe autorizar la instalacion o proporcionar un script firmado/paquetes corporativos.
- La virtualizacion de BIOS/UEFI, el hardware insuficiente y una version de Windows no compatible requieren una accion manual; el script los detecta y explica el bloqueo. No puede instalar RAM, espacio en disco ni soporte de virtualizacion.

### Recursos y arranque manual

El instalador completo de Windows exige un minimo conservador de 24 GB de RAM fisica para los dos datasets (32 GB recomendados), dos CPU logicas, 8 GiB libres en la unidad del proyecto y 25 GiB libres en la unidad de Windows. Reserva mas espacio para imagenes, logs y crecimiento. create.py comprueba ademas los 12 GiB minimos disponibles para Docker y 20 GiB libres en su disco despues de construir las imagenes. Estos umbrales son comprobaciones previas, no garantias para cualquier consulta.

Si Docker dispone de menos de 12 GiB y no hay otros trabajos activos, puede aumentar la memoria global WSL2 en .wslconfig, dejando al menos unos 6 GiB a Windows y con un maximo de 24 GiB para WSL. Conserva las otras opciones y una copia .wslconfig.graphscope-backup. Esto afecta a todas las distribuciones WSL: si detecta otros contenedores o distribuciones activas se detiene antes de apagarlos, para que el usuario los cierre primero.

El script desactiva el inicio automatico de Docker Desktop para el usuario, mantiene com.docker.service en modo manual cuando requiere corregirlo y conserva restart: "no" en los servicios del proyecto. Inicia Docker y la demo solo durante la instalacion solicitada; no los agrega al arranque del PC. Si la instalacion se detiene despues de arrancar Docker, puede quedar abierto: cierralo manualmente cuando termines.

Las bases existentes se conservan. Si una carga quedo parcial o no coincide, create.py se detiene sin borrarla; consulta la seccion de reintentos mas abajo. No copies .setup ni .env a otra persona: el primero es estado local del instalador y el segundo contiene la contrasena. Puedes omitir tambien .venv, .git, .installer-test y data/sdk.

### Validacion del bootstrap de Windows

Se han probado el diagnostico real en este equipo con Docker detenido y 23 aserciones con Windows PowerShell 5.1: hardware, indicadores de virtualizacion, RAM/disco, dependencias ausentes, reanudacion tras reinicio, conservacion de opciones WSL, rechazo de motores Docker remotos, inicio manual y JSON sin BOM. El instalador exige un contexto Docker Desktop local para no modificar servidores de empresa por error. No se ha ejecutado una instalacion limpia de Windows en otro equipo; las fases que requieren UAC/instalar paquetes se han revisado y sus decisiones se han probado sin reinstalar componentes ni modificar este PC.

Fuentes oficiales: [instalacion de Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), [instalacion de WSL](https://learn.microsoft.com/en-us/windows/wsl/install), [WinGet y su bootstrap oficial](https://learn.microsoft.com/en-us/windows/package-manager/winget/).

## Instalador del proyecto cuando Python y Docker ya existen

**Actualización de datasets:** el instalador configura ahora dos pares independientes de bases: Offshore Leaks y Epinions (75.879 usuarios y 508.837 enlaces). Copia también `data/small/graph.jsonl` y `data/small/manifest.json` para no descargar Epinions; si faltan, se descarga desde Stanford SNAP. Los umbrales de RAM son comprobaciones previas, no reservas ni garantías: cuatro motores comparten Docker y aumentan el consumo total respecto a la versión inicial. El perfil compacto con ambos grafos completos no se ha validado en una VM de 12 GiB.

Sí: puedes copiar la carpeta y ejecutar **create.py**. La primera instalación reconstruye las bases desde el grafo común; no copia los volúmenes internos del equipo de origen. Descarga las imágenes Docker y, cuando corresponde, el modelo local.

## Requisitos previos

- Python 3.10 o posterior en el equipo anfitrión. El instalador usa solo la biblioteca estándar; no necesitas copiar .venv ni instalar paquetes Python en el anfitrión.
- Docker Desktop con contenedores Linux, abierto y operativo, o Docker Engine + Compose en Linux. En Windows necesita WSL2. El instalador comprueba estas condiciones, pero no instala Docker ni cambia la BIOS ni reinicia Windows.
- Conexión a internet para las imágenes/modelo que aún no estén descargados.
- Al menos 8 GiB libres en las unidades de la carpeta y los datos; el instalador exige además 20 GiB libres en el disco de Docker después de construir las imágenes. Reserva más espacio para crecimiento, logs y copias.

## Qué copiar

Copia el código de la carpeta y **una de estas opciones**:

- data/canonical/graph.jsonl y data/canonical/manifest.json, o
- data/portable/graphscope-icij.zip, el paquete de unos 129 MB ya preparado.

Puedes omitir .venv, .git, __pycache__, .installer-test y data/sdk. No compartas .env con otras personas: si no lo copias, el instalador genera una contraseña nueva. Si lo conservas para reutilizar una instalación, mantiene sus credenciales. Comprueba DATA_DIR si contenía una ruta absoluta del equipo anterior. Si no hay datos locales ni paquete portable, descargará y normalizará ICIJ completo desde su fuente oficial.

## Ejecutar

Los servicios tienen `restart: "no"`: se arrancan manualmente. El instalador no registra tareas de inicio con Windows. Docker Desktop tiene su propia opción de inicio de sesión; en este equipo se ha desactivado también esa entrada de arranque.

En PowerShell o CMD, dentro de la carpeta copiada:

```text
python create.py
```

En Linux o en una distribución WSL con integración Docker habilitada:

```sh
python3 create.py
# O, sin necesitar marcar el archivo como ejecutable:
sh create.sh
```

Desde WSL la carpeta Windows de este equipo es /mnt/c/Users/Chema/Documents/ChatGPT/TuringDB; en otro equipo cambia según dónde la copies.

Para comprobar requisitos sin modificar archivos ni servicios:

```text
python create.py --check
```

El proceso construye las imágenes, restaura o descarga los datos si faltan, comprueba SHA-256, espera a los motores, importa únicamente bases vacías, compara íntegramente sus contenidos, descarga el modelo si está habilitado y arranca la aplicación. Una importación completa puede tardar varios minutos. Al terminar muestra la URL, normalmente http://localhost:8000.

## Memoria y perfiles

Se usa la **RAM disponible para Docker**, que puede ser bastante menor que la RAM física del ordenador:

| RAM de Docker | Perfil automático | Comportamiento |
|---|---|---|
| Menos de 12 GiB | Se detiene | Solicita aumentar los recursos; no intenta la carga completa. |
| Desde 12 hasta menos de 15 GiB | compact | Mismo dataset; límite de 5 GiB por motor, heap/page cache Neo4j de 1536 MiB cada uno, catálogo de preguntas sin Ollama. |
| Desde 15 GiB | full | Mismo dataset; límite de 8 GiB por motor, heap/page cache Neo4j de 3 GiB cada uno, Ollama en instalaciones nuevas. |

Los límites por servicio no son reservas de memoria: su suma puede superar la RAM de Docker y la viabilidad depende del consumo real y de la consulta. Son umbrales conservadores de admisión, no una garantía para cualquier carga. El perfil compact se ha probado con un fixture pequeño; todavía no se ha validado el dataset completo en una VM con 12 GiB. La demo completa sí se ha validado con unos 15,5 GiB de Docker en este equipo.

Puedes elegir explícitamente --profile compact o --profile full. Se mantiene el proveedor de lenguaje existente, salvo que compact desactiva Ollama para ahorrar RAM. Cada ejecución adapta las variables de RAM/CPU gestionadas por el instalador en .env y conserva las demás; compara benchmarks solo con sus condiciones de recursos documentadas. Ambos motores reciben el mismo límite de memoria y CPU (hasta 4 CPU, según Docker).

## Bases existentes y reintentos

El instalador no borra bases ni volúmenes. Si ya contienen datos, omite la importación y los verifica. Si el contenido es diferente o quedó una carga parcial, se detiene: no mezcla ni reemplaza datos automáticamente. Puedes corregir la causa o utilizar un proyecto Compose nuevo con --project otro-nombre. Si otra demo usa los puertos, configura API_PORT, NEO4J_HTTP_PORT y NEO4J_BOLT_PORT en .env con valores libres antes de arrancar el segundo proyecto.

Para el uso diario después de instalar, basta con scripts/start.ps1 en PowerShell o docker compose --profile ai up -d. Ejecutar create.py de nuevo también verifica íntegramente las bases, por lo que es más lento que el arranque normal.

## Visualización integrada

Las vistas Tabla/Grafo de ambos motores se incluyen en la aplicación: no requieren instalar componentes adicionales. Los límites del dibujo son 150 nodos y 200 relaciones, independientemente del tamaño de las bases. Consulta README.md para los controles y la separación entre exploración visual y tiempos medidos.

## Validación del instalador

Pruebas unitarias de elección de recursos y conservación de credenciales; comprobación real de requisitos en este equipo. La prueba integrada se ejecuta en un proyecto Docker separado con un grafo mínimo: comprueba instalación, carga y verificación sin tocar las bases de la demo. No equivale a haberlo probado en un segundo ordenador físico ni valida todas las combinaciones de hardware.

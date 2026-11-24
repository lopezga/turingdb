"""Keep the documented daemon alive and stop it cleanly on container shutdown."""
import signal
import subprocess
import threading

subprocess.run(['turingdb', '-demon', '-i', '0.0.0.0', '-turing-dir', '/var/lib/turing'], check=True)
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())
stop.wait()
subprocess.run(['turingdb', 'stop', '-turing-dir', '/var/lib/turing'], check=True)

import hashlib, subprocess, json, os
from pathlib import Path
import yaml

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()

def cargar_config(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)

def commit_git(raiz):
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True, timeout=10)
        sucio = subprocess.run(["git", "status", "--porcelain"], cwd=raiz, capture_output=True, text=True, timeout=10)
        if out.returncode != 0:
            return "sin-git"
        return out.stdout.strip() + ("+cambios-sin-commit" if sucio.stdout.strip() else "")
    except Exception:
        return "sin-git"

def escribir_json_atomico(ruta, obj):
    ruta = Path(ruta)
    tmp = ruta.with_name(ruta.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, ruta)   # reemplazo atómico: el tablero ve la versión vieja o la nueva, nunca a medias

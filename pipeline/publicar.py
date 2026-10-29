"""Etapas 8 a 11: candidato inmutable, versión aprobada y puntero atómico current.json."""
import json, os, shutil
from datetime import datetime
from pathlib import Path
from .util import escribir_json_atomico

ARCHIVOS = ["estimaciones.csv", "metricas.csv", "controles.csv", "backtest_detalle.csv", "manifest.json"]


def siguiente_version(pub, hoy=None):
    hoy = hoy or datetime.now()
    pref = f"v{hoy:%Y.%m.%d}-"
    vdir = Path(pub) / "versions"
    n = 1 + len([d for d in vdir.glob(pref + "*") if d.is_dir()]) if vdir.exists() else 1
    return f"{pref}{n:02d}"


def leer_puntero(pub):
    f = Path(pub) / "current.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def publicar(candidato, pub, version, aprobado_en):
    """Copia el candidato a published/versions/<version> (inmutable) y mueve el puntero de forma atómica."""
    pub = Path(pub)
    destino = pub / "versions" / version
    if destino.exists():
        raise FileExistsError(f"La versión {version} ya existe y es inmutable.")
    (pub / "versions").mkdir(parents=True, exist_ok=True)
    tmp = pub / "versions" / f".tmp-{version}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    for a in ARCHIVOS:
        shutil.copy2(Path(candidato) / a, tmp / a)
    os.rename(tmp, destino)
    previo = leer_puntero(pub)
    escribir_json_atomico(pub / "current.json", {
        "version": version, "ruta": f"versions/{version}", "aprobado_en": aprobado_en,
        "run_id": json.loads((destino / "manifest.json").read_text(encoding="utf-8"))["run_id"],
        "version_anterior": previo["version"] if previo else None})
    return destino


def restaurar(pub, version, ahora=None):
    """Vuelve a apuntar current.json a una versión aprobada anterior (la versión no se modifica)."""
    pub = Path(pub)
    destino = pub / "versions" / version
    if not (destino / "manifest.json").exists():
        raise FileNotFoundError(f"No existe la versión {version} en {pub / 'versions'}")
    previo = leer_puntero(pub)
    escribir_json_atomico(pub / "current.json", {
        "version": version, "ruta": f"versions/{version}", "aprobado_en": json.loads((destino / "manifest.json").read_text(encoding="utf-8")).get("aprobado_en"),
        "run_id": json.loads((destino / "manifest.json").read_text(encoding="utf-8"))["run_id"],
        "version_anterior": previo["version"] if previo else None,
        "restaurada_en": (ahora or datetime.now()).isoformat(timespec="seconds")})
    return destino

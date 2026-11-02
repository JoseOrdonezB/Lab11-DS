"""Lectura de la versión aprobada que consulta el tablero (ejercicio 6).

El tablero nunca reajusta modelos: lee `published/current.json` y los archivos de la
versión apuntada. Si no hay versión aprobada o la versión está incompleta, devuelve
None para que la interfaz muestre «estimaciones no disponibles» y conserve la última
versión válida que exista en disco.
"""
from dataclasses import dataclass, field
from pathlib import Path
import json

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PUBLICADO = RAIZ / "published"


@dataclass
class Publicacion:
    version: str
    ruta: Path
    puntero: dict = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)
    metricas: pd.DataFrame = field(default_factory=pd.DataFrame)
    estimaciones: pd.DataFrame = field(default_factory=pd.DataFrame)
    backtest: pd.DataFrame = field(default_factory=pd.DataFrame)
    reporte: str = ""
    monitoreo: dict = field(default_factory=dict)

    @property
    def actualizado_en(self):
        return self.manifest.get("aprobado_en") or self.puntero.get("aprobado_en") or "n/d"

    @property
    def run_id(self):
        return self.manifest.get("run_id") or self.puntero.get("run_id") or "n/d"

    @property
    def mlflow_run_id(self):
        return self.manifest.get("mlflow_run_id") or "n/d"

    @property
    def fuente_hash(self):
        return (self.manifest.get("fuente_hash") or "n/d")[:12]

    @property
    def config_hash(self):
        return (self.manifest.get("config_hash") or "n/d")[:12]


def _leer_json(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def cargar_publicacion(pub_dir=None):
    """Devuelve (Publicacion | None, motivo). No lanza excepciones hacia el tablero."""
    pub_dir = Path(pub_dir) if pub_dir is not None else PUBLICADO
    puntero_path = pub_dir / "current.json"
    if not puntero_path.exists():
        return None, "todavía no existe published/current.json"

    try:
        puntero = _leer_json(puntero_path)
        version = puntero.get("version")
        if not version:
            return None, "current.json no indica versión"
        vdir = pub_dir / (puntero.get("ruta") or f"versions/{version}")
        requeridos = ("manifest.json", "metricas.csv", "estimaciones.csv")
        faltan = [f for f in requeridos if not (vdir / f).exists()]
        if faltan:
            return None, f"la versión {version} está incompleta: faltan {', '.join(faltan)}"

        manifest = _leer_json(vdir / "manifest.json")
        metricas = pd.read_csv(vdir / "metricas.csv")
        estimaciones = pd.read_csv(vdir / "estimaciones.csv", parse_dates=["periodo"])
        backtest = (pd.read_csv(vdir / "backtest_detalle.csv", parse_dates=["periodo"])
                    if (vdir / "backtest_detalle.csv").exists() else pd.DataFrame())
        reporte = ((vdir / "reporte_validacion.md").read_text(encoding="utf-8")
                   if (vdir / "reporte_validacion.md").exists() else "")
        monitoreo = (_leer_json(vdir / "monitoreo.json")
                     if (vdir / "monitoreo.json").exists() else {})

        if version and not manifest.get("aprobado", False):
            return None, f"la versión {version} no está aprobada"
        return Publicacion(version=version, ruta=vdir, puntero=puntero, manifest=manifest,
                           metricas=metricas, estimaciones=estimaciones, backtest=backtest,
                           reporte=reporte, monitoreo=monitoreo), None
    except Exception as e:                     # JSON corrupto, CSV ilegible, etc.
        return None, f"no se pudo leer la versión publicada: {e!r}"


def series_publicadas(pub):
    """Series con estimaciones publicadas, en el orden del config y con Total primero."""
    if pub is None or pub.estimaciones.empty:
        return []
    nombres = list(dict.fromkeys(pub.estimaciones["serie"].astype(str)))
    return sorted(nombres, key=lambda s: (s != "Total", s))


def estado_por_serie(pub):
    """{serie: 'aprobado' | 'referencia'} a partir de las estimaciones publicadas."""
    if pub is None or pub.estimaciones.empty:
        return {}
    return (pub.estimaciones.groupby("serie")["estado"].first().to_dict())

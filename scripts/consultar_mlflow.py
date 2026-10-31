"""Consulta de las ejecuciones registradas en MLflow (ejercicios 4.2 y 4.3).

  python scripts/consultar_mlflow.py listar   [--salida docs/mlflow_ejecuciones.csv]
  python scripts/consultar_mlflow.py comparar [RUN_A RUN_B]

listar:   tabla de todas las ejecuciones: estado, resultado, causa si falló, hashes, commit y métricas de Total.
          Las ejecuciones detenidas antes de la evaluación aparecen sin métricas (no se inventan).
comparar: compara dos ejecuciones con los mismos datos y configuración (mismo hash de fuente y de config).
          Sin argumentos toma las dos más recientes que llegaron a la evaluación. Compara las estimaciones
          y las métricas con la tolerancia de config/pipeline.yaml (reproducibilidad.tolerancia_abs).
"""
import argparse, os, sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
import mlflow
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from pipeline.registro import slug           # noqa: E402
from pipeline.util import cargar_config      # noqa: E402


def conectar(cfg):
    uri = os.environ.get("MLFLOW_TRACKING_URI") or cfg["mlflow"]["tracking_uri"]
    mlflow.set_tracking_uri(uri)
    nombre = cfg["mlflow"]["experimento"] + f"-{slug(cfg['destino'])}"
    exp = mlflow.get_experiment_by_name(nombre)
    if exp is None:
        sys.exit(f"No existe el experimento {nombre} en {uri}. Corra primero: python -m pipeline.run")
    return exp, uri


def ejecuciones(exp):
    return mlflow.search_runs([exp.experiment_id], order_by=["attributes.start_time DESC"])


def listar(cfg, salida):
    exp, uri = conectar(cfg)
    r = ejecuciones(exp)
    if r.empty:
        print("El experimento no tiene ejecuciones."); return 0
    col = lambda c: r[c] if c in r.columns else pd.Series([None] * len(r))
    t = pd.DataFrame({
        "run_local": col("tags.run_id_local"), "mlflow_run_id": r["run_id"], "estado_mlflow": r["status"],
        "inicio": pd.to_datetime(r["start_time"], utc=True).dt.tz_convert(datetime.now().astimezone().tzinfo).dt.strftime("%Y-%m-%d %H:%M:%S"),
        "resultado": col("tags.resultado"), "codigo": col("tags.codigo_salida"), "etapa_final": col("tags.etapa_final"),
        "controles": col("tags.controles_resultado"), "causa": col("tags.causa"),
        "fuente_sha256": col("tags.fuente_sha256").str[:12], "config_sha256": col("tags.config_sha256").str[:12],
        "commit": col("tags.commit_git").str[:12], "version": col("tags.version_publicada"),
        "total_MAE": col("metrics.total_MAE").round(1), "total_ref_MAE": col("metrics.total_ref_MAE").round(1),
        "total_cumple": col("metrics.total_cumple_regla")})
    print(f"Experimento: {exp.name} (id {exp.experiment_id}) en {uri}\n")
    with pd.option_context("display.width", 220, "display.max_columns", 30, "display.max_colwidth", 60):
        print(t.drop(columns=["mlflow_run_id"]).to_string(index=False))
    fallidas = t[t["estado_mlflow"] == "FAILED"]
    print(f"\n{len(t)} ejecuciones · {len(fallidas)} fallidas")
    for _, f in fallidas.iterrows():
        print(f"  - {f['run_local']}: {f['causa']}  (sin métricas de evaluación: se detuvo en {f['etapa_final']})")
    if salida:
        Path(salida).parent.mkdir(parents=True, exist_ok=True)
        t.to_csv(salida, index=False)
        print(f"\nTabla guardada en {salida}")
    return 0


def _estimaciones(run_id):
    ruta = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="candidato/estimaciones.csv")
    return pd.read_csv(ruta)


def comparar(cfg, a, b):
    exp, _ = conectar(cfg)
    r = ejecuciones(exp)
    if not (a and b):
        evaluadas = r[r["metrics.total_MAE"].notna()] if "metrics.total_MAE" in r.columns else r.iloc[0:0]
        if len(evaluadas) < 2:
            sys.exit("Se necesitan al menos dos ejecuciones que hayan llegado a la evaluación.")
        a, b = evaluadas["run_id"].iloc[1], evaluadas["run_id"].iloc[0]       # la anterior y la más reciente
    ra, rb = (r[r["run_id"] == x].iloc[0] for x in (a, b))
    tol = float(cfg.get("reproducibilidad", {}).get("tolerancia_abs", 1e-6))
    print(f"A: {ra['tags.run_id_local']} ({a})\nB: {rb['tags.run_id_local']} ({b})\n")

    mismos = all(ra[f"tags.{k}"] == rb[f"tags.{k}"] for k in ("fuente_sha256", "config_sha256"))
    print(f"Misma fuente y misma configuración: {'sí' if mismos else 'NO'}"
          f"  (fuente {ra['tags.fuente_sha256'][:12]} / {rb['tags.fuente_sha256'][:12]},"
          f" config {ra['tags.config_sha256'][:12]} / {rb['tags.config_sha256'][:12]})")
    print(f"Mismo commit: {'sí' if ra['tags.commit_git'] == rb['tags.commit_git'] else 'no'}")

    ea, eb = _estimaciones(a), _estimaciones(b)
    clave = ["serie", "periodo", "conjunto"]
    m = ea[clave + ["valor"]].merge(eb[clave + ["valor"]], on=clave, how="outer", suffixes=("_a", "_b"), indicator=True)
    solo = int((m["_merge"] != "both").sum())
    dif = (m["valor_a"] - m["valor_b"]).abs()
    print(f"\nEstimaciones: {len(ea)} y {len(eb)} filas, {solo} sin pareja, diferencia máxima {dif.max():.3e} viajeros/mes")
    for serie, d in m.assign(dif=dif).groupby("serie", sort=False)["dif"].max().items():
        print(f"  {serie:<20} {d:.3e}")

    cols = sorted(c for c in r.columns if c.startswith("metrics.") and not c.startswith("metrics.controles"))
    dm = pd.Series({c[8:]: abs(ra[c] - rb[c]) for c in cols if pd.notna(ra[c]) and pd.notna(rb[c])})
    print(f"Métricas: {len(dm)} comparadas, diferencia máxima {dm.max():.3e}")

    ok = mismos and solo == 0 and dif.max() <= tol and dm.max() <= tol
    print(f"\nResultado: {'EQUIVALENTES' if ok else 'DIFERENTES'} (tolerancia {tol:g} viajeros/mes)")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["listar", "comparar"])
    ap.add_argument("runs", nargs="*", help="(comparar) dos mlflow_run_id; si se omiten, las dos últimas evaluadas")
    ap.add_argument("--config", default=str(RAIZ / "config" / "pipeline.yaml"))
    ap.add_argument("--salida", help="(listar) guardar la tabla en un CSV")
    a = ap.parse_args()
    cfg = cargar_config(a.config)
    if a.accion == "listar":
        return listar(cfg, a.salida)
    if len(a.runs) not in (0, 2):
        sys.exit("comparar recibe 0 o 2 identificadores de run")
    return comparar(cfg, *(a.runs or (None, None)))


if __name__ == "__main__":
    sys.exit(main())

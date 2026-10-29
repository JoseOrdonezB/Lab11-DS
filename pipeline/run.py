"""Orquestador. Un comando:  python -m pipeline.run [--config config/pipeline.yaml] [--fuente RUTA]
Restaurar una versión:      python -m pipeline.run --restaurar v2026.10.29-01

Códigos de salida: 0 publicado · 1 error inesperado · 2 detenido por control crítico · 3 candidato rechazado por la regla de aceptación.
"""
import argparse, json, sys, traceback, uuid, platform
from datetime import datetime
from importlib import metadata
from pathlib import Path
import numpy as np
import pandas as pd

from . import controles, modelos, publicar as pub, reporte
from .preparar import leer_fuente
from .util import cargar_config, sha256, commit_git

RAIZ = Path(__file__).resolve().parent.parent


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pipeline del Observatorio de Turismo Sostenible")
    ap.add_argument("--config", default=str(RAIZ / "config" / "pipeline.yaml"))
    ap.add_argument("--fuente", help="ruta de la fuente (sustituye a rutas.fuente del config)")
    ap.add_argument("--restaurar", metavar="VERSION", help="apuntar current.json a una versión aprobada anterior")
    a = ap.parse_args(argv)

    cfg_path = Path(a.config)
    cfg = cargar_config(cfg_path)
    base = Path.cwd()
    pub_dir = base / cfg["rutas"]["publicacion"]

    if a.restaurar:
        pub.restaurar(pub_dir, a.restaurar)
        print(f"current.json apunta ahora a {a.restaurar}")
        return 0

    inicio = datetime.now()
    run_id = f"{inicio:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    cand = base / cfg["rutas"]["corridas"] / run_id
    cand.mkdir(parents=True, exist_ok=True)
    logf = open(cand / "run.log", "w", encoding="utf-8")
    etapas, advertencias = [], []

    def log(msg):
        linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
        print(linea, flush=True)
        logf.write(linea + "\n"); logf.flush()
        if msg.startswith("WARN"):
            advertencias.append(msg)

    def cerrar(codigo, resultado, extra=None):
        fin = datetime.now()
        resumen = {"run_id": run_id, "inicio": inicio.isoformat(timespec="seconds"), "fin": fin.isoformat(timespec="seconds"),
                   "etapas_completadas": etapas, "advertencias": advertencias, "resultado_publicacion": resultado, "codigo_salida": codigo}
        resumen.update(extra or {})
        (cand / "run_summary.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"FIN run {run_id}: {resultado} (código {codigo})")
        logf.close()
        return codigo

    try:
        log(f"INICIO run {run_id}")
        # ---- Etapa 1: lectura e identificación -------------------------------------------
        fuente = Path(a.fuente or cfg["rutas"]["fuente"])
        if not fuente.is_absolute():
            fuente = base / fuente
        if not fuente.exists():
            log(f"ERROR no existe la fuente {fuente}. Copie el archivo institucional ahí o use --fuente.")
            return cerrar(1, "error: fuente no encontrada")
        hashes = {"fuente": sha256(fuente), "config": sha256(cfg_path)}
        df = leer_fuente(fuente)
        etapas.append("1_lectura")
        log(f"Etapa 1 lectura: {fuente.name}, {len(df)} filas, sha256 fuente {hashes['fuente'][:12]}, config {hashes['config'][:12]}")

        # ---- Etapa 2: validación -----------------------------------------------------------
        ts = datetime.now().isoformat(timespec="seconds")
        ctrl, df_ok, series = controles.ejecutar(df, cfg, log)
        ctrl["run_id"], ctrl["timestamp"] = run_id, ts
        ctrl.to_csv(cand / "controles.csv", index=False)
        reporte.generar(ctrl, run_id, hashes, cand / "reporte_controles.md")
        etapas.append("2_validacion")
        fallos = ctrl[(ctrl["severidad"] == "critico") & (ctrl["estado"] == "FAIL")]
        for _, r in ctrl[ctrl["estado"] == "WARN"].iterrows():
            advertencias.append(f"{r['control']}: {r['detalle']}")
        if len(fallos):
            log(f"DETENIDO: control crítico en FAIL -> {list(fallos['control'])}. No se reemplazan los resultados vigentes.")
            return cerrar(2, "detenido por control crítico; resultados vigentes intactos", {"controles_fallidos": list(fallos["control"])})

        # ---- Etapa 3: preparación (las series ya se construyeron sin imputar ceros) ------------
        etapas.append("3_preparacion")
        log("Etapa 3 preparación: " + ", ".join(f"{n} ({int(s.notna().sum())} meses con dato)" for n, s in series.items()))

        # ---- Etapas 4 y 5: ajuste y evaluación temporal --------------------------------------
        bt, avisos_bt = modelos.backtest(series, cfg, log)
        etapas += ["4_ajuste", "5_evaluacion"]
        met = modelos.tabla_metricas(bt, cfg, run_id)

        # ---- Etapa 6: regla de aceptación ------------------------------------------------------
        met = modelos.regla_aceptacion(met, series, cfg)
        etapas.append("6_regla_aceptacion")
        for _, r in met.iterrows():
            log(f"  {r['serie']}: MAE {r['MAE']:.0f} (ref. {r['baseline_MAE']:.0f}), RMSE {r['RMSE']:.0f}, n={r['n_obs']} -> {'cumple' if r['cumple_regla'] else 'NO cumple'} ({r['motivo']})")
        met.to_csv(cand / "metricas.csv", index=False)

        # ---- Etapa 7: estimaciones -------------------------------------------------------------
        version = pub.siguiente_version(pub_dir, inicio)
        est_f = modelos.pronosticar(series, cfg, run_id, ts, version, hashes)
        est_b = pd.DataFrame({
            "destino": cfg["destino"], "serie": bt["serie"], "periodo": bt["periodo"].dt.strftime("%Y-%m-%d"),
            "valor": bt["pred_modelo"], "unidad": cfg["unidad"],
            "modelo": [f"{cfg['modelo']['nombre']}{tuple(cfg['series'][s]['arima'])}" for s in bt["serie"]],
            "conjunto": "evaluacion", "horizonte": 0, "run_id": run_id, "fecha_generacion": ts,
            "version_procedimiento": version, "fuente_hash": hashes["fuente"], "config_hash": hashes["config"]})
        est = pd.concat([est_b, est_f], ignore_index=True)
        cumple = dict(zip(met["serie"], met["cumple_regla"]))
        est["estado"] = ["aprobado" if cumple[s] else "referencia" for s in est["serie"]]
        etapas.append("7_estimaciones")

        # ---- Etapa 8: candidato inmutable --------------------------------------------------------
        est.to_csv(cand / "estimaciones.csv", index=False)
        bt.assign(periodo=bt["periodo"].dt.strftime("%Y-%m-%d")).to_csv(cand / "backtest_detalle.csv", index=False)
        deps = {p: metadata.version(p) for p in ("pandas", "numpy", "statsmodels", "PyYAML") if _tiene(p)}

        # ---- Etapa 9: autorización -----------------------------------------------------------------
        razones = []
        a_cfg = cfg["aceptacion"]
        if not np.isfinite(est["valor"]).all():
            razones.append("hay estimaciones no finitas")
        if (est["valor"] < 0).any():
            razones.append("hay estimaciones negativas")
        tope = {n: cfg["umbrales"]["rango_plausible_max_factor"] * float(s.max()) for n, s in series.items()}
        fuera = est[est["valor"] > est["serie"].map(tope)]
        if len(fuera):
            razones.append(f"{len(fuera)} estimaciones fuera del rango plausible")
        for s in a_cfg["series_obligatorias"]:
            if not cumple.get(s, False):
                razones.append(f"la serie obligatoria {s} no cumple la regla de aceptación")
        aprobado = not razones
        manifest = {"version_procedimiento": version, "run_id": run_id, "commit_git": commit_git(RAIZ),
                    "fuente": fuente.name, "fuente_hash": hashes["fuente"], "config_hash": hashes["config"],
                    "periodos": cfg["periodos"], "semilla": cfg["semilla"], "python": platform.python_version(), "dependencias": deps,
                    "inicio": inicio.isoformat(timespec="seconds"), "aprobado": aprobado, "motivos_rechazo": razones,
                    "aprobado_en": datetime.now().isoformat(timespec="seconds") if aprobado else None,
                    "resumen_metricas": {r["serie"]: {"MAE": round(r["MAE"], 2), "RMSE": round(r["RMSE"], 2),
                                                      "baseline_MAE": round(r["baseline_MAE"], 2), "cumple_regla": bool(r["cumple_regla"])}
                                         for _, r in met.iterrows()}}
        (cand / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        etapas.append("8_candidato")
        if not aprobado:
            log("RECHAZADO: " + "; ".join(razones) + ". Se conserva la versión vigente.")
            return cerrar(3, "candidato rechazado; resultados vigentes intactos", {"motivos_rechazo": razones})
        etapas.append("9_autorizacion")

        # ---- Etapas 10 y 11: versión aprobada y puntero atómico --------------------------------------
        pub.publicar(cand, pub_dir, version, manifest["aprobado_en"])
        etapas += ["10_version_aprobada", "11_puntero"]
        log(f"PUBLICADO {version} en {pub_dir / 'versions' / version}")
        return cerrar(0, f"publicado {version}", {"version": version})
    except Exception as e:
        log("ERROR inesperado: " + repr(e))
        log(traceback.format_exc())
        return cerrar(1, "error inesperado; resultados vigentes intactos", {"error": repr(e)})


def _tiene(p):
    try:
        metadata.version(p); return True
    except metadata.PackageNotFoundError:
        return False


if __name__ == "__main__":
    sys.exit(main())

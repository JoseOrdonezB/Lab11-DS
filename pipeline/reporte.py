"""Reporte legible de los controles de calidad (ejercicio 3.2).

Por cada control indica qué verifica, cuándo genera advertencia, cuándo detiene la ejecución
y qué resultó en esta corrida. Se escribe como reporte_controles.md junto a controles.csv."""

CATALOGO = {
    "C1": ("Columnas y tipos",
           "Que existan las columnas indispensables del config y que su tipo sea compatible (entero, numérico, texto).",
           "Nunca.",
           "Falta una columna indispensable o tiene un tipo incompatible. Si falla, no se evalúan los demás controles."),
    "C2": ("Fechas y cobertura",
           "Que Año y Mes cod formen fechas válidas y que cada mes de la cobertura configurada tenga información.",
           "Hay filas fuera de la cobertura, o meses sin filas en alguna serie distinta de Total (quedan como faltantes, nunca como cero).",
           "Hay fechas inválidas, o un mes de la cobertura sin información en la serie Total."),
    "C3": ("Unicidad",
           "Que no haya filas con la misma clave (año, mes, vía, frontera, país, región, tipo de viajero).",
           "Hay claves repetidas pero su porcentaje no supera duplicados_pct_fallo (se suman como registros parciales, no se borran).",
           "El porcentaje de filas con clave repetida supera duplicados_pct_fallo del config."),
    "C4": ("Valores faltantes",
           "Nulos en las columnas utilizadas, distinguiendo ausencias permitidas (columnas_nulos_permitidos) de las que impiden estimar.",
           "Hay nulos solo en columnas permitidas (Frontera, País).",
           "Hay nulos en cualquier otra columna utilizada."),
    "C5": ("Valores y denominadores",
           "Conteos negativos, valores no finitos (inf o no numéricos) en Viajero y meses con valor observado cero en el backtest (denominador del MAPE).",
           "Hay meses observados iguales a cero en el backtest (se excluyen del MAPE).",
           "Hay algún conteo negativo o algún valor no finito."),
    "C6": ("Regla metodológica",
           "Que la serie mensual provenga de la fuente mensual (sin columnas diarias), que los tipos de viajero sean los conocidos y que Total sin el tipo excluido sea la suma de las vías.",
           "Nunca.",
           "La fuente trae columnas diarias, hay tipos de viajero desconocidos o Total no coincide con la suma de las vías."),
}


def _clave(nombre):
    return nombre.split()[0]


def generar(ctrl, run_id, hashes, ruta):
    """ctrl: DataFrame de controles (con columnas control, estado, n_afectados, detalle). Escribe el .md en ruta."""
    conteo = ctrl["estado"].value_counts().to_dict()
    fallos = ctrl[ctrl["estado"] == "FAIL"]
    decision = ("DETENIDO: un control crítico falló; no se reemplazan los resultados vigentes del tablero."
                if len(fallos) else "APROBADO por controles: la ejecución continúa a preparación y modelado.")
    L = [f"# Reporte de controles de calidad — corrida {run_id}", "",
         f"- Fuente (SHA-256): `{hashes.get('fuente', 'n/d')}`",
         f"- Config (SHA-256): `{hashes.get('config', 'n/d')}`",
         "- Resumen: " + ", ".join(f"{k} {conteo.get(k, 0)}" for k in ("OK", "WARN", "FAIL", "OMITIDO")),
         f"- Decisión: {decision}", "",
         "| Control | Estado | Afectados | Resultado |", "|---|---|---|---|"]
    for _, r in ctrl.iterrows():
        L.append(f"| {r['control']} | {r['estado']} | {r['n_afectados']} | {str(r['detalle']).replace('|', '/')} |")
    L += ["", "## Qué verifica cada control", ""]
    for k, (nombre, verifica, warn, fail) in CATALOGO.items():
        L += [f"**{k} {nombre}**", f"- Verifica: {verifica}", f"- Advertencia (WARN): {warn}", f"- Detiene (FAIL): {fail}", ""]
    L += ["Los controles son críticos: un FAIL detiene el pipeline antes de preparar datos o tocar `published/`.",
          "Los meses sin cobertura nunca se convierten en cero."]
    ruta.write_text("\n".join(L) + "\n", encoding="utf-8")

"""Etapa 2: seis controles de calidad. Cada control devuelve OK / WARN / FAIL.
FAIL de un control crítico detiene el pipeline antes de preparar o reemplazar resultados."""
import numpy as np
import pandas as pd
from .preparar import agregar_fecha, construir_series, meses

TIPOS = {"entero": "i", "numerico": "if", "texto": "OSU"}   # kinds de numpy aceptados


def _res(control, severidad, estado, n, detalle):
    return {"control": control, "severidad": severidad, "estado": estado, "n_afectados": int(n), "detalle": detalle}


def c1_columnas_tipos(df, cfg):
    esperadas = cfg["fuente"]["columnas"]
    faltan = [c for c in esperadas if c not in df.columns]
    if faltan:
        return _res("C1 columnas y tipos", "critico", "FAIL", len(faltan), f"Faltan columnas indispensables: {faltan}")
    malos = []
    for col, tipo in esperadas.items():
        kind = df[col].dtype.kind
        if tipo == "texto":
            ok = kind in "OSU" or str(df[col].dtype) in ("string", "str")
        else:
            ok = kind in TIPOS[tipo]
        if not ok:
            malos.append(f"{col} es {df[col].dtype}, se esperaba {tipo}")
    if malos:
        return _res("C1 columnas y tipos", "critico", "FAIL", len(malos), "; ".join(malos))
    return _res("C1 columnas y tipos", "critico", "OK", 0, f"Las {len(esperadas)} columnas indispensables existen con el tipo esperado.")


def c2_fechas_cobertura(df, cfg, series):
    n_inval = int(df["fecha"].isna().sum())
    if n_inval:
        return _res("C2 fechas y cobertura", "critico", "FAIL", n_inval, f"{n_inval} filas con Año o Mes cod inválido (mes fuera de 1-12 o año fuera de rango).")
    cob = cfg["periodos"]["cobertura"]
    esperados = meses(cob["inicio"], cob["fin"])
    fuera = int((~df["fecha"].isin(esperados)).sum())
    sin_total = series["Total"].index[series["Total"].isna()]
    if len(sin_total):
        return _res("C2 fechas y cobertura", "critico", "FAIL", len(sin_total),
                    f"Meses sin información en la serie Total: {list(sin_total.strftime('%Y-%m'))[:12]}. No se convierten en cero.")
    huecos = {n: list(s.index[s.isna()].strftime("%Y-%m")) for n, s in series.items() if s.isna().any()}
    partes = []
    if fuera:
        partes.append(f"{fuera} filas fuera de la cobertura configurada ({cob['inicio']} a {cob['fin']}), se ignoran")
    if huecos:
        partes.append("meses sin filas (quedan como faltantes, no como cero): " +
                      "; ".join(f"{n}: {len(m)} meses" for n, m in huecos.items()))
    if partes:
        n = fuera + sum(len(m) for m in huecos.values())
        return _res("C2 fechas y cobertura", "critico", "WARN", n, ". ".join(partes) + ".")
    return _res("C2 fechas y cobertura", "critico", "OK", 0, f"Fechas válidas y los {len(esperados)} meses de {cob['inicio']} a {cob['fin']} tienen información en todas las series.")


def c3_unicidad(df, cfg):
    clave = cfg["fuente"]["clave_unicidad"]
    dup = df.duplicated(clave, keep=False)
    n = int(dup.sum())
    pct = 100 * n / len(df)
    u = cfg["umbrales"]
    if n == 0:
        return _res("C3 unicidad", "critico", "OK", 0, "Sin claves repetidas.")
    detalle = (f"{n} filas ({pct:.3f} %) comparten clave ({', '.join(clave)}). Se conservan y se suman como registros parciales aditivos; "
               "no se eliminan en silencio.")
    estado = "FAIL" if pct > u["duplicados_pct_fallo"] else "WARN"
    if estado == "FAIL":
        detalle += f" Supera el umbral de fallo ({u['duplicados_pct_fallo']} %)."
    elif pct > u["duplicados_pct_advertencia"]:
        detalle += f" Pasa el umbral de advertencia ({u['duplicados_pct_advertencia']} %) pero no el de fallo ({u['duplicados_pct_fallo']} %)."
    else:
        detalle += f" Está por debajo del umbral de advertencia ({u['duplicados_pct_advertencia']} %); se avisa igual para que quede registrado."
    return _res("C3 unicidad", "critico", estado, n, detalle)


def c4_faltantes(df, cfg):
    permitidas = set(cfg["fuente"]["columnas_nulos_permitidos"])
    nulos = df[list(cfg["fuente"]["columnas"])].isna().sum()
    nulos = nulos[nulos > 0]
    if nulos.empty:
        return _res("C4 valores faltantes", "critico", "OK", 0, "Sin ausencias en las columnas utilizadas.")
    graves = {c: int(n) for c, n in nulos.items() if c not in permitidas}
    leves = {c: int(n) for c, n in nulos.items() if c in permitidas}
    if graves:
        return _res("C4 valores faltantes", "critico", "FAIL", sum(graves.values()),
                    f"Ausencias que impiden estimar: {graves}." + (f" Ausencias permitidas: {leves}." if leves else ""))
    return _res("C4 valores faltantes", "critico", "WARN", sum(leves.values()), f"Ausencias permitidas (no impiden estimar): {leves}.")


def c5_valores_denominadores(df, cfg, series):
    v = pd.to_numeric(df["Viajero"], errors="coerce")
    neg = int((v < 0).sum())
    nofin = int(np.isinf(v).sum()) + int((v.isna() & df["Viajero"].notna()).sum())
    if neg or nofin:
        return _res("C5 valores y denominadores", "critico", "FAIL", neg + nofin,
                    f"{neg} conteos negativos y {nofin} valores no finitos o no numéricos en Viajero.")
    bt = cfg["periodos"]["backtest"]
    idx = meses(bt["inicio"], bt["fin"])
    ceros = {n: int((s.reindex(idx) == 0).sum()) for n, s in series.items()}
    ceros = {n: c for n, c in ceros.items() if c}
    det = "Sin negativos ni valores no finitos."
    if ceros:
        return _res("C5 valores y denominadores", "critico", "WARN", sum(ceros.values()),
                    det + f" Meses observados iguales a cero en el backtest (denominador cero del MAPE, se excluyen del MAPE): {ceros}.")
    return _res("C5 valores y denominadores", "critico", "OK", 0, det + " Sin denominadores iguales a cero en el backtest.")


def c6_regla_metodologica(df, cfg, series):
    f = cfg["fuente"]
    prohibidas = [c for c in f["columnas_diarias_prohibidas"] if c in df.columns]
    if prohibidas:
        return _res("C6 regla metodológica", "critico", "FAIL", len(prohibidas),
                    f"La fuente trae columnas diarias {prohibidas}; la serie mensual no se puede construir sumando presencias diarias.")
    desconocidos = sorted(set(df["Tipo de Viajero"].dropna().unique()) - set(f["tipos_viajero_validos"]))
    if desconocidos:
        return _res("C6 regla metodológica", "critico", "FAIL", len(desconocidos),
                    f"Tipos de viajero fuera del dominio conocido {desconocidos}: podrían duplicar visitantes al sumarse.")
    # Aditividad: Total (sin tipo 'Viajero') debe ser la suma de las tres vías sin tipo 'Viajero'.
    sin_v = df[df["Tipo de Viajero"] != f["tipo_excluido"]]
    por_via = sin_v.groupby(["fecha", "Vía"])["Viajero"].sum().unstack("Vía").sum(axis=1)
    tot = series["Total"]
    diff = (tot - por_via.reindex(tot.index)).abs().max()
    if not diff <= 1e-6 * max(1.0, float(tot.max())):
        return _res("C6 regla metodológica", "critico", "FAIL", 1, f"Total no coincide con la suma de las vías (diferencia máxima {diff:.4f}).")
    return _res("C6 regla metodológica", "critico", "OK", 0,
                f"Fuente mensual (sin columnas diarias), tipos de viajero válidos, y Total sin '{f['tipo_excluido']}' = suma de vías (dif. máx. {diff:.2e}).")


def ejecutar(df_crudo, cfg, log):
    """Devuelve (tabla de controles, df con fecha, series). Si C1 falla no se evalúa el resto."""
    res = []
    r1 = c1_columnas_tipos(df_crudo, cfg)
    res.append(r1)
    log(f"{r1['control']}: {r1['estado']} - {r1['detalle']}")
    if r1["estado"] == "FAIL":
        for n in ("C2 fechas y cobertura", "C3 unicidad", "C4 valores faltantes", "C5 valores y denominadores", "C6 regla metodológica"):
            res.append(_res(n, "critico", "OMITIDO", 0, "No se evaluó porque C1 detuvo el flujo."))
        return pd.DataFrame(res), None, None
    df = agregar_fecha(df_crudo)
    df_ok = df[df["fecha"].notna()]
    series = construir_series(df_ok, cfg)
    for fn, args in ((c2_fechas_cobertura, (df, cfg, series)), (c3_unicidad, (df, cfg)), (c4_faltantes, (df, cfg)),
                     (c5_valores_denominadores, (df, cfg, series)), (c6_regla_metodologica, (df_ok, cfg, series))):
        try:
            r = fn(*args)
        except Exception as e:                       # un control que no puede correr se trata como fallo
            r = _res(fn.__name__, "critico", "FAIL", 0, f"El control no pudo ejecutarse: {e!r}")
        res.append(r)
        log(f"{r['control']}: {r['estado']} - {r['detalle']}")
    return pd.DataFrame(res), df_ok, series

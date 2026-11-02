"""
Observatorio de Turismo Sostenible — Guatemala (INGUAT/IGM, 2009–jun 2026)
Laboratorio 10 · CC3066 Data Science · UVG
Versión FINAL: 8 visualizaciones (V1–V8), V2→V3 enlazadas, 3 modelos del Lab 1.
Ejecutar:  streamlit run app/app.py
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from publicacion import cargar_publicacion, series_publicadas  # noqa: E402

# ---------------- Paleta (significado fijo en toda la aplicación) ----------------
AZUL = "#1B2A41"      # títulos, texto principal
PIZARRA = "#5C6B7A"   # referencias, ejes, pandemia
TEAL = "#0E8C99"      # SIEMPRE = dato observado (lo que ocurrió)
NARANJA = "#C8590F"   # SIEMPRE = estimación / pronóstico de un modelo
SELECC = "#1B2A41"    # elemento seleccionado
TEAL_TXT = "#0A6F7A"   # versión oscura del teal para TEXTO pequeño (contraste ≥ 4.5:1)
NARANJA_TXT = "#A84808"  # versión oscura del naranja para TEXTO pequeño (contraste ≥ 4.5:1)
GRIS_CLARO = "#C9D1D9"
FONDO = "#F7F9FB"

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MODELOS_DASH = ["ARIMA", "Seasonal Naive", "Prophet"]  # 3 modelos simples reutilizados del Lab 1

st.set_page_config(page_title="Observatorio de Turismo Sostenible · Guatemala",
                   page_icon="🌿", layout="wide")

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Open+Sans:wght@400;600&display=swap');
html, body, [class*="css"] {{ font-family: 'Open Sans', sans-serif; color: {AZUL}; }}
h1, h2, h3 {{ font-family: 'Montserrat', sans-serif; color: {AZUL}; }}
.block-container {{ padding-top: 1.6rem; }}
.kpi {{ background:{FONDO}; border-left:5px solid {TEAL}; padding:.7rem 1rem; border-radius:6px; }}
.kpi.est {{ border-left-color:{NARANJA}; }}
.kpi .v {{ font-family:'Montserrat'; font-weight:700; font-size:1.7rem; }}
.kpi .l {{ font-size:.85rem; color:{PIZARRA}; }}
.pregunta {{ font-family:'Montserrat'; font-weight:600; font-size:1.05rem; color:{AZUL}; margin-bottom:.1rem; }}
.nota {{ font-size:.85rem; color:{PIZARRA}; }}
.etq-obs {{ color:{TEAL_TXT}; font-weight:700; }} .etq-est {{ color:{NARANJA_TXT}; font-weight:700; }}
</style>""", unsafe_allow_html=True)


# ---------------- Datos (solo lectura de archivos exportados del Lab 1) ----------------
@st.cache_data
def cargar():
    base = pd.read_csv(DATA / "base_viajeros.csv.gz")
    base = base[base["Tipo de Viajero"] != "Viajero"]  # misma decisión metodológica del Lab 1
    series = pd.read_csv(DATA / "series_mensuales.csv", parse_dates=["fecha"])
    preds = pd.read_csv(DATA / "predicciones_lab1.csv", parse_dates=["fecha"])
    mets = pd.read_csv(DATA / "metricas_lab1.csv")
    return base, series, preds, mets


base, series, preds, mets = cargar()
publicacion, error_publicacion = cargar_publicacion()
nombre_corto = lambda m: "ARIMA" if m.startswith("ARIMA") else m


def fmt(n):
    return f"{n:,.0f}"


def etiqueta_estado(estado):
    return "Aprobado (ARIMA)" if estado == "aprobado" else "Referencia (Seasonal Naive)"


# ---------------- Encabezado ----------------
st.title("Observatorio de Turismo Sostenible · Guatemala")
st.caption("Llegadas internacionales de viajeros, enero 2009 – junio 2026 · Fuente: INGUAT / Migración "
           "(procesada en los Laboratorios 1 y 2).")
st.markdown(
    f"<span class='etq-obs'>■ Verde azulado = dato observado</span> &nbsp;&nbsp; "
    f"<span class='etq-est'>■ Naranja = estimación de un modelo</span> &nbsp;&nbsp; "
    f"<span style='color:{PIZARRA};font-weight:700'>■ Gris = referencia / periodo de pandemia</span>",
    unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs(["① ¿Cómo evoluciona el flujo?", "② ¿De dónde vienen los viajeros?",
                                        "③ ¿Por dónde y cuándo?", "④ ¿Qué esperar? (pronósticos)",
                                        "⑤ ¿Qué versión estoy viendo?"])

# =====================================================================================
# V1 — Serie mensual con nivel de detalle
# =====================================================================================
with tab1:
    st.markdown("<div class='pregunta'>¿Cuánto se ha recuperado el flujo de viajeros y en qué meses se concentra?</div>",
                unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    serie_sel = c1.selectbox("Segmento a observar", sorted(series["serie"].unique(), key=lambda s: (s != "Total", s)),
                             help="Total del país, por vía de ingreso o por región de origen.")
    nivel = c2.radio("Nivel de detalle", ["Mensual", "Trimestral", "Anual"], horizontal=True,
                     help="Anual resume el panorama; mensual deja ver las temporadas altas y bajas.")
    s = series[series["serie"] == serie_sel].set_index("fecha")["real"]
    if nivel == "Mensual":
        y, x, hover = s, s.index, "%{x|%b %Y}: %{y:,.0f} viajeros"
    elif nivel == "Trimestral":
        y = s.resample("QS").sum(); x = y.index; hover = "Trim. %{x|%b %Y}: %{y:,.0f} viajeros"
    else:
        y = s.resample("YS").sum(); x = y.index; hover = "%{x|%Y}: %{y:,.0f} viajeros"

    prom19 = s["2019"].sum()
    ult12 = s.iloc[-12:].sum()
    k1, k2, k3 = st.columns(3)
    k1.markdown(f"<div class='kpi'><div class='v'>{fmt(prom19)}</div><div class='l'>Viajeros en 2019 (año previo a la pandemia)</div></div>", unsafe_allow_html=True)
    k2.markdown(f"<div class='kpi'><div class='v'>{fmt(ult12)}</div><div class='l'>Últimos 12 meses (jul 2025 – jun 2026)</div></div>", unsafe_allow_html=True)
    ratio = ult12 / prom19 * 100 if prom19 else np.nan
    k3.markdown(f"<div class='kpi'><div class='v'>{ratio:,.0f}%</div><div class='l'>Últimos 12 meses respecto a 2019</div></div>", unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_vrect(x0="2020-03-01", x1="2021-06-30", fillcolor=GRIS_CLARO, opacity=.45, line_width=0,
                  annotation_text="Pandemia", annotation_position="top left", annotation_font_color=PIZARRA)
    if nivel == "Anual":
        etq = [f"{d.year}" + (" (ene–jun)" if d.year == 2026 else "") for d in x]
        colores = [TEAL if d.year != 2026 else GRIS_CLARO for d in x]
        fig.add_bar(x=etq, y=y.values, marker_color=colores, hovertemplate="%{x}: %{y:,.0f} viajeros<extra></extra>")
        fig.update_xaxes(type="category")
    else:
        fig.add_scatter(x=x, y=y.values, mode="lines", line=dict(color=TEAL, width=2.5),
                        hovertemplate=hover + "<extra></extra>")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white",
                      yaxis_title="Viajeros", xaxis_title=None, hovermode="x unified",
                      font=dict(family="Open Sans", size=14, color=AZUL))
    fig.update_yaxes(gridcolor="#E6EBF0", tickformat=",")
    if nivel != "Anual":
        fig.update_xaxes(rangeslider_visible=True, rangeslider_thickness=.07)
    st.plotly_chart(fig, width="stretch")
    msg = {"Mensual": "Cada punto es un mes. Use la franja inferior para acercarse a un periodo.",
           "Trimestral": "Cada punto suma tres meses. Suaviza las temporadas para ver la tendencia.",
           "Anual": "2026 incluye solo enero–junio, por eso aparece en gris y no es comparable con años completos."}[nivel]
    st.markdown(f"<div class='nota'><b>Lo observado:</b> {msg} La serie excluye el tipo de viajero «Viajero» "
                f"(cambio de metodología 2022-2023){' salvo en Vía Marítima, donde se incluye por completo' if serie_sel == 'Vía Marítima' else ''}.</div>",
                unsafe_allow_html=True)

# =====================================================================================
# V2 + V3 — Región → País (enlazadas)
# =====================================================================================
with tab2:
    st.markdown("<div class='pregunta'>¿Qué regiones aportan más viajeros y qué países hay detrás de cada una?</div>",
                unsafe_allow_html=True)
    anios = sorted(base["Año"].unique())
    a0, a1 = st.select_slider("Periodo", options=anios, value=(2019, 2025),
                              help="Seleccione el rango de años a sumar. 2026 solo tiene enero–junio.")
    b = base[(base["Año"] >= a0) & (base["Año"] <= a1)]
    if b.empty:
        st.info("No hay información para el periodo elegido.")
    else:
        por_region = b.groupby("Región dos")["Viajero"].sum().sort_values()
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**① Haga clic en una región**")
            colores = [TEAL] * len(por_region)
            figr = go.Figure(go.Bar(x=por_region.values, y=por_region.index, orientation="h",
                                    marker_color=colores, hovertemplate="%{y}: %{x:,.0f} viajeros<extra></extra>"))
            figr.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                               font=dict(family="Open Sans", size=14, color=AZUL), xaxis_title="Viajeros")
            figr.update_xaxes(gridcolor="#E6EBF0", tickformat=",")
            ev = st.plotly_chart(figr, width="stretch", on_select="rerun",
                                 selection_mode="points", key="sel_region")
            puntos = ev.selection.points if ev and ev.selection else []
            region = puntos[0]["y"] if puntos else por_region.index[-1]
        with col_b:
            st.markdown(f"**② Países de: {region}**" + ("" if puntos else "  _(mostrando la región más grande; haga clic para cambiar)_"))
            bp = b[b["Región dos"] == region].groupby("País")["Viajero"].sum().sort_values(ascending=False)
            top_n = st.slider("Cantidad de países a mostrar", 3, 15, 8,
                              help="Aumente o reduzca el nivel de detalle.")
            if bp.empty:
                st.info("No hay países registrados para esta región en el periodo elegido.")
            else:
                bp = bp.head(top_n).sort_values()
                figp = go.Figure(go.Bar(x=bp.values, y=bp.index, orientation="h", marker_color=AZUL,
                                        hovertemplate="%{y}: %{x:,.0f} viajeros<extra></extra>"))
                figp.update_layout(height=390, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                                   font=dict(family="Open Sans", size=14, color=AZUL), xaxis_title="Viajeros")
                figp.update_xaxes(gridcolor="#E6EBF0", tickformat=",")
                st.plotly_chart(figp, width="stretch")
                tot_r = por_region[region]
                extra = (" «Guatemala» aparece porque el registro incluye viajeros con residencia declarada en el país; "
                         "no necesariamente son visitantes extranjeros.") if region == "América Del Centro" else ""
                st.markdown(f"<div class='nota'><b>Lo observado:</b> {region} sumó {fmt(tot_r)} viajeros entre {a0} y {a1} "
                            f"({tot_r / por_region.sum() * 100:.0f}% del total).{extra}</div>", unsafe_allow_html=True)


# =====================================================================================
# V5 + V7 — Temporadas y fronteras (pestaña 3)
# =====================================================================================
with tab3:
    st.markdown("<div class='pregunta'>¿En qué meses y años se concentra el ingreso y por qué fronteras entra?</div>", unsafe_allow_html=True)
    seg5 = st.selectbox("Segmento", sorted(series["serie"].unique(), key=lambda s: (s != "Total", s)), key="seg_heat",
                        help="Cada celda es un mes; más oscuro significa más viajeros.")
    h = series[series["serie"] == seg5].copy()
    h["anio"], h["mes"] = h["fecha"].dt.year, h["fecha"].dt.month
    piv = h.pivot(index="anio", columns="mes", values="real").reindex(columns=range(1, 13))
    fh = go.Figure(go.Heatmap(z=piv.values, x=MESES, y=piv.index.astype(str), colorscale=[[0, "#EAF4F5"], [1, TEAL_TXT]],
                              hoverongaps=False, colorbar=dict(title="Viajeros"),
                              hovertemplate="%{y} %{x}: %{z:,.0f} viajeros<extra></extra>"))
    fh.update_yaxes(autorange="reversed", type="category")
    fh.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), font=dict(family="Open Sans", size=14, color=AZUL))
    st.plotly_chart(fh, width="stretch", key="v5")
    st.markdown("<div class='nota'><b>Lo observado:</b> cada fila es un año. 2020 y 2021 muestran el efecto de la pandemia y 2026 solo llega a junio "
                "(celdas vacías = sin dato).</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**Fronteras principales**")
    f1, f2, f3 = st.columns([1, 1, 2])
    via = f1.selectbox("Vía de ingreso", ["Todas", "Aérea", "Terrestre", "Marítima"], key="via7",
                       help="Al cambiar la vía, la gráfica muestra solo sus puntos de entrada.")
    n7 = f2.slider("Fronteras a mostrar", 3, 15, 8, key="n7")
    anios7 = sorted(base["Año"].unique())
    r7 = f3.select_slider("Periodo", options=anios7, value=(2019, 2025), key="per7")
    b7 = base[(base["Año"] >= r7[0]) & (base["Año"] <= r7[1])]
    if via != "Todas":
        b7 = b7[b7["Vía"] == via]
    fr = b7.groupby("Frontera")["Viajero"].sum().sort_values(ascending=False).head(n7).sort_values()
    if fr.empty or fr.sum() == 0:
        st.info("No hay información de fronteras para esta selección. Pruebe con otra vía o periodo.")
    else:
        f7 = go.Figure(go.Bar(x=fr.values, y=fr.index, orientation="h", marker_color=AZUL,
                              hovertemplate="%{y}: %{x:,.0f} viajeros<extra></extra>"))
        f7.update_layout(height=max(300, 40 * len(fr) + 60), margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                         xaxis_title="Viajeros", font=dict(family="Open Sans", size=14, color=AZUL))
        f7.update_xaxes(gridcolor="#E6EBF0", tickformat=",")
        st.plotly_chart(f7, width="stretch", key="v7")
        tot7 = b7["Viajero"].sum()
        st.markdown(f"<div class='nota'><b>Lo observado:</b> las {len(fr)} fronteras mostradas concentran {fr.sum() / tot7 * 100:.0f}% de los viajeros "
                    f"de {'todas las vías' if via == 'Todas' else 'la vía ' + via.lower()} entre {r7[0]} y {r7[1]}. "
                    f"Alta concentración implica más presión sobre pocos puntos de entrada; los datos no indican su capacidad.</div>",
                    unsafe_allow_html=True)

# =====================================================================================
# V4 — Pronóstico vs real con 3 modelos
# =====================================================================================
with tab4:
    st.markdown("<div class='pregunta'>Si el patrón histórico se repitiera, ¿cuántos viajeros se habrían esperado y qué tan confiable fue cada modelo?</div>",
                unsafe_allow_html=True)
    cc1, cc2 = st.columns([1, 2])
    serie_p = cc1.selectbox("Segmento", sorted(series["serie"].unique(), key=lambda s: (s != "Total", s)), key="seg_pred")
    elegidos = cc2.multiselect("Modelos a comparar", MODELOS_DASH, default=MODELOS_DASH,
                               help="ARIMA y Prophet ajustan la tendencia; Seasonal Naive repite el mismo mes del año anterior.")
    real = series[(series["serie"] == serie_p)].set_index("fecha")["real"]
    prueba = real[real.index >= "2021-04-01"]
    fp = go.Figure()
    fp.add_scatter(x=real[real.index < "2021-04-01"].index, y=real[real.index < "2021-04-01"].values,
                   mode="lines", line=dict(color=GRIS_CLARO, width=2), name="Observado (entrenamiento)",
                   hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra></extra>")
    fp.add_scatter(x=prueba.index, y=prueba.values, mode="lines", line=dict(color=TEAL, width=3),
                   name="Observado (prueba)", hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra></extra>")
    estilos = {"ARIMA": "solid", "Seasonal Naive": "dash", "Prophet": "dot"}
    sub = preds[preds["serie"] == serie_p].copy()
    sub["m"] = sub["modelo"].map(nombre_corto)
    for m in elegidos:
        d = sub[sub["m"] == m]
        fp.add_scatter(x=d["fecha"], y=d["prediccion"], mode="lines", name=f"Estimación: {m}",
                       line=dict(color=NARANJA, width=2.5, dash=estilos[m]),
                       hovertemplate=f"{m} %{{x|%b %Y}}: %{{y:,.0f}}<extra></extra>")
    fp.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", hovermode="x unified",
                     yaxis_title="Viajeros por mes", legend=dict(orientation="h", y=-0.15),
                     font=dict(family="Open Sans", size=14, color=AZUL))
    fp.update_yaxes(gridcolor="#E6EBF0", tickformat=",")
    if not elegidos:
        st.info("Seleccione al menos un modelo para ver su estimación.")
    st.plotly_chart(fp, width="stretch")

    mt = mets[mets["serie"] == serie_p].copy()
    mt["Modelo"] = mt["modelo"].map(nombre_corto)
    mt = mt[mt["Modelo"].isin(MODELOS_DASH)][["Modelo", "MAE", "RMSE", "MAPE_%"]].sort_values("RMSE")
    mejor = mt.iloc[0]["Modelo"]
    st.markdown(f"**Error de cada modelo en los 63 meses de prueba** (menor = más cercano a lo observado)")
    st.dataframe(mt.rename(columns={"MAE": "Error promedio (viajeros/mes)", "RMSE": "Error RMSE", "MAPE_%": "Error %"})
                 .style.format({"Error promedio (viajeros/mes)": "{:,.0f}", "Error RMSE": "{:,.0f}", "Error %": "{:.0f}%"}),
                 hide_index=True, width="stretch")
    st.markdown(f"<div class='nota'><b>Interpretación:</b> en «{serie_p}», el modelo con menor error fue <b>{mejor}</b>. "
                f"Son <span class='etq-est'>estimaciones</span>, no hechos: el periodo de prueba incluye la recuperación posterior a la pandemia, "
                f"un evento que ningún modelo anticipa, por lo que los errores son altos y no deben usarse como cifras oficiales.</div>",
                unsafe_allow_html=True)

# =====================================================================================
# V6 — Recuperación respecto a 2019 (pestaña 1)
# =====================================================================================
with tab1:
    st.markdown("---")
    st.markdown("<div class='pregunta'>¿Qué vías y regiones ya recuperaron su nivel de 2019 y cuáles no?</div>", unsafe_allow_html=True)
    rec = []
    for nom, g in series.groupby("serie"):
        g = g.set_index("fecha")["real"]
        base19 = g["2019"].sum()
        if base19 > 0:
            rec.append((nom, g.iloc[-12:].sum() / base19 * 100))
    rec = pd.DataFrame(rec, columns=["Segmento", "pct"]).query("Segmento != 'Total'").sort_values("pct")
    frec = go.Figure(go.Bar(x=rec["pct"], y=rec["Segmento"], orientation="h",
                            marker_color=[TEAL if v >= 100 else GRIS_CLARO for v in rec["pct"]],
                            text=[f"{v:,.0f}%" for v in rec["pct"]], textposition="outside",
                            hovertemplate="%{y}: %{x:,.0f}% del nivel de 2019<extra></extra>"))
    frec.add_vline(x=100, line_dash="dash", line_color=PIZARRA, annotation_text="Nivel de 2019 (100%)",
                   annotation_font_color=PIZARRA)
    frec.update_layout(height=340, margin=dict(l=10, r=40, t=30, b=10), plot_bgcolor="white",
                       xaxis_title="Últimos 12 meses (jul 2025–jun 2026) como % de 2019",
                       font=dict(family="Open Sans", size=14, color=AZUL))
    frec.update_xaxes(gridcolor="#E6EBF0", rangemode="tozero")
    st.plotly_chart(frec, width="stretch", key="v6")
    st.markdown("<div class='nota'><b>Lo observado:</b> verde azulado = igualó o superó 2019; gris = aún por debajo. "
                "<b>Limitación:</b> compara 12 meses contra un año completo y no explica las causas de las diferencias. "
                "Vía Marítima incluye todos los tipos de viajero (excepción metodológica del Lab 1).</div>", unsafe_allow_html=True)

# =====================================================================================
# V8 — Error por modelo y segmento (pestaña 4)
# =====================================================================================
with tab4:
    st.markdown("---")
    st.markdown("<div class='pregunta'>¿Qué modelo se equivocó menos en cada segmento?</div>", unsafe_allow_html=True)
    metrica = st.radio("Medida de error", ["Error porcentual medio (%)", "Error promedio (viajeros/mes)"], horizontal=True,
                       help="El porcentaje permite comparar segmentos de distinto tamaño; la otra opción muestra viajeros por mes.")
    col = "MAPE_%" if metrica.startswith("Error porcentual") else "MAE"
    mm = mets.copy(); mm["Modelo"] = mm["modelo"].map(nombre_corto)
    mm = mm[mm["Modelo"].isin(MODELOS_DASH)]
    f8 = go.Figure()
    for m, colr in zip(MODELOS_DASH, [AZUL, NARANJA, PIZARRA]):
        d = mm[mm["Modelo"] == m]
        f8.add_bar(x=d["serie"], y=d[col], name=m, marker_color=colr,
                   hovertemplate=f"{m} · %{{x}}: %{{y:,.0f}}<extra></extra>")
    f8.update_layout(barmode="group", height=400, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white",
                     yaxis_title=metrica, legend=dict(orientation="h", y=-0.25), font=dict(family="Open Sans", size=14, color=AZUL))
    f8.update_yaxes(gridcolor="#E6EBF0", tickformat=",")
    st.plotly_chart(f8, width="stretch", key="v8")
    gan = mm.loc[mm.groupby("serie")[col].idxmin()].groupby("Modelo").size()
    txt = ", ".join(f"{k}: {v}" for k, v in gan.items())
    st.markdown(f"<div class='nota'><b>Lo observado:</b> segmentos donde cada modelo tuvo el menor error → {txt}. "
                "<b>Limitación:</b> Vía Marítima tiene meses con muy pocos viajeros, por eso su error porcentual se dispara y debe leerse con cuidado. Ningún modelo domina en todos los segmentos y el periodo de prueba incluye la recuperación pos-pandemia; "
                "son <span class='etq-est'>estimaciones</span> para explorar, no cifras oficiales.</div>", unsafe_allow_html=True)

    # ---- Estimación de la versión aprobada (Laboratorio 11) --------------------------
    if publicacion is not None:
        st.markdown("---")
        st.markdown("<div class='pregunta'>Estimación publicada para julio–diciembre de 2026</div>", unsafe_allow_html=True)
        publicadas = series_publicadas(publicacion)
        if serie_p not in publicadas:
            st.info("La versión publicada no incluye este segmento. Elija otro en el selector de arriba.")
        else:
            e = publicacion.estimaciones
            ep = e[(e["serie"] == serie_p) & (e["conjunto"] == "pronostico")].sort_values("periodo")
            real = series[series["serie"] == serie_p].set_index("fecha")["real"]
            reciente = real[real.index >= real.index.max() - pd.DateOffset(months=23)]
            estado = str(ep["estado"].iloc[0])
            color = NARANJA if estado == "aprobado" else PIZARRA
            estilo = "solid" if estado == "aprobado" else "dash"
            fp2 = go.Figure()
            fp2.add_scatter(x=reciente.index, y=reciente.values, mode="lines", name="Observado",
                            line=dict(color=TEAL, width=2.5),
                            hovertemplate="Observado %{x|%b %Y}: %{y:,.0f}<extra></extra>")
            fp2.add_scatter(x=ep["periodo"], y=ep["valor"], mode="lines+markers",
                            name=etiqueta_estado(estado), line=dict(color=color, width=2.8, dash=estilo),
                            marker=dict(size=8), hovertemplate="Estimado %{x|%b %Y}: %{y:,.0f}<extra></extra>")
            fp2.add_vline(x=reciente.index.max(), line_dash="dot", line_color=GRIS_CLARO,
                          annotation_text="último dato observado", annotation_position="top left",
                          annotation_font_color=PIZARRA)
            fp2.update_layout(height=390, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white",
                              hovermode="x unified", yaxis_title="Viajeros por mes",
                              legend=dict(orientation="h", y=-0.18),
                              font=dict(family="Open Sans", size=14, color=AZUL))
            fp2.update_yaxes(gridcolor="#E6EBF0", tickformat=",")
            st.plotly_chart(fp2, width="stretch", key="v9_publicado")
            st.caption(f"Versión {publicacion.version} · actualizada {publicacion.actualizado_en.replace('T', ' ')} · "
                       f"serie publicada como {estado}. Los valores de jul–dic 2026 son estimaciones, no observaciones.")
            st.dataframe(ep.assign(periodo=ep["periodo"].dt.strftime("%Y-%m"))[["periodo", "valor", "unidad", "estado"]]
                         .rename(columns={"periodo": "Período", "valor": "Valor estimado", "unidad": "Unidad",
                                          "estado": "Estado"}),
                         hide_index=True, width="stretch")
            st.markdown(f"<div class='nota'><b>Cómo leerlo:</b> la línea verde azulada es lo observado. "
                        f"La línea {'naranja' if estado == 'aprobado' else 'gris discontinua'} es la estimación de la versión aprobada. "
                        f"Cuando el estado es <b>referencia</b>, la serie no pasó la regla de aceptación y se publica con "
                        f"Seasonal Naive (el mismo mes del año anterior), no con ARIMA.</div>", unsafe_allow_html=True)

# =====================================================================================
# V9 — Versión publicada: trazabilidad, métricas y limitaciones (Laboratorio 11)
# =====================================================================================
with tab5:
    st.markdown("<div class='pregunta'>¿Qué versión de resultados está viendo el tablero y qué tan confiable es?</div>",
                unsafe_allow_html=True)
    if publicacion is None:
        st.warning("**Estimaciones no disponibles.** Todavía no existe una versión aprobada que el tablero pueda consultar. "
                   "El tablero no reajusta modelos ni inventa valores: cuando el pipeline publique una versión aprobada, "
                   "aparecerá aquí automáticamente.")
        if error_publicacion:
            st.caption(f"Detalle técnico: {error_publicacion}")
    else:
        p = publicacion
        n_ok = int(p.metricas["cumple_regla"].astype(bool).sum()) if "cumple_regla" in p.metricas else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"<div class='kpi'><div class='v'>{p.version}</div><div class='l'>Versión aprobada que consulta el tablero</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi'><div class='v'>{p.actualizado_en.replace('T', ' ')}</div><div class='l'>Fecha de actualización</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi est'><div class='v'>{n_ok} / {len(p.metricas)}</div><div class='l'>Series con ARIMA aprobado (el resto se publica como referencia)</div></div>", unsafe_allow_html=True)
        c4.markdown(f"<div class='kpi'><div class='v'>{p.run_id}</div><div class='l'>Identificador de la ejecución</div></div>", unsafe_allow_html=True)
        destino = p.estimaciones["destino"].iloc[0] if "destino" in p.estimaciones else "Guatemala"
        unidad = p.estimaciones["unidad"].iloc[0] if "unidad" in p.estimaciones else "viajeros/mes"
        st.caption(f"Destino: {destino} · Unidad: {unidad} · Run de MLflow: {p.mlflow_run_id} · "
                   f"Fuente SHA-256: {p.fuente_hash}… · Config SHA-256: {p.config_hash}…")

        st.markdown("#### Validación temporal")
        m = p.metricas.copy()
        m["Estado"] = np.where(m["cumple_regla"].astype(bool), "aprobado", "referencia")
        periodo = (f"{m['periodo_inicio'].iloc[0]} a {m['periodo_fin'].iloc[0]}"
                   if {"periodo_inicio", "periodo_fin"} <= set(m.columns) else "el período configurado")
        st.markdown(f"**MAE** es el error promedio absoluto en {unidad}: qué tanto se alejó la estimación de lo observado, "
                    f"en promedio, durante el backtest **{periodo}**. **MAE / nivel** compara ese error con el tamaño medio "
                    f"del flujo (un 15 % es una tolerancia de planificación, no una promesa de precisión puntual). "
                    f"**MAE / ref.** compara con Seasonal Naive: valores mayores que 1 significan que el modelo no superó "
                    f"la referencia; el laboratorio no exige superarla (5.5), por eso se reporta sin bloquear.")
        tabla = m.rename(columns={
            "serie": "Serie", "n_obs": "Meses evaluados", "MAE": "MAE (viajeros/mes)",
            "MAE_pct_nivel": "MAE / nivel (%)", "baseline_MAE": "MAE referencia",
            "ratio_referencia": "MAE / referencia", "Estado": "Estado"})
        cols = ["Serie", "Meses evaluados", "MAE (viajeros/mes)", "MAE / nivel (%)", "MAE referencia",
                "MAE / referencia", "Estado"]
        st.dataframe(tabla[cols].style.format({
            "Meses evaluados": "{:,.0f}", "MAE (viajeros/mes)": "{:,.0f}", "MAE / nivel (%)": "{:.1f}%",
            "MAE referencia": "{:,.0f}", "MAE / referencia": "{:.2f}"}, na_rep="n/d"),
            hide_index=True, width="stretch")

        mon = p.monitoreo.get("verificaciones", []) if p.monitoreo else []
        alertas = [v for v in mon if v.get("estado") == "ALERTA"]
        if mon:
            if alertas:
                st.warning("**Monitoreo con alertas para revisión:** " +
                           "; ".join(f"{v.get('verificacion')}: {v.get('detalle')}" for v in alertas) +
                           ". Una alerta no demuestra por sí sola pérdida de precisión; el error predictivo solo se "
                           "actualiza cuando hay observaciones comparables.")
            else:
                st.success("Monitoreo de la última ejecución: actualización, calidad y resultados sin alertas.")
        st.markdown("#### Limitaciones")
        st.warning("• Los valores de julio–diciembre de 2026 son **estimaciones**, no observaciones; todavía no se pueden "
                   "calcular errores para esos meses.\n\n"
                   "• El backtest tiene 12 cortes mensuales: es una muestra corta y retrospectiva, no un experimento "
                   "pre-registrado.\n\n"
                   "• Las series marcadas como **referencia** no pasaron la regla de aceptación; se publican con "
                   "Seasonal Naive para no presentar como aprobado un modelo que no cumple.\n\n"
                   "• La pandemia, la recuperación y el cambio metodológico 2022–2023 impiden un contrafactual limpio. "
                   "El modelo no anticipa pandemias, shocks ni revisiones de la fuente.\n\n"
                   "• Los detalles técnicos de parámetros, ejecuciones y artefactos están en MLflow y en el reporte de "
                   "validación; esta pestaña está pensada para decisiones, no para depuración.")
        if p.reporte:
            with st.expander("Ver el reporte de validación completo (detalle técnico)"):
                st.markdown(p.reporte)


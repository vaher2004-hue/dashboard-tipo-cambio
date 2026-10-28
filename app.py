import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import date

st.set_page_config(page_title="Tipo de cambio USD/CRC", page_icon="💱", layout="wide")

st.title("💱 Explorador del tipo de cambio — Costa Rica")
st.caption("Dólar estadounidense frente al colón costarricense | Datos históricos e indicadores económicos")

st.info(
    "Este panel combina el tipo de cambio de referencia con indicadores macroeconómicos. "
    "Las coincidencias entre indicadores no demuestran, por sí solas, que el tipo de cambio haya causado un resultado económico."
)

@st.cache_data(ttl=3600, show_spinner=False)
def get_fx(year):
    url = "https://tipodecambio.cr/api/v1/tipo-cambio/historico"
    r = requests.get(url, params={"desde": f"{year}-01-01", "hasta": f"{year}-12-31"}, timeout=30)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("ok", True):
        raise ValueError(payload.get("error", "La fuente no devolvió datos"))
    data = payload.get("data", [])
    if isinstance(data, dict):
        data = data.get("data", [])
    rows = []
    for item in data:
        dt = item.get("date") or item.get("fecha")
        buy = item.get("compra")
        sell = item.get("venta")
        if dt and buy is not None and sell is not None:
            rows.append({"fecha": pd.to_datetime(dt, errors="coerce"), "Compra": float(buy), "Venta": float(sell)})
    df = pd.DataFrame(rows).dropna(subset=["fecha"])
    if not df.empty:
        df = df.sort_values("fecha").drop_duplicates("fecha")
        df = df[df["fecha"].dt.year == year]
    return df

@st.cache_data(ttl=86400, show_spinner=False)
def get_world_bank(indicator, year):
    url = f"https://api.worldbank.org/v2/country/CRI/indicator/{indicator}"
    r = requests.get(url, params={"date": f"{year-1}:{year+1}", "format": "json", "per_page": 100}, timeout=20)
    r.raise_for_status()
    payload = r.json()
    if len(payload) < 2 or not payload[1]:
        return {}
    out = {}
    for item in payload[1]:
        if item.get("value") is not None and item.get("date"):
            out[int(item["date"])] = float(item["value"])
    return out

year = int(st.sidebar.number_input(
    "Año que querés consultar",
    min_value=1991,
    max_value=date.today().year,
    value=min(2020, date.today().year),
    step=1,
))

st.sidebar.markdown("---")
st.sidebar.write("**Qué incluye**")
st.sidebar.write("• Compra y venta del dólar")
st.sidebar.write("• Evolución diaria y resumen anual")
st.sidebar.write("• Inflación y crecimiento del PIB")
st.sidebar.write("• Contexto sobre posibles impactos")

try:
    with st.spinner(f"Consultando datos de {year}..."):
        fx = get_fx(year)
        inflation = get_world_bank("FP.CPI.TOTL.ZG", year)
        gdp = get_world_bank("NY.GDP.MKTP.KD.ZG", year)
        exports = get_world_bank("NE.EXP.GNFS.ZS", year)
        imports = get_world_bank("NE.IMP.GNFS.ZS", year)
except Exception as exc:
    st.error("No fue posible consultar una de las fuentes de datos en este momento.")
    st.caption(f"Detalle técnico: {exc}")
    st.markdown("[Consultar indicadores económicos del BCCR](https://www.bccr.fi.cr/indicadores-economicos)")
    st.stop()

if fx.empty:
    st.warning(f"No se encontraron observaciones históricas para {year}. Probá otro año o consultá la fuente oficial.")
    st.markdown("[Consultar indicadores económicos del BCCR](https://www.bccr.fi.cr/indicadores-economicos)")
    st.stop()

first = fx.iloc[0]
last = fx.iloc[-1]
avg_buy = fx["Compra"].mean()
avg_sell = fx["Venta"].mean()
min_sell = fx["Venta"].min()
max_sell = fx["Venta"].max()
change = (last["Venta"] / first["Venta"] - 1) * 100 if first["Venta"] else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Venta promedio anual", f"₡{avg_sell:,.2f}")
c2.metric("Compra promedio anual", f"₡{avg_buy:,.2f}")
c3.metric("Venta máxima observada", f"₡{max_sell:,.2f}")
c4.metric("Cambio entre primer y último dato", f"{change:+.2f}%")

st.subheader(f"Evolución diaria del tipo de cambio en {year}")
view = st.radio("Mostrar", ["Venta", "Compra", "Ambas"], horizontal=True)
if view == "Ambas":
    fig = px.line(fx, x="fecha", y=["Compra", "Venta"], labels={"fecha": "Fecha", "value": "Colones por dólar", "variable": "Indicador"})
else:
    fig = px.line(fx, x="fecha", y=view, labels={"fecha": "Fecha", view: "Colones por dólar"})
fig.update_layout(hovermode="x unified", legend_title_text="")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Indicadores económicos para contextualizar el año")
i1, i2, i3, i4 = st.columns(4)
inf = inflation.get(year)
gd = gdp.get(year)
ex = exports.get(year)
im = imports.get(year)
i1.metric("Inflación anual", f"{inf:.2f}%" if inf is not None else "Sin dato")
i2.metric("Crecimiento del PIB real", f"{gd:.2f}%" if gd is not None else "Sin dato")
i3.metric("Exportaciones (% del PIB)", f"{ex:.1f}%" if ex is not None else "Sin dato")
i4.metric("Importaciones (% del PIB)", f"{im:.1f}%" if im is not None else "Sin dato")

st.markdown("### ¿Qué podría significar el movimiento del dólar?")
if change > 2:
    st.write(
        f"El tipo de cambio de venta aumentó aproximadamente {change:.2f}% entre el primer y el último registro disponible. "
        "Al final del período se necesitaban más colones para comprar un dólar. Esto puede encarecer bienes importados o deudas en dólares "
        "para quienes reciben ingresos en colones, aunque el efecto depende de contratos, precios y condiciones de cada persona o empresa."
    )
elif change < -2:
    st.write(
        f"El tipo de cambio de venta disminuyó aproximadamente {abs(change):.2f}% entre el primer y el último registro disponible. "
        "Al final del período se necesitaban menos colones para comprar un dólar. Esto puede abaratar importaciones y pagos en dólares "
        "para quienes reciben ingresos en colones, pero reduce los colones recibidos por cada dólar convertido."
    )
else:
    st.write(
        f"Entre el primer y el último registro disponible, el tipo de cambio de venta cambió aproximadamente {change:+.2f}%. "
        "Aunque el cambio neto sea moderado, el gráfico puede mostrar fluctuaciones importantes dentro del año."
    )

a, b = st.columns(2)
with a:
    st.markdown("**Si el dólar sube**")
    st.write("• Los costos de importación o insumos cotizados en dólares pueden aumentar.")
    st.write("• Las cuotas de deudas en dólares pueden requerir más colones si los ingresos son en colones.")
    st.write("• Quienes reciben dólares pueden obtener más colones al convertirlos.")
with b:
    st.markdown("**Si el dólar baja**")
    st.write("• Algunos productos importados y pagos en dólares pueden abaratarse.")
    st.write("• Las deudas en dólares pueden requerir menos colones si los ingresos son en colones.")
    st.write("• Quienes reciben dólares obtienen menos colones por cada dólar convertido.")

st.caption(
    "Interpretación orientativa, no una estimación causal. Los efectos dependen de contratos, endeudamiento, coberturas cambiarias, "
    "precios, decisiones del BCCR y condiciones internacionales. Los indicadores macroeconómicos provienen del Banco Mundial; "
    "el tipo de cambio proviene de una API pública que atribuye los datos al BCCR. Confirmá las cifras importantes con fuentes oficiales."
)

with st.expander("Ver y descargar los datos diarios"):
    st.dataframe(fx, use_container_width=True, hide_index=True)
    st.download_button(
        "Descargar datos del año en CSV",
        data=fx.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"tipo_cambio_USD_CRC_{year}.csv",
        mime="text/csv",
    )

st.markdown("---")
st.markdown(
    "Fuentes: [BCCR — Indicadores económicos](https://www.bccr.fi.cr/indicadores-economicos) · "
    "[API histórica de tipo de cambio](https://tipodecambio.cr/api) · "
    "[Banco Mundial — datos de Costa Rica](https://data.worldbank.org/country/costa-rica)"
)

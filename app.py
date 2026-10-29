"""Streamlit dashboard - System Capacity & Care Load Analytics (Unaccompanied Children).
Run:  streamlit run app.py
"""
import os
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from uac_core import load_clean, add_metrics, forecast_ar_diff

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CSV = os.path.join(HERE, "data", "uac.csv")

st.set_page_config(page_title="UAC Capacity & Care Load", layout="wide")
st.title("System Capacity & Care Load Analytics - Unaccompanied Children")
st.caption("CBP custody and HHS care: load, intake vs discharge, length of stay, early warning and forecast.")


@st.cache_data(show_spinner=False)
def get_data(source, cap_pct):
    df, log = load_clean(source)
    d, cap = add_metrics(df, cap_pct)
    return d, cap, log


@st.cache_data(show_spinner=False)
def get_forecast(series, horizon, p):
    return forecast_ar_diff(series, horizon, p=p, window=365, n_sim=400, seed=1)


# ---------------------------------------------------------------- sidebar
st.sidebar.header("Controls")
up = st.sidebar.file_uploader("Upload dataset (CSV) - optional", type="csv")
if up is None and not os.path.exists(DEFAULT_CSV):
    st.info("Upload the dataset CSV from the sidebar to begin.")
    st.stop()
cap_pct = st.sidebar.slider("Capacity threshold (percentile of HHS care)", 50, 99, 90)
d, cap, log = get_data(up if up is not None else DEFAULT_CSV, cap_pct)

rng = st.sidebar.date_input("Date range", [d.index.min().date(), d.index.max().date()],
                            min_value=d.index.min().date(), max_value=d.index.max().date())
if len(rng) != 2:
    st.stop()
view = d.loc[str(rng[0]):str(rng[1])]
horizon = st.sidebar.slider("Forecast horizon (days)", 14, 90, 60)
target = st.sidebar.selectbox("Forecast target", ["HHS care", "Total system load (CBP + HHS, from 2024)"])
order_p = st.sidebar.selectbox("ARIMA order p (ARIMA(p,1,0))", [1, 3, 7], index=2)

# ---------------------------------------------------------------- KPI cards
def last_valid(col):
    s = view[col].dropna()
    return s.iloc[-1] if len(s) else np.nan

def show(v, fmt):
    return "n/a" if pd.isna(v) else format(v, fmt)

k = st.columns(6)
k[0].metric("Total system load", show(last_valid("total_load"), ",.0f"))
k[1].metric("Children in HHS care", show(last_valid("hhs_care"), ",.0f"))
k[2].metric("7-day net intake / day", show(last_valid("net_7d"), "+.1f"))
k[3].metric("Est. length of stay (days)", show(last_valid("est_stay_days"), ".0f"))
k[4].metric("Capacity utilization", show(last_valid("utilization"), ".0%"))
alert_now = bool(view["alert"].iloc[-1])
k[5].metric("Early-warning alert", "ON" if alert_now else "off")
st.caption(f"Assumed capacity threshold = {cap:,.0f} children (percentile {cap_pct} of HHS care, whole dataset). "
           "CBP-based metrics exist only from 31 Jan 2024.")

t1, t2, t3, t4, t5, t6 = st.tabs(["Trends", "Intake vs Discharge", "Seasonality", "Forecast", "Alerts", "Data quality"])

with t1:
    fig = px.line(view, y="hhs_care", labels={"hhs_care": "Children in HHS care", "Date": ""}, title="Children in HHS care")
    fig.add_hline(y=cap, line_dash="dash", annotation_text="capacity threshold")
    st.plotly_chart(fig, use_container_width=True)
    c = view.dropna(subset=["cbp_custody"])
    if len(c):
        st.plotly_chart(px.line(c, y=["cbp_custody", "total_load"], title="CBP custody and total system load (from 2024)"),
                        use_container_width=True)
    st.plotly_chart(px.line(view, y="est_stay_days", title="Estimated length of stay (days) = HHS care / 30-day avg discharges"),
                    use_container_width=True)

with t2:
    c = view.dropna(subset=["cbp_custody"])
    if len(c):
        flows = c[["cbp_in", "cbp_transfer", "hhs_discharge"]].rolling("7D", min_periods=3).mean()
        st.plotly_chart(px.line(flows, title="Flows, 7-day average (children per reported day)"), use_container_width=True)
        st.plotly_chart(px.area(c, y="net_7d", title="Net intake into HHS (transfers in - discharges), 7-day average"),
                        use_container_width=True)
        st.plotly_chart(px.line(c, y="care_change_30d", title="30-day change in HHS care (backlog indicator)"),
                        use_container_width=True)
    else:
        st.info("CBP flow data is not available in the selected range (it starts on 31 Jan 2024).")

with t3:
    p = view.assign(year=view.index.year, month=view.index.month).pivot_table(
        values="hhs_care", index="month", columns="year", aggfunc="mean")
    st.plotly_chart(px.imshow(p, aspect="auto", color_continuous_scale="Blues", text_auto=".0f",
                              title="Average children in HHS care: month x year"), use_container_width=True)
    c = view.dropna(subset=["cbp_in"])
    if len(c):
        m = c.assign(year=c.index.year, month=c.index.month).groupby(["year", "month"])["cbp_in"].mean().reset_index()
        m["year"] = m["year"].astype(str)
        st.plotly_chart(px.line(m, x="month", y="cbp_in", color="year", markers=True, log_y=True,
                                title="Average daily apprehensions by month (log scale)"), use_container_width=True)

with t4:
    col = "hhs_care" if target == "HHS care" else "total_load"
    series = d[col].dropna()
    fc = get_forecast(series, horizon, order_p)
    hist = series.asfreq("D").interpolate().iloc[-240:]
    fig = go.Figure()
    fig.add_scatter(x=hist.index, y=hist, name="Actual")
    fig.add_scatter(x=fc.index, y=fc["mean"], name="Forecast")
    fig.add_scatter(x=fc.index, y=fc["lower"], line=dict(width=0), showlegend=False, hoverinfo="skip")
    fig.add_scatter(x=fc.index, y=fc["upper"], fill="tonexty", line=dict(width=0), name="80% band")
    fig.update_layout(title=f"{horizon}-day forecast - {target} (ARIMA({order_p},1,0))")
    st.plotly_chart(fig, use_container_width=True)
    st.write(f"Forecast on day {horizon}: **{fc['mean'].iloc[-1]:,.0f}** children "
             f"(80% band {fc['lower'].iloc[-1]:,.0f} - {fc['upper'].iloc[-1]:,.0f}); "
             f"utilization of the assumed threshold: **{fc['mean'].iloc[-1] / cap:.0%}**.")
    st.markdown("**Surge stress test** - days until the capacity threshold at a sustained net intake")
    cur = d["hhs_care"].iloc[-1]
    rate = st.slider("Sustained net intake (children per day)", 10, 200, 125)
    st.write(f"At +{rate} children/day, HHS care would reach the threshold in about "
             f"**{(cap - cur) / rate:,.0f} days** (from {cur:,.0f} today).")

with t5:
    a = view[view["alert"]]
    st.write(f"Alert days in selected range: **{len(a)}** of {len(view)}")
    st.caption("Rule: 7-day average net intake > 0 AND 7-day discharge/transfer ratio < 0.9")
    if len(a):
        monthly = a.resample("MS").size().rename("alert_days").reset_index()
        st.plotly_chart(px.bar(monthly, x="Date", y="alert_days", title="Alert days per month"), use_container_width=True)
        st.dataframe(a[["hhs_care", "net_7d", "dis_ratio_7d", "utilization"]].round(2))

with t6:
    st.write("How the raw file was cleaned:")
    st.json({k_: v for k_, v in log.items()})

st.download_button("Download processed data (CSV)", view.to_csv().encode(), "uac_processed.csv")

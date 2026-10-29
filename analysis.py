# %% [markdown]
# # System Capacity & Care Load Analytics - Unaccompanied Children
# Full analysis: cleaning, KPIs, EDA, lag analysis, early-warning rule, forecasting.
# Run top to bottom. Outputs: charts/*.png and results.json (used to build the report).

# %% Setup
import json, warnings, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from uac_core import (load_clean, add_metrics, forecast_ar_diff, forecast_baseline, _daily)
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
DATA = os.path.join(HERE, "data", "uac.csv")
os.makedirs(os.path.join(HERE, "charts"), exist_ok=True)
R = {}   # results dictionary -> results.json

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 9, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True})

def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "charts", name), dpi=200)
    plt.close(fig)

def runs(mask):
    """Continuous True runs of a boolean daily Series -> list of (start, end, days)."""
    out, start = [], None
    for dt, v in mask.items():
        if v and start is None: start = dt
        if (not v) and start is not None:
            out.append((start, prev, (prev - start).days + 1)); start = None
        prev = dt
    if start is not None: out.append((start, prev, (prev - start).days + 1))
    return out

# %% 1. Load and clean
df, log = load_clean(DATA)
R["quality"] = log
d, CAP = add_metrics(df, cap_pct=90)
R["capacity_threshold"] = CAP
print(json.dumps(log, indent=1, default=str)); print("capacity assumption (P90 HHS care):", CAP)

# %% 2. Reconciliation: do flows explain the change in HHS care? (data validation)
r = d[d["reported"]].copy()
r["gap"] = r.index.to_series().diff().dt.days
r["dcare"] = r["hhs_care"].diff()
r["net"] = r["cbp_transfer"] - r["hhs_discharge"]
c = r[r["cbp_transfer"].notna()]
g1 = c[c["gap"] == 1]
R["recon"] = {"n_consecutive_days": int(len(g1)),
              "corr_dcare_net": float(g1["dcare"].corr(g1["net"])),
              "mean_dcare": float(g1["dcare"].mean()), "mean_net": float(g1["net"].mean()),
              "cum_dcare_cbp_window": float(c["dcare"].sum()), "cum_net_cbp_window": float(c["net"].sum())}
byyr = c.groupby(c.index.year).agg(dcare=("dcare", "sum"), net=("net", "sum"))
R["recon"]["by_year"] = {int(k): {"dcare": float(v.dcare), "net": float(v.net)} for k, v in byyr.iterrows()}
wd = r.index.day_name().value_counts()
R["reported_weekdays"] = {k: int(v) for k, v in wd.items()}
print(R["recon"])

# %% 3. Headline numbers
hc = d["hhs_care"]
R["hhs"] = {"peak": float(hc.max()), "peak_date": str(hc.idxmax().date()),
            "min": float(hc.min()), "min_date": str(hc.idxmin().date()),
            "mean": float(hc.mean()), "current": float(hc.iloc[-1]), "current_date": str(hc.index[-1].date()),
            "current_vs_peak_pct": float(hc.iloc[-1] / hc.max() * 100)}
yr = d.groupby(d.index.year).agg(care_mean=("hhs_care", "mean"), care_min=("hhs_care", "min"),
                                  care_max=("hhs_care", "max"), dis_mean=("hhs_discharge", "mean"),
                                  stay_med=("est_stay_days", "median"))
R["by_year"] = {int(k): {kk: float(vv) for kk, vv in v.items()} for k, v in yr.iterrows()}
cb = d[d["cbp_custody"].notna()]
R["cbp"] = {"start": str(cb.index.min().date()), "n_days": int(len(cb)),
            "cbp_in_mean": float(cb["cbp_in"].mean()), "cbp_in_peak": float(cb["cbp_in"].max()),
            "cbp_in_peak_date": str(cb["cbp_in"].idxmax().date()),
            "custody_peak": float(cb["cbp_custody"].max()), "custody_peak_date": str(cb["cbp_custody"].idxmax().date()),
            "custody_mean": float(cb["cbp_custody"].mean()), "custody_current": float(cb["cbp_custody"].iloc[-1]),
            "transfer_mean": float(cb["cbp_transfer"].mean()),
            "total_peak": float(cb["total_load"].max()), "total_peak_date": str(cb["total_load"].idxmax().date()),
            "total_current": float(cb["total_load"].iloc[-1]), "total_mean": float(cb["total_load"].mean())}
cbyr = cb.groupby(cb.index.year).agg(cbp_in=("cbp_in", "mean"), custody=("cbp_custody", "mean"),
                                      transfer=("cbp_transfer", "mean"), discharge=("hhs_discharge", "mean"))
R["cbp_by_year"] = {int(k): {kk: float(vv) for kk, vv in v.items()} for k, v in cbyr.iterrows()}

# %% 4. Capacity / surge periods (assumption: threshold = 90th percentile of HHS care)
over = d["utilization"] > 1
sur = [(str(a.date()), str(b.date()), int(n)) for a, b, n in runs(over) if n >= 7]
R["surge_periods"] = sur
R["days_over_capacity"] = int(over.sum())
R["days_over_capacity_pct"] = float(over.mean() * 100)
R["sensitivity"] = {str(p): {"threshold": float(hc.quantile(p / 100)), "days_over": int((hc > hc.quantile(p / 100)).sum())}
                    for p in (80, 90, 95)}
R["utilization_current"] = float(d["utilization"].iloc[-1])
R["utilization_peak"] = float(d["utilization"].max())
print(sur)

# %% 5. Intake vs discharge (2024 onwards, where CBP data exists)
w = d.loc[d["cbp_custody"].notna()]
R["flow"] = {"dis_ratio_mean_by_year": {int(k): float(v) for k, v in w["dis_ratio_7d"].groupby(w.index.year).median().items()},
             "pct_days_ratio_below_1": float((w["dis_ratio_7d"] < 1).mean() * 100),
             "pct_days_net_positive": float((w["net_7d"] > 0).mean() * 100)}
pos_runs = runs((w["net_7d"] > 0))
longest = max(pos_runs, key=lambda x: x[2]) if pos_runs else None
R["flow"]["longest_positive_run"] = [str(longest[0].date()), str(longest[1].date()), int(longest[2])] if longest else None
R["flow"]["net7_current"] = float(w["net_7d"].iloc[-1]); R["flow"]["ratio7_current"] = float(w["dis_ratio_7d"].iloc[-1])
R["flow"]["net7_peak"] = float(w["net_7d"].max()); R["flow"]["net7_peak_date"] = str(w["net_7d"].idxmax().date())

# %% 6. Length of stay (Little's law)
R["stay"] = {"current": float(d["est_stay_days"].iloc[-1]),
             "median_all": float(d["est_stay_days"].median()),
             "min": float(d["est_stay_days"].min()), "min_date": str(d["est_stay_days"].idxmin().date()),
             "max": float(d["est_stay_days"].max()), "max_date": str(d["est_stay_days"].idxmax().date()),
             "median_over_cap": float(d.loc[over, "est_stay_days"].median()),
             "median_under_cap": float(d.loc[~over, "est_stay_days"].median())}

# %% 7. Seasonality
cbm = cb.groupby([cb.index.year, cb.index.month])["cbp_in"].mean().unstack(0)
R["season_cbp_in_by_month"] = {int(m): {int(y): (None if pd.isna(v) else float(v)) for y, v in row.items()} for m, row in cbm.iterrows()}
mm = cb.groupby(cb.index.month)["cbp_in"].mean()
R["season_top_months"] = [int(m) for m in mm.sort_values(ascending=False).index[:3]]
R["season_low_months"] = [int(m) for m in mm.sort_values().index[:3]]
ph = d["hhs_care"].resample("MS").mean()
R["hhs_monthly_peak_month"] = str(ph.idxmax().date())

# %% 8. Lag analysis (daily values, detrended with a 31-day centred mean so that the
# huge level shifts between years do not create fake correlation)
def detrend(x): return x - x.rolling(31, center=True, min_periods=10).mean()
cin, ctr, cdis = detrend(d["cbp_in"]), detrend(d["cbp_transfer"]), detrend(d["hhs_discharge"])
sub = d["cbp_custody"].notna()
dcare = d["hhs_care"].where(d["reported"]).diff()      # day-over-day change, only between two reported days
cc1 = {k: float(cin[sub].corr(ctr.shift(-k)[sub])) for k in range(0, 8)}     # apprehension -> transfer k days later
cc2 = {k: float(ctr.shift(k)[sub].corr(dcare[sub])) for k in range(0, 6)}    # transfer k days ago -> change in HHS care today
cc3 = {k: float(cdis.shift(k)[sub].corr(dcare[sub])) for k in range(0, 6)}   # discharge k days ago -> change in HHS care today
R["lag"] = {"apprehension_to_transfer": cc1, "transfer_to_hhs_growth": cc2, "discharge_to_hhs_growth": cc3,
            "best_lag_in_to_transfer": int(max(cc1, key=cc1.get)), "best_lag_transfer_to_hhs": int(max(cc2, key=cc2.get))}
cs = d[sub]
R["cbp_stay_by_year"] = {int(y): float(g["cbp_custody"].mean() / g["cbp_transfer"].mean()) for y, g in cs.groupby(cs.index.year)}
print(R["lag"]["best_lag_in_to_transfer"], R["lag"]["best_lag_transfer_to_hhs"], R["cbp_stay_by_year"])

# %% 9. Early-warning rule evaluation (does an alert precede growth in HHS care 14 days later?)
fut = d["hhs_care"].shift(-14) - d["hhs_care"]
ev = d.loc[sub & fut.notna() & d["net_7d"].notna() & d["dis_ratio_7d"].notna()].copy()
ev["fut"] = fut
base = float((ev["fut"] > 0).mean() * 100)
grid = {}
for th in (0.8, 0.9, 1.0):
    a = (ev["net_7d"] > 0) & (ev["dis_ratio_7d"] < th)
    grid[str(th)] = {"alert_days": int(a.sum()),
                     "pct_followed_by_growth": float((ev.loc[a, "fut"] > 0).mean() * 100) if a.sum() else None,
                     "mean_future_change_alert": float(ev.loc[a, "fut"].mean()) if a.sum() else None,
                     "mean_future_change_other": float(ev.loc[~a, "fut"].mean())}
R["alert"] = {"base_rate_growth_pct": base, "n_eval_days": int(len(ev)), "grid": grid,
              "alert_days_total": int(d["alert"].sum()),
              "alert_by_year": {int(k): int(v) for k, v in d.loc[d["alert"]].groupby(d.loc[d["alert"]].index.year).size().items()},
              "alert_by_month": {str(k): int(v) for k, v in d["alert"].resample("MS").sum().loc[lambda s: s > 0].items()},
              "last_alert_date": str(d.index[d["alert"]].max().date()) if d["alert"].any() else None}

# %% 10. Forecasting - backtest (time-based) then final forecast
models = {
    "Naive (last value)": lambda tr, h: forecast_baseline(tr, h, "naive"),
    "7-day moving average": lambda tr, h: forecast_baseline(tr, h, "ma7"),
    "Drift (last 30 days)": lambda tr, h: forecast_baseline(tr, h, "drift30"),
    "ARIMA(1,1,0)": lambda tr, h: forecast_ar_diff(tr, h, p=1, window=365, n_sim=20)["mean"],
    "ARIMA(3,1,0)": lambda tr, h: forecast_ar_diff(tr, h, p=3, window=365, n_sim=20)["mean"],
    "ARIMA(7,1,0)": lambda tr, h: forecast_ar_diff(tr, h, p=7, window=365, n_sim=20)["mean"],
}
def backtest(y, H, n, step):
    y = _daily(y); res = {k: [] for k in models}
    for i in range(n):
        e = len(y) - H - i * step; tr, te = y.iloc[:e], y.iloc[e:e + H]
        for k, f in models.items():
            p = f(tr, H).values
            res[k].append((np.abs(te.values - p).mean(), (np.abs(te.values - p) / te.values).mean() * 100))
    return {k: [float(v) for v in np.mean(a, axis=0)] for k, a in res.items()}
BT = {}
for name, y in [("hhs_care", d["hhs_care"]), ("total_load", d["total_load"])]:
    BT[name] = {"holdout60": backtest(y, 60, 1, 1), "rolling30": backtest(y, 30, 12, 30)}
R["backtest"] = BT
BEST = min(["ARIMA(1,1,0)", "ARIMA(3,1,0)", "ARIMA(7,1,0)"], key=lambda k: BT["hhs_care"]["rolling30"][k][0])
R["best_model"] = BEST
print("best ARIMA by rolling-origin MAE:", BEST)
P_BEST = int(BEST[6])
H = 60
FC = {}
for name, y in [("hhs_care", d["hhs_care"]), ("total_load", d["total_load"])]:
    f = forecast_ar_diff(y, H, p=P_BEST, window=365, n_sim=1000, seed=1)
    FC[name] = f
    R.setdefault("forecast", {})[name] = {
        "start": str(f.index[0].date()), "end": str(f.index[-1].date()),
        "last_actual": float(_daily(y).iloc[-1]),
        "d30": [float(f["mean"].iloc[29]), float(f["lower"].iloc[29]), float(f["upper"].iloc[29])],
        "d60": [float(f["mean"].iloc[59]), float(f["lower"].iloc[59]), float(f["upper"].iloc[59])]}
R["forecast"]["util_d60_upper"] = float(FC["hhs_care"]["upper"].iloc[59] / CAP)
R["forecast"]["util_d60_mean"] = float(FC["hhs_care"]["mean"].iloc[59] / CAP)
# Surge stress test: how long until the capacity threshold is reached at a sustained net intake?
cur = float(d["hhs_care"].iloc[-1])
R["stress"] = {"current": cur, "threshold": CAP,
               "net_peak_observed": R["flow"]["net7_peak"],
               "scenarios": {str(r_): {"days_to_threshold": float((CAP - cur) / r_), "care_after_60d": float(cur + r_ * 60),
                                       "util_after_60d": float((cur + r_ * 60) / CAP)} for r_ in (25, 50, 100, 125)}}
# naive check at the 60-day mark for context
R["forecast"]["horizon"] = H

# %% 11. Charts
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
def fmt_k(ax):
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
def yearly(ax, first, last):
    ax.set_xlim(first, last)
    ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
def halfyearly(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7])); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))

# Fig 1: HHS care with capacity threshold
fig, ax = plt.subplots(figsize=(7.2, 3.3))
ax.plot(d.index, d["hhs_care"], color=BLUE, lw=1.6)
ax.axhline(CAP, color=INK2, lw=1, ls=(0, (4, 3)))
ax.text(pd.Timestamp("2022-06-01"), CAP * 1.04, f"Assumed capacity threshold = {CAP:,.0f} (90th percentile of HHS care)", color=INK2, fontsize=8, va="bottom")
ax.fill_between(d.index, CAP, d["hhs_care"], where=d["hhs_care"] > CAP, color=BLUE, alpha=0.15, lw=0)
pk = hc.idxmax()
ax.annotate(f"Peak {hc.max():,.0f} ({pk:%d %b %Y})", (pk, hc.max()), xytext=(10, -2), textcoords="offset points", fontsize=8, color=INK, va="top")
ax.annotate(f"Latest {hc.iloc[-1]:,.0f}", (hc.index[-1], hc.iloc[-1]), xytext=(-4, 10), textcoords="offset points", fontsize=8, ha="right", color=INK)
ax.set_title("Children in HHS care, March 2021 - October 2026"); ax.set_ylabel("Children"); fmt_k(ax)
ax.set_ylim(0, hc.max() * 1.1); yearly(ax, d.index[0], d.index[-1] + pd.Timedelta(days=20))
save(fig, "fig1_hhs_care.png")

# Fig 2: CBP flows vs HHS discharges (7-day avg), full view and zoom on 2025-26
s_ = d.loc[d["cbp_custody"].notna()]
a_in = s_["cbp_in"].rolling("7D", min_periods=3).mean()
a_tr = s_["cbp_transfer"].rolling("7D", min_periods=3).mean()
a_di = s_["hhs_discharge"].rolling("7D", min_periods=3).mean()
fig, axs = plt.subplots(2, 1, figsize=(7.2, 5.0))
for ax, lo in zip(axs, (None, "2025-04-01")):
    for ser, col in [(a_in, BLUE), (a_tr, ORANGE), (a_di, AQUA)]:
        z = ser if lo is None else ser.loc[lo:]
        ax.plot(z.index, z, color=col, lw=1.5)
    ax.set_ylabel("Children per day"); halfyearly(ax)
axs[0].set_title("Daily flows, 7-day average (children per reported day)")
axs[1].set_title("Zoom: April 2025 onward"); axs[1].set_ylim(0, 40)
axs[0].legend(handles=[plt.Line2D([], [], color=c, lw=2) for c in (BLUE, ORANGE, AQUA)],
              labels=["Apprehended into CBP custody", "Transferred out of CBP to HHS", "Discharged from HHS care"], frameon=False, loc="upper right", fontsize=8)
save(fig, "fig2_flows.png")

# Fig 3: Net intake (7d avg) and 30-day change in HHS care
fig, axs = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True)
s = s_
axs[0].fill_between(s.index, 0, s["net_7d"], where=s["net_7d"] >= 0, color=ORANGE, alpha=0.85, lw=0)
axs[0].fill_between(s.index, 0, s["net_7d"], where=s["net_7d"] < 0, color=BLUE, alpha=0.85, lw=0)
axs[0].axhline(0, color=INK2, lw=0.8)
axs[0].set_title("Net intake into HHS: transfers in minus discharges (7-day average per day)"); axs[0].set_ylabel("Children / day")
axs[0].text(0.60, 0.93, "Orange: intake above discharges (load builds)", transform=axs[0].transAxes, fontsize=8, color=INK, va="top")
axs[0].text(0.60, 0.81, "Blue: discharges above intake (load falls)", transform=axs[0].transAxes, fontsize=8, color=INK, va="top")
axs[1].plot(s.index, s["care_change_30d"], color=BLUE, lw=1.5); axs[1].axhline(0, color=INK2, lw=0.8)
axs[1].set_title("30-day change in HHS care (backlog indicator)"); axs[1].set_ylabel("Children"); halfyearly(axs[1])
save(fig, "fig3_net_intake.png")

# Fig 4: heatmap month x year of average HHS care
pv = d.assign(y=d.index.year, m=d.index.month).pivot_table(values="hhs_care", index="m", columns="y", aggfunc="mean")
from matplotlib.colors import LinearSegmentedColormap
cmap = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"])
fig, ax = plt.subplots(figsize=(6.4, 4.2))
im = ax.imshow(pv.values / 1000, aspect="auto", cmap=cmap)
ax.set_xticks(range(len(pv.columns))); ax.set_xticklabels(pv.columns)
ax.set_yticks(range(12)); ax.set_yticklabels(MONTHS); ax.grid(False)
vmax = np.nanmax(pv.values / 1000)
for i in range(pv.shape[0]):
    for j in range(pv.shape[1]):
        v = pv.values[i, j] / 1000
        if not np.isnan(v): ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8, color="#ffffff" if v > vmax * 0.5 else INK)
ax.set_title("Average children in HHS care by month and year (thousands)")
cb_ = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03); cb_.outline.set_visible(False)
save(fig, "fig4_heatmap.png")

# Fig 5: apprehensions by calendar month, per year (log scale)
fig, ax = plt.subplots(figsize=(7.2, 3.3))
ends = {}
for yv, col in zip((2024, 2025, 2026), (BLUE, ORANGE, AQUA)):
    ser = cbm[yv].dropna()
    ax.plot(ser.index, ser.values, color=col, lw=1.8, marker="o", ms=3.5, label=str(yv))
    ends[yv] = (ser.index[-1], ser.values[-1])
ax.set_yscale("log"); ax.set_yticks([5, 10, 20, 50, 100, 200]); ax.yaxis.set_major_formatter(matplotlib.ticker.ScalarFormatter())
ax.set_xticks(range(1, 13)); ax.set_xticklabels(MONTHS); ax.set_xlim(0.7, 12.4)
ax.text(ends[2024][0] + 0.2, ends[2024][1], "2024", fontsize=8, va="center")
ax.text(ends[2025][0] + 0.2, ends[2025][1] * 1.25, "2025", fontsize=8, va="center")
ax.text(ends[2026][0] + 0.2, ends[2026][1] * 0.8, "2026", fontsize=8, va="center")
ax.set_title("Average daily apprehensions into CBP custody, by month (log scale)"); ax.set_ylabel("Children per day")
ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=3)
save(fig, "fig5_season.png")

# Fig 6: estimated length of stay
fig, ax = plt.subplots(figsize=(7.2, 3.1))
es = d["est_stay_days"].dropna()
ax.plot(es.index, es, color=BLUE, lw=1.5)
ax.set_title("Estimated length of stay: HHS care / 30-day average discharges"); ax.set_ylabel("Days")
yearly(ax, es.index[0], es.index[-1] + pd.Timedelta(days=20))
ax.annotate(f"Latest {es.iloc[-1]:.0f} days", (es.index[-1], es.iloc[-1]), xytext=(-12, -45), textcoords="offset points", ha="right", fontsize=8,
            arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
ax.annotate(f"2021-2024 typical: about {R['by_year'][2023]['stay_med']:.0f} days", (pd.Timestamp("2023-01-01"), 35), xytext=(0, 40), textcoords="offset points",
            ha="center", fontsize=8, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
save(fig, "fig6_stay.png")

# Fig 7: lag correlations
fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
axs[0].bar(list(cc1.keys()), list(cc1.values()), color=BLUE, width=0.7)
axs[0].set_title("Apprehension -> transfer out of CBP", fontsize=9); axs[0].set_xlabel("Days after apprehension"); axs[0].set_ylabel("Correlation (detrended daily values)")
xs = np.arange(len(cc2)); wd_ = 0.38
axs[1].bar(xs - wd_ / 2, list(cc2.values()), width=wd_, color=ORANGE)
axs[1].bar(xs + wd_ / 2, list(cc3.values()), width=wd_, color=BLUE)
axs[1].axhline(0, color=INK2, lw=0.8)
axs[1].set_xticks(xs); axs[1].set_title("Same-day change in HHS care", fontsize=9); axs[1].set_xlabel("Days earlier")
axs[1].legend(handles=[plt.Rectangle((0, 0), 1, 1, color=ORANGE), plt.Rectangle((0, 0), 1, 1, color=BLUE)],
              labels=["Transfers from CBP", "HHS discharges"], frameon=False, fontsize=8, loc="lower right")
save(fig, "fig7_lag.png")

# Fig 8: forecast
fig, ax = plt.subplots(figsize=(7.2, 3.3))
hist = _daily(d["hhs_care"]).iloc[-240:]
f = FC["hhs_care"]
ax.plot(hist.index, hist, color=BLUE, lw=1.6)
ax.plot(f.index, f["mean"], color=ORANGE, lw=1.8)
ax.fill_between(f.index, f["lower"], f["upper"], color=ORANGE, alpha=0.18, lw=0)
ax.text(hist.index[30], hist.iloc[0] - 10, "Actual", color=INK, fontsize=8)
ax.text(f.index[-1], f["upper"].iloc[-1] + 15, "Forecast and 80% band", color=INK, fontsize=8, ha="right")
ax.set_title(f"60-day forecast of children in HHS care ({BEST})"); ax.set_ylabel("Children"); fmt_k(ax)
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
save(fig, "fig8_forecast.png")

# Fig 9: alert days by month
fig, ax = plt.subplots(figsize=(7.2, 2.8))
am = d["alert"].resample("MS").sum().loc["2024-02-01":]
ax.bar(am.index, am.values, width=20, color=ORANGE)
ax.set_title("Early-warning alert days per month"); ax.set_ylabel("Alert days"); halfyearly(ax)
save(fig, "fig9_alerts.png")

# %% 12. Save
d.to_csv(os.path.join(HERE, "data", "uac_clean_with_metrics.csv"))
json.dump(R, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=str)
print("saved results.json and charts")

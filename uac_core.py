"""Core data preparation, metrics and forecasting helpers for the
System Capacity & Care Load Analytics (Unaccompanied Children) project."""
import numpy as np
import pandas as pd

STOCKS = ["cbp_custody", "hhs_care"]
FLOWS = ["cbp_in", "cbp_transfer", "hhs_discharge"]
NUMERIC = ["cbp_in", "cbp_custody", "cbp_transfer", "hhs_care", "hhs_discharge"]


def _rename(df):
    """Map the original column names to short names (robust to the * footnote)."""
    new = {}
    for c in df.columns:
        k = c.lower()
        if k.strip() == "date":
            new[c] = "Date"
        elif "apprehended" in k:
            new[c] = "cbp_in"
        elif "transferred" in k:
            new[c] = "cbp_transfer"
        elif "in cbp" in k:
            new[c] = "cbp_custody"
        elif "discharged" in k:
            new[c] = "hhs_discharge"
        elif "in hhs" in k:
            new[c] = "hhs_care"
    return df.rename(columns=new)


def load_clean(source, max_gap_days=30, outlier_rel=0.12, outlier_max_neighbor_gap=4):
    """Read the raw CSV and return (daily_df, log).

    Steps: rename -> parse dates -> numeric -> drop duplicate dates (keep first listed)
    -> keep the last continuous segment (no gap > max_gap_days) -> remove isolated
    spikes in HHS care -> daily calendar -> interpolate STOCK gaps only.
    Flows are never interpolated (a day with no report stays missing).
    """
    raw = pd.read_csv(source)
    log = {"raw_rows": int(len(raw))}
    df = _rename(raw)
    df["Date"] = pd.to_datetime(df["Date"], format="mixed")
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False), errors="coerce")

    # duplicates: same date listed twice (values may conflict) -> keep first listed
    dup_mask = df["Date"].duplicated(keep=False)
    log["duplicate_dates"] = int(df.loc[dup_mask, "Date"].nunique())
    conflict = df[dup_mask].groupby("Date")["hhs_care"].agg(lambda s: s.max() - s.min())
    log["duplicate_max_conflict"] = float(conflict.max()) if len(conflict) else 0.0
    log["duplicate_periods"] = (str(df.loc[dup_mask, "Date"].min().date()),
                                str(df.loc[dup_mask, "Date"].max().date())) if dup_mask.any() else None
    df = df.drop_duplicates("Date", keep="first").sort_values("Date").reset_index(drop=True)

    # long gap: keep only the last continuous segment
    gaps = df["Date"].diff().dt.days
    big = df.index[gaps > max_gap_days]
    log["long_gap_days"] = int(gaps.max()) if gaps.max() > max_gap_days else 0
    log["dropped_rows_before_gap"] = 0
    if len(big):
        cut = big[-1]
        log["dropped_rows_before_gap"] = int(cut)
        log["long_gap_from"] = str(df.loc[cut - 1, "Date"].date())
        log["long_gap_to"] = str(df.loc[cut, "Date"].date())
        df = df.iloc[cut:].reset_index(drop=True)

    # isolated spikes in HHS care (compare with centred 9-observation median)
    med = df["hhs_care"].rolling(9, center=True, min_periods=5).median()
    rel = (df["hhs_care"] - med).abs() / df["hhs_care"]
    prev_gap = df["Date"].diff().dt.days
    next_gap = -df["Date"].diff(-1).dt.days
    spike = (rel > outlier_rel) & (prev_gap <= outlier_max_neighbor_gap) & (next_gap <= outlier_max_neighbor_gap)
    log["outliers_removed"] = [(str(d.date()), int(v)) for d, v in zip(df.loc[spike, "Date"], df.loc[spike, "hhs_care"])]
    df.loc[spike, "hhs_care"] = np.nan

    df = df.set_index("Date")
    reported = df["hhs_discharge"].notna() | df["hhs_care"].notna()
    log["reported_days"] = int(reported.sum())
    full = df.asfreq("D")
    full["reported"] = full.index.isin(df.index)
    log["calendar_days"] = int(len(full))
    log["unreported_days"] = int((~full["reported"]).sum())
    # interpolate stock gaps (inside only); flows stay NaN
    before = full[STOCKS].isna().sum()
    full[STOCKS] = full[STOCKS].interpolate(limit_area="inside")
    log["stock_days_filled"] = int(full["hhs_care"].notna().sum() - df["hhs_care"].notna().sum())
    gap_runs = (~full["reported"]).astype(int)
    runs = gap_runs.groupby((gap_runs != gap_runs.shift()).cumsum()).sum()
    log["longest_unreported_run"] = int(runs.max())
    log["start"] = str(full.index.min().date())
    log["end"] = str(full.index.max().date())
    cbp = full["cbp_custody"].dropna()
    log["cbp_start"] = str(cbp.index.min().date()) if len(cbp) else None
    return full, log


def add_metrics(df, cap_pct=90):
    """Add KPI columns. Returns (df, capacity_threshold)."""
    d = df.copy()
    d["total_load"] = d["cbp_custody"] + d["hhs_care"]
    d["net_intake"] = d["cbp_transfer"] - d["hhs_discharge"]
    d["care_growth"] = d["hhs_care"].diff()
    # rolling averages of flows use only reported days inside the window
    d["discharge_7d"] = d["hhs_discharge"].rolling("7D", min_periods=3).mean()
    d["discharge_30d"] = d["hhs_discharge"].rolling("30D", min_periods=10).mean()
    d["transfer_7d"] = d["cbp_transfer"].rolling("7D", min_periods=3).mean()
    d["net_7d"] = d["net_intake"].rolling("7D", min_periods=3).mean()
    both = d["cbp_transfer"].notna() & d["hhs_discharge"].notna()
    num = d["hhs_discharge"].where(both).rolling("7D", min_periods=3).sum()
    den = d["cbp_transfer"].where(both).rolling("7D", min_periods=3).sum()
    d["dis_ratio_7d"] = num / den.replace(0, np.nan)
    # Backlog is measured from the STOCK (HHS care), not by summing flows: flows are
    # only reported on ~5 of 7 days, so cumulative flow sums drift away from reality.
    d["care_change_30d"] = d["hhs_care"] - d["hhs_care"].shift(30)
    d["load_7d"] = d["total_load"].rolling(7, min_periods=4).mean()
    d["load_30d"] = d["total_load"].rolling(30, min_periods=15).mean()
    d["care_7d"] = d["hhs_care"].rolling(7, min_periods=4).mean()
    d["volatility_14d"] = d["total_load"].rolling(14, min_periods=7).std()
    d["est_stay_days"] = d["hhs_care"] / d["discharge_30d"].replace(0, np.nan)
    cap = float(d["hhs_care"].quantile(cap_pct / 100))
    d["utilization"] = d["hhs_care"] / cap
    d["alert"] = (d["net_7d"] > 0) & (d["dis_ratio_7d"] < 0.9)
    return d, cap


# ---------------------------------------------------------------------------
# Forecasting (numpy only): ARIMA(p,1,0) = autoregression on daily changes
# ---------------------------------------------------------------------------
def _future_index(series, h):
    return pd.date_range(series.index[-1] + pd.Timedelta(days=1), periods=h, freq="D")


def _daily(series):
    return series.dropna().asfreq("D").interpolate()


def _fit_ar_diff(y, p, window, drift):
    """OLS fit of  dy_t = c + a1*dy_{t-1} + ... + ap*dy_{t-p} + e_t  on the last `window` days."""
    dy = np.diff(y.values[-(window + 1):])
    rows = [dy[t - p:t][::-1] for t in range(p, len(dy))]
    X = np.array(rows) if p else np.empty((len(dy), 0))
    t = dy[p:]
    if drift:
        X = np.column_stack([np.ones(len(t)), X])
    coef, *_ = np.linalg.lstsq(X, t, rcond=None)
    resid = t - X @ coef
    return coef, resid, dy


def forecast_ar_diff(series, h, p=3, window=365, drift=False, n_sim=400, seed=0, alpha=0.2):
    """Forecast `h` days. Returns DataFrame[mean, lower, upper] (lower/upper = 1-alpha central band)."""
    y = _daily(series)
    coef, resid, dy = _fit_ar_diff(y, p, window, drift)
    c = coef[0] if drift else 0.0
    a = coef[1:] if drift else coef
    rng = np.random.default_rng(seed)
    paths = np.empty((n_sim, h))
    for s in range(n_sim):
        hist = list(dy[-p:]) if p else []
        level = y.iloc[-1]
        for k in range(h):
            lag = hist[::-1][:p]
            nxt = c + (np.dot(a, lag) if p else 0.0) + rng.choice(resid)
            hist.append(nxt)
            level += nxt
            paths[s, k] = level
    # point forecast = noise-free recursion
    hist = list(dy[-p:]) if p else []
    level = y.iloc[-1]; mean = []
    for k in range(h):
        lag = hist[::-1][:p]
        nxt = c + (np.dot(a, lag) if p else 0.0)
        hist.append(nxt); level += nxt; mean.append(level)
    idx = _future_index(y, h)
    return pd.DataFrame({"mean": mean,
                         "lower": np.quantile(paths, alpha / 2, axis=0),
                         "upper": np.quantile(paths, 1 - alpha / 2, axis=0)}, index=idx)


def forecast_baseline(series, h, kind="naive"):
    y = _daily(series)
    idx = _future_index(y, h)
    if kind == "naive":
        return pd.Series(y.iloc[-1], index=idx)
    if kind == "ma7":
        return pd.Series(y.iloc[-7:].mean(), index=idx)
    if kind == "drift30":
        slope = (y.iloc[-1] - y.iloc[-31]) / 30
        return pd.Series(y.iloc[-1] + slope * np.arange(1, h + 1), index=idx)
    raise ValueError(kind)

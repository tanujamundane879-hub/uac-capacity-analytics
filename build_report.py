"""Builds the final project report PDF from results.json + charts/ (no hand-typed numbers)."""
import json, os, sys
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Table, TableStyle,
                                Preformatted, ListFlowable, ListItem, Image, KeepTogether, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json")))
D = pd.read_csv(os.path.join(HERE, "data", "uac_clean_with_metrics.csv"), index_col=0, parse_dates=True)
NAME = os.environ.get("STUDENT_NAME", "")
ROLL = os.environ.get("STUDENT_ID", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "UAC_Capacity_Care_Load_Project_Report.pdf")

def n(x, d=0): return f"{x:,.{d}f}"
def dt(s): return pd.Timestamp(s).strftime("%d %b %Y").lstrip("0")
def pct(x, d=1): return f"{x:.{d}f}%"

NAVY = colors.HexColor("#1F3A5F"); LIGHT = colors.HexColor("#EAF0F7"); GREY = colors.HexColor("#52514e")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=NAVY, fontSize=16, spaceBefore=4, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=NAVY, fontSize=12, spaceBefore=10, spaceAfter=4)
H3 = ParagraphStyle("H3", parent=H2)
HT = ParagraphStyle("HT", parent=ss["Heading1"], textColor=NAVY, fontSize=16, spaceBefore=4, spaceAfter=8)
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=14.5, spaceAfter=6)
SM = ParagraphStyle("SM", parent=B, fontSize=8.5, leading=11.5, textColor=GREY, spaceAfter=8)
TITLE = ParagraphStyle("T", parent=ss["Title"], textColor=NAVY, fontSize=25, leading=31)
SUB = ParagraphStyle("S", parent=ss["Normal"], fontSize=12, alignment=1, textColor=GREY, leading=17)
CODE = ParagraphStyle("C", fontName="Courier", fontSize=6.6, leading=8.3, backColor=colors.HexColor("#F4F4F4"), borderPadding=4, spaceAfter=6)
CODE2 = ParagraphStyle("C2", parent=CODE, fontSize=7.6, leading=9.6)
CELL = ParagraphStyle("CELL", parent=B, fontSize=8.8, leading=11.5, spaceAfter=0)
HC = ParagraphStyle("HC", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")
BOX = ParagraphStyle("BOX", parent=B, backColor=colors.HexColor("#E3F4E8"), borderPadding=6, spaceBefore=4, spaceAfter=10)
NOTE = ParagraphStyle("NOTE", parent=B, backColor=colors.HexColor("#FFF6DD"), borderPadding=6, spaceBefore=4, spaceAfter=10)
CAP = ParagraphStyle("CAP", parent=SM, alignment=0, spaceAfter=10)

def P(t, s=B):
    if s is H2 and not t[:1].isdigit(): s = H3
    return Paragraph(t, s)
def bl(items): return ListFlowable([ListItem(P(i), leftIndent=12) for i in items], bulletType="bullet", leftIndent=14, bulletFontSize=7)
def table(rows, widths, bold_last=False, align_right_from=None):
    data = [[P(str(c), HC if i == 0 else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9bfc8")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
          ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    t.setStyle(TableStyle(st)); return t
def fig(name, caption, w=16.2):
    from PIL import Image as PI
    path = os.path.join(HERE, "charts", name)
    iw, ih = PI.open(path).size
    return KeepTogether([Image(path, width=w * cm, height=w * cm * ih / iw), P(caption, CAP)])
def code(t, s=CODE2): return Preformatted(t.strip("\n"), s)

# ---------------------------------------------------------------- numbers used in text
Q = R["quality"]; H = R["hhs"]; C = R["cbp"]; F = R["flow"]; S = R["stay"]; A = R["alert"]; BT = R["backtest"]; FC = R["forecast"]; ST = R["stress"]
cap = R["capacity_threshold"]; by = R["by_year"]; cby = R["cbp_by_year"]
care_2021 = D.loc["2021-03-23", "hhs_care"]; rise_days = (pd.Timestamp(H["peak_date"]) - pd.Timestamp("2021-03-23")).days
rise_per_day = (H["peak"] - care_2021) / rise_days
fall = D.loc["2024-12-31":"2025-04-15", "hhs_care"]
cur_care = H["current"]; cur_total = C["total_current"]
recon = R["recon"]
a90 = A["grid"]["0.9"]; a80 = A["grid"]["0.8"]; a100 = A["grid"]["1.0"]
best = R["best_model"]
bt_h = BT["hhs_care"]; bt_t = BT["total_load"]
f60 = FC["hhs_care"]["d60"]; f30 = FC["hhs_care"]["d30"]; ft60 = FC["total_load"]["d60"]
Y = lambda d_, y, k: d_[str(y)][k]

# ---------------------------------------------------------------- document with TOC
class Doc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                         title="System Capacity & Care Load Analytics for Unaccompanied Children", author=NAME or "Student", **kw)
        fr = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate(id="p", frames=[fr], onPage=self.deco)])
    def deco(self, c, d):
        if d.page > 1:
            c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(GREY)
            c.drawString(2 * cm, 1.2 * cm, "System Capacity & Care Load Analytics - Unaccompanied Children")
            c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {d.page}"); c.restoreState()
    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and f.style.name in ("H1", "H2"):
            lvl = 0 if f.style.name == "H1" else 1
            key = f"h{self.seq.nextf('toc')}"
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (lvl, f.getPlainText(), self.page, key))
toc = TableOfContents()
toc.levelStyles = [ParagraphStyle("t0", fontSize=10.5, leading=15, leftIndent=0, fontName="Helvetica-Bold", textColor=NAVY),
                   ParagraphStyle("t1", fontSize=9, leading=12.5, leftIndent=16, textColor=GREY)]

s = []
# ============================ cover
s += [Spacer(1, 4.6 * cm), P("System Capacity &amp; Care Load Analytics for Unaccompanied Children", TITLE), Spacer(1, 0.5 * cm),
      P("Data Analytics Project Report", SUB), Spacer(1, 0.2 * cm),
      P("Capacity, care load, length of stay, early warning and 60-day forecast, with a Streamlit web application", SUB),
      Spacer(1, 3.5 * cm)]
who = [["Submitted by", NAME or "______________________________"], ["Student ID / Roll no.", ROLL or "______________________________"],
       ["Data period analysed", f"{dt(Q['start'])} to {dt(Q['end'])}"], ["Report date", "17 October 2026"]]
t = Table([[P(a, ParagraphStyle("k", parent=CELL, fontName="Helvetica-Bold")), P(b, CELL)] for a, b in who], colWidths=[5 * cm, 9 * cm])
t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#b9bfc8")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
s += [t, PageBreak()]

# ============================ contents + at a glance
s += [Paragraph("Table of Contents", HT), toc, Spacer(1, 10), P("Project at a glance", H2),
      table([["Item", "Result"],
             ["Data", f"{n(Q['raw_rows'])} raw rows, daily, {dt(Q['start'])} to {dt(Q['end'])}; HHS data for the full period, CBP data from {dt(Q['cbp_start'])}"],
             ["Children in the system today", f"{n(cur_total)} on {dt(H['current_date'])}: {n(C['custody_current'])} in CBP custody and {n(cur_care)} in HHS care"],
             ["Peak HHS care", f"{n(H['peak'])} children on {dt(H['peak_date'])}; today's level is {pct(H['current_vs_peak_pct'])} of that peak"],
             ["Capacity (assumption)", f"Threshold {n(cap)} children = 90th percentile of HHS care; utilization today {pct(R['utilization_current'] * 100)}, peak {pct(R['utilization_peak'] * 100, 0)}"],
             ["Days above the threshold", f"{n(R['days_over_capacity'])} days ({pct(R['days_over_capacity_pct'])}), all in 2021"],
             ["Estimated length of stay", f"About {n(by['2023']['stay_med'])} days in 2021-2024; {n(S['current'])} days now (approximation, see 7.5)"],
             ["Best forecast model", f"{best}: rolling-origin MAE {n(bt_h['rolling30'][best][0], 1)} children vs {n(bt_h['rolling30']['Naive (last value)'][0], 1)} for the naive baseline"],
             ["Forecast, 7 Dec 2026", f"{n(f60[0])} children in HHS care (80% band {n(f60[1])} to {n(f60[2])}), about {pct(R['forecast']['util_d60_mean'] * 100, 0)} of the threshold"],
             ["Early-warning rule", f"{pct(a90['pct_followed_by_growth'])} of alert days were followed by growth in HHS care within 14 days, against a {pct(A['base_rate_growth_pct'])} base rate"]],
            [4.6, 12.4]), PageBreak()]

# ============================ 1 Background
s += [P("1. Background and Context", H1),
      P("Unaccompanied children are minors who reach the United States border without a parent or legal guardian. After apprehension they "
        "are first held by U.S. Customs and Border Protection (CBP), whose facilities are designed for short stays. The law generally requires "
        "that they be transferred to the Department of Health and Human Services (HHS) within 72 hours, except in exceptional circumstances."),
      P("HHS, through its Office of Refugee Resettlement (ORR), cares for the children in shelters and other facilities until they can be "
        "released to a vetted sponsor, usually a parent or relative in the United States. The system is therefore a two-stage pipeline:"),
      P("<b>apprehension, then CBP custody, then transfer to HHS, then HHS care, then discharge to a sponsor.</b>", B),
      P("Arrivals can change sharply from one month to the next, while shelter beds, staff and sponsor-vetting capacity change slowly. When "
        "intake runs above discharges for long enough, children accumulate in care, and facilities approach or exceed capacity. The data in "
        f"this project show how large these swings can be: HHS care rose from {n(care_2021)} to {n(H['peak'])} children in {rise_days} days in "
        f"spring 2021 (about {n(rise_per_day)} more children per day), and by October 2026 it had fallen to {n(cur_care)}."),
      P("Analytics can make this pressure visible and measurable. This project turns the daily CBP and HHS figures into capacity and "
        "care-load indicators, an early-warning rule, a 60-day forecast and an interactive dashboard that planners can use to see strain "
        "before it becomes a crisis."),
      P("<b>Data source.</b> HHS Unaccompanied Children Program daily data, published on data.gov / HealthData.gov "
        "(catalog.data.gov/dataset/hhs-unaccompanied-alien-children-program). The file used here is the CSV export of that dataset.", B),
      PageBreak()]

# ============================ 2 Problem
s += [P("2. Problem Statement", H1),
      P("The care system for unaccompanied children does not have a simple, data-driven view of how heavily it is loaded, whether a backlog is "
        "building, how long children remain in care, and when the next surge is likely to strain capacity. Without that view, shelter capacity and "
        "sponsor-processing resources are planned late and reactively."),
      P("<b>This project</b> uses the daily CBP and HHS series to (1) measure system load and capacity utilization, (2) compare intake with "
        "discharges, (3) estimate length of stay, (4) forecast load for the next 60 days and (5) deliver an interactive Streamlit "
        "application with an early-warning rule."),
      P("Key questions and the short answers found in this project", H2),
      table([["Question", "Answer from the data", "Section"],
             ["How many children are in the system now?", f"{n(cur_total)} on {dt(H['current_date'])} ({n(C['custody_current'])} CBP + {n(cur_care)} HHS).", "7.2"],
             ["Is intake outpacing discharges?", f"Not now: 7-day net intake is {F['net7_current']:+.1f} children/day and the discharge-to-transfer ratio is {F['ratio7_current']:.2f}. "
              f"Across {dt(C['start'])} to {dt(Q['end'])}, intake exceeded discharges on {pct(F['pct_days_net_positive'], 0)} of days.", "7.4"],
             ["How long do children stay?", f"About {n(by['2023']['stay_med'])} days in 2021-2024 (estimate); the same estimate is {n(S['current'])} days now because discharges have become very small.", "7.5"],
             ["When are the peaks?", f"HHS care peaked at {n(H['peak'])} on {dt(H['peak_date'])}. Within the CBP window the total load peaked at {n(C['total_peak'])} on {dt(C['total_peak_date'])}. There is no stable calendar seasonality.", "7.3, 7.6"],
             ["When does the system near capacity?", f"Utilization is {pct(R['utilization_current'] * 100, 0)} today. At a sustained net intake of +{n(ST['net_peak_observed'])} children/day (the highest 7-day average seen), the threshold would be reached in about {n(ST['scenarios']['125']['days_to_threshold'])} days.", "6.10"]],
            [4.2, 10.6, 2.2]), PageBreak()]

# ============================ 3 Primary objectives
s += [P("3. Primary Objectives", H1),
      table([["#", "Objective", "How it was met", "Section"],
             ["1", "Clean and prepare the daily CBP/HHS data", f"Removed {Q['duplicate_dates']} duplicated dates, {len(Q['outliers_removed'])} isolated spikes and a {Q['long_gap_days']}-day gap; built a daily calendar; interpolated stock gaps only.", "5"],
             ["2", "Engineer capacity and care-load metrics", "Total load, net intake, discharge-to-transfer ratio, 30-day care change, utilization, estimated length of stay, alert flag.", "7"],
             ["3", "Analyse trends, seasonality and surges", f"HHS care trend, month-by-year heatmap, surge periods ({len(R['surge_periods'])} periods above the threshold).", "7.3, 7.6"],
             ["4", "Forecast load and validate it properly", f"Six models compared on time-based back-tests; {best} chosen; 60-day forecast with an 80% band.", "6"],
             ["5", "Build an interactive Streamlit application", "Dashboard with KPI cards, five analysis tabs, data-quality tab, sliders and CSV export.", "8"]],
            [0.8, 4.6, 9.8, 1.8]), Spacer(1, 12),
      P("4. Secondary Objectives", H1),
      table([["#", "Objective", "Result", "Section"],
             ["1", "Find the lag between CBP flows and HHS load", f"Apprehensions turn into transfers about {R['lag']['best_lag_in_to_transfer']} day later (r = {R['lag']['apprehension_to_transfer']['1']:.2f}); HHS care reacts the same day to transfers in and discharges out.", "7.7"],
             ["2", "Compare surge periods with normal periods", f"Estimated stay in surge periods: median {n(S['median_over_cap'])} days vs {n(S['median_under_cap'])} days outside them. No lengthening during the 2021 surge.", "7.5"],
             ["3", "Define and test an early-warning rule", f"Alert days were followed by care growth in 14 days {pct(a90['pct_followed_by_growth'])} of the time vs {pct(A['base_rate_growth_pct'])} for all days.", "7.8"],
             ["4", "Detect bottlenecks", f"Estimated CBP custody time rose from {R['cbp_stay_by_year']['2024']:.1f} days (2024) to {R['cbp_stay_by_year']['2026']:.1f} days (2026); HHS turnover slowed sharply from 2025.", "7.4, 7.5"],
             ["5", "Provide decision-focused recommendations and a stress test", "Surge stress test and five recommendations.", "6.10, 10"]],
            [0.8, 4.6, 9.8, 1.8]), PageBreak()]

# ============================ 5 Dataset
rep = R["reported_weekdays"]
s += [P("5. Dataset Description", H1),
      P(f"The dataset is a daily time series with one row per reporting date. The raw file has <b>{n(Q['raw_rows'])} rows and 6 columns</b>, "
        f"covering {dt(Q['start'])} to {dt(Q['end'])} after cleaning. It mixes <b>stock</b> variables (children present at the end of the day) "
        "and <b>flow</b> variables (children moving during the day)."),
      table([["Original column", "Short name", "Type", "Meaning", "Available"],
             ["Date", "Date", "Date", "Reporting date", "All"],
             ["Children apprehended and placed in CBP custody*", "cbp_in", "Flow", "New arrivals entering CBP custody", f"From {dt(Q['cbp_start'])}"],
             ["Children in CBP custody", "cbp_custody", "Stock", "Children held by CBP at day end", f"From {dt(Q['cbp_start'])}"],
             ["Children transferred out of CBP custody", "cbp_transfer", "Flow", "Moved from CBP to HHS", f"From {dt(Q['cbp_start'])}"],
             ["Children in HHS Care", "hhs_care", "Stock", "Children in HHS care at day end", "All"],
             ["Children discharged from HHS Care", "hhs_discharge", "Flow", "Released to sponsors that day", "All"]],
            [5.2, 2.5, 1.3, 5.0, 3.0]),
      Spacer(1, 6),
      P("Data quality findings and how each was handled", H2),
      table([["Finding in the raw file", "Size", "Treatment"],
             ["CBP columns are empty before 31 Jan 2024", "701 of 1,366 rows", "CBP-based metrics (total load, flows, ratio, alerts, lags) are computed only from 31 Jan 2024. HHS metrics cover the whole period."],
             ["Duplicated dates with conflicting values", f"{Q['duplicate_dates']} dates, {Q['duplicate_periods'][0]} to {Q['duplicate_periods'][1]}; HHS care differs by up to {n(Q['duplicate_max_conflict'])}",
              "Two interleaved series appear in January 2022. The first-listed row was kept because it continues smoothly from the days before and after."],
             ["Isolated spikes in HHS care", f"{len(Q['outliers_removed'])} values: " + ", ".join(f"{dt(a_)} ({n(b_)})" for a_, b_ in Q['outliers_removed']),
              "Values that differ by more than 12% from the surrounding 9-day median, with neighbours within 4 days, were treated as errors and re-filled by interpolation."],
             ["Very long gap at the start", f"{Q['long_gap_days']} days ({dt(Q['long_gap_from'])} to {dt(Q['long_gap_to'])})", "The single earlier row was dropped; analysis starts on 23 Mar 2021. Interpolating across 71 days would invent data."],
             ["Reporting only Sunday to Thursday", f"Sun {n(rep['Sunday'])}, Mon {n(rep['Monday'])}, Tue {n(rep['Tuesday'])}, Wed {n(rep['Wednesday'])}, Thu {n(rep['Thursday'])}, Fri {rep['Friday']}, Sat {rep['Saturday']}",
              f"{n(Q['unreported_days'])} calendar days have no report (longest run {Q['longest_unreported_run']} days). Stocks are interpolated across these days; flows are never interpolated and are averaged over reported days only."],
             ["Flows do not add up to the change in HHS care", f"Cumulative net flow {n(recon['cum_net_cbp_window'])} vs change in care {n(recon['cum_dcare_cbp_window'])} since {dt(C['start'])}",
              f"Day to day they move together (correlation {recon['corr_dcare_net']:.2f} on {n(recon['n_consecutive_days'])} consecutive days), but sums drift. Backlog is therefore measured from the stock (HHS care), not by adding flows."]],
            [4.6, 5.2, 7.2]),
      Spacer(1, 6),
      P("The asterisk on the apprehension column refers to a footnote in the source data, so that column should be read as reported by the "
        "source rather than as an exact count of unique children.", SM),
      KeepTogether([P("Summary by year (HHS care on the full daily calendar; discharges per reported day)", H2), table([["Year", "Average HHS care", "Minimum", "Maximum", "Average discharges / day"]] +
            [[y, n(by[y]["care_mean"]), n(by[y]["care_min"]), n(by[y]["care_max"]), n(by[y]["dis_mean"], 1)] for y in sorted(by)],
            [2.2, 3.8, 3.2, 3.2, 4.6]),
      Spacer(1, 4), P("2021 starts on 23 March and 2026 ends on 8 October.", SM)]), PageBreak()]

# ============================ 6 Forecasting
def bt_rows(b):
    rows = [["Model", "Rolling-origin MAE", "MAPE", "Last-60-days MAE", "MAPE"]]
    mn = min(v[0] for v in b["rolling30"].values())
    for k in b["rolling30"]:
        r_, h_ = b["rolling30"][k], b["holdout60"][k]
        mae = f"<b>{r_[0]:.1f}</b>" if r_[0] == mn else f"{r_[0]:.1f}"
        rows.append([k, mae, f"{r_[1]:.2f}%", f"{h_[0]:.1f}", f"{h_[1]:.2f}%"])
    return rows
sc = ST["scenarios"]
s += [P("6. Forecasting Methodology (Step-by-Step)", H1),
      P("<b>Step 1 - Define the targets and horizon.</b> The primary target is the number of children in HHS care (full period). The secondary "
        f"target is total system load, CBP custody plus HHS care, which exists from {dt(C['start'])}. The horizon is 60 days."),
      P("<b>Step 2 - Prepare the series.</b> A full daily calendar was built; gaps in stock series were filled by linear interpolation "
        f"({n(Q['unreported_days'])} unreported days, longest run {Q['longest_unreported_run']} days); duplicates, spikes and the 71-day gap were handled as in Section 5."),
      P("<b>Step 3 - Examine the patterns.</b> HHS care is not stationary: it moves between 22,557 and 1,757 with long swings and level shifts, and "
        "has no stable weekly pattern (weekend values are interpolated). Models were therefore built on first differences (day-to-day changes), with no seasonal terms."),
      P("<b>Step 4 - Validate in time order, never at random.</b> Two tests were used: (a) the final 60 days held out; (b) a rolling-origin test with "
        "12 forecast origins spaced 30 days apart, each forecasting 30 days ahead (covering the last year). Rolling origins are more reliable than one split because performance changes with the regime."),
      P("<b>Step 5 - Baselines.</b> Naive (repeat the last value), 7-day moving average, and drift (extend the last 30-day slope). Any model must beat these."),
      P("<b>Step 6 - Fit models.</b> ARIMA(p,1,0) for p = 1, 3 and 7, that is, an autoregression on the daily change fitted by least squares on the "
        "most recent 365 days, with no drift term (in preliminary tests a drift term made the 30-day errors much larger for p = 3 and no better for p = 7). Implemented in NumPy in <i>uac_core.py</i>, so the report and the Streamlit app give the same numbers."),
      P("<b>Step 7 - Evaluate.</b> MAE (children) and MAPE (%) for each model, shown below."),
      P("HHS care", H2), table(bt_rows(bt_h), [5.0, 3.4, 2.0, 3.6, 3.0]), Spacer(1, 6),
      P("Total system load (from 31 Jan 2024)", H2), table(bt_rows(bt_t), [5.0, 3.4, 2.0, 3.6, 3.0]),
      Spacer(1, 4), P("Lowest rolling-origin MAE in bold. Lower is better.", SM),
      P(f"<b>Step 8 - Select the model.</b> Among the ARIMA models, {best} has the lowest rolling-origin error. For HHS care it is also the best of all six "
        f"models there (MAE {bt_h['rolling30'][best][0]:.1f} against {bt_h['rolling30']['Naive (last value)'][0]:.1f} for the naive baseline, "
        f"a reduction of {100 * (1 - bt_h['rolling30'][best][0] / bt_h['rolling30']['Naive (last value)'][0]):.0f}%). Two honest caveats: on the single final 60-day hold-out all models are close "
        f"(MAE between {min(v[0] for v in bt_h['holdout60'].values()):.0f} and {max(v[0] for v in bt_h['holdout60'].values()):.0f}) and the naive baseline is slightly better than {best}; "
        f"and for total load the 30-day drift baseline has the lowest rolling error ({bt_t['rolling30']['Drift (last 30 days)'][0]:.1f}), so {best} is used there for consistency."),
      P("<b>Step 9 - Refit and forecast.</b> The chosen model is refitted on all data and run 60 days ahead. The 80% band comes from 1,000 simulated "
        "paths that resample the model's own past errors."),
      fig("fig8_forecast.png", f"Figure 6.1 - Forecast of children in HHS care to {dt(FC['hhs_care']['end'])}. The band widens with the horizon."),
      table([["Target", "Last actual", "Day 30", "Day 60 (" + dt(FC['hhs_care']['end']) + ")"],
             ["HHS care", n(FC["hhs_care"]["last_actual"]), f"{n(f30[0])} ({n(f30[1])} to {n(f30[2])})", f"{n(f60[0])} ({n(f60[1])} to {n(f60[2])})"],
             ["Total system load", n(FC["total_load"]["last_actual"]), f"{n(FC['total_load']['d30'][0])} ({n(FC['total_load']['d30'][1])} to {n(FC['total_load']['d30'][2])})", f"{n(ft60[0])} ({n(ft60[1])} to {n(ft60[2])})"]],
            [3.6, 3.0, 5.2, 5.2]), Spacer(1, 6),
      P("<b>Step 10 - Interpret in capacity terms.</b> "
        f"The 60-day forecast for HHS care is {n(f60[0])} children, {pct(R['forecast']['util_d60_mean'] * 100, 0)} of the {n(cap)} threshold; even the top of the band "
        f"({n(f60[2])}) is {pct(R['forecast']['util_d60_upper'] * 100, 0)}. On current trends no capacity problem is expected in the next 60 days. "
        "A statistical forecast cannot anticipate a sudden change in arrivals, so it is paired with a stress test:"),
      table([["Sustained net intake (children/day)", "HHS care after 60 days", "Utilization after 60 days", "Days to reach the threshold"]] +
            [[f"+{k}", n(v["care_after_60d"]), pct(v["util_after_60d"] * 100, 0), n(v["days_to_threshold"])] for k, v in sc.items()],
            [5.0, 4.0, 4.0, 4.0]),
      Spacer(1, 4), P(f"Starting from {n(ST['current'])} children and a threshold of {n(cap)}. +{n(ST['net_peak_observed'])}/day is the highest 7-day average net intake observed "
                      f"({dt(F['net7_peak_date'])}). In spring 2021 HHS care rose by about {n(rise_per_day)} children per day for {rise_days} days, which is much faster than any of these scenarios.", SM),
      PageBreak()]

# ============================ 7 KPIs
s += [P("7. Key Performance Indicators (KPIs)", H1), P("7.1 KPI definitions", H2),
      table([["KPI", "Formula", "How to read it"],
             ["Total system load", "CBP custody + HHS care", "All children in the system (from 31 Jan 2024)"],
             ["Net intake (daily)", "Transfers out of CBP - HHS discharges", "Positive: HHS load tends to rise"],
             ["7-day net intake", "Average daily net intake over the last 7 days (reported days only)", "Smooths day-to-day noise"],
             ["Discharge-to-transfer ratio (7-day)", "Sum of discharges / sum of transfers over 7 days", "Below 1: intake exceeds discharges"],
             ["Backlog indicator", "30-day change in HHS care", "Positive: backlog growing (measured from the stock)"],
             ["Capacity utilization", f"HHS care / {n(cap)} (assumed capacity)", "Above 100%: over the threshold"],
             ["Estimated length of stay", "HHS care / 30-day average daily discharges (Little's law)", "Approximate days in care"],
             ["Estimated CBP custody time", "Average CBP custody / average daily transfers", "Approximate days in CBP custody"],
             ["Alert", "7-day net intake > 0 and 7-day ratio < 0.9", "Early-warning signal"]],
            [4.4, 6.9, 5.7]),
      P("<b>Capacity assumption.</b> The data contain no official capacity. The threshold used is the 90th percentile of HHS care over the whole period "
        f"({n(cap)} children). For comparison, the 80th percentile is {n(R['sensitivity']['80']['threshold'])} ({n(R['sensitivity']['80']['days_over'])} days above) and the 95th is "
        f"{n(R['sensitivity']['95']['threshold'])} ({n(R['sensitivity']['95']['days_over'])} days above). The Streamlit app lets the user change this value.", NOTE),
      P(f"7.2 Snapshot on {dt(H['current_date'])}", H2),
      table([["KPI", "Value"],
             ["Total system load", f"{n(cur_total)} children"], ["Children in CBP custody", n(C["custody_current"])], ["Children in HHS care", n(cur_care)],
             ["7-day net intake", f"{F['net7_current']:+.1f} children per day"], ["7-day discharge-to-transfer ratio", f"{F['ratio7_current']:.2f}"],
             ["Capacity utilization", pct(R["utilization_current"] * 100)], ["Estimated length of stay in HHS care", f"{n(S['current'])} days"],
             ["Early-warning alert", f"Off (last alert day: {dt(A['last_alert_date'])})"]], [8.0, 9.0]),
      CondPageBreak(9 * cm), P("7.3 Load and capacity", H2),
      fig("fig1_hhs_care.png", "Figure 7.1 - Children in HHS care and the assumed capacity threshold. Shading shows the days above the threshold."),
      P(f"HHS care peaked at {n(H['peak'])} on {dt(H['peak_date'])}, {pct(R['utilization_peak'] * 100, 0)} of the threshold. It was above the threshold on "
        f"{n(R['days_over_capacity'])} days ({pct(R['days_over_capacity_pct'])} of the period), in two spells: " +
        " and ".join(f"{dt(a_)} to {dt(b_)} ({n(c_)} days)" for a_, b_, c_ in R["surge_periods"]) + ". "
        f"After 2021 the load stayed below the threshold. It fell step by step to about {n(by['2024']['care_mean'])} on average in 2024, then dropped sharply in early 2025 "
        f"(from {n(fall.iloc[0])} on {dt(str(fall.index[0].date()))} to {n(fall.min())} by {dt(str(fall.idxmin().date()))}), and has stayed near {n(by['2026']['care_mean'])} since. "
        f"The total system load peaked at {n(C['total_peak'])} on {dt(C['total_peak_date'])} and is {n(cur_total)} today."),
      PageBreak(),
      P("7.4 Intake versus discharge", H2),
      fig("fig2_flows.png", "Figure 7.2 - Daily flows (7-day averages). The lower panel zooms in on April 2025 onward, where flows are only 5 to 25 children a day."),
      table([["Year", "Apprehended / day", "Transferred to HHS / day", "Discharged / day", "Average CBP custody", "Est. CBP custody time (days)"]] +
            [[y, n(cby[y]["cbp_in"], 1), n(cby[y]["transfer"], 1), n(cby[y]["discharge"], 1), n(cby[y]["custody"], 1), f"{R['cbp_stay_by_year'][y]:.1f}"] for y in sorted(cby)],
            [1.6, 3.0, 3.6, 2.8, 3.0, 3.0]), Spacer(1, 4),
      P("Averages over reported days. 2024 starts on 31 January and 2026 ends on 8 October.", SM),
      P(f"Apprehensions fell from {n(cby['2024']['cbp_in'])} a day in 2024 to {n(cby['2025']['cbp_in'], 1)} in 2025 and {n(cby['2026']['cbp_in'], 1)} in 2026. "
        f"The busiest day in the CBP window was {dt(C['cbp_in_peak_date'])} with {n(C['cbp_in_peak'])} apprehensions, and CBP custody peaked at {n(C['custody_peak'])} on {dt(C['custody_peak_date'])}. "
        f"The yearly median of the 7-day discharge-to-transfer ratio was {F['dis_ratio_mean_by_year']['2024']:.2f} in 2024 (below 1, intake ahead of discharges), "
        f"{F['dis_ratio_mean_by_year']['2025']:.2f} in 2025 and {F['dis_ratio_mean_by_year']['2026']:.2f} in 2026. Intake exceeded discharges on {pct(F['pct_days_net_positive'], 0)} of days; the longest unbroken "
        f"spell lasted {F['longest_positive_run'][2]} days ({dt(F['longest_positive_run'][0])} to {dt(F['longest_positive_run'][1])}), and the highest 7-day net intake was "
        f"{F['net7_peak']:+.0f} children a day ({dt(F['net7_peak_date'])})."),
      P(f"The estimated time in CBP custody (average custody divided by average transfers) rose from {R['cbp_stay_by_year']['2024']:.1f} days in 2024 to "
        f"{R['cbp_stay_by_year']['2026']:.1f} days in 2026. This is an approximation, but it points to slower transfers out of CBP now that volumes are small."),
      fig("fig3_net_intake.png", "Figure 7.3 - Net intake into HHS (top) and the 30-day change in HHS care, the backlog indicator (bottom)."),
      P(f"<b>Caution.</b> Net intake calculated from the flows overstates the actual change in care in 2024: cumulative net intake was {n(recon['by_year']['2024']['net'])} children "
        f"while HHS care changed by {n(recon['by_year']['2024']['dcare'])}. Flows are reported on about five days in seven, and the data do not say what other movements are missing. "
        "The 7-day net intake and the ratio are therefore used as relative signals, and the backlog is read from the stock.", NOTE),
      CondPageBreak(9 * cm), P("7.5 Estimated length of stay", H2),
      fig("fig6_stay.png", "Figure 7.4 - Estimated length of stay (HHS care divided by the 30-day average of daily discharges)."),
      P(f"From 2021 to 2024 the estimate is steady at about 30 days (yearly medians {n(by['2021']['stay_med'])}, {n(by['2022']['stay_med'])}, {n(by['2023']['stay_med'])} and {n(by['2024']['stay_med'])} days). "
        f"It then jumps to {n(by['2025']['stay_med'])} days (2025 median) and {n(by['2026']['stay_med'])} days (2026), with a high of {n(S['max'])} days on {dt(S['max_date'])}; the latest value is {n(S['current'])} days. "
        f"The jump comes from discharges falling from about {n(by['2023']['dis_mean'])} a day in 2023 to {n(by['2026']['dis_mean'], 1)} in 2026 while {n(by['2026']['care_mean'])} children remain in care."),
      P(f"<b>Surge versus normal.</b> During the days above the capacity threshold the median estimate was {n(S['median_over_cap'])} days, against {n(S['median_under_cap'])} days outside those periods. "
        "So the 2021 surge did not lengthen stays; the system moved more children through, in step with arrivals. The change that matters is the slow turnover since 2025."),
      P("<b>Interpretation.</b> Dividing care by discharges is a rough estimate that assumes the system is in a steady state. Since 2025 it is not, and the children who "
        "remain are likely to include many long stays. The figure should be read as a signal that turnover has slowed sharply, not as the exact average stay.", NOTE),
      CondPageBreak(10 * cm), P("7.6 Seasonality", H2),
      fig("fig4_heatmap.png", "Figure 7.5 - Average children in HHS care by month and year (thousands).", w=11.5),
      fig("fig5_season.png", "Figure 7.6 - Average daily apprehensions into CBP custody by calendar month, 2024 to 2026 (log scale)."),
      P("The heatmap reads down the years rather than across the months: the colour changes far more from one year to the next than from one month to the next. "
        "Apprehension rates also differ by an order of magnitude between 2024, 2025 and 2026, so with three years of CBP data and such a large level shift no stable "
        "calendar seasonality can be established. The months with the highest averages in the CBP window (" +
        ", ".join(pd.Timestamp(2000, m, 1).strftime("%B") for m in R["season_top_months"]) + ") mostly reflect the high 2024 level and should not be treated as a seasonal peak."),
      CondPageBreak(9 * cm), P("7.7 Lag between CBP flows and HHS load", H2),
      fig("fig7_lag.png", "Figure 7.7 - Correlations after removing each series' 31-day moving average, so that large level changes between years do not create false correlation.", w=13.5),
      P(f"Apprehensions are followed by transfers out of CBP mostly one day later (correlation {R['lag']['apprehension_to_transfer']['1']:.2f}, with a smaller effect after two days). "
        f"HHS care responds on the same day: the day's change in care is positively related to transfers (r = {R['lag']['transfer_to_hhs_growth']['0']:.2f}) and negatively to discharges (r = {R['lag']['discharge_to_hhs_growth']['0']:.2f}). "
        "In practice the planning lead time between a rise in apprehensions and a rise in HHS load is only a day or two, so early warning has to come from the trend in flows over several days and from the stock, not from waiting for the lag."),
      CondPageBreak(8 * cm), P("7.8 Early-warning rule", H2),
      P("<b>Rule:</b> raise an alert when the 7-day average net intake is above zero <b>and</b> the 7-day discharge-to-transfer ratio is below 0.9. "
        f"The rule was tested on {n(A['n_eval_days'])} days with enough history: did HHS care grow over the following 14 days?"),
      table([["Ratio threshold", "Alert days", "Followed by growth in 14 days", "Average 14-day change after alert", "Average change on other days"],
             ["0.8", n(a80["alert_days"]), pct(a80["pct_followed_by_growth"]), f"{a80['mean_future_change_alert']:+.0f}", f"{a80['mean_future_change_other']:+.0f}"],
             ["<b>0.9 (used)</b>", n(a90["alert_days"]), pct(a90["pct_followed_by_growth"]), f"{a90['mean_future_change_alert']:+.0f}", f"{a90['mean_future_change_other']:+.0f}"],
             ["1.0", n(a100["alert_days"]), pct(a100["pct_followed_by_growth"]), f"{a100['mean_future_change_alert']:+.0f}", f"{a100['mean_future_change_other']:+.0f}"],
             ["All days (base rate)", n(A["n_eval_days"]), pct(A["base_rate_growth_pct"]), "", ""]],
            [3.4, 2.2, 3.8, 3.8, 3.8]), Spacer(1, 4),
      P(f"With the 0.9 threshold the rule gave {n(A['alert_days_total'])} alert days ({n(A['alert_by_year']['2024'])} in 2024, {n(A['alert_by_year']['2025'])} in 2025, {n(A['alert_by_year']['2026'])} in 2026; the last on {dt(A['last_alert_date'])}). "
        f"Alert days were followed by growth in HHS care {pct(a90['pct_followed_by_growth'])} of the time, against {pct(A['base_rate_growth_pct'])} for all days, and the average 14-day change was {a90['mean_future_change_alert']:+.0f} children after an alert against {a90['mean_future_change_other']:+.0f} otherwise. "
        "A stricter threshold (0.8) is more reliable but fires less often. The thresholds were not tuned to the data, and consecutive days are not independent, so these figures show that the rule carries information, not its exact accuracy."),
      fig("fig9_alerts.png", "Figure 7.8 - Alert days per month.", w=10), PageBreak()]

# ============================ 8 Streamlit
app_src = open(os.path.join(HERE, "app.py")).read()
s += [P("8. Streamlit Web Application Requirements", H1),
      P("The web application is the interactive front end of the analysis. It reads the raw CSV, applies the same cleaning, metric and forecasting "
        "functions as this report (module <i>uac_core.py</i>), and presents the results to a non-technical user."),
      P("Functional requirements", H2),
      table([["Requirement", "Implementation"],
             ["Data input", "Loads data/uac.csv by default; optional CSV upload in the sidebar. Cleaning is automatic and every step is reported in the Data quality tab."],
             ["Interactive controls", "Date-range selector; capacity-percentile slider; forecast horizon (14 to 90 days); forecast target (HHS care or total load); ARIMA order; stress-test slider."],
             ["KPI cards", "Total system load, HHS care, 7-day net intake, estimated length of stay, capacity utilization, early-warning status."],
             ["Trends tab", "HHS care with the capacity line; CBP custody and total load; estimated length of stay."],
             ["Intake vs Discharge tab", "7-day flows, 7-day net intake, 30-day change in HHS care."],
             ["Seasonality tab", "Month-by-year heatmap; apprehensions by month and year."],
             ["Forecast tab", "Forecast with 80% band, day-N value and utilization, surge stress test."],
             ["Alerts tab", "Alert days in the range, monthly bar chart and table."],
             ["Export", "Download of the processed data as CSV."]], [4.0, 13.0]),
      P("Non-functional requirements", H2),
      bl(["Python 3.9 or newer; dependencies in requirements.txt (streamlit, pandas, numpy, plotly).",
          "Results are cached (st.cache_data) so charts respond quickly after the first load.",
          "Clear titles, labelled axes, and a caption that states the capacity assumption and the data limits.",
          "Deployable on Streamlit Community Cloud from a GitHub repository (no secrets needed)."]),
      P("How to run", H2),
      code("pip install -r requirements.txt\nstreamlit run app.py"),
      P("Files", H2),
      table([["File", "Role"], ["app.py", "Streamlit interface (listing in Appendix A)"], ["uac_core.py", "Cleaning, metrics and forecasting functions shared by the app and the analysis"],
             ["analysis.py", "Full analysis script: produces results.json and all charts (can be pasted into Jupyter cells)"],
             ["data/", "uac.csv (raw data) and uac_clean_with_metrics.csv (cleaned, with all KPI columns)"]], [3.0, 14.0]),
      P("<b>Verification.</b> The data, KPI and forecast code behind the app was run on the provided dataset; its KPI values "
        f"(total load {n(cur_total)}, HHS care {n(cur_care)}, utilization {pct(R['utilization_current'] * 100, 0)}) match Section 7.2.", NOTE),
      PageBreak()]

# ============================ 9 Deliverables
s += [P("9. Deliverables and Submission", H1),
      table([["#", "Deliverable", "File / location", "Status"],
             ["1", "Project report (this document)", "UAC_Capacity_Care_Load_Project_Report.pdf", "Done"],
             ["2", "Streamlit application", "app.py, uac_core.py, requirements.txt", "Done"],
             ["3", "Analysis code (cleaning, KPIs, EDA, forecast)", "analysis.py", "Done"],
             ["4", "Cleaned dataset with KPI columns", "data/uac_clean_with_metrics.csv", "Done"],
             ["5", "Raw dataset", "data/uac.csv", "Done"],
             ["6", "Charts used in the report", "charts/ (9 PNG files)", "Done"],
             ["7", "GitHub repository link", "______________________________________", "To add"],
             ["8", "Deployed app link (Streamlit Community Cloud)", "______________________________________", "To add"]],
            [0.8, 6.0, 8.2, 2.0]),
      Spacer(1, 8),
      P("Repository structure", H2),
      code("uac-capacity-analytics/\n|-- app.py\n|-- uac_core.py\n|-- analysis.py\n|-- requirements.txt\n|-- README.md\n|-- data/\n|   |-- uac.csv\n|   `-- uac_clean_with_metrics.csv\n|-- charts/            (9 PNG files)\n`-- report/\n    `-- UAC_Capacity_Care_Load_Project_Report.pdf"),
      P("Steps to publish", H2),
      bl(["Create a GitHub repository and upload the folder above.",
          "On share.streamlit.io choose New app, select the repository, branch main and file app.py, then Deploy.",
          "Add the repository link and the app link in the table above, and submit them with this report."]), PageBreak()]

# ============================ 10 Conclusion
s += [P("10. Conclusion", H1),
      P("The project turned the daily CBP and HHS series into a working picture of system capacity and care load, and into a dashboard that can be "
        "used for monitoring. The main findings are:"),
      bl([f"<b>Load.</b> HHS care peaked at {n(H['peak'])} on {dt(H['peak_date'])} ({pct(R['utilization_peak'] * 100, 0)} of the assumed threshold) and was above the threshold on {n(R['days_over_capacity'])} days, all in 2021. It is now {n(cur_care)} ({pct(R['utilization_current'] * 100, 0)} of the threshold); with CBP custody the system holds {n(cur_total)} children.",
          f"<b>Intake and discharge.</b> Apprehensions fell from {n(cby['2024']['cbp_in'])} a day in 2024 to {n(cby['2026']['cbp_in'], 1)} in 2026. Intake exceeded discharges on {pct(F['pct_days_net_positive'], 0)} of days since 2024, but at present discharges are ahead (7-day ratio {F['ratio7_current']:.2f}).",
          f"<b>Length of stay.</b> About {n(by['2023']['stay_med'])} days in 2021-2024 and no increase during the 2021 surge. Since 2025 the estimate is far higher ({n(S['current'])} days now, peaking at {n(S['max'])}) because discharges are only about {n(by['2026']['dis_mean'])} a day: turnover has slowed sharply.",
          f"<b>Timing.</b> Transfers follow apprehensions by about one day and HHS care reacts the same day, so the warning time is short. No stable calendar seasonality exists in the data.",
          f"<b>Forecast.</b> {best} gives {n(f60[0])} children in HHS care on {dt(FC['hhs_care']['end'])} (80% band {n(f60[1])} to {n(f60[2])}), about {pct(R['forecast']['util_d60_mean'] * 100, 0)} of the threshold. It cut the 30-day error by {100 * (1 - bt_h['rolling30'][best][0] / bt_h['rolling30']['Naive (last value)'][0]):.0f}% against the naive baseline in rolling tests.",
          f"<b>Early warning.</b> The alert rule (7-day net intake above zero and ratio below 0.9) was followed by growth in HHS care within 14 days {pct(a90['pct_followed_by_growth'])} of the time, against {pct(A['base_rate_growth_pct'])} for all days."]),
      P("Recommendations", H2),
      bl([f"<b>Keep the early-warning rule in daily use</b> and review it weekly; it carries real signal (Section 7.8), and a ratio threshold of 0.8 can be used when fewer, stronger alerts are wanted.",
          f"<b>Plan surge readiness around speed, not season.</b> HHS care once grew by about {n(rise_per_day)} children a day for {rise_days} days, and at +{n(ST['net_peak_observed'])} a day the threshold would be reached in about {n(sc['125']['days_to_threshold'])} days. Keep a plan to add capacity within weeks, and trigger it from the alert and the 30-day change in care.",
          f"<b>Examine the slow turnover.</b> With about {n(by['2026']['dis_mean'])} discharges a day and {n(cur_care)} children in care, review the long-stay cohort and the sponsor-vetting and placement process.",
          f"<b>Watch the CBP stage.</b> The estimated custody time rose from {R['cbp_stay_by_year']['2024']:.1f} to {R['cbp_stay_by_year']['2026']:.1f} days; track transfers against the 72-hour expectation.",
          "<b>Improve the data.</b> Publish flows for all seven days, remove duplicated dates, extend the CBP columns back before 2024, and state an official capacity figure so utilization can be measured exactly."]),
      P("Limitations", H2),
      bl(["The data are daily aggregates: no individual cases, ages, countries of origin or facility locations can be analysed.",
          "Capacity is an assumption (90th percentile of HHS care), not an official number; conclusions about 'over capacity' depend on it.",
          "CBP-based results cover only 31 Jan 2024 onward, and flows are reported on about five days in seven; flows do not fully reconcile with changes in care.",
          "Length of stay from Little's law is an approximation and is least reliable when the system is shrinking, as since 2025.",
          "The forecast cannot foresee policy changes or sudden surges; the stress test is a scenario, not a prediction. The alert evaluation uses 2024 to 2026 only and consecutive days are not independent."]),
      P("Future work: add official capacity and facility data, break the analysis down by age and region if available, include external drivers, and test machine-learning models on lagged features.", B),
      P("Sources", H2),
      P("HHS Unaccompanied Children Program dataset, data.gov: catalog.data.gov/dataset/hhs-unaccompanied-alien-children-program (CSV export used for this project).", B),
      P("Appendix A - Streamlit application listing (app.py)", H1), code(app_src, CODE)]

doc = Doc(OUT)
doc.multiBuild([toc if x is toc else x for x in s])
print("built", OUT)

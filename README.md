# System Capacity & Care Load Analytics - Unaccompanied Children

Daily CBP custody and HHS care analysis: load, capacity utilization, intake vs discharge, estimated length of stay,
early-warning rule, 60-day forecast and a Streamlit dashboard.

## Run the dashboard
```
pip install -r requirements.txt
streamlit run app.py
```
The app loads `data/uac.csv` by default; you can also upload another CSV with the same columns from the sidebar.

## Re-run the full analysis
```
python analysis.py        # writes results.json, charts/*.png and data/uac_clean_with_metrics.csv
python build_report.py    # writes the PDF report (needs reportlab and pillow)
```

## Files
- `app.py` - Streamlit interface
- `uac_core.py` - cleaning, metrics, forecasting (NumPy only)
- `analysis.py` - complete analysis script
- `build_report.py` - builds the PDF report from `results.json` and `charts/`
- `data/` - raw and cleaned data

Data source: HHS Unaccompanied Children Program dataset on data.gov
(catalog.data.gov/dataset/hhs-unaccompanied-alien-children-program).

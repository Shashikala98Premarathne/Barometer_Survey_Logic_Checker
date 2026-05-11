# ==========================================================
# Full Barometer Survey Logic Checker
# ==========================================================
import re
import numpy as np
import pandas as pd
import streamlit as st
import io, csv
from io import BytesIO

# -------------------------------------------------------------------
# App setup
# -------------------------------------------------------------------
st.set_page_config(page_title="Barometer Survey Logic Checker", layout="wide")

def set_background_solid(main="#6CD7E551", sidebar="#EEEFF3"):
    st.markdown(f"""
    <style>
      [data-testid="stAppViewContainer"],
      [data-testid="stAppViewContainer"] .main,
      [data-testid="stAppViewContainer"] .block-container {{
        background-color: {main} !important;
      }}
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] > div,
      [data-testid="stSidebar"] .block-container {{
        background-color: {sidebar} !important;
      }}
      header[data-testid="stHeader"] {{ background: transparent; }}
      [data-testid="stDataFrame"],
      [data-testid="stTable"] {{ background-color: transparent !important; }}
    </style>
    """, unsafe_allow_html=True)

set_background_solid()

st.title("🚛 Barometer Survey Logic Checker")
st.caption("Validation tool for barometer data.")

# -------------------------------------------------------------------
# File helpers
# -------------------------------------------------------------------
COMMON_ENCODINGS = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")

def _sniff_sep(sample_text: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample_text[:4096], delimiters=",;\t|")
        return dialect.delimiter
    except Exception:
        return ","

def _norm_delim(sel: str) -> str:
    return {"\\t": "\t"}.get(sel, sel)

def read_any_table(uploaded_file, enc_override="auto", delim_override="auto", skip_bad=True):
    name = (uploaded_file.name or "").lower()
    raw = uploaded_file.read()

    if raw.startswith(ZIP_SIGNATURES) or name.endswith((".xlsx", ".xls")):
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file)

    encodings = COMMON_ENCODINGS if enc_override == "auto" else [enc_override]

    for enc_try in encodings:
        try:
            text = raw.decode(enc_try, errors="strict")
            sep = _sniff_sep(text) if delim_override == "auto" else _norm_delim(delim_override)

            kwargs = dict(
                encoding=enc_try,
                sep=sep,
                engine="python"
            )

            if skip_bad:
                kwargs["on_bad_lines"] = "skip"

            return pd.read_csv(BytesIO(raw), **kwargs)

        except Exception:
            continue

    sep = "," if delim_override == "auto" else _norm_delim(delim_override)

    kwargs = dict(
        encoding="latin-1",
        sep=sep,
        engine="python"
    )

    if skip_bad:
        kwargs["on_bad_lines"] = "skip"

    return pd.read_csv(BytesIO(raw), **kwargs)

# -------------------------------------------------------------------
# Sidebar upload
# -------------------------------------------------------------------
with st.sidebar:

    st.header("Input")

    data_file = st.file_uploader(
        "Upload survey data",
        type=["csv", "xlsx", "xls"]
    )

    enc = st.selectbox(
        "Encoding",
        ["auto", "utf-8", "utf-8-sig", "cp1252", "latin-1"],
        index=0
    )

    delim = st.selectbox(
        "Delimiter",
        ["auto", ",", ";", "\\t", "|"],
        index=0
    )

    skip_bad = st.checkbox("Skip bad lines", value=True)

if not data_file:
    st.info("Upload a CSV/XLSX file to begin.")
    st.stop()

# -------------------------------------------------------------------
# Read file
# -------------------------------------------------------------------
try:
    data_file.seek(0)

    df = read_any_table(
        data_file,
        enc_override=enc,
        delim_override=delim,
        skip_bad=skip_bad
    )

except Exception as e:
    st.error(f"Failed to read file: {e}")
    st.stop()

# -------------------------------------------------------------------
# Normalize nulls
# -------------------------------------------------------------------
df.replace(
    {
        "#NULL!": np.nan,
        "NULL": np.nan,
        "null": np.nan,
        "NaN": np.nan,
        "nan": np.nan,
        "": np.nan,
        "na": np.nan,
        "N/A": np.nan,
        "n/a": np.nan
    },
    inplace=True
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
digest = []
detailed = []

def is_blank(val):

    if pd.isna(val):
        return True

    sval = str(val).strip().lower()

    return sval in {
        "",
        "nan",
        "na",
        "n/a",
        "null",
        "#null!",
        "none"
    }

def add_issue(rule_id, msg, idx=None):

    digest.append((rule_id, msg))

    if idx is not None:
        detailed.append((idx, rule_id, msg))

# -------------------------------------------------------------------
# Rules dictionary
# -------------------------------------------------------------------
SURVEY_RULES = {

    0: "Invalid value / out-of-range",
    1: "Required variable missing",
    2: "Fleet size invalid",
    3: "Truck fleet sum mismatch",
    4: "Truck quantity sum mismatch",
    5: "Main supplier missing",
    6: "Fuel type logic failed",
    7: "Truck consideration type missing",
    8: "Electric consideration logic failed",
    9: "Electric barriers logic failed",
    10: "Gas application logic failed",
    11: "Gas barriers logic failed",
    12: "Sustainability quality logic failed",
    13: "Adhoc electric logic failed",
    14: "Safety follow-up missing",
    15: "Chinese truck logic failed",
}

# -------------------------------------------------------------------
# Variable validation structure
# -------------------------------------------------------------------
VARIABLE_STRUCTURE = {

    "countryquestion": [1,2,3,4,5],
    "intro": [1],
    "decision_maker": [1],

    "goodsvolume": [1,2,3,4,5],
    "freightrates": [1,2,3],
    "profitability": [1,2,3,4,5],

    "consideration_china": [1,2,3,4,5],
    "business_situation": [1,2,3],
    "business_expectations": [1,2,3],

    "last_purchase": [1,2,3,4],
    "business_description": [1,2,3,4,5],
    "business_usage": [1,2,3,4,5,6],
    "business_distance": [1,2,3],

    "business_sustain": [1,2,3],
    "business_climate": [1,2,3,9],

    "country": [1,2,3,4,5,6,7,8],

    "electric_purchase": [1,2,3,4,5],

    "sustainability_risks": [1,2,3,4,5],
    "sustainability_duration": [1,2,3,4,5,9],
    "sustainability_cost": [1,2,3,4,5],
    "sustainability_newbusiness": [1,2,3,4,5],

    "adhoc_electric_consider": [1,2,3,4,5],

    "gas_purchase": [1,2,3,4,5],
    "gas_cost": [1,2,3],

    "safety_SF1": [1,2,3,4,5],
    "safety_SF4": [1,2,3,4,5],

    "replacement_interval": "numeric",
    "replacement_interval_2": "numeric",

    "adhoc_ch_consideration": [1,2,3,4,5],

}

# -------------------------------------------------------------------
# -------------------------------------------------------------------
# Rule 0 – Basic range validation
# -------------------------------------------------------------------
for col, allowed in VARIABLE_STRUCTURE.items():

    if col not in df.columns:
        add_issue(1, f"Missing variable: {col}")
        continue

    # ---------------------------------------------------------------
    # Numeric-only validation
    # ---------------------------------------------------------------
    if allowed == "numeric":

        vals = pd.to_numeric(df[col], errors="coerce")

        invalid_mask = vals.isna() & df[col].notna()

        for i in df[invalid_mask].index:
            add_issue(
                0,
                f"{col} must be numeric",
                i
            )

    # ---------------------------------------------------------------
    # Standard coded validation
    # ---------------------------------------------------------------
    else:

        df[col] = pd.to_numeric(df[col], errors="coerce")

        invalid_mask = ~df[col].isin(allowed) & df[col].notna()

        for i in df[invalid_mask].index:
            add_issue(
                0,
                f"{col} contains invalid value {df.loc[i, col]}",
                i
            )
# -------------------------------------------------------------------
# Fleet size validation
# -------------------------------------------------------------------
if "fleetsize" in df.columns:

    vals = pd.to_numeric(df["fleetsize"], errors="coerce")

    for i in df[vals.isna()].index:
        add_issue(2, "Invalid fleetsize", i)

    for i in df[(vals < 0) | (vals > 99999)].index:
        add_issue(2, "fleetsize out of range 0-99999", i)

# -------------------------------------------------------------------
# Truck fleet validation
# -------------------------------------------------------------------
truckfleet_cols = [c for c in df.columns if c.startswith("truckfleet_b")]

for c in truckfleet_cols:

    vals = pd.to_numeric(df[c], errors="coerce")

    invalid = ~vals.isin([0,1]) & vals.notna()

    for i in df[invalid].index:
        add_issue(0, f"{c} invalid (allowed 0,1)", i)

# -------------------------------------------------------------------
# Truck quantity validation
# -------------------------------------------------------------------
truckqty_cols = [
    c for c in df.columns
    if c.startswith("truckquantity_")
]

for c in truckqty_cols:

    vals = pd.to_numeric(df[c], errors="coerce")

    invalid = (
        (vals < 0) |
        (vals > 999) |
        vals.isna()
    )

    for i in df[invalid].index:
        add_issue(
            0,
            f"{c} invalid quantity",
            i
        )

# -------------------------------------------------------------------
# Truck quantity sum = fleetsize
# -------------------------------------------------------------------
if "fleetsize" in df.columns and truckqty_cols:

    qty_sum = df[truckqty_cols].apply(
        pd.to_numeric,
        errors="coerce"
    ).fillna(0).sum(axis=1)

    fleetsize = pd.to_numeric(
        df["fleetsize"],
        errors="coerce"
    )

    bad = qty_sum != fleetsize

    for i in df[bad].index:
        add_issue(
            4,
            "Sum truckquantity != fleetsize",
            i
        )

# -------------------------------------------------------------------
# Main supplier logic
# Ask if more than one truckfleet brand selected
# -------------------------------------------------------------------
if "mainsupplier" in df.columns and truckfleet_cols:

    fleet_sum = df[truckfleet_cols].fillna(0).sum(axis=1)

    bad = (fleet_sum > 1) & df["mainsupplier"].isna()

    for i in df[bad].index:
        add_issue(
            5,
            "mainsupplier required",
            i
        )

# -------------------------------------------------------------------
# Fuel consideration logic
# -------------------------------------------------------------------
fuel_cols = [
    c for c in df.columns
    if c.startswith("fueltypes_consideration_")
]

if "outlook_1" in df.columns and "outlook_2" in df.columns:

    trigger = (
        (df["outlook_1"] == 1) |
        (df["outlook_2"] == 1)
    )

    for i in df[trigger].index:

        any_answer = False

        for c in fuel_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                6,
                "fueltypes_consideration required",
                i
            )

# -------------------------------------------------------------------
# Trucks consideration type logic
# -------------------------------------------------------------------
consider_cols = [
    c for c in df.columns
    if c.startswith("trucks_consideration_b")
]

for c in consider_cols:

    m = re.search(r"_b(\d+)$", c)

    if not m:
        continue

    bid = m.group(1)

    type_col = f"trucks_consideration_type_{bid}"

    if type_col not in df.columns:
        continue

    bad = (
        (df[c] == 1) &
        (df[type_col].isna())
    )

    for i in df[bad].index:
        add_issue(
            7,
            f"{type_col} required",
            i
        )

# -------------------------------------------------------------------
# Electric consideration logic
# -------------------------------------------------------------------
electric_cons_cols = [
    c for c in df.columns
    if c.startswith("electric_consideration_")
]

if "electric_purchase" in df.columns:

    trigger = df["electric_purchase"].isin([3,4,5])

    for i in df[trigger].index:

        any_answer = False

        for c in electric_cons_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                8,
                "electric_consideration missing",
                i
            )

# -------------------------------------------------------------------
# Electric barriers logic
# -------------------------------------------------------------------
electric_barrier_cols = [
    c for c in df.columns
    if c.startswith("electric_barriers_")
]

if "electric_purchase" in df.columns:

    trigger = df["electric_purchase"].isin([1,2])

    for i in df[trigger].index:

        any_answer = False

        for c in electric_barrier_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                9,
                "electric_barriers missing",
                i
            )

# -------------------------------------------------------------------
# Gas application logic
# -------------------------------------------------------------------
gas_app_cols = [
    c for c in df.columns
    if c.startswith("gas_applications_")
]

if "gas_purchase" in df.columns:

    trigger = df["gas_purchase"].isin([3,4,5])

    for i in df[trigger].index:

        any_answer = False

        for c in gas_app_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                10,
                "gas_applications missing",
                i
            )

# -------------------------------------------------------------------
# Gas barriers logic
# -------------------------------------------------------------------
gas_barrier_cols = [
    c for c in df.columns
    if c.startswith("gas_barriers_")
]

if "gas_purchase" in df.columns:

    trigger = df["gas_purchase"].isin([1,2])

    for i in df[trigger].index:

        any_answer = False

        for c in gas_barrier_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                11,
                "gas_barriers missing",
                i
            )

# -------------------------------------------------------------------
# Sustainability quality logic
# -------------------------------------------------------------------
sustain_cols = [
    c for c in df.columns
    if c.startswith("sustainability_qualities_")
]

if "sustainability_duration" in df.columns:

    trigger = df["sustainability_duration"].isin([1,2,3])

    for i in df[trigger].index:

        any_answer = False

        for c in sustain_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                12,
                "sustainability_qualities missing",
                i
            )

# -------------------------------------------------------------------
# Adhoc electric logic
# -------------------------------------------------------------------
adhoc_attr_cols = [
    c for c in df.columns
    if c.startswith("adhoc_electric_consider_attr_")
]

if "adhoc_electric_consider" in df.columns:

    trigger = df["adhoc_electric_consider"].isin([3,4,5])

    for i in df[trigger].index:

        any_answer = False

        for c in adhoc_attr_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                13,
                "adhoc electric attributes missing",
                i
            )

# -------------------------------------------------------------------
# Safety logic
# -------------------------------------------------------------------
sf2_cols = [
    c for c in df.columns
    if c.startswith("safety_SF2_")
]

if "safety_SF1" in df.columns:

    trigger = df["safety_SF1"].isin([4,5])

    for i in df[trigger].index:

        any_answer = False

        for c in sf2_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                14,
                "safety_SF2 follow-up missing",
                i
            )

# -------------------------------------------------------------------
# Chinese truck logic
# -------------------------------------------------------------------
china_barr_cols = [
    c for c in df.columns
    if c.startswith("adhoc_ch_barr_")
]

if "adhoc_ch_consideration" in df.columns:

    trigger = df["adhoc_ch_consideration"].isin([1,2])

    for i in df[trigger].index:

        any_answer = False

        for c in china_barr_cols:

            if not is_blank(df.loc[i, c]):
                any_answer = True
                break

        if not any_answer:
            add_issue(
                15,
                "adhoc_ch_barr missing",
                i
            )

# -------------------------------------------------------------------
# Results output
# -------------------------------------------------------------------
if detailed:

    results_df = pd.DataFrame(
        detailed,
        columns=["RowID", "RuleID", "Issue"]
    )

    results_df["Rule Description"] = results_df["RuleID"].map(SURVEY_RULES)

    if "respid" in df.columns:

        results_df["Respondent ID"] = results_df["RowID"].apply(
            lambda i: df.loc[i, "respid"]
            if i in df.index else np.nan
        )

    else:
        results_df["Respondent ID"] = np.nan

    results_df = results_df[
        [
            "Respondent ID",
            "RowID",
            "RuleID",
            "Rule Description",
            "Issue"
        ]
    ]

else:

    results_df = pd.DataFrame(
        columns=[
            "Respondent ID",
            "RowID",
            "RuleID",
            "Rule Description",
            "Issue"
        ]
    )

# -------------------------------------------------------------------
# Display results
# -------------------------------------------------------------------
st.subheader("Survey Logic Issues")

if results_df.empty:

    st.success("✅ No issues found – dataset follows survey logic.")

else:

    st.dataframe(
        results_df,
        use_container_width=True
    )

# -------------------------------------------------------------------
# Excel export
# -------------------------------------------------------------------
output = BytesIO()

with pd.ExcelWriter(output, engine="xlsxwriter") as writer:

    pd.DataFrame(
        digest,
        columns=["RuleID", "Issue"]
    ).to_excel(
        writer,
        index=False,
        sheet_name="Digest"
    )

    results_df.to_excel(
        writer,
        index=False,
        sheet_name="Detailed"
    )

output.seek(0)

st.download_button(
    label="📥 Download Validation Report",
    data=output,
    file_name="Truck_Survey_Logic_Check_Report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
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
    10: "Electric application logic failed",
    11: "Gas application logic failed",
    12: "Gas barriers logic failed",
    13: "Sustainability quality logic failed",
    14: "Adhoc electric logic failed",
    15: "Adhoc electric use logic failed",
    16: "Adhoc electric barrier logic failed",
    17: "Adhoc electric future logic failed",
    18: "Safety follow-up missing",
    19: "Chinese truck logic failed",
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

    "transport_increase": "numeric_non_negative",

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

    "fueltypes_mostlikely": [1,2,3,4,5,6,7,8,9,10,11,12,95,99],

    "business_operations": [1,2,3,4,5,6,7,8,9,10,11,12,13,98,99],

    "sustainability_transport": [1,2,3,4,5,6,7,8,9,10,11,12,95,99],

    "adhoc_erange_modify": [1,2],

    "adhoc_fuel_transfer": [1,2],
    "adhoc_business_transfer": [1,2],

    "adhoc_cat_configs": [1,2,3],

    "adhoc_gs_gs1": [1,2],

    "adhoc_last_purchase": [1,2,3,4],

    "adhoc_price_last_type": [1,2],

    "adhoc_price_last_axle": [1,2,3,4,5,6,7,8,9,10,11],

    "adhoc_price_last_cab": [1,2,3],

    "adhoc_ch_fueltypes": list(range(1,15)),

    "gas_mileage": "numeric",

    "adhoc_trucks_1shift": "numeric",
    "adhoc_erange_dist": "numeric",
    "adhoc_erange_load": "numeric",

    "adhoc_erange_configs_prop_1": "numeric",
    "adhoc_erange_configs_prop_2": "numeric",
    "adhoc_erange_configs_prop_3": "numeric",

    "adhoc_price_last_engine": "numeric",
    "adhoc_price_last_disp": "numeric",
    "adhoc_price_cost": "numeric",
    "adhoc_price_last_weight": "numeric",
}

# -------------------------------------------------------------------
# Generic helper validators
# -------------------------------------------------------------------
def validate_binary_prefix(prefix):

    cols = [c for c in df.columns if c.startswith(prefix)]

    for c in cols:

        vals = pd.to_numeric(df[c], errors="coerce")

        invalid = (
            ~vals.isin([0,1])
            &
            vals.notna()
        )

        for i in df[invalid].index:
            add_issue(
                0,
                f"{c} invalid (allowed 0,1)",
                i
            )

def validate_scale_prefix(prefix, allowed):

    cols = [c for c in df.columns if c.startswith(prefix)]

    for c in cols:

        vals = pd.to_numeric(df[c], errors="coerce")

        invalid = (
            ~vals.isin(allowed)
            &
            vals.notna()
        )

        for i in df[invalid].index:
            add_issue(
                0,
                f"{c} invalid value",
                i
            )

def require_any_answer(trigger_mask, cols, rule_id, msg):

    for i in df[trigger_mask].index:

        any_answer = False

        for c in cols:

            if c in df.columns:

                if not is_blank(df.loc[i, c]):
                    any_answer = True
                    break

        if not any_answer:
            add_issue(rule_id, msg, i)
fuel_cols = [
    c for c in df.columns
    if c.startswith("fueltypes_consideration_")
]

electric_cons_cols = [
    c for c in df.columns
    if c.startswith("electric_consideration_")
]

electric_barrier_cols = [
    c for c in df.columns
    if c.startswith("electric_barriers_")
]

gas_app_cols = [
    c for c in df.columns
    if c.startswith("gas_applications_")
]

gas_barrier_cols = [
    c for c in df.columns
    if c.startswith("gas_barriers_")
]

sustain_cols = [
    c for c in df.columns
    if c.startswith("sustainability_qualities_")
]

adhoc_attr_cols = [
    c for c in df.columns
    if c.startswith("adhoc_electric_consider_attr_")
]

adhoc_attr_cols2 = [
    c for c in df.columns
    if c.startswith("adhoc_electric_use_")
]

adhoc_attr_cols3 = [
    c for c in df.columns
    if c.startswith("adhoc_electric_barr_")
]

adhoc_attr_cols4 = [
    c for c in df.columns
    if c.startswith("adhoc_electric_future_")
]
sf2_cols = [
    c for c in df.columns
    if c.startswith("safety_SF2_")
]

china_barr_cols = [
    c for c in df.columns
    if c.startswith("adhoc_ch_barr_")
]
# -------------------------------------------------------------------
# Rule 0 – Basic validation
# -------------------------------------------------------------------
for col, allowed in VARIABLE_STRUCTURE.items():

    if col not in df.columns:
        add_issue(1, f"Missing variable: {col}")
        continue

    if allowed == "numeric":

        vals = pd.to_numeric(df[col], errors="coerce")

        invalid_mask = (
            vals.isna()
            &
            df[col].apply(lambda v: not is_blank(v))
        )

        for i in df[invalid_mask].index:
            add_issue(
                0,
                f"{col} must be numeric",
                i
            )

    elif allowed == "numeric_non_negative":

        vals = pd.to_numeric(df[col], errors="coerce")

        invalid_mask = (
            df[col].apply(lambda v: not is_blank(v))
            &
            (
                vals.isna()
                |
                (vals < 0)
            )
        )

        for i in df[invalid_mask].index:
            add_issue(
                0,
                f"{col} must be numeric and >= 0",
                i
            )

    else:

        vals = pd.to_numeric(df[col], errors="coerce")

        invalid_mask = (
            ~vals.isin(allowed)
            &
            vals.notna()
        )

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

    invalid = (
        vals.isna()
        |
        (vals < 0)
        |
        (vals > 99999)
    )

    for i in df[invalid].index:
        add_issue(
            2,
            "fleetsize invalid",
            i
        )

# -------------------------------------------------------------------
# Binary validations
# -------------------------------------------------------------------
validate_binary_prefix("truckfleet_b")
validate_binary_prefix("fueltypes_consideration_")
validate_binary_prefix("trucks_consideration_b")
validate_binary_prefix("trucks_consideration_type_b")
validate_binary_prefix("electric_consideration_")
validate_binary_prefix("electric_applications_")
validate_binary_prefix("electric_barriers_")
validate_binary_prefix("sustainability_alternatives_")
validate_binary_prefix("adhoc_electric_consider_attr_")
validate_binary_prefix("adhoc_electric_use_")
validate_binary_prefix("adhoc_electric_barr_")
validate_binary_prefix("adhoc_electric_future_attr_")
validate_binary_prefix("adhoc_dist_cat_")
validate_binary_prefix("adhoc_erange_configs_")
validate_binary_prefix("adhoc_erange_charge_when_")
validate_binary_prefix("adhoc_erange_charge_where_")
validate_binary_prefix("adhoc_barr_china_")
validate_binary_prefix("adhoc_reason_china_")
validate_binary_prefix("gas_consideration_")
validate_binary_prefix("gas_applications_")
validate_binary_prefix("gas_barriers_")
validate_binary_prefix("gas_fuel_reason_")
validate_binary_prefix("adhoc_gs_gs2_")
validate_binary_prefix("adhoc_gs_gs3_")
validate_binary_prefix("safety_SF2_")
validate_binary_prefix("safety_SF5_")
validate_binary_prefix("adhoc_ch_barr_")
validate_binary_prefix("adhoc_ch_reason_")
validate_binary_prefix("adhoc_ch_unaided_aware_")
validate_binary_prefix("image_")

# -------------------------------------------------------------------
# Scale validations
# -------------------------------------------------------------------
validate_scale_prefix("sustainability_qualities_", [1,2,3,4,5])
validate_scale_prefix("adhoc_truck_", [1,2,3,4,5])
validate_scale_prefix("adhoc_ch_truck_attr_", [1,2,3,4,5])

# -------------------------------------------------------------------
# Truck quantity validation
# -------------------------------------------------------------------
truckqty_cols = [
    c for c in df.columns
    if c.startswith("truckquantity_")
]

for c in truckqty_cols:

    vals = pd.to_numeric(df[c], errors="coerce")

    has_real_value = df[c].apply(
        lambda v: not is_blank(v)
    )

    invalid = (
        has_real_value
        &
        (
            vals.isna()
            |
            (vals < 0)
            |
            (vals > 999)
        )
    )

    for i in df[invalid].index:

        add_issue(
            0,
            f"{c} invalid quantity (0-999)",
            i
        )

# -------------------------------------------------------------------
# Truck quantity sum
# -------------------------------------------------------------------
if "fleetsize" in df.columns and truckqty_cols:

    qty_sum = (
        df[truckqty_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .sum(axis=1)
    )

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
# adhoc_dist_cat validation
# Sum must equal fleetsize
# Ignore #NULL! / blanks completely
# -------------------------------------------------------------------
adhoc_dist_cols = [
    "adhoc_dist_cat_1",
    "adhoc_dist_cat_2",
    "adhoc_dist_cat_3",
    "adhoc_dist_cat_4"
]

existing_dist_cols = [
    c for c in adhoc_dist_cols
    if c in df.columns
]

# ---------------------------------------------------------------
# Validate individual values
# ---------------------------------------------------------------
for c in existing_dist_cols:

    vals = pd.to_numeric(
        df[c],
        errors="coerce"
    )

    has_real_value = df[c].apply(
        lambda v: not is_blank(v)
    )

    invalid = (
        has_real_value
        &
        (
            vals.isna()
            |
            (vals < 0)
        )
    )

    for i in df[invalid].index:

        add_issue(
            0,
            f"{c} must be numeric and >= 0",
            i
        )

# ---------------------------------------------------------------
# Sum validation
# ONLY check rows where at least one real value exists
# ---------------------------------------------------------------
if "fleetsize" in df.columns and existing_dist_cols:

    # Detect rows with real entered values
    has_any_real = df[existing_dist_cols].apply(
        lambda row: any(
            not is_blank(v)
            for v in row
        ),
        axis=1
    )

    dist_sum = (
        df[existing_dist_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
        .sum(axis=1)
    )

    fleetsize = pd.to_numeric(
        df["fleetsize"],
        errors="coerce"
    )

    bad = (
        has_any_real
        &
        (dist_sum != fleetsize)
    )

    for i in df[bad].index:

        add_issue(
            4,
            "Sum adhoc_dist_cat_1-4 != fleetsize",
            i
        )

# -------------------------------------------------------------------
# Logic validations
# -------------------------------------------------------------------
require_any_answer(
    (
        (df["outlook_1"] == 1)
        |
        (df["outlook_2"] == 1)
    ),
    fuel_cols,
    6,
    "fueltypes_consideration required"
)

require_any_answer(
    df["electric_purchase"].isin([3,4,5]),
    electric_cons_cols,
    8,
    "electric_consideration missing"
)

require_any_answer(
    df["electric_purchase"].isin([1,2]),
    electric_barrier_cols,
    9,
    "electric_barriers missing"
)

require_any_answer(
    df["electric_purchase"].isin([3,4,5]),
    electric_cons_cols,
    10,
    "electric_application missing"
)

require_any_answer(
    df["gas_purchase"].isin([3,4,5]),
    gas_app_cols,
    11,
    "gas_applications missing"
)

require_any_answer(
    df["gas_purchase"].isin([1,2]),
    gas_barrier_cols,
    12,
    "gas_barriers missing"
)

require_any_answer(
    df["sustainability_duration"].isin([1,2,3]),
    sustain_cols,
    13,
    "sustainability_qualities missing"
)

require_any_answer(
    df["adhoc_electric_consider"].isin([3,4,5]),
    adhoc_attr_cols,
    14,
    "adhoc electric consider attributes missing"
)
require_any_answer(
    df["adhoc_electric_consider"].isin([3,4,5]),
    adhoc_attr_cols2,
    15,
    "adhoc electric use attributes missing"
)

require_any_answer(
    df["adhoc_electric_consider"].isin([1,2]),
    adhoc_attr_cols3,
    16,
    "adhoc electric barr attributes missing"
)

require_any_answer(
    df["adhoc_electric_consider"].isin([1,2]),
    adhoc_attr_cols4,
    17,
    "adhoc electric future attributes missing"
)
require_any_answer(
    df["safety_SF1"].isin([4,5]),
    sf2_cols,
    18,
    "safety_SF2 follow-up missing"
)

require_any_answer(
    df["adhoc_ch_consideration"].isin([1,2]),
    china_barr_cols,
    19,
    "adhoc_ch_barr missing"
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
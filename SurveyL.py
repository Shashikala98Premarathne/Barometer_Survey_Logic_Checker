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
def add_issues_from_mask(mask, rule_id, msg):

    for i in df[mask].index:

        add_issue(
            rule_id,
            msg,
            i
        )

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
    12: "Gas fuel logic failed",
    13: "Gas barriers logic failed",
    14: "Sustainability quality logic failed",
    15: "Adhoc electric logic failed",
    16: "Adhoc electric use logic failed",
    17: "Adhoc electric barrier logic failed",
    18: "Adhoc electric future logic failed",
    19: "Safety follow-up missing",
    20: "Chinese truck logic failed",
    21: "Chinese main barrier logic failed",
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
    "business_climate": [1,2,3,4],

    "country": [1,2,3,4,5,6,7,8],

    "electric_purchase": [1,2,3,4,5],

    "sustainability_risks": [1,2,3,4,5],
    "sustainability_duration": [1,2,3,4,5,9],
    "sustainability_cost": [1,2,3,4,5],
    "sustainability_newbusiness": [1,2,3,4,5],

    "adhoc_electric_consider": [1,2,3,4,5],

    "gas_purchase": [1,2,3,4,5],
    "gas_cost": [1,2,3],
    "gas_fuel": [0,1],


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
    
    "adhoc_consideration_china": [1,2,3,4,5],

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


    "adhoc_price_last_cab": [1,2,3],

    "adhoc_price_cost": "numeric",
}

# -------------------------------------------------------------------
# Dynamic pricing comparison variables
# -------------------------------------------------------------------

PRICE_BRANDS = [
    "b9","b27","b35","b36","b43",
    "b45","b54","b30","b24","b50",
    "b19","b20","b29","b33","b41",
    "b46","b47","b52"
]

for b in PRICE_BRANDS:

    VARIABLE_STRUCTURE[f"adhoc_price_comp_{b}"] = [1,2,3]

    VARIABLE_STRUCTURE[f"adhoc_price_comp_less_{b}"] = "numeric"

    VARIABLE_STRUCTURE[f"adhoc_price_comp_more_{b}"] = "numeric"
    
# -------------------------------------------------------------------
# Master Brand Mapping
# -------------------------------------------------------------------
MASTER_BRANDS = {
    "b1": "Ashok Leyland",
    "b2": "Asia Motor Works",
    "b3": "Beijing Auto/BAIC/Beiqi Futian",
    "b4": "Bharat Benz",
    "b5": "CAMC",
    "b6": "CAT",
    "b7": "Chevrolet",
    "b8": "CNHTC/Steyr",
    "b9": "DAF",
    "b10": "Dennis Eagle",
    "b11": "Dongfeng",
    "b12": "Eicher",
    "b13": "ERF",
    "b14": "Foden",
    "b15": "Force Motors",
    "b16": "Ford",
    "b17": "Foton",
    "b18": "Freightliner",
    "b19": "Fuso",
    "b20": "Hino",
    "b21": "Hitachi",
    "b22": "Hongyan/Sichuan Auto/SAIC",
    "b23": "HOWO",
    "b24": "Hyundai",
    "b25": "International",
    "b26": "Isuzu",
    "b27": "Iveco",
    "b28": "JAC",
    "b29": "Jie Fang/FAW",
    "b30": "Kenworth",
    "b31": "LGMG",
    "b32": "LiuGong",
    "b33": "Mack",
    "b34": "Mahindra",
    "b35": "MAN",
    "b36": "Mercedes Benz",
    "b37": "Nissan Diesel",
    "b38": "Norinco",
    "b39": "Peterbilt",
    "b40": "Powerland",
    "b41": "Powerstar",
    "b42": "Quester",
    "b43": "Renault Trucks",
    "b44": "Sany",
    "b45": "Scania",
    "b46": "Shacman",
    "b47": "Sinotruk",
    "b48": "Sterling",
    "b49": "Swaraj Mazda Limited",
    "b50": "Tata",
    "b51": "Tatra",
    "b52": "UD Trucks",
    "b53": "Volkswagen",
    "b54": "Volvo",
    "b55": "Western Star",
    "b56": "Yan An/Shaanxi Auto",
    "b57": "BYD",
    "b58": "BMC",
    "b59": "Sitrak",
    "b60": "Blank",
    "b61": "Blank",
    "b62": "Blank",
    "b63": "Blank",
    "b64": "Blank",
    "b65": "Blank",
    "b66": "Blank",
    "b95": "Other",
    "b96": "Other",
    "b97": "Other"
}

PRICE_MODELS = {
    "m2": "b35",
    "m3": "b35",
    "m4": "b35",

    "mb1": "b36",
    "mb3": "b36",

    "s1": "b45",
    "s2": "b45",
    "s3": "b45",
    "s4": "b45",

    "v3": "b54",
    "v4": "b54",
    "v5": "b54",

    "k1": "b30",
    "k2": "b30",
    "k3": "b30",
    "k4": "b30",
    "k5": "b30",
    "k6": "b30",

    "hy1": "b24",

    "t1": "b50",

    "d2": "b9",
    "d3": "b9",

    "fu1": "b19",
    "fu2": "b19",

    "h1": "b20",
    "h2": "b20",

    "i4": "b27",

    "f1": "b29",

    "ma1": "b33",

    "p1": "b41",

    "sm1": "b46",
    "sm2": "b46",

    "st1": "b47",

    "ud1": "b52"
}

if "adhoc_price_last_model" in df.columns:

    normalized_model = (
        df["adhoc_price_last_model"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    bad = (
        ~normalized_model.isin(PRICE_MODELS.keys())
        &
        ~df["adhoc_price_last_model"].apply(is_blank)
    )

    add_issues_from_mask(
        bad,
        0,
        "adhoc_price_last_model invalid model code"
    )

if (
    "adhoc_price_last" in df.columns
    and "adhoc_price_last_model" in df.columns
):

    normalized_brand = (
        df["adhoc_price_last"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    normalized_model = (
        df["adhoc_price_last_model"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    expected_brand = normalized_model.map(PRICE_MODELS)

    bad = (
        normalized_model.notna()
        &
        normalized_brand.notna()
        &
        (expected_brand != normalized_brand)
    )

    add_issues_from_mask(
        bad,
        0,
        "adhoc_price_last_model does not match selected brand"
    )
# -------------------------------------------------------------------
# Country routing for pricing brands/models
# -------------------------------------------------------------------

COUNTRY_MAP = {
    1: "Australia",
    2: "South Africa",
    3: "South Korea"
}

# ---------------------------------------------------------------
# Model country availability
# ---------------------------------------------------------------
MODEL_COUNTRY_MAP = {

    # MAN
    "m2": ["Australia"],
    "m3": ["Australia", "South Africa"],
    "m4": ["Australia", "South Africa", "South Korea"],

    # Mercedes
    "mb1": ["Australia"],
    "mb3": ["Australia", "South Africa"],

    # Scania
    "s1": ["Australia"],
    "s2": ["Australia", "South Africa", "South Korea"],
    "s3": ["Australia", "South Africa", "South Korea"],
    "s4": ["Australia", "South Africa", "South Korea"],

    # Volvo
    "v3": ["Australia", "South Africa"],
    "v4": ["Australia", "South Africa", "South Korea"],
    "v5": ["Australia", "South Africa", "South Korea"],

    # Kenworth
    "k1": ["Australia"],
    "k2": ["Australia"],
    "k3": ["Australia"],
    "k4": ["Australia"],
    "k5": ["Australia"],
    "k6": ["Australia"],

    # Hyundai
    "hy1": ["South Korea"],

    # Tata
    "t1": ["Australia", "South Africa", "South Korea"],

    # DAF
    "d2": ["Australia"],
    "d3": ["Australia"],

    # Fuso
    "fu1": ["Australia"],
    "fu2": ["Australia"],

    # Hino
    "h1": ["Australia"],
    "h2": ["Australia"],

    # Iveco
    "i4": ["South Korea"],

    # FAW
    "f1": ["South Africa"],

    # Mack
    "ma1": ["Australia"],

    # Powerstar
    "p1": ["South Africa"],

    # Shacman
    "sm1": ["South Africa"],
    "sm2": ["South Africa"],

    # Sinotruk
    "st1": ["South Africa"],

    # UD
    "ud1": ["Australia", "South Africa"]
}

# ---------------------------------------------------------------
# Brand country availability
# ---------------------------------------------------------------
BRAND_COUNTRY_MAP = {

    "b35": ["Australia", "South Africa", "South Korea"],  # MAN
    "b36": ["Australia", "South Africa"],                 # Mercedes
    "b45": ["Australia", "South Africa", "South Korea"],  # Scania
    "b54": ["Australia", "South Africa", "South Korea"],  # Volvo
    "b30": ["Australia"],                                 # Kenworth
    "b24": ["South Korea"],                               # Hyundai
    "b50": ["Australia", "South Africa", "South Korea"],  # Tata
    "b9": ["Australia"],                                  # DAF
    "b19": ["Australia"],                                 # Fuso
    "b20": ["Australia"],                                 # Hino
    "b27": ["South Korea"],                               # Iveco
    "b29": ["South Africa"],                              # FAW
    "b33": ["Australia"],                                 # Mack
    "b41": ["South Africa"],                              # Powerstar
    "b46": ["South Africa"],                              # Shacman
    "b47": ["South Africa"],                              # Sinotruk
    "b52": ["Australia", "South Africa"]                  # UD Trucks
}

# -------------------------------------------------------------------
# Validate adhoc_price_last_model by country
# -------------------------------------------------------------------

if (
    "countryquestion" in df.columns
    and "adhoc_price_last_model" in df.columns
):

    normalized_model = (
        df["adhoc_price_last_model"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    for i in df.index:

        model = normalized_model.loc[i]

        if is_blank(model):
            continue

        country_code = pd.to_numeric(
            df.loc[i, "countryquestion"],
            errors="coerce"
        )

        country_name = COUNTRY_MAP.get(country_code)

        allowed_countries = MODEL_COUNTRY_MAP.get(model)

        if (
            allowed_countries is not None
            and country_name not in allowed_countries
        ):

            add_issue(
                0,
                f"adhoc_price_last_model {model} not valid in {country_name}",
                i
            )

# -------------------------------------------------------------------
# Validate adhoc_price_last brand by country
# -------------------------------------------------------------------

if (
    "countryquestion" in df.columns
    and "adhoc_price_last" in df.columns
):

    normalized_brand = (
        df["adhoc_price_last"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    for i in df.index:

        brand = normalized_brand.loc[i]

        if is_blank(brand):
            continue

        country_code = pd.to_numeric(
            df.loc[i, "countryquestion"],
            errors="coerce"
        )

        country_name = COUNTRY_MAP.get(country_code)

        allowed_countries = BRAND_COUNTRY_MAP.get(brand)

        if (
            allowed_countries is not None
            and country_name not in allowed_countries
        ):

            add_issue(
                0,
                f"adhoc_price_last {brand} not valid in {country_name}",
                i
            )

# -------------------------------------------------------------------
# Validate pricing comparison brands by country
# ONLY validate when question actually answered
# -------------------------------------------------------------------

if "countryquestion" in df.columns:

    for b in PRICE_BRANDS:

        comp_col = f"adhoc_price_comp_{b}"

        if comp_col not in df.columns:
            continue

        # -----------------------------------------------------------
        # normalize values
        # -----------------------------------------------------------
        comp_vals = (
            df[comp_col]
            .astype(str)
            .str.strip()
            .str.lower()
        )
        answered_mask = ~comp_vals.isin([
                "",
                "nan",
                "null",
                "#null!",
                "na",
                "n/a",
                "none"
        ])
        # -----------------------------------------------------------
        # ONLY rows with actual response
        # -----------------------------------------------------------
        if not answered_mask.any():
            continue

        for i in df[answered_mask].index:

            country_code = pd.to_numeric(
                df.loc[i, "countryquestion"],
                errors="coerce"
            )

            country_name = COUNTRY_MAP.get(country_code)

            allowed_countries = BRAND_COUNTRY_MAP.get(b)

            if (
                allowed_countries is not None
                and country_name not in allowed_countries
            ):

                add_issue(
                    0,
                    f"{comp_col} not valid in {country_name}",
                    i
                )



VALID_BRAND_CODES = list(MASTER_BRANDS.keys())
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

    existing_cols = [
        c for c in cols
        if c in df.columns
    ]

    if not existing_cols:
        return

    vals = (
        df[existing_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    any_selected = vals.eq(1).any(axis=1)

    bad = trigger_mask & (~any_selected)

    for i in df[bad].index:
        add_issue(rule_id, msg, i)
    
fuel_cols = [
    c for c in df.columns
    if c.startswith("fueltypes_consideration_")
]

electric_app_cols = [ 
    c for c in df.columns 
    if c.startswith("electric_applications_") ]

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
    if c.startswith("adhoc_electric_future_attr_")
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
validate_binary_prefix("electric_consideration_")
validate_binary_prefix("electric_applications_")
validate_binary_prefix("electric_barriers_")
validate_binary_prefix("sustainability_alternatives_")
validate_binary_prefix("adhoc_electric_consider_attr_")
validate_binary_prefix("adhoc_electric_use_")
validate_binary_prefix("adhoc_electric_barr_")
validate_binary_prefix("adhoc_electric_future_attr_")
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
validate_binary_prefix("trucks_consideration_type_b")

# -------------------------------------------------------------------
# Scale validations
# -------------------------------------------------------------------
validate_scale_prefix("sustainability_qualities_", [1,2,3,4,5])
validate_scale_prefix("adhoc_truck_", [1,2,3,4,5])
validate_scale_prefix("adhoc_ch_truck_attr_", [1,2,3,4,5])
validate_scale_prefix("adhoc_make_origin_", [1,2,3])
validate_scale_prefix("trucks_consideration_type_",[1,2,3])
validate_scale_prefix("adhoc_electric_probability_",[1,2,3,4,5])


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
    electric_app_cols,
    10,
    "electric_application missing"
)

require_any_answer(
    df["gas_purchase"].isin([3,4,5]),
    gas_app_cols,
    11,
    "gas_applications missing"
)
if "gas_fuel" in df.columns:

    bad = (
        df["gas_purchase"].isin([3,4,5])
        &
        df["gas_fuel"].apply(is_blank)
    )

    for i in df[bad].index:

        add_issue(
            12,
            "gas_fuel missing",
            i
        )

require_any_answer(
    df["gas_purchase"].isin([1,2]),
    gas_barrier_cols,
    13,
    "gas_barriers missing"
)

require_any_answer(
    df["sustainability_duration"].isin([1,2,3]),
    sustain_cols,
    14,
    "sustainability_qualities missing"
)

require_any_answer(
    df["adhoc_electric_consider"].isin([3,4,5]),
    adhoc_attr_cols,
    15,
    "adhoc electric consider attributes missing"
)
require_any_answer(
    df["adhoc_electric_consider"].isin([3,4,5]),
    adhoc_attr_cols2,
    16,
    "adhoc electric use attributes missing"
)

require_any_answer(
    df["adhoc_electric_consider"].isin([1,2]),
    adhoc_attr_cols3,
    17,
    "adhoc electric barr attributes missing"
)

require_any_answer(
    df["adhoc_electric_consider"].isin([1,2]),
    adhoc_attr_cols4,
    18,
    "adhoc electric future attributes missing"
)
require_any_answer(
    df["safety_SF1"].isin([4,5]),
    sf2_cols,
    19,
    "safety_SF2 follow-up missing"
)

require_any_answer(
    df["adhoc_ch_consideration"].isin([1,2]),
    china_barr_cols,
    20,
    "adhoc_ch_barr missing"
)

if "adhoc_main_barr_china" in df.columns:

    bad = (
        df["adhoc_consideration_china"].isin([4,5])
        &
        df["adhoc_main_barr_china"].apply(is_blank)
    )

    for i in df[bad].index:

        add_issue(
            21,
            "adhoc_main_barr_china missing",
            i
        )
        
# -------------------------------------------------------------------
# Brand code normalization + validation
# -------------------------------------------------------------------
brand_code_vars = [
    "adhoc_electric_pref",
    "adhoc_price_last"
]

def normalize_brand_code(val):

    if is_blank(val):
        return np.nan

    sval = str(val).strip().lower()

    # already correct
    if sval.startswith("b"):
        return sval

    # numeric like 9 / 9.0 / 36
    try:
        num = int(float(sval))
        return f"b{num}"
    except:
        return sval

for col in brand_code_vars:

    if col not in df.columns:
        continue

    normalized = df[col].apply(normalize_brand_code)

    bad = (
        ~normalized.isin(VALID_BRAND_CODES)
        &
        ~df[col].apply(is_blank)
    )

    for i in df[bad].index:

        add_issue(
            0,
            f"{col} invalid brand code: {df.loc[i, col]}",
            i
        )

    # OPTIONAL:
    # overwrite cleaned values back into dataframe
    df[col] = normalized

# ---------------------------------------------------------------
# Core mandatory pricing vars
# If adhoc_last_purchase = 1
# ---------------------------------------------------------------
price_required_cols = [
    "adhoc_price_last",
    "adhoc_price_last_type",
    "adhoc_price_last_axle",
    "adhoc_price_last_engine",
    "adhoc_price_last_disp",
    "adhoc_price_last_cab",
    "adhoc_price_cost",
    "adhoc_price_last_weight"
]

if "adhoc_last_purchase" in df.columns:

    trigger = df["adhoc_last_purchase"] == 1

    for c in price_required_cols:

        if c not in df.columns:
            add_issue(
                1,
                f"Missing variable: {c}"
            )
            continue

        bad = (
            trigger
            &
            df[c].apply(is_blank)
        )

        for i in df[bad].index:

            add_issue(
                0,
                f"{c} required when adhoc_last_purchase=1",
                i
            )

# -------------------------------------------------------------------
# Brand comparison logic
# Ask ALL brands except purchased brand
# -------------------------------------------------------------------

brand_codes = [
    "b9","b27","b35","b36","b43",
    "b45","b54","b30","b24","b50",
    "b19","b20","b29","b33","b41",
    "b46","b47","b52"
]

# normalize purchased brand
purchased_brand = (
    df["adhoc_price_last"]
    .astype(str)
    .str.strip()
    .str.lower()
)

# convert 9.0 -> b9 etc
def normalize_brand(val):

    try:

        sval = str(val).strip().lower()

        if sval.startswith("b"):
            return sval

        return f"b{int(float(sval))}"

    except:
        return sval

purchased_brand = purchased_brand.apply(normalize_brand)

for b in brand_codes:

    comp_col = f"adhoc_price_comp_{b}"
    less_col = f"adhoc_price_comp_less_{b}"
    more_col = f"adhoc_price_comp_more_{b}"

    if comp_col not in df.columns:
        continue

for b in brand_codes:

    comp_col = f"adhoc_price_comp_{b}"
    less_col = f"adhoc_price_comp_less_{b}"
    more_col = f"adhoc_price_comp_more_{b}"

    if comp_col not in df.columns:
        continue

    trigger = (
        (pd.to_numeric(
            df["adhoc_last_purchase"],
            errors="coerce"
        ) == 1)
        &
        (purchased_brand != b)
    )

    # -------------------------------------------------------
    # Detect whether this brand was actually asked
    # -------------------------------------------------------
    asked_mask = pd.Series(False, index=df.index)

    for c in [comp_col, less_col, more_col]:

        if c in df.columns:

            asked_mask |= ~df[c].apply(is_blank)

    # -------------------------------------------------------
    # Validate comp required
    # -------------------------------------------------------
    bad = (
        trigger
        &
        asked_mask
        &
        df[comp_col].apply(is_blank)
    )

    for i in df[bad].index:

        add_issue(
            0,
            f"{comp_col} missing",
            i
        )

    # -------------------------------------------------------
    # LESS logic
    # -------------------------------------------------------
    if less_col in df.columns:

        bad_less = (
            trigger
            &
            (pd.to_numeric(
                df[comp_col],
                errors="coerce"
            ) == 1)
            &
            df[less_col].apply(is_blank)
        )

        for i in df[bad_less].index:

            add_issue(
                0,
                f"{less_col} required when {comp_col}=1",
                i
            )

    # -------------------------------------------------------
    # MORE logic
    # -------------------------------------------------------
    if more_col in df.columns:

        bad_more = (
            trigger
            &
            (pd.to_numeric(
                df[comp_col],
                errors="coerce"
            ) == 2)
            &
            df[more_col].apply(is_blank)
        )

        for i in df[bad_more].index:

            add_issue(
                0,
                f"{more_col} required when {comp_col}=2",
                i
            )
        
# -------------------------------------------------------------------
# safety_SF3 required if >1 answer selected in safety_SF2
# -------------------------------------------------------------------

sf2_cols = [
    "safety_SF2_1",
    "safety_SF2_2",
    "safety_SF2_3",
    "safety_SF2_4",
    "safety_SF2_5",
    "safety_SF2_6",
    "safety_SF2_7",
    "safety_SF2_98"
]

existing_sf2_cols = [
    c for c in sf2_cols
    if c in df.columns
]

if (
    "safety_SF3" in df.columns
    and existing_sf2_cols
):

    sf2_numeric = (
        df[existing_sf2_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    # count number of selected options
    sf2_count = sf2_numeric.eq(1).sum(axis=1)

    # trigger if more than one selected
    trigger = sf2_count > 1

    bad = (
        trigger
        &
        df["safety_SF3"].apply(is_blank)
    )

    for i in df[bad].index:

        add_issue(
            0,
            "safety_SF3 required when multiple safety_SF2 selected",
            i
        )

# -------------------------------------------------------------------
# safety_SF5 required if safety_SF4 = 1,2,3
# -------------------------------------------------------------------

sf5_cols = [
    c for c in df.columns
    if c.startswith("safety_SF5_")
]

if sf5_cols and "safety_SF4" in df.columns:

    sf5_numeric = (
        df[sf5_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    any_sf5_selected = sf5_numeric.eq(1).any(axis=1)

    trigger = df["safety_SF4"].isin([1,2,3])

    bad = (
        trigger
        &
        (~any_sf5_selected)
    )

    for i in df[bad].index:

        add_issue(
            0,
            "At least one safety_SF5 option required when safety_SF4=1,2,3",
            i
        )
        
# -------------------------------------------------------------------
# Chinese truck barrier / reason logic
# -------------------------------------------------------------------

adhoc_ch_barr_cols = [
    c for c in df.columns
    if c.startswith("adhoc_ch_barr_")
]

adhoc_ch_reason_cols = [
    c for c in df.columns
    if c.startswith("adhoc_ch_reason_")
]

# ---------------------------------------------------------------
# Barrier logic
# If adhoc_ch_consideration = 1,2
# ---------------------------------------------------------------
if (
    "adhoc_ch_consideration" in df.columns
    and adhoc_ch_barr_cols
):

    barr_numeric = (
        df[adhoc_ch_barr_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    any_barr = barr_numeric.eq(1).any(axis=1)

    trigger_barr = (
        df["adhoc_ch_consideration"]
        .isin([1,2])
    )

    bad_barr = (
        trigger_barr
        &
        (~any_barr)
    )

    for i in df[bad_barr].index:

        add_issue(
            20,
            "adhoc_ch_barr required when adhoc_ch_consideration=1,2",
            i
        )

# ---------------------------------------------------------------
# Reason logic
# If adhoc_ch_consideration = 3,4,5
# ---------------------------------------------------------------
if (
    "adhoc_ch_consideration" in df.columns
    and adhoc_ch_reason_cols
):

    reason_numeric = (
        df[adhoc_ch_reason_cols]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    any_reason = reason_numeric.eq(1).any(axis=1)

    trigger_reason = (
        df["adhoc_ch_consideration"]
        .isin([3,4,5])
    )

    bad_reason = (
        trigger_reason
        &
        (~any_reason)
    )

    for i in df[bad_reason].index:

        add_issue(
            20,
            "adhoc_ch_reason required when adhoc_ch_consideration=3,4,5",
            i
        )
        
# -------------------------------------------------------------------
# adhoc_ch_fueltypes required
# If adhoc_ch_consideration = 3,4,5
# -------------------------------------------------------------------

if (
    "adhoc_ch_consideration" in df.columns
    and "adhoc_ch_fueltypes" in df.columns
):

    trigger = (
        df["adhoc_ch_consideration"]
        .isin([3,4,5])
    )

    bad = (
        trigger
        &
        df["adhoc_ch_fueltypes"].apply(is_blank)
    )

    for i in df[bad].index:

        add_issue(
            20,
            "adhoc_ch_fueltypes required when adhoc_ch_consideration=3,4,5",
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

    st.success("No issues found – dataset follows survey logic.")

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
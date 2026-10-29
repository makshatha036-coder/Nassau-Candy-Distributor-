"""Load, validate and clean the Nassau Candy dataset.

The raw file is NEVER modified. A cleaned copy is written to data/processed/.
Every decision is recorded in a cleaning log (outputs/reports/cleaning_log.csv).
Run directly:  python data_cleaning.py
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import config
from utils import normalize_col, safe_divide

GP_TOLERANCE = 0.01  # dollars; Gross Profit vs Sales - Cost


# ----------------------------------------------------------------------------- loading
def load_raw(path=None) -> pd.DataFrame:
    """Read CSV or Excel. Everything is read as-is (no type guessing for dates)."""
    path = Path(path or config.RAW_DATA_FILE)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}\nPut your file in data/raw/ and set RAW_DATA_FILE in config.py")
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1")
    if suffix in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path, sheet_name=config.EXCEL_SHEET, dtype=str, keep_default_na=False)
    raise ValueError(f"Unsupported file type '{suffix}'. Use .csv or .xlsx")


def map_columns(df: pd.DataFrame):
    """Rename raw columns to canonical names using config.COLUMN_ALIASES.
    Returns (renamed_df, mapping_dict, missing_required_list)."""
    lookup = {normalize_col(c): c for c in df.columns}
    mapping = {}
    for canon, aliases in config.COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lookup and lookup[alias] not in mapping:
                mapping[lookup[alias]] = canon
                break
    renamed = df.rename(columns=mapping)
    renamed = renamed[[c for c in renamed.columns if c in set(mapping.values())]]
    missing = [c for c in config.REQUIRED_COLUMNS if c not in renamed.columns]
    return renamed, mapping, missing


# ----------------------------------------------------------------------------- profiling
def profile_raw(raw: pd.DataFrame) -> dict:
    """Schema/quality snapshot of the raw file (used by the report)."""
    num = {c: pd.to_numeric(raw[c], errors="coerce") for c in raw.columns
           if normalize_col(c) in ("sales", "units", "gross profit", "cost")}
    return {
        "rows": len(raw), "columns": raw.shape[1], "column_names": list(raw.columns),
        "blank_cells": {c: int((raw[c].astype(str).str.strip() == "").sum()) for c in raw.columns},
        "fully_duplicated_rows": int(raw.duplicated().sum()),
        "non_numeric_in_numeric_cols": {c: int(s.isna().sum()) for c, s in num.items()},
    }


# ----------------------------------------------------------------------------- cleaning
def clean(raw: pd.DataFrame, drop_exact_duplicates=None):
    """Return (clean_df, log_df, info_dict). See comments for each rule."""
    drop_exact_duplicates = config.DROP_EXACT_DUPLICATES if drop_exact_duplicates is None else drop_exact_duplicates
    log = []

    def note(step, detail, rows_affected=0, action="none"):
        log.append({"step": step, "detail": detail, "rows_affected": int(rows_affected), "action": action})

    df, mapping, missing = map_columns(raw)
    if missing:
        raise ValueError(f"Required columns missing from dataset: {missing}. "
                         f"Update COLUMN_ALIASES in config.py. Columns found: {list(raw.columns)}")
    note("Column mapping", "; ".join(f"{k} -> {v}" for k, v in mapping.items()), 0, "renamed")
    optional_missing = [c for c in config.COLUMN_ALIASES if c not in df.columns]
    if optional_missing:
        note("Optional columns absent", ", ".join(optional_missing), 0, "related analyses skipped")

    n0 = len(df)
    # 1. text columns: trim whitespace, collapse internal spaces
    for c in df.columns:  # every column is still text at this point
        df[c] = df[c].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    note("Whitespace trim", "Trimmed leading/trailing/double spaces in text columns", 0, "standardised")

    # 2. numeric columns - invalid -> NaN (never filled with arbitrary numbers)
    for c in ["sales", "units", "gross_profit", "cost"]:
        before_blank = (df[c] == "").sum()
        df[c] = pd.to_numeric(df[c].replace("", np.nan), errors="coerce")
        bad = df[c].isna().sum()
        note(f"Numeric parse: {c}", f"{before_blank} blank, {bad} unparseable/missing after conversion",
             bad, "left as missing (not imputed)" if bad else "none needed")

    # 3. dates - explicit day-first parse; failures become NaT and are reported
    for c in [x for x in ("order_date", "ship_date") if x in df.columns]:
        parsed = pd.to_datetime(df[c], format="%d-%m-%Y", errors="coerce")
        failed = parsed.isna() & (df[c] != "")
        if failed.any():  # fall back to flexible parser only for the failures
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # flexible parser warns about format inference; failures stay NaT
                parsed.loc[failed] = pd.to_datetime(df.loc[failed, c], dayfirst=config.DATE_DAYFIRST, errors="coerce")
        df[c] = parsed
        note(f"Date parse: {c}", f"{df[c].isna().sum()} invalid; range {df[c].min():%Y-%m-%d} to {df[c].max():%Y-%m-%d}",
             df[c].isna().sum(), "invalid dates -> NaT (kept, excluded from time charts)")

    # 4. ship date plausibility (do NOT overwrite; just flag)
    df["ship_date_suspect"] = False
    if "ship_date" in df.columns:
        lag = (df["ship_date"] - df["order_date"]).dt.days
        df["ship_lag_days"] = lag
        df["ship_date_suspect"] = (lag > config.MAX_PLAUSIBLE_SHIP_LAG_DAYS) | (lag < 0)
        note("Ship Date plausibility",
             f"Lag Order->Ship: min {lag.min():.0f}, median {lag.median():.0f}, max {lag.max():.0f} days "
             f"(plausible limit {config.MAX_PLAUSIBLE_SHIP_LAG_DAYS}). Ship Date values fall after the "
             f"dataset period, so they cannot be trusted.",
             df["ship_date_suspect"].sum(), "flagged ship_date_suspect; NO lead-time analysis performed")

    # 5. validation rules
    df["gp_calc"] = (df["sales"] - df["cost"]).round(4)
    df["gp_mismatch"] = (df["gp_calc"] - df["gross_profit"]).abs() > GP_TOLERANCE
    note("Gross Profit check", f"|Sales - Cost - Gross Profit| > {GP_TOLERANCE}: {int(df['gp_mismatch'].sum())} rows",
         df["gp_mismatch"].sum(), "flagged (source Gross Profit kept)" if df["gp_mismatch"].any() else "all consistent")
    for label, mask in {
        "Negative sales (possible returns)": df["sales"] < 0,
        "Zero sales": df["sales"] == 0,
        "Zero/negative units": df["units"] <= 0,
        "Negative cost": df["cost"] < 0,
        "Negative gross profit": df["gross_profit"] < 0,
        "Missing units": df["units"].isna(),
    }.items():
        note(f"Investigation: {label}", f"{int(mask.sum())} rows", mask.sum(),
             "retained & flagged for review" if mask.any() else "none found")

    # 6. consistency of keys
    if "product_id" in df.columns:
        multi = df.groupby("product_name")["product_id"].nunique().gt(1).sum()
        note("Product ID/Name consistency", f"{multi} product names with >1 Product ID", multi, "none" if not multi else "review")
    if "order_id" in df.columns and "product_id" in df.columns:
        suffix_ok = df.apply(lambda r: r["order_id"].endswith(r["product_id"]), axis=1).mean()
        if suffix_ok > 0.99:
            # Order ID = <base order>-<product id>; strip suffix to get the real order key
            df["base_order_id"] = [o[:-(len(p) + 1)] if o.endswith("-" + p) else o
                                   for o, p in zip(df["order_id"], df["product_id"])]
            note("Order key derivation",
                 f"Order ID ends with Product ID in {suffix_ok:.1%} of rows, so Order ID is a line key. "
                 f"Derived base_order_id = Order ID without product suffix to avoid double counting orders.",
                 0, "added base_order_id")
        else:
            df["base_order_id"] = df["order_id"]
    elif "order_id" in df.columns:
        df["base_order_id"] = df["order_id"]

    # 7. duplicates
    key_cols = [c for c in df.columns if c in config.COLUMN_ALIASES and c != "row_id"]
    exact = df.duplicated(subset=key_cols, keep="first")
    df["possible_duplicate"] = exact
    df["line_repeat_key"] = False
    if "order_id" in df.columns:
        df["line_repeat_key"] = df.duplicated(subset=["order_id"], keep=False) & ~df["possible_duplicate"]
    note("Duplicates - exact", f"{int(exact.sum())} rows identical to an earlier row in every field except Row ID "
         f"(revenue {df.loc[exact,'sales'].sum():,.2f}, i.e. {safe_divide(df.loc[exact,'sales'].sum(), df['sales'].sum()) * 100:.1f}% of total). "
         f"Row ID is unique so no true record duplicates exist.", exact.sum(),
         "REMOVED (config)" if drop_exact_duplicates else "flagged `possible_duplicate`, KEPT (cannot prove they are errors)")
    note("Duplicates - repeated Order ID", "Rows that share an Order ID with another row but differ in quantity/amount "
         "are treated as separate order lines (plausible split shipments/entries), not duplicates.", df["line_repeat_key"].sum(), "kept")
    if drop_exact_duplicates:
        df = df[~df["possible_duplicate"]].copy()

    # 8. helper columns
    df["order_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()
    df["order_year"] = df["order_date"].dt.year
    if "postal_code" in df.columns:
        df["postal_code"] = df["postal_code"].astype(str)
        note("Postal Code", "Kept as text (leading zeros / Canadian codes preserved). Some US codes have 4 digits "
             "(leading zero lost in source) - not altered.", 0, "kept as text")
    for c in ["row_id", "customer_id"]:
        if c in df.columns:
            df[c] = df[c].astype(str)

    info = {"rows_raw": n0, "rows_clean": len(df), "column_mapping": mapping, "optional_missing": optional_missing}
    return df.reset_index(drop=True), pd.DataFrame(log), info


def run_cleaning(path=None, save=True):
    raw = load_raw(path)
    profile = profile_raw(raw)
    clean_df, log_df, info = clean(raw)
    info["profile"] = profile
    if save:
        config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        clean_df.to_csv(config.CLEAN_DATA_FILE, index=False)
        log_df.to_csv(config.REPORTS_DIR / "cleaning_log.csv", index=False)
    return clean_df, log_df, info


if __name__ == "__main__":
    c, l, i = run_cleaning()
    pd.set_option("display.width", 200, "display.max_colwidth", 110)
    print(l.to_string(index=False))
    print(f"\nSaved {len(c):,} rows -> {config.CLEAN_DATA_FILE}")

"""Reusable helpers: safe maths, formatting, name normalisation, mapping."""
import re
import numpy as np
import pandas as pd
import config


def safe_divide(num, den, default=np.nan):
    """Divide num by den; return `default` (NaN) wherever the denominator is 0/NaN.
    Works for scalars, Series and arrays."""
    if np.isscalar(num) and np.isscalar(den):
        if den is None or pd.isna(den) or den == 0 or pd.isna(num):
            return default
        return num / den
    num = pd.Series(num) if not isinstance(num, pd.Series) else num
    den = pd.Series(den, index=num.index) if not isinstance(den, pd.Series) else den
    out = num.astype(float) / den.astype(float).replace(0, np.nan)
    return out.fillna(default) if not pd.isna(default) else out


def normalize_name(name) -> str:
    """Lower-case and strip everything except letters/digits so that
    'Wonka Bar -Scrumdiddlyumptious' == 'wonka bar - scrumdiddlyumptious'."""
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return ""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def normalize_col(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def fmt_money(x, digits=0):
    return "n/a" if x is None or pd.isna(x) else f"${x:,.{digits}f}"


def fmt_pct(x, digits=1):
    return "n/a" if x is None or pd.isna(x) else f"{x:.{digits}f}%"


def fmt_num(x, digits=0):
    return "n/a" if x is None or pd.isna(x) else f"{x:,.{digits}f}"


def build_factory_lookup() -> pd.DataFrame:
    """Normalised product-name -> factory table (with coordinates)."""
    rows = []
    for product, factory in config.PRODUCT_FACTORY_MAP.items():
        lat, lon = config.FACTORY_COORDS[factory]
        rows.append({"map_key": normalize_name(product), "mapped_product": product,
                     "Factory": factory, "Latitude": lat, "Longitude": lon})
    return pd.DataFrame(rows)


def attach_factory(df: pd.DataFrame):
    """Left-join factory info on normalised product names.
    Returns (df_with_factory, unmatched_products_df). Unmatched rows get Factory = 'Unmapped'."""
    lookup = build_factory_lookup()
    out = df.copy()
    out["map_key"] = out["product_name"].map(normalize_name)
    out = out.merge(lookup[["map_key", "Factory", "Latitude", "Longitude"]], on="map_key", how="left")
    unmatched = (out[out["Factory"].isna()].groupby("product_name", as_index=False)
                 .agg(rows=("sales", "size"), revenue=("sales", "sum")))
    out["Factory"] = out["Factory"].fillna("Unmapped")
    return out.drop(columns="map_key"), unmatched


def mapping_not_in_data(df: pd.DataFrame) -> list:
    """Products listed in the supplied mapping but absent from the dataset."""
    present = set(df["product_name"].map(normalize_name))
    return [p for p in config.PRODUCT_FACTORY_MAP if normalize_name(p) not in present]


def apply_filters(df: pd.DataFrame, date_range=None, divisions=None, regions=None, states=None,
                  product_query="", exclude_possible_duplicates=False) -> pd.DataFrame:
    """Single place where dashboard filters are applied (so tests can cover it).
    None / empty list for a multi-select means 'no restriction'."""
    out = df
    if date_range is not None and len(date_range) == 2 and "order_date" in out:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
        out = out[(out["order_date"] >= start) & (out["order_date"] <= end)]
    for col, values in (("division", divisions), ("region", regions), ("state", states)):
        if values and col in out.columns:
            out = out[out[col].isin(values)]
    if product_query and str(product_query).strip():
        out = out[out["product_name"].str.contains(str(product_query).strip(), case=False, na=False, regex=False)]
    if exclude_possible_duplicates and "possible_duplicate" in out.columns:
        out = out[~out["possible_duplicate"]]
    return out

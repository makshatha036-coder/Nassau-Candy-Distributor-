"""Unit tests. Run from the project folder:  python -m pytest -q"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analysis as A
import config
import data_cleaning as dc
import utils


def raw_frame(rows=None):
    base = dict(**{"Row ID": "1", "Order ID": "US-2024-1-AAA-001", "Order Date": "05-03-2024", "Ship Date": "09-03-2024",
                   "Customer ID": "10", "State/Province": "Texas", "Region": "Gulf", "Division": "Chocolate",
                   "Product ID": "AAA-001", "Product Name": "Wonka Bar - Milk Chocolate",
                   "Sales": "10", "Units": "2", "Gross Profit": "6", "Cost": "4"})
    rows = rows or [{}]
    out = []
    for i, r in enumerate(rows, 1):
        d = dict(base); d.update(r); d.setdefault("Row ID", str(i))
        if "Row ID" not in r: d["Row ID"] = str(i)
        out.append(d)
    return pd.DataFrame(out)


def cleaned(rows=None):
    df, log, info = dc.clean(raw_frame(rows))
    return df


# ---------------------------------------------------------------- calculations
def test_gross_profit_matches_sales_minus_cost():
    df = cleaned()
    assert not df["gp_mismatch"].any()
    df2 = cleaned([{"Gross Profit": "9"}])
    assert df2["gp_mismatch"].all()          # inconsistent source value is flagged, not silently fixed


def test_weighted_margin_vs_simple_average():
    df = cleaned([{"Product Name": "A", "Product ID": "A1", "Sales": "100", "Cost": "10", "Gross Profit": "90"},
                  {"Product Name": "B", "Product ID": "B1", "Sales": "10", "Cost": "9", "Gross Profit": "1"}])
    k = A.overall_kpis(df)
    assert k["gross_margin_pct"] == pytest.approx(91 / 110 * 100)   # weighted
    assert k["simple_avg_product_margin_pct"] == pytest.approx((90 + 10) / 2)  # simple mean differs


def test_zero_sales_and_zero_units_are_safe():
    df = cleaned([{"Sales": "0", "Cost": "0", "Gross Profit": "0", "Units": "0"}])
    k = A.overall_kpis(df)
    assert np.isnan(k["gross_margin_pct"]) and np.isnan(k["profit_per_unit"])
    assert np.isnan(utils.safe_divide(1, 0))
    assert utils.fmt_pct(np.nan) == "n/a"


def test_missing_values_not_imputed():
    df = cleaned([{"Units": ""}])
    assert df["units"].isna().all()


def test_contributions_sum_to_100():
    df = cleaned([{"Product Name": "A", "Product ID": "A1"}, {"Product Name": "B", "Product ID": "B1", "Sales": "30", "Cost": "10", "Gross Profit": "20"}])
    p = A.summarize(df, "product_name")
    assert p["revenue_contribution_pct"].sum() == pytest.approx(100)
    assert p["profit_contribution_pct"].sum() == pytest.approx(100)


def test_orders_not_double_counted():
    rows = [{"Order ID": "US-1-X-A", "Product ID": "A", "Product Name": "P1"},
            {"Order ID": "US-1-X-B", "Product ID": "B", "Product Name": "P2"}]
    df = cleaned(rows)
    assert df["base_order_id"].nunique() == 1       # two lines of one base order
    assert A.overall_kpis(df)["orders"] == 1


# ---------------------------------------------------------------- cleaning
def test_invalid_dates_become_nat_and_are_reported():
    df, log, _ = dc.clean(raw_frame([{"Order Date": "31-02-2024"}, {"Order Date": "garbage"}, {}]))
    assert df["order_date"].isna().sum() == 2
    assert (log["step"] == "Date parse: order_date").any()


def test_exact_duplicates_flagged_not_dropped_by_default():
    rows = [{"Row ID": "1"}, {"Row ID": "2"}]    # identical except Row ID
    df, log, _ = dc.clean(raw_frame(rows))
    assert len(df) == 2 and df["possible_duplicate"].sum() == 1
    df2, _, _ = dc.clean(raw_frame(rows), drop_exact_duplicates=True)
    assert len(df2) == 1


def test_negative_values_are_retained_and_flagged():
    df, log, _ = dc.clean(raw_frame([{"Sales": "-5", "Cost": "2", "Gross Profit": "-7"}]))
    assert len(df) == 1
    assert log.loc[log["step"].str.contains("Negative sales"), "rows_affected"].iloc[0] == 1


def test_missing_required_column_raises_clear_error():
    with pytest.raises(ValueError, match="Required columns missing"):
        dc.clean(raw_frame().drop(columns=["Sales"]))


def test_missing_optional_columns_still_works():
    df = raw_frame().drop(columns=["Region", "State/Province", "Ship Date"])
    out, log, _ = dc.clean(df)
    assert "region" not in out.columns
    assert len(A.overall_kpis(out)) > 0
    t, s = A.concentration(out, "state")
    assert t.empty and s == {}


def test_alias_mapping():
    df = raw_frame().rename(columns={"Sales": "Revenue", "Product Name": "Product", "Units": "Quantity"})
    out, _, info = dc.clean(df)
    assert {"sales", "product_name", "units"} <= set(out.columns)


def test_missing_file_message(tmp_path):
    with pytest.raises(FileNotFoundError):
        dc.load_raw(tmp_path / "nope.csv")


# ---------------------------------------------------------------- Pareto
def test_pareto_cumulative_reaches_100_and_is_sorted():
    t = pd.DataFrame({"p": list("abcde"), "v": [50, 30, 10, 6, 4]})
    p, s = A.pareto(t, "p", "v")
    assert p["cumulative_pct"].iloc[-1] == pytest.approx(100)
    assert p["cumulative_pct"].is_monotonic_increasing
    assert s["n_to_cutoff"] == 2 and s["pct_items_to_cutoff"] == pytest.approx(40)   # 50+30 = 80%


def test_pareto_negative_and_zero_total():
    p, s = A.pareto(pd.DataFrame({"p": list("abc"), "v": [10, 5, -4]}), "p", "v")
    assert s["valid"] and s["negative_values"] and p["cumulative_pct"].max() <= 100
    p, s = A.pareto(pd.DataFrame({"p": ["a", "b"], "v": [0, 0]}), "p", "v")
    assert not s["valid"]
    p, s = A.pareto(pd.DataFrame(), "p", "v")
    assert not s["valid"]


# ---------------------------------------------------------------- risk flags, classification, volatility
def test_risk_flags_follow_threshold():
    prod = pd.DataFrame({"product_name": ["a", "b", "c"], "revenue": [100, 100, 100], "cost": [30, 70, 120],
                         "gross_profit": [70, 30, -20], "units": [1, 1, 1]})
    prod = A.add_ratios(prod)
    r = A.margin_risk_table(prod, margin_threshold=50, cost_ratio_threshold=0.6).set_index("product_name")
    assert not r.loc["a", "flag_low_margin"]
    assert r.loc["b", "flag_low_margin"] and r.loc["b", "flag_high_cost_ratio"]
    assert r.loc["c", "flag_negative_profit"]
    assert r.loc["c", "risk_level"] == "High"


def test_classification_quadrants():
    prod = A.add_ratios(pd.DataFrame({"product_name": list("abcd"), "revenue": [1000, 1000, 10, 10], "cost": [200, 800, 2, 8],
                                      "gross_profit": [800, 200, 8, 2], "units": [1, 1, 1, 1]}))
    c = A.classify_products(prod, revenue_split=500, margin_split=50).set_index("product_name")["profitability_class"]
    assert c["a"] == "High Revenue / High Margin" and c["b"] == "High Revenue / Low Margin"
    assert c["c"] == "Low Revenue / High Margin" and c["d"] == "Low Revenue / Low Margin"


def test_volatility_needs_three_months():
    m = pd.DataFrame({"order_month": pd.to_datetime(["2024-01-01", "2024-02-01"]), "revenue": [10, 10],
                      "gross_profit": [5, 6], "cost": [5, 4], "units": [1, 1]})
    m["gross_margin_pct"] = m["gross_profit"] / m["revenue"] * 100
    assert np.isnan(A.margin_volatility(m)["volatility_pp"].iloc[0])


# ---------------------------------------------------------------- factory mapping
def test_factory_mapping_normalised_and_unmatched_reported():
    rows = [{"Product Name": "wonka bar - scrumdiddlyumptious", "Product ID": "P1"},   # spacing/case differs from the mapping
            {"Product Name": "Mystery Candy", "Product ID": "P2"}]
    df = cleaned(rows)
    fs, pf, unmatched, enriched = A.factory_analysis(df)
    assert enriched.loc[enriched["product_name"].str.contains("scrumdid"), "Factory"].iloc[0] == "Lot's O' Nuts"
    assert list(unmatched["product_name"]) == ["Mystery Candy"]
    assert (enriched.loc[enriched["product_name"] == "Mystery Candy", "Factory"] == "Unmapped").all()


# ---------------------------------------------------------------- filters
def test_filters_division_product_date_and_empty():
    rows = [{"Division": "Chocolate", "Product Name": "Wonka Bar - Milk Chocolate", "Product ID": "A", "Order Date": "05-03-2024"},
            {"Division": "Sugar", "Product Name": "Nerds", "Product ID": "B", "Order Date": "05-06-2024"}]
    df = cleaned(rows)
    assert len(utils.apply_filters(df, divisions=["Sugar"])) == 1
    assert len(utils.apply_filters(df, product_query="nerd")) == 1
    assert len(utils.apply_filters(df, date_range=("2024-01-01", "2024-04-01"))) == 1
    empty = utils.apply_filters(df, product_query="zzz")
    assert empty.empty and A.summarize(empty, "product_name").empty and A.pareto(A.summarize(empty, "x") if False else pd.DataFrame(), "a", "b")[1]["valid"] is False
    assert A.build_insights(empty) == ["No data for the current filters."]


# ---------------------------------------------------------------- real dataset (skipped if file absent)
@pytest.mark.skipif(not config.RAW_DATA_FILE.exists(), reason="dataset not present")
def test_real_dataset_end_to_end():
    r = A.run_pipeline(save=False)
    k = r["kpis"]
    assert k["revenue"] - k["cost"] == pytest.approx(k["gross_profit"], abs=0.5)
    assert r["product"]["revenue"].sum() == pytest.approx(k["revenue"])
    assert r["division"]["revenue"].sum() == pytest.approx(k["revenue"])
    assert r["unmatched"].empty

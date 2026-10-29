"""Metrics and analysis functions + a runnable pipeline.

Run:  python analysis.py      (cleans data, computes everything, saves CSVs + PNG charts)
Every function accepts a (possibly filtered) DataFrame, so the dashboard reuses them.
"""
import json
import numpy as np
import pandas as pd
import config
from utils import safe_divide, attach_factory, mapping_not_in_data, fmt_money, fmt_pct


# ============================================================ core aggregation
def add_ratios(g: pd.DataFrame, total_rev=None, total_gp=None) -> pd.DataFrame:
    """Add margin, profit/unit, cost ratio and contribution % to an aggregated table."""
    total_rev = g["revenue"].sum() if total_rev is None else total_rev
    total_gp = g["gross_profit"].sum() if total_gp is None else total_gp
    g = g.copy()
    g["gross_margin_pct"] = safe_divide(g["gross_profit"], g["revenue"]) * 100       # weighted margin
    g["profit_per_unit"] = safe_divide(g["gross_profit"], g["units"])
    g["cost_ratio"] = safe_divide(g["cost"], g["revenue"])
    g["revenue_contribution_pct"] = safe_divide(g["revenue"], total_rev) * 100
    g["profit_contribution_pct"] = safe_divide(g["gross_profit"], total_gp) * 100
    return g


def summarize(df: pd.DataFrame, by) -> pd.DataFrame:
    """Aggregate revenue/cost/profit/units by one or more columns.
    Orders are counted on base_order_id (distinct) to avoid double counting."""
    if df.empty:
        return pd.DataFrame()
    by = [by] if isinstance(by, str) else list(by)
    agg = dict(revenue=("sales", "sum"), cost=("cost", "sum"), gross_profit=("gross_profit", "sum"),
               units=("units", "sum"), line_items=("sales", "size"))
    if "base_order_id" in df.columns:
        agg["orders"] = ("base_order_id", "nunique")
    g = df.groupby(by, dropna=False).agg(**agg).reset_index()
    g = add_ratios(g, df["sales"].sum(), df["gross_profit"].sum())
    return g.sort_values("revenue", ascending=False).reset_index(drop=True)


def overall_kpis(df: pd.DataFrame) -> dict:
    """Business-level KPIs. Margin is WEIGHTED (total GP / total revenue)."""
    rev, cost, gp, units = df["sales"].sum(), df["cost"].sum(), df["gross_profit"].sum(), df["units"].sum()
    k = dict(revenue=rev, cost=cost, gross_profit=gp, units=units,
             gross_margin_pct=safe_divide(gp, rev) * 100 if rev else np.nan,
             profit_per_unit=safe_divide(gp, units), line_items=len(df))
    if "base_order_id" in df.columns and len(df):
        k["orders"] = df["base_order_id"].nunique()
        order_rev = df.groupby("base_order_id")["sales"].sum()
        k["avg_order_value"] = order_rev.mean()
    else:
        k["orders"], k["avg_order_value"] = np.nan, np.nan
    k["customers"] = df["customer_id"].nunique() if "customer_id" in df.columns else np.nan
    k["n_products"] = df["product_name"].nunique()
    k["simple_avg_product_margin_pct"] = simple_avg_margin(df)
    return k


def simple_avg_margin(df: pd.DataFrame) -> float:
    """UNWEIGHTED mean of product margins - shown only to contrast with the weighted margin."""
    p = summarize(df, "product_name")
    return p["gross_margin_pct"].mean() if len(p) else np.nan


# ============================================================ time series
def monthly(df: pd.DataFrame, by=None) -> pd.DataFrame:
    if df.empty or df["order_month"].isna().all():
        return pd.DataFrame()
    keys = ["order_month"] + ([by] if isinstance(by, str) else list(by or []))
    m = df.dropna(subset=["order_month"]).groupby(keys).agg(
        revenue=("sales", "sum"), cost=("cost", "sum"), gross_profit=("gross_profit", "sum"),
        units=("units", "sum")).reset_index()
    m["gross_margin_pct"] = safe_divide(m["gross_profit"], m["revenue"]) * 100
    return m.sort_values(keys)


def margin_volatility(monthly_df: pd.DataFrame, by=None) -> pd.DataFrame:
    """Margin volatility = standard deviation (sample, in percentage points) of the MONTHLY weighted
    gross margin, over months with revenue > 0. Also reports min, max and coefficient of variation.
    Needs >= 3 months, otherwise NaN."""
    if monthly_df.empty:
        return pd.DataFrame()

    def _vol(x):
        s = x.loc[x["revenue"] > 0, "gross_margin_pct"].dropna()
        if len(s) < 3:
            return pd.Series(dict(months=len(s), mean_margin_pct=s.mean(), volatility_pp=np.nan,
                                  min_margin_pct=s.min(), max_margin_pct=s.max(), cv=np.nan))
        return pd.Series(dict(months=len(s), mean_margin_pct=s.mean(), volatility_pp=s.std(ddof=1),
                              min_margin_pct=s.min(), max_margin_pct=s.max(),
                              cv=safe_divide(s.std(ddof=1), s.mean())))
    if by is None:
        return _vol(monthly_df).to_frame().T
    return monthly_df.groupby(by).apply(_vol, include_groups=False).reset_index()


# ============================================================ product analysis
def product_leaderboards(prod: pd.DataFrame, n=10, min_rev=None, min_rows=None) -> dict:
    min_rev = config.MIN_REVENUE_FOR_MARGIN_RANK if min_rev is None else min_rev
    min_rows = config.MIN_ROWS_FOR_MARGIN_RANK if min_rows is None else min_rows
    eligible = prod[(prod["revenue"] >= min_rev) & (prod["line_items"] >= min_rows)]
    return {
        "top_revenue": prod.nlargest(n, "revenue"),
        "top_profit": prod.nlargest(n, "gross_profit"),
        "top_margin": eligible.nlargest(n, "gross_margin_pct"),
        "bottom_profit": prod.nsmallest(n, "gross_profit"),
        "margin_rank_excluded": prod[~prod.index.isin(eligible.index)],
    }


def _split_value(series: pd.Series, rule, weighted_value=None):
    """Turn a split rule into a number: a $/% value, 'median', 'mean', 'share:X' (X% of total) or 'weighted'."""
    if isinstance(rule, (int, float)):
        return float(rule)
    if isinstance(rule, str) and rule.startswith("share:"):
        return float(series.sum()) * float(rule.split(":")[1]) / 100
    if rule == "mean":
        return float(series.mean())
    if rule == "weighted" and weighted_value is not None and not pd.isna(weighted_value):
        return float(weighted_value)
    return float(series.median())


def classify_products(prod: pd.DataFrame, revenue_split=None, margin_split=None) -> pd.DataFrame:
    """Four-quadrant classification.
    High revenue = revenue >= revenue_split (default: 5% of total revenue).
    High margin  = gross margin % >= margin_split (default: overall WEIGHTED margin of the data).
    Both cut-offs are configurable (config.py / dashboard)."""
    if prod.empty:
        return prod.assign(profitability_class=[])
    revenue_split = config.REVENUE_SPLIT if revenue_split is None else revenue_split
    margin_split = config.MARGIN_SPLIT if margin_split is None else margin_split
    overall = safe_divide(prod["gross_profit"].sum(), prod["revenue"].sum()) * 100
    rs = _split_value(prod["revenue"], revenue_split)
    ms = _split_value(prod["gross_margin_pct"], margin_split, overall)
    out = prod.copy()
    hi_r, hi_m = out["revenue"] >= rs, out["gross_margin_pct"] >= ms
    out["profitability_class"] = np.select(
        [hi_r & hi_m, hi_r & ~hi_m, ~hi_r & hi_m],
        ["High Revenue / High Margin", "High Revenue / Low Margin", "Low Revenue / High Margin"],
        default="Low Revenue / Low Margin")
    out["margin_vs_overall_pp"] = out["gross_margin_pct"] - overall
    out.attrs["revenue_split"], out.attrs["margin_split"] = rs, ms
    return out


def margin_risk_table(prod: pd.DataFrame, margin_threshold=None, cost_ratio_threshold=None) -> pd.DataFrame:
    """Transparent rule-based flags (no black box):
      Low margin           : gross margin % < margin_threshold
      Negative gross profit: gross profit < 0
      High cost ratio      : cost / revenue > cost_ratio_threshold
    risk_flags counts how many rules fire. These are SCREENING flags, not conclusions."""
    margin_threshold = config.LOW_MARGIN_THRESHOLD if margin_threshold is None else margin_threshold
    cost_ratio_threshold = config.HIGH_COST_RATIO_THRESHOLD if cost_ratio_threshold is None else cost_ratio_threshold
    if prod.empty:
        return prod
    r = prod.copy()
    r["flag_low_margin"] = r["gross_margin_pct"] < margin_threshold
    r["flag_negative_profit"] = r["gross_profit"] < 0
    r["flag_high_cost_ratio"] = r["cost_ratio"] > cost_ratio_threshold
    r["risk_flags"] = r[["flag_low_margin", "flag_negative_profit", "flag_high_cost_ratio"]].sum(axis=1)
    r["risk_level"] = np.select([r["risk_flags"] >= 2, r["risk_flags"] == 1], ["High", "Watch"], default="OK")
    return r.sort_values(["risk_flags", "revenue"], ascending=[False, False])


# ============================================================ Pareto
def pareto(table: pd.DataFrame, name_col: str, value_col: str, cutoff=None) -> tuple:
    """Pareto table sorted by value desc. Returns (table, stats).
    NEGATIVE VALUES: cumulative shares need non-negative parts. If negatives exist the denominator is the
    sum of POSITIVE values only, negatives are listed last and flagged (stats['negative_values']=True).
    Zero/negative total -> stats['valid']=False and no shares are produced."""
    cutoff = config.PARETO_CUTOFF if cutoff is None else cutoff
    empty_stats = dict(valid=False, n_items=0, n_to_cutoff=np.nan, pct_items_to_cutoff=np.nan,
                       top1_share=np.nan, top3_share=np.nan, negative_values=False)
    if table.empty or name_col not in table:
        return pd.DataFrame(), empty_stats
    p = table[[name_col, value_col]].sort_values(value_col, ascending=False).reset_index(drop=True)
    pos_total = p.loc[p[value_col] > 0, value_col].sum()
    neg = bool((p[value_col] < 0).any())
    if pos_total <= 0:
        return p, {**empty_stats, "n_items": len(p), "negative_values": neg}
    p["share_pct"] = np.where(p[value_col] > 0, p[value_col] / pos_total * 100, 0.0)
    p["cumulative_pct"] = p["share_pct"].cumsum().clip(upper=100)
    p["rank"] = np.arange(1, len(p) + 1)
    k = int((p["cumulative_pct"] < cutoff * 100 - 1e-9).sum() + 1)
    k = min(k, len(p))
    stats = dict(valid=True, n_items=len(p), n_to_cutoff=k, pct_items_to_cutoff=k / len(p) * 100,
                 top1_share=p["share_pct"].iloc[0], top3_share=p["share_pct"].head(3).sum(),
                 top1_name=p[name_col].iloc[0], negative_values=neg, cutoff=cutoff)
    p["in_cutoff_group"] = p["rank"] <= k
    return p, stats


def concentration(df: pd.DataFrame, col: str, top_n=5) -> tuple:
    """Revenue/profit concentration across a location column. HHI on revenue shares (0-10,000)."""
    if df.empty or col not in df.columns:
        return pd.DataFrame(), {}
    t = summarize(df, col)
    shares = t["revenue"] / t["revenue"].sum()
    stats = dict(n_locations=len(t), top1=t[col].iloc[0], top1_rev_share=shares.iloc[0] * 100,
                 top_n_rev_share=shares.head(top_n).sum() * 100,
                 top_n_profit_share=t.nlargest(top_n, "gross_profit")["gross_profit"].sum() / t["gross_profit"].sum() * 100,
                 hhi=float((shares ** 2).sum() * 10000), top_n=top_n)
    return t, stats


# ============================================================ factory
def factory_analysis(df: pd.DataFrame):
    """Returns (factory_summary, product_factory_table, unmatched_products, enriched_df)."""
    enriched, unmatched = attach_factory(df)
    if enriched.empty:
        return pd.DataFrame(), pd.DataFrame(), unmatched, enriched
    mapped = enriched[enriched["Factory"] != "Unmapped"]
    fs = summarize(mapped, "Factory") if len(mapped) else pd.DataFrame()
    if len(fs):
        nprod = mapped.groupby("Factory")["product_name"].nunique().rename("products")
        fs = fs.merge(nprod, on="Factory", how="left")
        coords = mapped.groupby("Factory")[["Latitude", "Longitude"]].first().reset_index()
        fs = fs.merge(coords, on="Factory", how="left")
    pf = summarize(enriched, ["Factory", "product_name"]) if len(enriched) else pd.DataFrame()
    return fs, pf, unmatched, enriched


# ============================================================ insights
def build_insights(df: pd.DataFrame, margin_threshold=None) -> list:
    """Short observations generated ONLY from the data passed in."""
    if df.empty:
        return ["No data for the current filters."]
    margin_threshold = config.LOW_MARGIN_THRESHOLD if margin_threshold is None else margin_threshold
    k = overall_kpis(df)
    prod = summarize(df, "product_name")
    div = summarize(df, "division") if "division" in df else pd.DataFrame()
    out = [f"Revenue is {fmt_money(k['revenue'])} with gross profit of {fmt_money(k['gross_profit'])} "
           f"(weighted gross margin {fmt_pct(k['gross_margin_pct'])}); the simple average of product margins is "
           f"{fmt_pct(k['simple_avg_product_margin_pct'])} - a different measure because it ignores sales volume."]
    top = prod.iloc[0]
    out.append(f"{top['product_name']} is the top product by revenue ({fmt_pct(top['revenue_contribution_pct'])} of revenue, "
               f"{fmt_pct(top['profit_contribution_pct'])} of gross profit).")
    if len(div):
        d = div.iloc[0]
        out.append(f"{d['division']} generates {fmt_pct(d['revenue_contribution_pct'])} of revenue and "
                   f"{fmt_pct(d['profit_contribution_pct'])} of gross profit.")
    low = prod[prod["gross_margin_pct"] < margin_threshold]
    if len(low):
        lr = low["revenue"].sum() / prod["revenue"].sum() * 100
        out.append(f"{len(low)} of {len(prod)} products fall below the {margin_threshold:.0f}% margin threshold "
                   f"({', '.join(low.sort_values('revenue', ascending=False)['product_name'].head(3))}"
                   f"{'...' if len(low) > 3 else ''}); together they are {lr:.1f}% of revenue.")
    else:
        out.append(f"No product falls below the {margin_threshold:.0f}% margin threshold.")
    ps, st = pareto(prod, "product_name", "gross_profit")
    if st.get("valid"):
        out.append(f"{st['n_to_cutoff']} of {st['n_items']} products ({st['pct_items_to_cutoff']:.0f}%) generate 80% of gross profit.")
    return out


# ============================================================ pipeline + charts
def save_charts(df: pd.DataFrame, results: dict):
    """Static Matplotlib versions of the key charts (PNG) for the report."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = config.CHARTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    prod, div = results["product"], results["division"]

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(out / name, dpi=130)
        plt.close(fig)

    top = prod.nlargest(10, "revenue").iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5)); ax.barh(top["product_name"], top["revenue"], color="#3b6ea5")
    ax.set_title("Top products by revenue"); ax.set_xlabel("Revenue ($)"); save(fig, "top_products_revenue.png")

    x = np.arange(len(prod)); fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - .2, prod["revenue"], .4, label="Revenue", color="#3b6ea5")
    ax.bar(x + .2, prod["gross_profit"], .4, label="Gross profit", color="#e0873b")
    ax.set_xticks(x, prod["product_name"], rotation=60, ha="right"); ax.legend(); ax.set_title("Revenue vs gross profit by product")
    save(fig, "product_revenue_vs_profit.png")

    fig, ax = plt.subplots(figsize=(7, 4)); ax.bar(div["division"], div["gross_margin_pct"], color="#4c9a6a")
    ax.axhline(results["kpis"]["gross_margin_pct"], ls="--", c="grey", label="Overall weighted margin")
    ax.set_ylabel("Gross margin (%)"); ax.set_title("Gross margin by division"); ax.legend(); save(fig, "division_margin.png")

    m = results["monthly"]
    fig, ax = plt.subplots(figsize=(10, 4.5)); ax.plot(m["order_month"], m["revenue"], marker="o", label="Revenue")
    ax.plot(m["order_month"], m["gross_profit"], marker="o", label="Gross profit"); ax.legend()
    ax.set_title("Monthly revenue and gross profit"); save(fig, "monthly_trend.png")

    for key, label in (("pareto_revenue", "Revenue"), ("pareto_profit", "Gross profit")):
        p = results[key]
        if len(p):
            fig, ax = plt.subplots(figsize=(10, 5)); ax.bar(p.iloc[:, 0], p["share_pct"], color="#3b6ea5")
            ax.set_ylabel("Individual share (%)"); ax.tick_params(axis="x", rotation=60)
            ax2 = ax.twinx(); ax2.plot(p.iloc[:, 0], p["cumulative_pct"], c="#d1495b", marker="o")
            ax2.axhline(80, ls="--", c="grey"); ax2.set_ylabel("Cumulative (%)"); ax2.set_ylim(0, 105)
            ax.set_title(f"Pareto - {label} by product"); plt.setp(ax.get_xticklabels(), ha="right"); save(fig, f"{key}.png")

    fig, ax = plt.subplots(figsize=(6.5, 5)); ax.scatter(prod["revenue"], prod["cost"], s=60)
    for _, r in prod.iterrows():
        ax.annotate(r["product_name"], (r["revenue"], r["cost"]), fontsize=7, xytext=(3, 3), textcoords="offset points")
    lim = max(prod["revenue"].max(), prod["cost"].max()); ax.plot([0, lim], [0, lim], ls=":", c="red", label="Cost = Sales")
    ax.set_xlabel("Revenue ($)"); ax.set_ylabel("Cost ($)"); ax.set_title("Cost vs revenue by product"); ax.legend(); save(fig, "cost_vs_sales.png")


def run_pipeline(save=True) -> dict:
    from data_cleaning import run_cleaning
    df, log, info = run_cleaning(save=save)
    work = df
    kpis = overall_kpis(work)
    prod = classify_products(summarize(work, "product_name"))
    div = summarize(work, "division")
    mon = monthly(work)
    results = dict(kpis=kpis, product=prod, division=div, monthly=mon, cleaning_info=info, cleaning_log=log)
    results["leaderboards"] = product_leaderboards(prod)
    results["risk"] = margin_risk_table(prod)
    results["pareto_revenue"], results["pareto_revenue_stats"] = pareto(prod, "product_name", "revenue")
    results["pareto_profit"], results["pareto_profit_stats"] = pareto(prod, "product_name", "gross_profit")
    results["volatility_overall"] = margin_volatility(mon)
    results["volatility_division"] = margin_volatility(monthly(work, "division"), "division")
    results["division_monthly"] = monthly(work, "division")
    results["state"], results["state_stats"] = concentration(work, "state")
    results["region"], results["region_stats"] = concentration(work, "region")
    results["country"], _ = concentration(work, "country")
    fs, pf, unmatched, enriched = factory_analysis(work)
    results.update(factory=fs, product_factory=pf, unmatched=unmatched, missing_from_data=mapping_not_in_data(work))
    # duplicate sensitivity check
    nodup = work[~work["possible_duplicate"]]
    kd = overall_kpis(nodup)
    results["dup_sensitivity"] = dict(revenue_with=kpis["revenue"], revenue_without=kd["revenue"],
                                      margin_with=kpis["gross_margin_pct"], margin_without=kd["gross_margin_pct"],
                                      rows_flagged=int(work["possible_duplicate"].sum()))
    if save:
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("product", "division", "monthly", "risk", "pareto_revenue", "pareto_profit", "state", "region",
                     "factory", "product_factory", "unmatched", "division_monthly"):
            if len(results[name]):
                results[name].to_csv(config.REPORTS_DIR / f"{name}_summary.csv", index=False)
        save_charts(work, results)
    return results


if __name__ == "__main__":
    pd.set_option("display.width", 220, "display.max_columns", 30)
    r = run_pipeline()
    print("KPIs:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r["kpis"].items()})
    print(r["product"][["product_name", "revenue", "gross_profit", "gross_margin_pct", "profitability_class"]].round(2).to_string(index=False))
    print(r["division"].round(2).to_string(index=False))
    print("Charts and CSVs saved in outputs/")

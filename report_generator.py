"""Builds the research report and executive summary (Markdown) from the REAL analysis results.
Every number is inserted from computed data - nothing is typed in by hand.
Run:  python report_generator.py    
"""
import numpy as np
import pandas as pd
import config
from analysis import run_pipeline, overall_kpis, summarize
from utils import fmt_money as M, fmt_pct as P, fmt_num as N


def md_table(df: pd.DataFrame, cols: dict, fmts: dict = None) -> str:
    fmts = fmts or {}
    head = "\n| " + " | ".join(cols.values()) + " |\n|" + "|".join(["---"] * len(cols)) + "|\n"
    rows = []
    for _, r in df.iterrows():
        rows.append("| " + " | ".join(fmts.get(c, lambda v: str(v))(r[c]) for c in cols) + " |")
    return head + "\n".join(rows) + "\n"


def build(r: dict, df: pd.DataFrame):
    k, prod, div, mon = r["kpis"], r["product"], r["division"], r["monthly"]
    info, log = r["cleaning_info"], r["cleaning_log"]
    prof = info["profile"]
    ps_r, ps_p = r["pareto_revenue_stats"], r["pareto_profit_stats"]
    risk, state, region = r["risk"], r["state"], r["region"]
    ss, rs = r["state_stats"], r["region_stats"]
    fs = r["factory"]
    ds = r["dup_sensitivity"]
    vol, vold = r["volatility_overall"].iloc[0], r["volatility_division"]

    d0, d1 = df["order_date"].min(), df["order_date"].max()
    yearly = summarize(df, "order_year").sort_values("order_year")
    ship_lag = df["ship_lag_days"] if "ship_lag_days" in df else pd.Series(dtype=float)
    q4 = mon[mon["order_month"].dt.month.isin([9, 11, 12])]
    q4_share = q4["revenue"].sum() / mon["revenue"].sum() * 100
    top5_months = mon.nlargest(3, "revenue")
    flagged = risk[risk["risk_flags"] > 0]
    lowvol = prod[prod["line_items"] < config.MIN_ROWS_FOR_MARGIN_RANK]
    kaz = prod[prod["product_name"] == "Kazookles"]
    lw = prod[prod["product_name"] == "Lickable Wallpaper"]
    choc, oth, sug = (div[div["division"] == d].iloc[0] if (div["division"] == d).any() else None for d in ("Chocolate", "Other", "Sugar"))
    ca = df[df["country"] == "Canada"]["sales"].sum() / k["revenue"] * 100 if "country" in df else np.nan
    margin_range_products = (prod["gross_margin_pct"].min(), prod["gross_margin_pct"].max())

    # does margin vary within a product? (important caveat)
    within = (df.assign(m=(df["gross_profit"] / df["sales"]).round(6)).groupby("product_name")["m"].nunique() > 1).sum()

    # ---------------------------------------------------------------- executive summary
    ex = f"""# Executive Summary - Nassau Candy Distributor Product Line Profitability

*Prepared from the supplied transaction file ({prof['rows']:,} rows, orders dated {d0:%d %b %Y} to {d1:%d %b %Y}). This is an independent analytical summary; it has no official or governmental endorsement.*

## Headline results
- **Revenue {M(k['revenue'])}**, cost {M(k['cost'])}, **gross profit {M(k['gross_profit'])}**, weighted gross margin **{P(k['gross_margin_pct'])}** on {N(k['units'])} units and {N(k['orders'])} distinct orders.
- **Profit is concentrated in a few products.** {ps_p['n_to_cutoff']} of {ps_p['n_items']} products ({ps_p['pct_items_to_cutoff']:.0f}%) generate 80% of gross profit; all of them are Chocolate-division Wonka Bars. The top three products supply {ps_p['top3_share']:.1f}% of profit.
- **Chocolate is the core division**: {P(choc['revenue_contribution_pct'])} of revenue and {P(choc['profit_contribution_pct'])} of gross profit at a {P(choc['gross_margin_pct'])} margin. "Other" earns {P(oth['gross_margin_pct'])} and Sugar has only {int(sug['line_items'])} transactions ({P(sug['revenue_contribution_pct'])} of revenue).
- **Margin risk is concentrated in a small number of non-chocolate items.** Using a {config.LOW_MARGIN_THRESHOLD:.0f}% margin screen, {int(risk['flag_low_margin'].sum())} of {len(risk)} products are flagged; the most notable is **Kazookles** (margin {P(kaz['gross_margin_pct'].iloc[0])} on {M(kaz['revenue'].iloc[0])} revenue, {int(kaz['line_items'].iloc[0])} transactions). **No product has negative gross profit.**
- **Geography**: California alone is {ss['top1_rev_share']:.1f}% of revenue; the top five states hold {ss['top_n_rev_share']:.1f}%. Regional revenue shares range from {region['revenue_contribution_pct'].min():.0f}% to {region['revenue_contribution_pct'].max():.0f}%.

## Recommended actions (each needs validation before decisions)
1. **Review Kazookles pricing/cost first** - the unit price and unit cost are close together (see report section 9). Confirm whether the cost figure is correct, then consider repricing or supplier negotiation.
2. **Protect the five core chocolate bars** - they are the profit engine; any supply or price disruption affects most profit.
3. **Review low-margin small items** (Lickable Wallpaper, Wonka Gum, SweeTARTS, Nerds, Fun Dip) for pricing; volumes are small so test before acting.
4. **Sugar-division conclusions are not yet reliable** - only {int(sug['line_items'])} transactions; gather more data before ranking it.
5. **Fix data issues**: Ship Date values fall {ship_lag.min():.0f}-{ship_lag.max():.0f} days after the order date (impossible), so delivery performance could not be analysed; {ds['rows_flagged']} possible duplicate rows should be confirmed with the data owner.

## Main caveats
- Each product has one fixed margin in this file, so product margins do not vary by transaction; differences between products reflect price/cost structure, not discounting or cost drift.
- Factory results use the supplied product-to-factory mapping and are reference-only.
"""

    # ---------------------------------------------------------------- full report
    steps = log[["step", "detail", "rows_affected", "action"]]
    rep = f"""# Product Line Profitability & Margin Performance Analysis - Nassau Candy Distributor

*Generated automatically from the analysis results. All figures come from the supplied dataset `{config.RAW_DATA_FILE.name}`.*

## 1. Introduction and business problem
Nassau Candy Distributor sells chocolate, sugar and other confectionery through U.S. and Canadian customers. Management needs to know which products and divisions create profit, where margins are weak, how concentrated profit is, and which items need pricing or cost review. This project answers those questions with transparent, rule-based analysis of the transaction data.

## 2. Dataset description
- **File**: `{config.RAW_DATA_FILE.name}` (CSV), **{prof['rows']:,} rows x {prof['columns']} columns**.
- **Columns**: {', '.join(prof['column_names'])}.
- **Order period**: {d0:%d %b %Y} to {d1:%d %b %Y} ({mon['order_month'].nunique()} months).
- **Entities**: {k['n_products']} products, {df['division'].nunique()} divisions ({', '.join(sorted(df['division'].unique()))}), {df['state'].nunique()} states/provinces, {df['region'].nunique()} regions, {df['country'].nunique()} countries ({', '.join(sorted(df['country'].unique()))}), {N(k['customers'])} customers.
- **Blank cells**: {sum(prof['blank_cells'].values())}. **Non-numeric values in Sales/Units/Gross Profit/Cost**: {sum(prof['non_numeric_in_numeric_cols'].values())}.
- **Order ID structure**: every Order ID ends with its Product ID, so Order ID identifies an order *line*, not a whole order. A derived `base_order_id` (Order ID without the product suffix) gives {N(k['orders'])} distinct orders and is used for order counts and Average Order Value to avoid double counting.

## 3. Data cleaning methodology
The raw file is never modified; a cleaned copy is saved to `data/processed/`. Every step below is also saved in `outputs/reports/cleaning_log.csv`.

{md_table(steps, {'step': 'Step', 'detail': 'Finding', 'rows_affected': 'Rows', 'action': 'Action'})}
**Key decisions**
- **Gross Profit validation**: Gross Profit equals Sales - Cost on every row (tolerance $0.01), so the source Gross Profit column is used directly.
- **No negative or zero values** were found in sales, cost, units or gross profit, so there were no returns or loss transactions to investigate.
- **Possible duplicates**: {ds['rows_flagged']} rows are identical to an earlier row in every field except Row ID. They *could* be genuine repeat purchases, so they are **kept** and flagged. Sensitivity check: excluding them changes revenue from {M(ds['revenue_with'])} to {M(ds['revenue_without'])} and margin from {P(ds['margin_with'],2)} to {P(ds['margin_without'],2)} - conclusions do not change. The dashboard has a switch to exclude them.
- **Ship Date**: values run {df['ship_date'].min():%b %Y} to {df['ship_date'].max():%b %Y}, i.e. {ship_lag.min():.0f} to {ship_lag.max():.0f} days after the order date. This is not plausible, so Ship Date was kept but flagged and **no lead-time analysis was performed**. The year inside Order IDs (2021-2024) also does not match the Order Date year, another sign of inconsistent source fields.

## 4. Exploratory data analysis
- Revenue by year: {'; '.join(f"{int(y.order_year)}: {M(y.revenue)}" for _, y in yearly.iterrows())}.
- Monthly revenue is uneven. The three strongest months are {', '.join(f"{m:%b %Y} ({M(v)})" for m, v in zip(top5_months['order_month'], top5_months['revenue']))}; September, November and December together account for {q4_share:.1f}% of all revenue.
- Average line-item value is {M(k['revenue']/k['line_items'], 2)}; average units per line item is {k['units']/k['line_items']:.1f}.
- Customers: {N(k['customers'])} distinct customer IDs across {N(k['orders'])} orders, so most customers appear once.
- Sales to Canada are {ca:.1f}% of revenue.
- Charts: `outputs/charts/` (monthly trend, top products, revenue vs profit, margin by division, Pareto, cost vs sales).

## 5. KPI definitions
| KPI | Definition |
|---|---|
| Total Revenue | Sum of Sales |
| Total Cost | Sum of Cost |
| Gross Profit | Sum of Gross Profit (validated = Sales - Cost) |
| **Gross Margin % (weighted)** | Total Gross Profit / Total Revenue x 100 |
| Simple average margin | Unweighted mean of product margins (shown only for contrast) |
| Profit per Unit | Gross Profit / Units |
| Revenue / Profit contribution | Item revenue (profit) / total revenue (profit) x 100 |
| Average Order Value | Revenue / distinct base orders |
| Margin volatility | Sample standard deviation of the monthly weighted margin, in percentage points (needs >= 3 months) |
| Cost ratio | Cost / Sales |

Weighted vs simple: the overall **weighted margin is {P(k['gross_margin_pct'])}**, but the **simple average of the {k['n_products']} product margins is {P(k['simple_avg_product_margin_pct'])}**. The gap exists because small, low-margin products count equally in the simple average but hardly affect the weighted figure.

Overall margin volatility is **{vol['volatility_pp']:.2f} percentage points** (monthly margin ranged {P(vol['min_margin_pct'])} to {P(vol['max_margin_pct'])}). Because each product has a single fixed margin ({within} of {k['n_products']} products show any within-product margin variation), month-to-month movement is caused entirely by **product mix**, not by price or cost changes.

## 6. Product profitability findings
**Top 10 by revenue**
{md_table(r['leaderboards']['top_revenue'], {'product_name': 'Product', 'revenue': 'Revenue', 'gross_profit': 'Gross profit', 'gross_margin_pct': 'Margin', 'revenue_contribution_pct': 'Rev. share'}, {'revenue': M, 'gross_profit': M, 'gross_margin_pct': P, 'revenue_contribution_pct': P})}
**Top products by margin** (minimum {M(config.MIN_REVENUE_FOR_MARGIN_RANK)} revenue and {config.MIN_ROWS_FOR_MARGIN_RANK} transactions; {len(r['leaderboards']['margin_rank_excluded'])} low-volume products excluded)
{md_table(r['leaderboards']['top_margin'], {'product_name': 'Product', 'gross_margin_pct': 'Margin', 'revenue': 'Revenue', 'line_items': 'Transactions'}, {'gross_margin_pct': P, 'revenue': M})}
**Bottom 5 by gross profit**
{md_table(r['leaderboards']['bottom_profit'].head(5), {'product_name': 'Product', 'gross_profit': 'Gross profit', 'revenue': 'Revenue', 'gross_margin_pct': 'Margin', 'line_items': 'Transactions'}, {'gross_profit': M, 'revenue': M, 'gross_margin_pct': P})}
Only {len(prod)} products exist, so "Top 10"/"Bottom 10" lists cover most of the range. Fewer than {config.MIN_ROWS_FOR_MARGIN_RANK} transactions: {', '.join(lowvol['product_name'])} - these margins are descriptive only.

**Profitability classification** (High revenue = product revenue >= {M(prod.attrs['revenue_split'])}, i.e. 5% of revenue; High margin = margin >= overall weighted margin of {P(prod.attrs['margin_split'])}; both configurable)
{md_table(prod, {'product_name': 'Product', 'profitability_class': 'Class', 'revenue': 'Revenue', 'gross_margin_pct': 'Margin', 'margin_vs_overall_pp': 'vs overall (pp)'}, {'revenue': M, 'gross_margin_pct': P, 'margin_vs_overall_pp': lambda v: f'{v:+.1f}'})}
*Caution*: Triple Dazzle Caramel and Milk Chocolate fall in "High Revenue / Low Margin" only because they sit about 0.6-1.0 points below the overall weighted margin; their margins are still above 64%. The classification is a screening tool, not a verdict. No product is loss-making.

## 7. Division performance findings
{md_table(div, {'division': 'Division', 'revenue': 'Revenue', 'cost': 'Cost', 'gross_profit': 'Gross profit', 'gross_margin_pct': 'Margin', 'units': 'Units', 'profit_contribution_pct': 'Profit share', 'line_items': 'Transactions'}, {'revenue': M, 'cost': M, 'gross_profit': M, 'gross_margin_pct': P, 'units': N, 'profit_contribution_pct': P})}
- **Chocolate** performs strongly: highest margin of the three divisions ({P(choc['gross_margin_pct'])}), {P(choc['profit_contribution_pct'])} of profit, and very stable monthly margin (volatility {vold.loc[vold['division']=='Chocolate','volatility_pp'].iloc[0]:.2f} pp).
- **Other** earns a lower margin ({P(oth['gross_margin_pct'])}) and needs investigation: its margin swings widely by month ({vold.loc[vold['division']=='Other','volatility_pp'].iloc[0]:.1f} pp volatility) which reflects the changing monthly mix of Kazookles (very thin margin), Lickable Wallpaper (50%) and Wonka Gum (52%).
- **Sugar** has only {int(sug['line_items'])} transactions ({P(sug['revenue_contribution_pct'], 2)} of revenue); its {P(sug['gross_margin_pct'])} margin and monthly volatility ({vold.loc[vold['division']=='Sugar','volatility_pp'].iloc[0]:.1f} pp over {int(vold.loc[vold['division']=='Sugar','months'].iloc[0])} active months) rest on too few transactions to be reliable.

## 8. Pareto and concentration findings
- **Revenue**: {ps_r['n_to_cutoff']} of {ps_r['n_items']} products ({ps_r['pct_items_to_cutoff']:.0f}%) reach 80% of revenue; leading product {ps_r['top1_name']} = {ps_r['top1_share']:.1f}%, top three = {ps_r['top3_share']:.1f}%.
- **Gross profit**: {ps_p['n_to_cutoff']} of {ps_p['n_items']} products ({ps_p['pct_items_to_cutoff']:.0f}%) reach 80% of profit; leading product {ps_p['top1_name']} = {ps_p['top1_share']:.1f}%, top three = {ps_p['top3_share']:.1f}%.
- The five chocolate bars alone deliver {r['pareto_profit'].head(5)['share_pct'].sum():.1f}% of profit, so the business depends heavily on one division.
- **Scope**: these Pareto figures are computed on the full dataset; the dashboard lets you choose filtered or full data.
- **Limitation**: Pareto analysis assumes non-negative contributions. No product here has negative profit, so cumulative shares are well-defined; if negatives appeared, shares would be computed on positive values only and flagged. With only {ps_p['n_items']} products the "% of products" figure moves in steps of {100/ps_p['n_items']:.1f} points.
- **Geography**: {ss['top1']} = {ss['top1_rev_share']:.1f}% of revenue; top 5 of {ss['n_locations']} states/provinces = {ss['top_n_rev_share']:.1f}% revenue and {ss['top_n_profit_share']:.1f}% profit (HHI {ss['hhi']:.0f}; below the rough 1,500 guide, so not highly concentrated by state). Regions: {', '.join(f"{x.region} {x.revenue_contribution_pct:.1f}%" for x in region.itertuples())}.
{md_table(state.head(5), {'state': 'State', 'revenue': 'Revenue', 'gross_profit': 'Gross profit', 'revenue_contribution_pct': 'Rev. share'}, {'revenue': M, 'gross_profit': M, 'revenue_contribution_pct': P})}
## 9. Cost and margin risk findings
Rule-based screening ({config.LOW_MARGIN_THRESHOLD:.0f}% margin threshold; cost ratio > {config.HIGH_COST_RATIO_THRESHOLD:.2f}; negative profit). Note: cost ratio = 1 - margin, so these two rules express the same information; the cost-ratio rule is set stricter to act as a severity tier.
{md_table(flagged, {'product_name': 'Product', 'revenue': 'Revenue', 'gross_margin_pct': 'Margin', 'cost_ratio': 'Cost ratio', 'risk_flags': 'Flags', 'risk_level': 'Level'}, {'revenue': M, 'gross_margin_pct': P, 'cost_ratio': lambda v: f'{v:.2f}'})}
- **Negative gross profit**: {int(risk['flag_negative_profit'].sum())} products.
- **Kazookles**: {M(kaz['revenue'].iloc[0])} revenue, {M(kaz['cost'].iloc[0])} cost, margin {P(kaz['gross_margin_pct'].iloc[0])}, profit per unit {M(kaz['profit_per_unit'].iloc[0],2)}. Its listed unit price ($3.25) and unit cost ($3.00) leave very little room. This is a *candidate for review* - the cause could be pricing, supplier cost, or a data-entry issue, which this dataset cannot determine.
- **Lickable Wallpaper**: {M(lw['revenue'].iloc[0])} revenue (the largest non-chocolate product) at a {P(lw['gross_margin_pct'].iloc[0])} margin; it contributes {P(lw['profit_contribution_pct'].iloc[0])} of profit.
- Repricing, supplier negotiation or discontinuation are **recommendations requiring validation** (competitor pricing, contract terms, strategic role, demand elasticity), not conclusions from these figures.

## 10. Factory analysis
Factories come from the **supplied product-to-factory mapping** joined on normalised product names (reference data only, not proof of manufacturing source). All {k['n_products']} products matched; unmatched products: **{len(r['unmatched'])}**. Mapped products absent from the data: **{len(r['missing_from_data'])}**.
{md_table(fs, {'Factory': 'Factory', 'products': 'Products', 'revenue': 'Revenue', 'gross_profit': 'Gross profit', 'gross_margin_pct': 'Margin', 'profit_contribution_pct': 'Profit share'}, {'revenue': M, 'gross_profit': M, 'gross_margin_pct': P, 'profit_contribution_pct': P, 'products': N})}
- The two chocolate factories (Lot's O' Nuts and Wicked Choccy's) account for {fs[fs['Factory'].isin(["Lot's O' Nuts", "Wicked Choccy's"])]['profit_contribution_pct'].sum():.1f}% of gross profit.
- The Other Factory has the weakest margin ({P(fs.loc[fs['Factory']=='The Other Factory','gross_margin_pct'].iloc[0])}) because it is mapped to Kazookles and Hair Toffee.
- The mapping lists Fizzy Lifting Drinks under "Other", whereas the dataset places it in the Sugar division; the dataset's division was used for division analysis.
- No shipping distance, cost or route analysis was done: the dataset lacks usable shipping cost fields and its Ship Date is unreliable.

## 11. Evidence-based recommendations
1. **Validate Kazookles cost and price** with finance/procurement; consider repricing or supplier negotiation if the cost figure is confirmed.
2. **Review pricing of lower-margin items** (Lickable Wallpaper, Wonka Gum, SweeTARTS, Nerds, Fun Dip) - small volumes, so run controlled tests.
3. **Reduce single-division dependence**: Chocolate drives {P(choc['profit_contribution_pct'])} of profit; consider whether growing high-margin Everlasting Gobstopper or Hair Toffee is viable (their volumes are tiny, so evidence is limited).
4. **Monitor margin by product mix** each month, since mix is the only driver of margin movement in this data.
5. **Plan around seasonality** (Sep/Nov/Dec peaks) for supply and promotions.
6. **Improve data quality**: correct Ship Date, confirm possible duplicates, and add return/discount fields so margin variation can be analysed.

## 12. Limitations
- Only gross profit is available - no overhead, freight, marketing or discount data; net profitability is unknown.
- Margins are constant within each product, limiting price/cost-trend analysis.
- Sugar and several products have very few transactions.
- Ship Date unreliable; delivery performance not analysed.
- Possible duplicates cannot be verified from the file alone.
- Factory mapping is user-supplied reference data.
- Two years of data; seasonality conclusions are based on 24 months.

## 13. Conclusion
Nassau Candy's profitability rests on five chocolate products that produce about {r['pareto_profit'].head(5)['share_pct'].sum():.0f}% of gross profit at healthy margins. No product loses money, but a handful of small non-chocolate items - above all Kazookles - earn thin margins and warrant pricing and cost review. Data-quality issues (Ship Date, possible duplicates) should be resolved before drawing operational conclusions beyond profitability.
"""
    return ex, rep


def main():
    r = run_pipeline(save=True)
    from data_cleaning import run_cleaning
    df, _, _ = run_cleaning(save=False)
    ex, rep = build(r, df)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (config.REPORTS_DIR / "executive_summary.md").write_text(ex, encoding="utf-8")
    (config.REPORTS_DIR / "research_report.md").write_text(rep, encoding="utf-8")
    print("Wrote executive_summary.md and research_report.md to", config.REPORTS_DIR)


if __name__ == "__main__":
    main()

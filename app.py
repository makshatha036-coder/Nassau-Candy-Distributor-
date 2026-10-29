"""Nassau Candy Distributor - Product Line Profitability Dashboard.
Run:  streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from analysis import (build_insights, classify_products, concentration, factory_analysis,
                      margin_risk_table, margin_volatility, monthly, overall_kpis, pareto,
                      product_leaderboards, summarize)
from data_cleaning import run_cleaning
from utils import apply_filters, fmt_money, fmt_num, fmt_pct

st.set_page_config(page_title="Nassau Candy - Profitability", page_icon="🍬", layout="wide")
st.markdown("""<style>
.block-container {padding-top: 1.5rem;}
[data-testid="stMetric"] {background: rgba(128,128,128,0.08); border-radius: 10px; padding: 10px 14px;}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- data loading
_chart_counter = [0]


def show(fig):
    """Render a Plotly figure with a unique key (avoids duplicate-ID errors when two charts look identical,
    e.g. when only one product is selected)."""
    _chart_counter[0] += 1
    st.plotly_chart(fig, width="stretch", key=f"chart_{_chart_counter[0]}")


@st.cache_data(show_spinner="Loading and cleaning data...")
def load_data():
    df, log, info = run_cleaning(save=False)
    return df, log, info


try:
    full_df, cleaning_log, clean_info = load_data()
except FileNotFoundError as e:
    st.error(f"**Dataset not found.** {e}")
    st.info("Place your CSV/Excel file in `data/raw/` and set `RAW_DATA_FILE` in `config.py`.")
    st.stop()
except Exception as e:  # noqa: BLE001 - show any problem in friendly form
    st.error(f"**Could not load the dataset:** {e}")
    st.stop()

# ----------------------------------------------------------------------------- sidebar filters
st.sidebar.title("🍬 Filters")
dmin, dmax = full_df["order_date"].min().date(), full_df["order_date"].max().date()
date_sel = st.sidebar.date_input("Order date range", (dmin, dmax), min_value=dmin, max_value=dmax)
if not isinstance(date_sel, (list, tuple)) or len(date_sel) != 2:
    st.sidebar.warning("Select both a start and an end date.")
    date_sel = (dmin, dmax)
divisions = st.sidebar.multiselect("Division", sorted(full_df["division"].unique()))
regions = st.sidebar.multiselect("Region", sorted(full_df["region"].unique())) if "region" in full_df else []
state_options = sorted(full_df.loc[full_df["region"].isin(regions), "state"].unique()) if regions and "state" in full_df \
    else (sorted(full_df["state"].unique()) if "state" in full_df else [])
states = st.sidebar.multiselect("State / Province", state_options) if "state" in full_df else []
product_q = st.sidebar.text_input("Product search", placeholder="e.g. Wonka, Taffy")
excl_dup = st.sidebar.checkbox("Exclude 'possible duplicate' rows", value=config.DROP_EXACT_DUPLICATES,
                               help="Rows identical to an earlier row in every field except Row ID. "
                                    "Kept by default because they cannot be proven to be errors.")
st.sidebar.markdown("---")
st.sidebar.subheader("Thresholds")
margin_thr = st.sidebar.slider("Low gross-margin threshold (%)", 0, 100, int(config.LOW_MARGIN_THRESHOLD))
cost_thr = st.sidebar.slider("High cost-ratio threshold (cost / sales)", 0.0, 1.0, float(config.HIGH_COST_RATIO_THRESHOLD), 0.01)
rev_share_thr = st.sidebar.slider("'High revenue' = product share of revenue ≥ (%)", 0.0, 20.0, 5.0, 0.5)
pareto_scope = st.sidebar.radio("Pareto / concentration scope", ["Filtered data", "Full dataset"],
                                help="Choose whether concentration is computed on the current filters or ignores them.")

df = apply_filters(full_df, date_sel, divisions, regions, states, product_q, excl_dup)
st.sidebar.caption(f"{len(df):,} of {len(full_df):,} rows selected")

st.title("Nassau Candy Distributor — Product Line Profitability")
st.caption(f"Orders {date_sel[0]:%d %b %Y} → {date_sel[1]:%d %b %Y} · Source: `{config.RAW_DATA_FILE.name}`")

if df.empty:
    st.warning("No data matches the current filters. Widen the date range or clear some filters.")
    st.stop()

pareto_df = df if pareto_scope == "Filtered data" else full_df
prod = classify_products(summarize(df, "product_name"), revenue_split=f"share:{rev_share_thr}")
div = summarize(df, "division")
mon = monthly(df)

tabs = st.tabs(["A · Executive Overview", "B · Product Profitability", "C · Division Performance",
                "D · Cost & Margin Diagnostics", "E · Pareto & Concentration", "F · Factory Analysis", "Data Notes"])

# ============================================================================ A. Executive
with tabs[0]:
    k = overall_kpis(df)
    c = st.columns(5)
    c[0].metric("Revenue", fmt_money(k["revenue"]))
    c[1].metric("Total cost", fmt_money(k["cost"]))
    c[2].metric("Gross profit", fmt_money(k["gross_profit"]))
    c[3].metric("Gross margin (weighted)", fmt_pct(k["gross_margin_pct"]))
    c[4].metric("Units sold", fmt_num(k["units"]))
    c = st.columns(4)
    c[0].metric("Distinct orders", fmt_num(k["orders"]))
    c[1].metric("Avg order value", fmt_money(k["avg_order_value"], 2))
    c[2].metric("Profit per unit", fmt_money(k["profit_per_unit"], 2))
    c[3].metric("Simple avg of product margins", fmt_pct(k["simple_avg_product_margin_pct"]),
                help="Unweighted mean of each product's margin. Differs from the weighted margin because it ignores volume.")
    left, right = st.columns([3, 2])
    with left:
        if len(mon):
            fig = go.Figure()
            fig.add_bar(x=mon["order_month"], y=mon["revenue"], name="Revenue", marker_color="#3b6ea5")
            fig.add_bar(x=mon["order_month"], y=mon["gross_profit"], name="Gross profit", marker_color="#e0873b")
            fig.add_scatter(x=mon["order_month"], y=mon["gross_margin_pct"], name="Margin %", yaxis="y2",
                            mode="lines+markers", line=dict(color="#d1495b"))
            fig.update_layout(barmode="group", title="Monthly revenue, gross profit and margin", height=400,
                              yaxis2=dict(overlaying="y", side="right", title="Margin %", range=[0, 100]),
                              legend=dict(orientation="h", y=-0.2), margin=dict(t=50))
            show(fig)
        vol = margin_volatility(mon)
        if len(vol) and not pd.isna(vol["volatility_pp"].iloc[0]):
            st.caption(f"Margin volatility (std. dev. of monthly weighted margin): **{vol['volatility_pp'].iloc[0]:.2f} pp** "
                       f"over {int(vol['months'].iloc[0])} months (range {vol['min_margin_pct'].iloc[0]:.1f}%–{vol['max_margin_pct'].iloc[0]:.1f}%).")
        else:
            st.caption("Margin volatility needs at least 3 months of data.")
    with right:
        st.subheader("Observations")
        for line in build_insights(df, margin_thr):
            st.markdown(f"- {line}")
        st.caption("Generated from the filtered data only.")

# ============================================================================ B. Product
with tabs[1]:
    st.subheader("Product leaderboard")
    lb = product_leaderboards(prod)
    metric = st.selectbox("Rank by", ["Revenue (top 10)", "Gross profit (top 10)", "Gross margin (top 10, minimum volume)",
                                      "Gross profit (bottom 10)"])
    key = {"Revenue (top 10)": "top_revenue", "Gross profit (top 10)": "top_profit",
           "Gross margin (top 10, minimum volume)": "top_margin", "Gross profit (bottom 10)": "bottom_profit"}[metric]
    board = lb[key]
    if key == "top_margin":
        st.caption(f"Eligibility: revenue ≥ {fmt_money(config.MIN_REVENUE_FOR_MARGIN_RANK)} and ≥ {config.MIN_ROWS_FOR_MARGIN_RANK} line items "
                   f"({len(lb['margin_rank_excluded'])} product(s) excluded for low volume).")
    show_cols = ["product_name", "revenue", "cost", "gross_profit", "gross_margin_pct", "units", "profit_per_unit"]
    st.dataframe(board[show_cols], width="stretch", hide_index=True,
                 column_config={"revenue": st.column_config.NumberColumn(format="$%.2f"),
                                "cost": st.column_config.NumberColumn(format="$%.2f"),
                                "gross_profit": st.column_config.NumberColumn(format="$%.2f"),
                                "gross_margin_pct": st.column_config.NumberColumn("Margin %", format="%.1f"),
                                "profit_per_unit": st.column_config.NumberColumn(format="$%.2f")})
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(prod.sort_values("revenue_contribution_pct"), x="revenue_contribution_pct", y="product_name",
                     orientation="h", title="Revenue contribution (%)", labels={"revenue_contribution_pct": "%", "product_name": ""})
        fig.update_layout(height=450); show(fig)
    with c2:
        fig = px.bar(prod.sort_values("profit_contribution_pct"), x="profit_contribution_pct", y="product_name",
                     orientation="h", title="Gross profit contribution (%)", labels={"profit_contribution_pct": "%", "product_name": ""},
                     color_discrete_sequence=["#e0873b"])
        fig.update_layout(height=450); show(fig)

    st.subheader("Profitability classification")
    rs, ms = prod.attrs.get("revenue_split"), prod.attrs.get("margin_split")
    st.caption(f"**High revenue** = product revenue ≥ {fmt_money(rs)} ({rev_share_thr:g}% of selected revenue). "
               f"**High margin** = product margin ≥ overall weighted margin ({fmt_pct(ms)}). "
               "Products just under/over the margin line differ by fractions of a point - read the 'margin vs overall' column.")
    fig = px.scatter(prod, x="revenue", y="gross_margin_pct", color="profitability_class", size="units", text="product_name",
                     hover_data=["gross_profit"], title="Revenue vs gross margin", log_x=True,
                     labels={"revenue": "Revenue ($, log scale)", "gross_margin_pct": "Gross margin %"})
    fig.add_hline(y=ms, line_dash="dash", line_color="grey"); fig.add_vline(x=max(rs, 1), line_dash="dash", line_color="grey")
    fig.update_traces(textposition="top center", textfont_size=9); fig.update_layout(height=520)
    show(fig)
    cls = prod[["product_name", "profitability_class", "revenue", "gross_profit", "gross_margin_pct", "margin_vs_overall_pp"]]
    st.dataframe(cls.sort_values(["profitability_class", "revenue"], ascending=[True, False]),
                 width="stretch", hide_index=True)

    st.subheader("Product detail table")
    detail = prod.copy()
    q = st.text_input("Filter this table by product name", key="detail_q")
    if q:
        detail = detail[detail["product_name"].str.contains(q, case=False, regex=False)]
    st.dataframe(detail, width="stretch", hide_index=True)
    st.download_button("Download product table (CSV)", detail.to_csv(index=False).encode(), "product_summary.csv", "text/csv")

# ============================================================================ C. Division
with tabs[2]:
    c1, c2 = st.columns(2)
    with c1:
        d = div.melt(id_vars="division", value_vars=["revenue", "gross_profit"], var_name="Measure", value_name="$")
        fig = px.bar(d, x="division", y="$", color="Measure", barmode="group", title="Revenue vs gross profit by division")
        show(fig)
    with c2:
        fig = px.bar(div, x="division", y="gross_margin_pct", text=div["gross_margin_pct"].round(1), title="Gross margin % by division",
                     color_discrete_sequence=["#4c9a6a"])
        fig.add_hline(y=overall_kpis(df)["gross_margin_pct"], line_dash="dash", annotation_text="overall weighted margin")
        show(fig)
    st.subheader("Division ranking")
    rk = div.copy()
    rk["rank_by_gross_profit"] = rk["gross_profit"].rank(ascending=False, method="min").astype(int)
    rk["rank_by_margin"] = rk["gross_margin_pct"].rank(ascending=False, method="min").astype(int)
    st.dataframe(rk.sort_values("rank_by_gross_profit"), width="stretch", hide_index=True)
    st.caption("Small divisions have few transactions - compare margins together with `line_items` before drawing conclusions.")
    work = df.assign(line_margin_pct=np.where(df["sales"] > 0, df["gross_profit"] / df["sales"] * 100, np.nan))
    fig = px.box(work, x="division", y="line_margin_pct", points="outliers", title="Distribution of line-item margins by division")
    show(fig)
    dm = monthly(df, "division")
    if len(dm):
        metric_sel = st.radio("Trend metric", ["revenue", "gross_profit", "gross_margin_pct"], horizontal=True)
        fig = px.line(dm, x="order_month", y=metric_sel, color="division", markers=True, title=f"Monthly {metric_sel.replace('_', ' ')} by division")
        show(fig)
        vd = margin_volatility(dm, "division")
        st.markdown("**Margin volatility by division** (std. dev. of monthly weighted margin, percentage points)")
        st.dataframe(vd.round(2), width="stretch", hide_index=True)

# ============================================================================ D. Diagnostics
with tabs[3]:
    risk = margin_risk_table(prod, margin_thr, cost_thr)
    st.caption(f"Rules: **Low margin** = margin < {margin_thr}% · **Negative gross profit** = profit < 0 · **High cost ratio** = cost/sales > {cost_thr:.2f}. "
               "These are screening flags, not conclusions: repricing, supplier negotiation or discontinuation need further validation.")
    level = st.radio("Scatter level", ["Product", "Line item"], horizontal=True)
    if level == "Product":
        sc = prod
        hover = "product_name"
    else:
        sc = df.sample(min(len(df), 4000), random_state=1) if len(df) > 4000 else df
        hover = "product_name"
    c1, c2 = st.columns(2)
    xcol, ycol, gcol = ("revenue", "cost", "gross_profit") if level == "Product" else ("sales", "cost", "gross_profit")
    with c1:
        fig = px.scatter(sc, x=xcol, y=ycol, hover_name=hover, color="product_name" if level == "Line item" else None,
                         size="units" if level == "Product" else None, title="Cost vs sales")
        lim = max(sc[xcol].max(), sc[ycol].max()); fig.add_scatter(x=[0, lim], y=[0, lim], mode="lines", name="Cost = Sales", line=dict(dash="dot", color="red"))
        show(fig)
    with c2:
        fig = px.scatter(sc, x=xcol, y=gcol, hover_name=hover, color="product_name" if level == "Line item" else None,
                         size="units" if level == "Product" else None, title="Gross profit vs revenue")
        show(fig)
    if level == "Line item" and len(df) > 4000:
        st.caption("Random sample of 4,000 line items shown for speed.")
    st.subheader("Product margin-risk table")
    st.dataframe(risk[["product_name", "revenue", "gross_profit", "gross_margin_pct", "cost_ratio", "flag_low_margin",
                       "flag_negative_profit", "flag_high_cost_ratio", "risk_flags", "risk_level"]],
                 width="stretch", hide_index=True)
    st.subheader("Negative gross-profit products")
    neg = risk[risk["flag_negative_profit"]]
    if neg.empty:
        st.success("No product has negative gross profit in the selected data.")
    else:
        st.dataframe(neg, width="stretch", hide_index=True)
    st.subheader("High-cost, low-margin products")
    hl = risk[risk["flag_low_margin"] & risk["flag_high_cost_ratio"]]
    if len(hl):
        st.dataframe(hl[["product_name", "revenue", "gross_margin_pct", "cost_ratio", "units"]], width="stretch", hide_index=True)
    else:
        st.info("No product breaches both the margin and cost-ratio thresholds.")
    st.subheader("Division cost efficiency")
    eff = div[["division", "revenue", "cost", "cost_ratio", "profit_per_unit", "gross_margin_pct"]].copy()
    eff["cost_per_unit"] = eff["cost"] / div["units"].replace(0, np.nan)
    st.dataframe(eff, width="stretch", hide_index=True)

# ============================================================================ E. Pareto
with tabs[4]:
    scope_txt = "the **currently filtered** data" if pareto_scope == "Filtered data" else "the **full dataset** (filters ignored)"
    st.info(f"Pareto and concentration below are calculated on {scope_txt}.")
    pprod = summarize(pareto_df, "product_name")
    if pprod.empty:
        st.warning("No data for Pareto analysis.")
    else:
        for label, col in (("Revenue", "revenue"), ("Gross profit", "gross_profit")):
            ptab, stt = pareto(pprod, "product_name", col)
            st.subheader(f"{label} Pareto (by product)")
            if not stt["valid"]:
                st.warning(f"Total positive {label.lower()} is zero - Pareto is not defined.")
                continue
            if stt["negative_values"]:
                st.warning("Some products have negative values; shares use the sum of positive values only (limitation of Pareto with losses).")
            m = st.columns(4)
            m[0].metric("Products for 80%", f"{stt['n_to_cutoff']} of {stt['n_items']}")
            m[1].metric("% of products", f"{stt['pct_items_to_cutoff']:.0f}%")
            m[2].metric("Top product share", fmt_pct(stt["top1_share"]), help=stt.get("top1_name", ""))
            m[3].metric("Top-3 share", fmt_pct(stt["top3_share"]))
            fig = go.Figure()
            fig.add_bar(x=ptab["product_name"], y=ptab["share_pct"], name="Individual %", marker_color="#3b6ea5")
            fig.add_scatter(x=ptab["product_name"], y=ptab["cumulative_pct"], name="Cumulative %", yaxis="y2", mode="lines+markers", line=dict(color="#d1495b"))
            fig.add_hline(y=80, yref="y2", line_dash="dash", line_color="grey", annotation_text="80%")
            fig.update_layout(yaxis=dict(title="Individual %"), yaxis2=dict(overlaying="y", side="right", range=[0, 105], title="Cumulative %"),
                              height=450, legend=dict(orientation="h", y=-0.4), margin=dict(b=120))
            show(fig)
            with st.expander(f"{label} Pareto table"):
                st.dataframe(ptab, width="stretch", hide_index=True)
    st.subheader("Geographic concentration")
    for col, label in (("region", "Region"), ("state", "State / Province")):
        if col in pareto_df.columns:
            t, s = concentration(pareto_df, col)
            if t.empty:
                continue
            st.markdown(f"**{label}** - top location **{s['top1']}** holds {s['top1_rev_share']:.1f}% of revenue; top {s['top_n']} hold "
                        f"{s['top_n_rev_share']:.1f}% of revenue and {s['top_n_profit_share']:.1f}% of profit; HHI = {s['hhi']:.0f} "
                        f"({s['n_locations']} locations).")
            top_t = t.head(15)
            fig = px.bar(top_t, x=col, y=["revenue", "gross_profit"], barmode="group", title=f"Top {len(top_t)} {label.lower()}s: revenue vs profit")
            show(fig)
            with st.expander(f"{label} table"):
                st.dataframe(t, width="stretch", hide_index=True)
    st.caption("HHI: sum of squared revenue shares ×10,000. Roughly <1,500 = diversified, >2,500 = concentrated (US antitrust convention, used here only as a rough guide).")

# ============================================================================ F. Factory
with tabs[5]:
    st.caption("Factory assignment comes from the **supplied product-to-factory mapping** joined on normalised product names. "
               "It is reference data - the dataset itself has no factory field, so this is not proof of actual manufacturing source. "
               "No shipping distances or costs are calculated.")
    fs, pf, unmatched, enriched = factory_analysis(df)
    if fs.empty:
        st.warning("No products in the current selection matched the factory mapping.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            d = fs.melt(id_vars="Factory", value_vars=["revenue", "gross_profit"], var_name="Measure", value_name="$")
            show(px.bar(d, x="Factory", y="$", color="Measure", barmode="group", title="Revenue and gross profit by factory"))
        with c2:
            show(px.bar(fs, x="Factory", y="gross_margin_pct", text=fs["gross_margin_pct"].round(1), title="Gross margin % by factory",
                                   color_discrete_sequence=["#4c9a6a"]))
        fig = px.scatter_geo(fs, lat="Latitude", lon="Longitude", size="revenue", color="gross_margin_pct", hover_name="Factory",
                             hover_data={"revenue": ":,.0f", "gross_profit": ":,.0f", "gross_margin_pct": ":.1f", "Latitude": False, "Longitude": False},
                             scope="north america", color_continuous_scale="RdYlGn", title="Factory locations (bubble = revenue, colour = margin %)")
        fig.update_geos(showcountries=True, showsubunits=True, subunitcolor="lightgrey")
        fig.update_layout(height=520, margin=dict(t=50, b=0))
        show(fig)
        st.dataframe(fs.drop(columns=["Latitude", "Longitude"]), width="stretch", hide_index=True)
        st.subheader("Products by factory")
        st.dataframe(pf, width="stretch", hide_index=True)
    st.subheader("Unmatched product mapping report")
    if unmatched.empty:
        st.success("All products in the selection matched the supplied factory mapping.")
    else:
        st.error(f"{len(unmatched)} product(s) have no factory mapping and are reported as 'Unmapped':")
        st.dataframe(unmatched, width="stretch", hide_index=True)
    present = set(full_df["product_name"].map(lambda x: "".join(ch for ch in x.lower() if ch.isalnum())))
    absent = [p for p in config.PRODUCT_FACTORY_MAP if "".join(ch for ch in p.lower() if ch.isalnum()) not in present]
    st.caption("Mapped products absent from the dataset: " + (", ".join(absent) if absent else "none"))

# ============================================================================ Notes
with tabs[6]:
    st.subheader("Data quality & cleaning log")
    st.caption(f"{clean_info['rows_raw']:,} raw rows · {clean_info['rows_clean']:,} rows after cleaning · "
               "the raw file is never modified.")
    st.dataframe(cleaning_log, width="stretch", hide_index=True)
    st.warning("**Ship Date** values fall years after the order period (see log), so shipping lead-time is NOT analysed.")
    st.markdown("**KPI definitions**: Gross margin = total gross profit ÷ total revenue (weighted). "
                "Profit per unit = gross profit ÷ units. Avg order value uses distinct base orders (Order ID without the product suffix). "
                "Margin volatility = std. dev. of monthly weighted margin (percentage points).")

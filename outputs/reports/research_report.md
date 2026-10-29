# Product Line Profitability & Margin Performance Analysis - Nassau Candy Distributor

*Generated automatically from the analysis results. All figures come from the supplied dataset `Nassau_Candy_Distributor__1_.csv`.*

## 1. Introduction and business problem
Nassau Candy Distributor sells chocolate, sugar and other confectionery through U.S. and Canadian customers. Management needs to know which products and divisions create profit, where margins are weak, how concentrated profit is, and which items need pricing or cost review. This project answers those questions with transparent, rule-based analysis of the transaction data.

## 2. Dataset description
- **File**: `Nassau_Candy_Distributor__1_.csv` (CSV), **10,194 rows x 18 columns**.
- **Columns**: Row ID, Order ID, Order Date, Ship Date, Ship Mode, Customer ID, Country/Region, City, State/Province, Postal Code, Division, Region, Product ID, Product Name, Sales, Units, Gross Profit, Cost.
- **Order period**: 02 Jan 2024 to 31 Dec 2025 (24 months).
- **Entities**: 15 products, 3 divisions (Chocolate, Other, Sugar), 59 states/provinces, 4 regions, 2 countries (Canada, United States), 5,044 customers.
- **Blank cells**: 0. **Non-numeric values in Sales/Units/Gross Profit/Cost**: 0.
- **Order ID structure**: every Order ID ends with its Product ID, so Order ID identifies an order *line*, not a whole order. A derived `base_order_id` (Order ID without the product suffix) gives 5,111 distinct orders and is used for order counts and Average Order Value to avoid double counting.

## 3. Data cleaning methodology
The raw file is never modified; a cleaned copy is saved to `data/processed/`. Every step below is also saved in `outputs/reports/cleaning_log.csv`.


| Step | Finding | Rows | Action |
|---|---|---|---|
| Column mapping | Row ID -> row_id; Order ID -> order_id; Order Date -> order_date; Ship Date -> ship_date; Ship Mode -> ship_mode; Customer ID -> customer_id; Country/Region -> country; City -> city; State/Province -> state; Postal Code -> postal_code; Division -> division; Region -> region; Product ID -> product_id; Product Name -> product_name; Sales -> sales; Units -> units; Gross Profit -> gross_profit; Cost -> cost | 0 | renamed |
| Whitespace trim | Trimmed leading/trailing/double spaces in text columns | 0 | standardised |
| Numeric parse: sales | 0 blank, 0 unparseable/missing after conversion | 0 | none needed |
| Numeric parse: units | 0 blank, 0 unparseable/missing after conversion | 0 | none needed |
| Numeric parse: gross_profit | 0 blank, 0 unparseable/missing after conversion | 0 | none needed |
| Numeric parse: cost | 0 blank, 0 unparseable/missing after conversion | 0 | none needed |
| Date parse: order_date | 0 invalid; range 2024-01-02 to 2025-12-31 | 0 | invalid dates -> NaT (kept, excluded from time charts) |
| Date parse: ship_date | 0 invalid; range 2026-06-30 to 2030-06-28 | 0 | invalid dates -> NaT (kept, excluded from time charts) |
| Ship Date plausibility | Lag Order->Ship: min 904, median 1274, max 1642 days (plausible limit 60). Ship Date values fall after the dataset period, so they cannot be trusted. | 10194 | flagged ship_date_suspect; NO lead-time analysis performed |
| Gross Profit check | |Sales - Cost - Gross Profit| > 0.01: 0 rows | 0 | all consistent |
| Investigation: Negative sales (possible returns) | 0 rows | 0 | none found |
| Investigation: Zero sales | 0 rows | 0 | none found |
| Investigation: Zero/negative units | 0 rows | 0 | none found |
| Investigation: Negative cost | 0 rows | 0 | none found |
| Investigation: Negative gross profit | 0 rows | 0 | none found |
| Investigation: Missing units | 0 rows | 0 | none found |
| Product ID/Name consistency | 0 product names with >1 Product ID | 0 | none |
| Order key derivation | Order ID ends with Product ID in 100.0% of rows, so Order ID is a line key. Derived base_order_id = Order ID without product suffix to avoid double counting orders. | 0 | added base_order_id |
| Duplicates - exact | 313 rows identical to an earlier row in every field except Row ID (revenue 3,499.51, i.e. 2.5% of total). Row ID is unique so no true record duplicates exist. | 313 | flagged `possible_duplicate`, KEPT (cannot prove they are errors) |
| Duplicates - repeated Order ID | Rows that share an Order ID with another row but differ in quantity/amount are treated as separate order lines (plausible split shipments/entries), not duplicates. | 2705 | kept |
| Postal Code | Kept as text (leading zeros / Canadian codes preserved). Some US codes have 4 digits (leading zero lost in source) - not altered. | 0 | kept as text |

**Key decisions**
- **Gross Profit validation**: Gross Profit equals Sales - Cost on every row (tolerance $0.01), so the source Gross Profit column is used directly.
- **No negative or zero values** were found in sales, cost, units or gross profit, so there were no returns or loss transactions to investigate.
- **Possible duplicates**: 313 rows are identical to an earlier row in every field except Row ID. They *could* be genuine repeat purchases, so they are **kept** and flagged. Sensitivity check: excluding them changes revenue from $141,784 to $138,284 and margin from 65.91% to 65.86% - conclusions do not change. The dashboard has a switch to exclude them.
- **Ship Date**: values run Jun 2026 to Jun 2030, i.e. 904 to 1642 days after the order date. This is not plausible, so Ship Date was kept but flagged and **no lead-time analysis was performed**. The year inside Order IDs (2021-2024) also does not match the Order Date year, another sign of inconsistent source fields.

## 4. Exploratory data analysis
- Revenue by year: 2024: $57,956; 2025: $83,827.
- Monthly revenue is uneven. The three strongest months are Dec 2025 ($12,338), Nov 2025 ($11,729), Sep 2025 ($11,458); September, November and December together account for 43.2% of all revenue.
- Average line-item value is $13.91; average units per line item is 3.8.
- Customers: 5,044 distinct customer IDs across 5,111 orders, so most customers appear once.
- Sales to Canada are 2.1% of revenue.
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

Weighted vs simple: the overall **weighted margin is 65.9%**, but the **simple average of the 15 product margins is 57.4%**. The gap exists because small, low-margin products count equally in the simple average but hardly affect the weighted figure.

Overall margin volatility is **0.53 percentage points** (monthly margin ranged 64.5% to 66.7%). Because each product has a single fixed margin (0 of 15 products show any within-product margin variation), month-to-month movement is caused entirely by **product mix**, not by price or cost changes.

## 6. Product profitability findings
**Top 10 by revenue**

| Product | Revenue | Gross profit | Margin | Rev. share |
|---|---|---|---|---|
| Wonka Bar - Triple Dazzle Caramel | $28,485 | $18,610 | 65.3% | 20.1% |
| Wonka Bar -Scrumdiddlyumptious | $27,875 | $19,358 | 69.4% | 19.7% |
| Wonka Bar - Milk Chocolate | $26,868 | $17,443 | 64.9% | 18.9% |
| Wonka Bar - Fudge Mallows | $24,890 | $16,594 | 66.7% | 17.6% |
| Wonka Bar - Nutty Crunch Surprise | $23,575 | $16,820 | 71.3% | 16.6% |
| Lickable Wallpaper | $7,860 | $3,930 | 50.0% | 5.5% |
| Kazookles | $1,206 | $93 | 7.7% | 0.9% |
| Wonka Gum | $598 | $311 | 52.0% | 0.4% |
| Everlasting Gobstopper | $130 | $104 | 80.0% | 0.1% |
| Fizzy Lifting Drinks | $79 | $47 | 60.0% | 0.1% |

**Top products by margin** (minimum $100 revenue and 20 transactions; 7 low-volume products excluded)

| Product | Margin | Revenue | Transactions |
|---|---|---|---|
| Wonka Bar - Nutty Crunch Surprise | 71.3% | $23,575 | 1810 |
| Wonka Bar -Scrumdiddlyumptious | 69.4% | $27,875 | 2064 |
| Wonka Bar - Fudge Mallows | 66.7% | $24,890 | 1818 |
| Wonka Bar - Triple Dazzle Caramel | 65.3% | $28,485 | 2015 |
| Wonka Bar - Milk Chocolate | 64.9% | $26,868 | 2137 |
| Wonka Gum | 52.0% | $598 | 120 |
| Lickable Wallpaper | 50.0% | $7,860 | 94 |
| Kazookles | 7.7% | $1,206 | 96 |

**Bottom 5 by gross profit**

| Product | Gross profit | Revenue | Margin | Transactions |
|---|---|---|---|---|
| Fun Dip | $5 | $12 | 40.0% | 3 |
| Nerds | $7 | $15 | 46.7% | 4 |
| SweeTARTS | $29 | $62 | 46.7% | 10 |
| Laffy Taffy | $33 | $54 | 62.3% | 10 |
| Fizzy Lifting Drinks | $47 | $79 | 60.0% | 6 |

Only 15 products exist, so "Top 10"/"Bottom 10" lists cover most of the range. Fewer than 20 transactions: Everlasting Gobstopper, Fizzy Lifting Drinks, Hair Toffee, SweeTARTS, Laffy Taffy, Nerds, Fun Dip - these margins are descriptive only.

**Profitability classification** (High revenue = product revenue >= $7,089, i.e. 5% of revenue; High margin = margin >= overall weighted margin of 65.9%; both configurable)

| Product | Class | Revenue | Margin | vs overall (pp) |
|---|---|---|---|---|
| Wonka Bar - Triple Dazzle Caramel | High Revenue / Low Margin | $28,485 | 65.3% | -0.6 |
| Wonka Bar -Scrumdiddlyumptious | High Revenue / High Margin | $27,875 | 69.4% | +3.5 |
| Wonka Bar - Milk Chocolate | High Revenue / Low Margin | $26,868 | 64.9% | -1.0 |
| Wonka Bar - Fudge Mallows | High Revenue / High Margin | $24,890 | 66.7% | +0.8 |
| Wonka Bar - Nutty Crunch Surprise | High Revenue / High Margin | $23,575 | 71.3% | +5.4 |
| Lickable Wallpaper | High Revenue / Low Margin | $7,860 | 50.0% | -15.9 |
| Kazookles | Low Revenue / Low Margin | $1,206 | 7.7% | -58.2 |
| Wonka Gum | Low Revenue / Low Margin | $598 | 52.0% | -13.9 |
| Everlasting Gobstopper | Low Revenue / High Margin | $130 | 80.0% | +14.1 |
| Fizzy Lifting Drinks | Low Revenue / Low Margin | $79 | 60.0% | -5.9 |
| Hair Toffee | Low Revenue / High Margin | $76 | 77.8% | +11.9 |
| SweeTARTS | Low Revenue / Low Margin | $62 | 46.7% | -19.2 |
| Laffy Taffy | Low Revenue / Low Margin | $54 | 62.3% | -3.6 |
| Nerds | Low Revenue / Low Margin | $15 | 46.7% | -19.2 |
| Fun Dip | Low Revenue / Low Margin | $12 | 40.0% | -25.9 |

*Caution*: Triple Dazzle Caramel and Milk Chocolate fall in "High Revenue / Low Margin" only because they sit about 0.6-1.0 points below the overall weighted margin; their margins are still above 64%. The classification is a screening tool, not a verdict. No product is loss-making.

## 7. Division performance findings

| Division | Revenue | Cost | Gross profit | Margin | Units | Profit share | Transactions |
|---|---|---|---|---|---|---|---|
| Chocolate | $131,693 | $42,868 | $88,825 | 67.4% | 37,275 | 95.1% | 9844 |
| Other | $9,663 | $5,330 | $4,333 | 44.8% | 1,242 | 4.6% | 310 |
| Sugar | $427 | $143 | $285 | 66.6% | 137 | 0.3% | 40 |

- **Chocolate** performs strongly: highest margin of the three divisions (67.4%), 95.1% of profit, and very stable monthly margin (volatility 0.24 pp).
- **Other** earns a lower margin (44.8%) and needs investigation: its margin swings widely by month (10.2 pp volatility) which reflects the changing monthly mix of Kazookles (very thin margin), Lickable Wallpaper (50%) and Wonka Gum (52%).
- **Sugar** has only 40 transactions (0.30% of revenue); its 66.6% margin and monthly volatility (11.1 pp over 16 active months) rest on too few transactions to be reliable.

## 8. Pareto and concentration findings
- **Revenue**: 5 of 15 products (33%) reach 80% of revenue; leading product Wonka Bar - Triple Dazzle Caramel = 20.1%, top three = 58.7%.
- **Gross profit**: 5 of 15 products (33%) reach 80% of profit; leading product Wonka Bar -Scrumdiddlyumptious = 20.7%, top three = 59.3%.
- The five chocolate bars alone deliver 95.1% of profit, so the business depends heavily on one division.
- **Scope**: these Pareto figures are computed on the full dataset; the dashboard lets you choose filtered or full data.
- **Limitation**: Pareto analysis assumes non-negative contributions. No product here has negative profit, so cumulative shares are well-defined; if negatives appeared, shares would be computed on positive values only and flagged. With only 15 products the "% of products" figure moves in steps of 6.7 points.
- **Geography**: California = 19.7% of revenue; top 5 of 59 states/provinces = 50.7% revenue and 50.7% profit (HHI 762; below the rough 1,500 guide, so not highly concentrated by state). Regions: Pacific 32.7%, Atlantic 29.1%, Interior 22.6%, Gulf 15.7%.

| State | Revenue | Gross profit | Rev. share |
|---|---|---|---|
| California | $27,917 | $18,479 | 19.7% |
| New York | $15,541 | $10,222 | 11.0% |
| Texas | $13,416 | $8,910 | 9.5% |
| Pennsylvania | $8,027 | $5,225 | 5.7% |
| Washington | $6,921 | $4,567 | 4.9% |

## 9. Cost and margin risk findings
Rule-based screening (55% margin threshold; cost ratio > 0.60; negative profit). Note: cost ratio = 1 - margin, so these two rules express the same information; the cost-ratio rule is set stricter to act as a severity tier.

| Product | Revenue | Margin | Cost ratio | Flags | Level |
|---|---|---|---|---|---|
| Kazookles | $1,206 | 7.7% | 0.92 | 2 | High |
| Lickable Wallpaper | $7,860 | 50.0% | 0.50 | 1 | Watch |
| Wonka Gum | $598 | 52.0% | 0.48 | 1 | Watch |
| SweeTARTS | $62 | 46.7% | 0.53 | 1 | Watch |
| Nerds | $15 | 46.7% | 0.53 | 1 | Watch |
| Fun Dip | $12 | 40.0% | 0.60 | 1 | Watch |

- **Negative gross profit**: 0 products.
- **Kazookles**: $1,206 revenue, $1,113 cost, margin 7.7%, profit per unit $0.25. Its listed unit price ($3.25) and unit cost ($3.00) leave very little room. This is a *candidate for review* - the cause could be pricing, supplier cost, or a data-entry issue, which this dataset cannot determine.
- **Lickable Wallpaper**: $7,860 revenue (the largest non-chocolate product) at a 50.0% margin; it contributes 4.2% of profit.
- Repricing, supplier negotiation or discontinuation are **recommendations requiring validation** (competitor pricing, contract terms, strategic role, demand elasticity), not conclusions from these figures.

## 10. Factory analysis
Factories come from the **supplied product-to-factory mapping** joined on normalised product names (reference data only, not proof of manufacturing source). All 15 products matched; unmatched products: **0**. Mapped products absent from the data: **0**.

| Factory | Products | Revenue | Gross profit | Margin | Profit share |
|---|---|---|---|---|---|
| Lot's O' Nuts | 3 | $76,340 | $52,771 | 69.1% | 56.5% |
| Wicked Choccy's | 2 | $55,353 | $36,054 | 65.1% | 38.6% |
| Secret Factory | 3 | $8,588 | $4,345 | 50.6% | 4.6% |
| The Other Factory | 2 | $1,282 | $152 | 11.9% | 0.2% |
| Sugar Shack | 5 | $221 | $121 | 54.9% | 0.1% |

- The two chocolate factories (Lot's O' Nuts and Wicked Choccy's) account for 95.1% of gross profit.
- The Other Factory has the weakest margin (11.9%) because it is mapped to Kazookles and Hair Toffee.
- The mapping lists Fizzy Lifting Drinks under "Other", whereas the dataset places it in the Sugar division; the dataset's division was used for division analysis.
- No shipping distance, cost or route analysis was done: the dataset lacks usable shipping cost fields and its Ship Date is unreliable.

## 11. Evidence-based recommendations
1. **Validate Kazookles cost and price** with finance/procurement; consider repricing or supplier negotiation if the cost figure is confirmed.
2. **Review pricing of lower-margin items** (Lickable Wallpaper, Wonka Gum, SweeTARTS, Nerds, Fun Dip) - small volumes, so run controlled tests.
3. **Reduce single-division dependence**: Chocolate drives 95.1% of profit; consider whether growing high-margin Everlasting Gobstopper or Hair Toffee is viable (their volumes are tiny, so evidence is limited).
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
Nassau Candy's profitability rests on five chocolate products that produce about 95% of gross profit at healthy margins. No product loses money, but a handful of small non-chocolate items - above all Kazookles - earn thin margins and warrant pricing and cost review. Data-quality issues (Ship Date, possible duplicates) should be resolved before drawing operational conclusions beyond profitability.

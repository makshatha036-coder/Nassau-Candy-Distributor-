# Executive Summary - Nassau Candy Distributor Product Line Profitability

*Prepared from the supplied transaction file (10,194 rows, orders dated 02 Jan 2024 to 31 Dec 2025). This is an independent analytical summary; it has no official or governmental endorsement.*

## Headline results
- **Revenue $141,784**, cost $48,341, **gross profit $93,443**, weighted gross margin **65.9%** on 38,654 units and 5,111 distinct orders.
- **Profit is concentrated in a few products.** 5 of 15 products (33%) generate 80% of gross profit; all of them are Chocolate-division Wonka Bars. The top three products supply 59.3% of profit.
- **Chocolate is the core division**: 92.9% of revenue and 95.1% of gross profit at a 67.4% margin. "Other" earns 44.8% and Sugar has only 40 transactions (0.3% of revenue).
- **Margin risk is concentrated in a small number of non-chocolate items.** Using a 55% margin screen, 6 of 15 products are flagged; the most notable is **Kazookles** (margin 7.7% on $1,206 revenue, 96 transactions). **No product has negative gross profit.**
- **Geography**: California alone is 19.7% of revenue; the top five states hold 50.7%. Regional revenue shares range from 16% to 33%.

## Recommended actions (each needs validation before decisions)
1. **Review Kazookles pricing/cost first** - the unit price and unit cost are close together (see report section 9). Confirm whether the cost figure is correct, then consider repricing or supplier negotiation.
2. **Protect the five core chocolate bars** - they are the profit engine; any supply or price disruption affects most profit.
3. **Review low-margin small items** (Lickable Wallpaper, Wonka Gum, SweeTARTS, Nerds, Fun Dip) for pricing; volumes are small so test before acting.
4. **Sugar-division conclusions are not yet reliable** - only 40 transactions; gather more data before ranking it.
5. **Fix data issues**: Ship Date values fall 904-1642 days after the order date (impossible), so delivery performance could not be analysed; 313 possible duplicate rows should be confirmed with the data owner.

## Main caveats
- Each product has one fixed margin in this file, so product margins do not vary by transaction; differences between products reflect price/cost structure, not discounting or cost drift.
- Factory results use the supplied product-to-factory mapping and are reference-only.

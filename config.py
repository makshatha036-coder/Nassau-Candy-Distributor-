"""Central configuration. Edit values here - nothing else needs to change."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ---- Input file (CSV or Excel). Change this one line to use another file. ----
RAW_DATA_FILE = BASE_DIR / "data" / "raw" / "Nassau_Candy_Distributor__1_.csv"
EXCEL_SHEET = 0  # only used when RAW_DATA_FILE is .xlsx/.xls

PROCESSED_DIR = BASE_DIR / "data" / "processed"
CLEAN_DATA_FILE = PROCESSED_DIR / "nassau_candy_clean.csv"
CHARTS_DIR = BASE_DIR / "outputs" / "charts"
REPORTS_DIR = BASE_DIR / "outputs" / "reports"

# ---- Date handling ----
DATE_DAYFIRST = True            # dataset uses DD-MM-YYYY
# Ship Date is flagged as suspect when the gap to Order Date exceeds this many days
MAX_PLAUSIBLE_SHIP_LAG_DAYS = 60

# ---- Duplicate handling ----
# Rows identical in EVERY field except Row ID are flagged as "possible duplicates".
# They are KEPT by default because the file cannot prove they are errors
# (a customer can legitimately buy the same quantity twice on one day).
# Set True to exclude them from analysis (a sensitivity check is reported either way).
DROP_EXACT_DUPLICATES = False

# ---- Analysis thresholds (also adjustable in the dashboard sidebar) ----
LOW_MARGIN_THRESHOLD = 55.0       # gross margin % below this = "Low margin"
# NOTE: cost_ratio = 1 - margin when Gross Profit = Sales - Cost, so this rule is the same information as
# the margin rule viewed from the cost side. It is set stricter (0.60 = margin < 40%) to act as a severity tier.
HIGH_COST_RATIO_THRESHOLD = 0.60  # cost / sales above this = "High cost ratio"
# High vs Low revenue cut-off: "share:5" = product must hold >=5% of total revenue (default),
# "median", "mean", or a dollar number. (The median is a poor cut-off here: revenue is very skewed.)
REVENUE_SPLIT = "share:5"
MARGIN_SPLIT = "weighted"         # "weighted" (overall weighted margin), "median" or a number
MIN_REVENUE_FOR_MARGIN_RANK = 100.0   # minimum revenue to enter "top products by margin"
MIN_ROWS_FOR_MARGIN_RANK = 20         # minimum transaction rows for margin ranking
PARETO_CUTOFF = 0.80

# ---- Factory reference data (supplementary only) ----
FACTORY_COORDS = {
    "Lot's O' Nuts": (32.881893, -111.768036),
    "Wicked Choccy's": (32.076176, -81.088371),
    "Sugar Shack": (48.11914, -96.18115),
    "Secret Factory": (41.446333, -90.565487),
    "The Other Factory": (35.1175, -89.971107),
}

PRODUCT_FACTORY_MAP = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows": "Lot's O' Nuts",
    "Wonka Bar -Scrumdiddlyumptious": "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate": "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy": "Sugar Shack",
    "SweeTARTS": "Sugar Shack",
    "Nerds": "Sugar Shack",
    "Fun Dip": "Sugar Shack",
    "Everlasting Gobstopper": "Secret Factory",
    "Hair Toffee": "The Other Factory",
    "Fizzy Lifting Drinks": "Sugar Shack",
    "Lickable Wallpaper": "Secret Factory",
    "Wonka Gum": "Secret Factory",
    "Kazookles": "The Other Factory",
}

# ---- Column aliases: canonical name -> accepted variants (case/space-insensitive) ----
COLUMN_ALIASES = {
    "row_id": ["row id", "rowid", "id"],
    "order_id": ["order id", "orderid", "order number"],
    "order_date": ["order date", "orderdate", "date"],
    "ship_date": ["ship date", "shipdate", "shipping date"],
    "ship_mode": ["ship mode", "shipmode"],
    "customer_id": ["customer id", "customerid", "customer"],
    "country": ["country/region", "country"],
    "city": ["city"],
    "state": ["state/province", "state", "province"],
    "postal_code": ["postal code", "zip", "zip code", "postcode"],
    "division": ["division", "category", "product division"],
    "region": ["region", "sales region"],
    "product_id": ["product id", "productid", "sku"],
    "product_name": ["product name", "product", "productname", "item"],
    "sales": ["sales", "revenue", "sales amount"],
    "units": ["units", "quantity", "qty"],
    "gross_profit": ["gross profit", "profit", "grossprofit"],
    "cost": ["cost", "total cost", "cogs"],
}
REQUIRED_COLUMNS = ["order_date", "division", "product_name", "sales", "units", "gross_profit", "cost"]

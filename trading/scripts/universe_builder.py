"""
Universe Builder — comprehensive tradeable stock/ETF universe for screening.

Provides ~1,500 liquid US equities and ETFs covering:
- S&P 500 constituents
- Nasdaq-100 constituents
- S&P MidCap 400 (top ~200 by liquidity)
- Major sector, commodity, international, and thematic ETFs

Two operating modes:
1. Static: Use the embedded curated list (no network required)
2. Dynamic: Optionally refresh S&P 500 from Wikipedia or IBKR scanner

Liquidity pre-filter is applied *after* data fetch, in the screener itself.
This module only provides the candidate symbols to scan.
"""

import logging
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Curated universe — comprehensive US equities + ETFs
# ---------------------------------------------------------------------------

# S&P 500 (as of early 2026, ~500 symbols)
_SP500 = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "ADI", "ADM", "ADP", "ADSK", "AEE",
    "AEP", "AES", "AFL", "AIG", "AIZ", "AJG", "AKAM", "ALB", "ALGN", "ALK",
    "ALL", "ALLE", "AMAT", "AMCR", "AMD", "AME", "AMGN", "AMP", "AMT", "AMZN",
    "ANET", "ANSS", "AON", "AOS", "APA", "APD", "APH", "APTV", "ARE", "ATO",
    "ATVI", "AVB", "AVGO", "AVY", "AWK", "AXP", "AZO", "BA", "BAC", "BAX",
    "BBWI", "BBY", "BDX", "BEN", "BF.B", "BIO", "BIIB", "BK", "BKNG", "BKR",
    "BLK", "BMY", "BR", "BRK.B", "BRO", "BSX", "BWA", "BXP", "C", "CAG",
    "CAH", "CARR", "CAT", "CB", "CBOE", "CBRE", "CCI", "CCL", "CDAY", "CDNS",
    "CDW", "CE", "CEG", "CF", "CFG", "CHD", "CHRW", "CHTR", "CI", "CINF",
    "CL", "CLX", "CMA", "CMCSA", "CME", "CMG", "CMI", "CMS", "CNC", "CNP",
    "COF", "COO", "COP", "COST", "CPB", "CPRT", "CPT", "CRL", "CRM", "CSCO",
    "CSGP", "CSX", "CTAS", "CTLT", "CTRA", "CTSH", "CTVA", "CVS", "CVX", "CZR",
    "D", "DAL", "DD", "DE", "DFS", "DG", "DGX", "DHI", "DHR", "DIS",
    "DISH", "DLR", "DLTR", "DOV", "DOW", "DPZ", "DRI", "DTE", "DUK", "DVA",
    "DVN", "DXC", "DXCM", "EA", "EBAY", "ECL", "ED", "EFX", "EIX", "EL",
    "EMN", "EMR", "ENPH", "EOG", "EPAM", "EQIX", "EQR", "EQT", "ES", "ESS",
    "ETN", "ETR", "ETSY", "EVRG", "EW", "EXC", "EXPD", "EXPE", "EXR", "F",
    "FANG", "FAST", "FBHS", "FCX", "FDS", "FDX", "FE", "FFIV", "FIS", "FISV",
    "FITB", "FLT", "FMC", "FOX", "FOXA", "FRC", "FRT", "FTNT", "FTV", "GD",
    "GE", "GEHC", "GEN", "GILD", "GIS", "GL", "GLW", "GM", "GNRC", "GOOG",
    "GOOGL", "GPC", "GPN", "GRMN", "GS", "GWW", "HAL", "HAS", "HBAN", "HCA",
    "HD", "HOLX", "HON", "HPE", "HPQ", "HRL", "HSIC", "HST", "HSY", "HUM",
    "HWM", "IBM", "ICE", "IDXX", "IEX", "IFF", "ILMN", "INCY", "INTC", "INTU",
    "INVH", "IP", "IPG", "IQV", "IR", "IRM", "ISRG", "IT", "ITW", "IVZ",
    "J", "JBHT", "JCI", "JKHY", "JNJ", "JNPR", "JPM", "K", "KDP", "KEY",
    "KEYS", "KHC", "KIM", "KLAC", "KMB", "KMI", "KMX", "KO", "KR", "L",
    "LDOS", "LEN", "LH", "LHX", "LIN", "LKQ", "LLY", "LMT", "LNC", "LNT",
    "LOW", "LRCX", "LUMN", "LUV", "LVS", "LW", "LYB", "LYV", "MA", "MAA",
    "MAR", "MAS", "MCD", "MCHP", "MCK", "MCO", "MDLZ", "MDT", "MET", "META",
    "MGM", "MHK", "MKC", "MKTX", "MLM", "MMC", "MMM", "MNST", "MO", "MOH",
    "MOS", "MPC", "MPWR", "MRK", "MRNA", "MRO", "MS", "MSCI", "MSFT", "MSI",
    "MTB", "MTCH", "MTD", "MU", "NCLH", "NDAQ", "NDSN", "NEE", "NEM", "NFLX",
    "NI", "NKE", "NOC", "NOW", "NRG", "NSC", "NTAP", "NTRS", "NUE", "NVDA",
    "NVR", "NWL", "NWS", "NWSA", "NXPI", "O", "ODFL", "OGN", "OKE", "OMC",
    "ON", "ORCL", "ORLY", "OTIS", "OXY", "PARA", "PAYC", "PAYX", "PCAR", "PCG",
    "PEAK", "PEG", "PEP", "PFE", "PFG", "PG", "PGR", "PH", "PHM", "PKG",
    "PKI", "PLD", "PM", "PNC", "PNR", "PNW", "POOL", "PPG", "PPL", "PRU",
    "PSA", "PSX", "PTC", "PVH", "PWR", "PXD", "PYPL", "QCOM", "QRVO", "RCL",
    "RE", "REG", "REGN", "RF", "RHI", "RJF", "RL", "RMD", "ROK", "ROL",
    "ROP", "ROST", "RSG", "RTX", "RVTY", "SBAC", "SBNY", "SBUX", "SCHW", "SEE",
    "SHW", "SIVB", "SJM", "SLB", "SNA", "SNPS", "SO", "SPG", "SPGI", "SRE",
    "STE", "STT", "STX", "STZ", "SWK", "SWKS", "SYF", "SYK", "SYY", "T",
    "TAP", "TDG", "TDY", "TECH", "TEL", "TER", "TFC", "TFX", "TGT", "TMO",
    "TMUS", "TPR", "TRGP", "TRMB", "TROW", "TRV", "TSCO", "TSLA", "TSN", "TT",
    "TTWO", "TXN", "TXT", "TYL", "UAL", "UDR", "UHS", "ULTA", "UNH", "UNP",
    "UPS", "URI", "USB", "V", "VFC", "VICI", "VLO", "VMC", "VRSK", "VRSN",
    "VRTX", "VTR", "VTRS", "VZ", "WAB", "WAT", "WBA", "WBD", "WDC", "WEC",
    "WELL", "WFC", "WHR", "WM", "WMB", "WMT", "WRB", "WRK", "WST", "WTW",
    "WY", "WYNN", "XEL", "XOM", "XRAY", "XYL", "YUM", "ZBH", "ZBRA", "ZION", "ZTS",
]

# Nasdaq-100 additions (not already in S&P 500)
_NDX_EXTRA = [
    "ABNB", "AZN", "BIDU", "BMRN", "CCEP", "CSGP", "CPRT", "CRWD", "DDOG",
    "DLTR", "DXCM", "EA", "ENPH", "FANG", "FAST", "FTNT", "GEHC", "GFS",
    "IDXX", "ILMN", "JD", "KDP", "KHC", "LCID", "LULU", "MELI", "MNST",
    "MRNA", "MRVL", "NXPI", "ODFL", "ON", "PANW", "PAYX", "PDD", "PYPL",
    "RIVN", "ROST", "SIRI", "SNPS", "SPLK", "TEAM", "TMUS", "VRSK", "WDAY",
    "ZM", "ZS",
]

# S&P MidCap 400 — top ~200 most liquid names
_MIDCAP = [
    "ACGL", "ACM", "AGCO", "AIT", "ALLY", "AMH", "AMKR", "AN", "AR", "ARMK",
    "ATI", "AXON", "AYI", "AZEK", "BERY", "BJ", "BKH", "BOOT", "BRKR", "BRX",
    "BWA", "CALM", "CASY", "CATY", "CBT", "CC", "CENTA", "CHE", "CHRD", "CLF",
    "CMC", "CNA", "CNM", "COKE", "CRC", "CRI", "CRS", "CW", "DECK", "DKS",
    "DOCS", "DORM", "EAT", "EBC", "EGP", "ELAN", "ENIC", "ENSG", "EPAC",
    "ESI", "EXP", "FBIN", "FHN", "FIX", "FLO", "FNB", "FND", "FNF", "FRPT",
    "G", "GEF", "GGG", "GLOB", "GNTX", "GPOR", "GXO", "H", "HALO", "HBI",
    "HGV", "HLI", "HQY", "HUBG", "IAC", "IBKR", "IBP", "ICLR", "IDA", "INGR",
    "INSM", "IOSP", "ITCI", "ITT", "JBGS", "JBL", "JEF", "KMPR", "KNX", "KNTK",
    "LANC", "LBRT", "LEA", "LFUS", "LKFN", "LNTH", "LSTR", "MANH", "MASI",
    "MAT", "MEDP", "MGEE", "MIDD", "MKSI", "MLI", "MOD", "MPWR", "MTG",
    "MTDR", "MUSA", "NBIX", "NFG", "NMIH", "NOV", "NVT", "OC", "OGE", "OLN",
    "OMF", "ORI", "OZKB", "PACS", "PCTY", "PEN", "PFGC", "PII", "PLNT",
    "POST", "POWI", "PR", "PRI", "PRMW", "PRGO", "PSN", "PVH", "R", "RBC",
    "RGA", "RGLD", "RHI", "RIG", "RLI", "RPM", "RPRX", "RUSHA", "SAM",
    "SAIC", "SCI", "SEIC", "SF", "SFM", "SITE", "SKX", "SM", "SMTC", "SN",
    "SNX", "SON", "SPB", "SSD", "ST", "STAG", "SWX", "SXT", "THC", "THG",
    "THO", "TKR", "TMHC", "TNC", "TNET", "TOL", "TPX", "TTC", "TXRH",
    "UFPI", "UMBF", "UNM", "USFD", "VCTR", "VIRT", "VNT", "VSH", "WERN",
    "WEX", "WH", "WLK", "WOLF", "WPC", "WPM", "WSC", "WSM", "WTS", "X",
    "XNCR", "YETI",
]

# Major ETFs — sector, commodity, international, bond, thematic
_ETFS = [
    # Broad market
    "SPY", "QQQ", "IWM", "IWF", "IWD", "DIA", "VOO", "VTI", "RSP",
    # Sector
    "XLK", "XLF", "XLE", "XLV", "XLI", "XLC", "XLY", "XLP", "XLB", "XLU", "XLRE",
    "SMH", "XBI", "XHB", "XRT", "KRE", "KBE", "OIH", "GDX", "GDXJ", "XME",
    "ITB", "IBB", "IYR", "VNQ", "ARKK", "ARKF", "ARKG", "IGV", "SOXX", "HACK",
    "CIBR", "TAN", "ICLN", "LIT", "REMX", "JETS", "PBW", "KWEB",
    # International
    "EEM", "EFA", "VWO", "IEMG", "FXI", "MCHI", "INDA", "EWZ", "EWJ", "EWG",
    "EWU", "EWY", "EWT", "EWH", "EWS", "EWA", "EWC", "EWW", "RSX", "ECH",
    "THD", "EIDO", "EPHE", "VNM", "GREK", "TUR", "CQQQ", "GXC", "YINN",
    # Commodity
    "GLD", "SLV", "USO", "UNG", "DBA", "DBC", "PDBC", "CORN", "WEAT",
    # Bonds / rates
    "TLT", "IEF", "SHY", "HYG", "LQD", "AGG", "BND", "BNDX", "EMB", "JNK",
    # Volatility
    "VXX", "VIXY", "SVXY", "UVXY",
    # Leveraged (popular for short-term)
    "TQQQ", "SQQQ", "SPXL", "SPXS", "SOXL", "SOXS", "LABU", "LABD",
    "FNGU", "FNGD", "TNA", "TZA", "FAS", "FAZ", "ERX", "ERY",
]

# Additional popular large-cap not in indices above
_EXTRA_LARGE_CAP = [
    "AFRM", "AI", "BILL", "COIN", "DKNG", "DUOL", "GRAB", "HOOD",
    "HUBS", "IOT", "LYFT", "MARA", "NET", "OKTA", "PATH", "PINS",
    "PLTR", "RBLX", "RIOT", "ROKU", "SE", "SHOP", "SNAP", "SNOW",
    "SQ", "TWLO", "U", "UBER", "UPST",
]


def _deduplicate(symbols: List[str]) -> List[str]:
    """Remove duplicates preserving order, uppercase, strip whitespace."""
    seen: Set[str] = set()
    out: List[str] = []
    for s in symbols:
        if not isinstance(s, str):
            continue
        s = s.strip().upper()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def get_full_universe() -> List[str]:
    """Return the complete deduplicated universe of ~1,500 tradeable symbols.

    Combines S&P 500, Nasdaq-100, MidCap 400 (top 200), major ETFs,
    and extra popular large-caps.
    """
    all_symbols = _SP500 + _NDX_EXTRA + _MIDCAP + _ETFS + _EXTRA_LARGE_CAP
    universe = _deduplicate(all_symbols)
    logger.info("Full universe: %d symbols", len(universe))
    return universe


def get_equity_universe() -> List[str]:
    """Stocks only (no ETFs). For use in short/long equity screening."""
    all_stocks = _SP500 + _NDX_EXTRA + _MIDCAP + _EXTRA_LARGE_CAP
    return _deduplicate(all_stocks)


def get_etf_universe() -> List[str]:
    """ETFs only."""
    return _deduplicate(_ETFS)


def load_universe_from_csv(csv_path: Path) -> List[str]:
    """Load symbols from a CSV file with a 'symbol' column.

    Falls back to the first column if 'symbol' is not found.
    Returns empty list on error.
    """
    try:
        df = pd.read_csv(csv_path)
        if "symbol" in df.columns:
            symbols = df["symbol"].dropna().astype(str).tolist()
        elif "Symbol" in df.columns:
            symbols = df["Symbol"].dropna().astype(str).tolist()
        elif "ticker" in df.columns:
            symbols = df["ticker"].dropna().astype(str).tolist()
        else:
            symbols = df.iloc[:, 0].dropna().astype(str).tolist()
        out = _deduplicate(symbols)
        logger.info("Loaded %d symbols from %s", len(out), csv_path)
        return out
    except Exception as e:
        logger.warning("Could not load CSV universe from %s: %s", csv_path, e)
        return []


def try_fetch_sp500_from_wikipedia() -> List[str]:
    """Attempt to fetch current S&P 500 constituents from Wikipedia.

    Returns empty list on failure (network/parsing issues).
    """
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        if tables:
            df = tables[0]
            col = "Symbol" if "Symbol" in df.columns else df.columns[0]
            symbols = df[col].dropna().astype(str).str.replace(".", "-", regex=False).tolist()
            out = _deduplicate(symbols)
            logger.info("Fetched %d S&P 500 symbols from Wikipedia", len(out))
            return out
    except Exception as e:
        logger.debug("Wikipedia S&P 500 fetch failed: %s", e)
    return []


def build_universe(
    csv_path: Optional[Path] = None,
    include_etfs: bool = True,
    refresh_sp500: bool = False,
) -> List[str]:
    """Build the screening universe from all available sources.

    Priority:
    1. CSV file (if provided and exists)
    2. Wikipedia S&P 500 refresh (if requested, merged with static lists)
    3. Static curated lists (always used as the base)

    ETFs are included by default; set include_etfs=False for equity-only screening.
    """
    base = get_equity_universe()

    if csv_path and csv_path.exists():
        csv_symbols = load_universe_from_csv(csv_path)
        if csv_symbols:
            base = _deduplicate(base + csv_symbols)

    if refresh_sp500:
        wiki = try_fetch_sp500_from_wikipedia()
        if wiki:
            base = _deduplicate(base + wiki)

    if include_etfs:
        base = _deduplicate(base + get_etf_universe())

    logger.info("Final universe: %d symbols (etfs=%s)", len(base), include_etfs)
    return base

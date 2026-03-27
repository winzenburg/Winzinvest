#!/usr/bin/env python3
"""
Shared sector map and sector-concentration gate for executors.

Used by execute_candidates.py (short-only) and execute_dual_mode.py (mixed).
Sector classification follows GICS for equities; ETFs get their own category.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:
    from broker_protocols import BrokerClient

_logger = logging.getLogger(__name__)

_DYNAMIC_CACHE_PATH = Path(__file__).resolve().parents[1] / "logs" / "sector_cache.json"

# Comprehensive GICS-aligned sector map for the full universe (~500+ equities + ETFs)
SECTOR_MAP: Dict[str, str] = {
    # ── Technology ─────────────────────────────────────────────────
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology", "GOOG": "Technology",
    "NVDA": "Technology", "META": "Technology", "AMZN": "Technology", "TSLA": "Technology",
    "AMD": "Technology", "INTC": "Technology", "CRM": "Technology", "ORCL": "Technology",
    "ADBE": "Technology", "CSCO": "Technology", "AVGO": "Technology", "QCOM": "Technology",
    "TXN": "Technology", "IBM": "Technology", "NOW": "Technology", "AMAT": "Technology",
    "MU": "Technology", "LRCX": "Technology", "INTU": "Technology", "PANW": "Technology",
    "NFLX": "Technology", "ASML": "Technology", "SNPS": "Technology", "CDNS": "Technology",
    "MCHP": "Technology", "KLA": "Technology", "KLAC": "Technology", "NXPI": "Technology",
    "MRVL": "Technology", "ON": "Technology", "SWKS": "Technology", "QRVO": "Technology",
    "ADI": "Technology", "MPWR": "Technology", "FTNT": "Technology", "CRWD": "Technology",
    "DDOG": "Technology", "NET": "Technology", "OKTA": "Technology", "ZS": "Technology",
    "SNOW": "Technology", "SHOP": "Technology", "COIN": "Technology", "UPST": "Technology",
    "AFRM": "Technology", "MSI": "Technology", "KEYS": "Technology", "TER": "Technology",
    "ANSS": "Technology", "PTC": "Technology", "ADSK": "Technology", "EPAM": "Technology",
    "IT": "Technology", "LDOS": "Technology", "AKAM": "Technology", "FFIV": "Technology",
    "JNPR": "Technology", "CDW": "Technology", "JKHY": "Technology", "CTSH": "Technology",
    "ACN": "Technology", "GEN": "Technology", "CSGP": "Technology", "CPRT": "Technology",
    "BR": "Technology", "DXC": "Technology", "HPQ": "Technology", "HPE": "Technology",
    "NTAP": "Technology", "STX": "Technology", "WDC": "Technology", "ZBRA": "Technology",
    "TYL": "Technology", "AI": "Technology", "PLTR": "Technology", "RBLX": "Technology",
    "U": "Technology", "SNAP": "Technology", "PINS": "Technology", "TWLO": "Technology",
    "BILL": "Technology", "HUBS": "Technology", "IOT": "Technology", "DUOL": "Technology",
    "HOOD": "Technology", "PATH": "Technology", "ROKU": "Technology", "WDAY": "Technology",
    "TEAM": "Technology", "ZM": "Technology", "AMKR": "Technology", "MKSI": "Technology",
    "SMTC": "Technology", "GFS": "Technology", "MANH": "Technology",
    # ── Energy ─────────────────────────────────────────────────────
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "EOG": "Energy",
    "PXD": "Energy", "MPC": "Energy", "PSX": "Energy", "VLO": "Energy", "OXY": "Energy",
    "HAL": "Energy", "BKR": "Energy", "DVN": "Energy", "FANG": "Energy", "CTRA": "Energy",
    "MRO": "Energy", "APA": "Energy", "HES": "Energy", "OKE": "Energy", "WMB": "Energy",
    "KMI": "Energy", "TRGP": "Energy", "EQT": "Energy", "RIG": "Energy", "NOV": "Energy",
    "AR": "Energy", "SM": "Energy", "MTDR": "Energy", "LBRT": "Energy", "CHRD": "Energy",
    "CRC": "Energy", "GPOR": "Energy", "PR": "Energy",
    # ── Financials ─────────────────────────────────────────────────
    "JPM": "Financials", "GS": "Financials", "BAC": "Financials", "WFC": "Financials",
    "MS": "Financials", "C": "Financials", "BLK": "Financials", "SCHW": "Financials",
    "AXP": "Financials", "USB": "Financials", "PNC": "Financials", "TFC": "Financials",
    "BK": "Financials", "COF": "Financials", "STT": "Financials", "NTRS": "Financials",
    "FITB": "Financials", "KEY": "Financials", "CFG": "Financials", "RF": "Financials",
    "HBAN": "Financials", "CMA": "Financials", "ZION": "Financials", "MTB": "Financials",
    "CBOE": "Financials", "ICE": "Financials", "CME": "Financials", "NDAQ": "Financials",
    "SPGI": "Financials", "MCO": "Financials", "MSCI": "Financials", "FDS": "Financials",
    "MKTX": "Financials", "RJF": "Financials", "AMP": "Financials", "BEN": "Financials",
    "IVZ": "Financials", "TROW": "Financials", "DFS": "Financials", "SYF": "Financials",
    "AIG": "Financials", "ALL": "Financials", "PGR": "Financials", "TRV": "Financials",
    "CB": "Financials", "MMC": "Financials", "AON": "Financials", "CINF": "Financials",
    "GL": "Financials", "AFL": "Financials", "MET": "Financials", "PRU": "Financials",
    "LNC": "Financials", "L": "Financials", "AIZ": "Financials", "RE": "Financials",
    "WRB": "Financials", "BRO": "Financials", "AJG": "Financials", "FRC": "Financials",
    "SIVB": "Financials", "FNB": "Financials", "FNF": "Financials", "ALLY": "Financials",
    "IBKR": "Financials", "SF": "Financials", "SEIC": "Financials", "JEF": "Financials",
    "ACGL": "Financials", "RGA": "Financials", "FHN": "Financials", "OMF": "Financials",
    "VIRT": "Financials", "SQ": "Technology", "PYPL": "Technology",
    # ── Healthcare ─────────────────────────────────────────────────
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare", "TMO": "Healthcare", "ABT": "Healthcare",
    "DHR": "Healthcare", "BMY": "Healthcare", "AMGN": "Healthcare", "GILD": "Healthcare",
    "ISRG": "Healthcare", "VRTX": "Healthcare", "REGN": "Healthcare", "MDT": "Healthcare",
    "BDX": "Healthcare", "SYK": "Healthcare", "BSX": "Healthcare", "EW": "Healthcare",
    "ZBH": "Healthcare", "IDXX": "Healthcare", "IQV": "Healthcare", "CI": "Healthcare",
    "HUM": "Healthcare", "CNC": "Healthcare", "MOH": "Healthcare", "HCA": "Healthcare",
    "DVA": "Healthcare", "UHS": "Healthcare", "BAX": "Healthcare", "HOLX": "Healthcare", "CAH": "Healthcare",
    "DXCM": "Healthcare", "ILMN": "Healthcare", "BIIB": "Healthcare", "MRNA": "Healthcare",
    "INCY": "Healthcare", "BIO": "Healthcare", "CRL": "Healthcare", "DGX": "Healthcare",
    "LH": "Healthcare", "STE": "Healthcare", "RMD": "Healthcare", "ENPH": "Healthcare",
    "ALGN": "Healthcare", "COO": "Healthcare", "HSIC": "Healthcare", "TFX": "Healthcare",
    "PKI": "Healthcare", "CTLT": "Healthcare", "OGN": "Healthcare", "VTRS": "Healthcare",
    "BMRN": "Healthcare", "NBIX": "Healthcare", "INSM": "Healthcare", "MEDP": "Healthcare",
    "HALO": "Healthcare", "ICLR": "Healthcare", "LNTH": "Healthcare",
    # ── Consumer Discretionary ─────────────────────────────────────
    "HD": "Consumer Discretionary", "LOW": "Consumer Discretionary",
    "NKE": "Consumer Discretionary", "SBUX": "Consumer Discretionary",
    "TGT": "Consumer Discretionary", "ROST": "Consumer Discretionary",
    "TJX": "Consumer Discretionary", "BKNG": "Consumer Discretionary",
    "MAR": "Consumer Discretionary", "HLT": "Consumer Discretionary",
    "CCL": "Consumer Discretionary", "RCL": "Consumer Discretionary",
    "NCLH": "Consumer Discretionary", "DPZ": "Consumer Discretionary",
    "CMG": "Consumer Discretionary", "DRI": "Consumer Discretionary",
    "YUM": "Consumer Discretionary", "MCD": "Consumer Discretionary",
    "APTV": "Consumer Discretionary", "GM": "Consumer Discretionary",
    "F": "Consumer Discretionary", "BWA": "Consumer Discretionary",
    "LEA": "Consumer Discretionary", "DHI": "Consumer Discretionary",
    "LEN": "Consumer Discretionary", "NVR": "Consumer Discretionary",
    "PHM": "Consumer Discretionary", "TOL": "Consumer Discretionary",
    "TMHC": "Consumer Discretionary", "ETSY": "Consumer Discretionary",
    "EBAY": "Consumer Discretionary", "EXPE": "Consumer Discretionary",
    "UBER": "Consumer Discretionary", "LYFT": "Consumer Discretionary",
    "DKNG": "Consumer Discretionary", "LVS": "Consumer Discretionary",
    "WYNN": "Consumer Discretionary", "MGM": "Consumer Discretionary",
    "CZR": "Consumer Discretionary", "HAS": "Consumer Discretionary",
    "TTWO": "Consumer Discretionary", "EA": "Consumer Discretionary",
    "MTCH": "Consumer Discretionary", "ULTA": "Consumer Discretionary",
    "RL": "Consumer Discretionary", "PVH": "Consumer Discretionary",
    "TPR": "Consumer Discretionary", "VFC": "Consumer Discretionary",
    "NWL": "Consumer Discretionary", "WHR": "Consumer Discretionary",
    "BBY": "Consumer Discretionary", "KMX": "Consumer Discretionary",
    "GPC": "Consumer Discretionary", "GRMN": "Consumer Discretionary",
    "POOL": "Consumer Discretionary", "TSCO": "Consumer Discretionary",
    "DG": "Consumer Discretionary", "DLTR": "Consumer Discretionary",
    "ABNB": "Consumer Discretionary", "SE": "Consumer Discretionary",
    "GRAB": "Consumer Discretionary", "MELI": "Consumer Discretionary",
    "DKS": "Consumer Discretionary", "BJ": "Consumer Discretionary",
    "BOOT": "Consumer Discretionary", "SKX": "Consumer Discretionary",
    "DECK": "Consumer Discretionary", "LULU": "Consumer Discretionary",
    "AN": "Consumer Discretionary", "TXRH": "Consumer Discretionary",
    "EAT": "Consumer Discretionary", "PLNT": "Consumer Discretionary",
    "HGV": "Consumer Discretionary", "YETI": "Consumer Discretionary",
    "WSM": "Consumer Discretionary", "CASY": "Consumer Discretionary",
    # ── Consumer Staples ───────────────────────────────────────────
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples",
    "COST": "Consumer Staples", "WMT": "Consumer Staples", "MDLZ": "Consumer Staples",
    "MO": "Consumer Staples", "PM": "Consumer Staples", "CL": "Consumer Staples",
    "KMB": "Consumer Staples", "GIS": "Consumer Staples", "SJM": "Consumer Staples",
    "K": "Consumer Staples", "CPB": "Consumer Staples", "CAG": "Consumer Staples",
    "HRL": "Consumer Staples", "TSN": "Consumer Staples", "HSY": "Consumer Staples",
    "MNST": "Consumer Staples", "KDP": "Consumer Staples", "KHC": "Consumer Staples",
    "STZ": "Consumer Staples", "TAP": "Consumer Staples", "CHD": "Consumer Staples",
    "CLX": "Consumer Staples", "SPC": "Consumer Staples", "EL": "Consumer Staples",
    "KR": "Consumer Staples", "SYY": "Consumer Staples", "ADM": "Consumer Staples",
    "WBA": "Consumer Staples", "CVS": "Consumer Staples",
    "SFM": "Consumer Staples", "USFD": "Consumer Staples",
    "POST": "Consumer Staples", "LANC": "Consumer Staples", "CALM": "Consumer Staples",
    "SAM": "Consumer Staples", "INGR": "Consumer Staples",
    # ── Industrials ────────────────────────────────────────────────
    "BA": "Industrials", "CAT": "Industrials", "GE": "Industrials", "HON": "Industrials",
    "UNP": "Industrials", "UPS": "Industrials", "RTX": "Industrials", "LMT": "Industrials",
    "NOC": "Industrials", "GD": "Industrials", "LHX": "Industrials", "TDG": "Industrials",
    "TDY": "Industrials", "DE": "Industrials", "EMR": "Industrials", "ETN": "Industrials",
    "ITW": "Industrials", "PH": "Industrials", "ROK": "Industrials", "DOV": "Industrials",
    "FTV": "Industrials", "IR": "Industrials", "AME": "Industrials", "IEX": "Industrials",
    "OTIS": "Industrials", "CARR": "Industrials", "WM": "Industrials", "RSG": "Industrials",
    "FAST": "Industrials", "SNA": "Industrials", "SWK": "Industrials",
    "JBHT": "Industrials", "CSX": "Industrials", "NSC": "Industrials", "DAL": "Industrials",
    "UAL": "Industrials", "ALK": "Industrials", "LUV": "Industrials",
    "WAB": "Industrials", "TT": "Industrials", "ODFL": "Industrials",
    "CMI": "Industrials", "PCAR": "Industrials", "GNRC": "Industrials",
    "ROL": "Industrials", "ROP": "Industrials", "CHRW": "Industrials",
    "EXPD": "Industrials", "FDX": "Industrials", "URI": "Industrials",
    "PWR": "Industrials", "TRMB": "Industrials", "CTAS": "Industrials",
    "PAYC": "Industrials", "PAYX": "Industrials", "ADP": "Industrials",
    "GWW": "Industrials", "NDSN": "Industrials", "HWM": "Industrials",
    "AXON": "Industrials", "SAIC": "Industrials", "ACM": "Industrials",
    "GXO": "Industrials", "KNX": "Industrials", "HUBG": "Industrials",
    "WERN": "Industrials", "JBL": "Industrials", "FIX": "Industrials",
    "TTC": "Industrials", "AGCO": "Industrials", "ITT": "Industrials",
    "RBC": "Industrials", "ARMK": "Industrials", "AIT": "Industrials",
    "THO": "Industrials", "LSTR": "Industrials", "WSC": "Industrials",
    "CW": "Industrials", "GGG": "Industrials",
    # ── Materials ──────────────────────────────────────────────────
    "LIN": "Materials", "APD": "Materials", "ECL": "Materials", "SHW": "Materials",
    "PPG": "Materials", "DD": "Materials", "DOW": "Materials", "NUE": "Materials",
    "FCX": "Materials", "NEM": "Materials", "FMC": "Materials", "CF": "Materials",
    "MOS": "Materials", "ALB": "Materials", "EMN": "Materials", "CE": "Materials",
    "AVY": "Materials", "IFF": "Materials", "MLM": "Materials", "VMC": "Materials",
    "LYB": "Materials", "OLN": "Materials", "AMCR": "Materials", "PKG": "Materials",
    "IP": "Materials", "WRK": "Materials", "SEE": "Materials", "BHP": "Materials",
    "RIO": "Materials", "VALE": "Materials", "TECK": "Materials", "MT": "Materials",
    "HL": "Materials", "ICL": "Materials", "CLF": "Materials", "X": "Materials",
    "CMC": "Materials", "ATI": "Materials", "RGLD": "Materials", "WPM": "Materials",
    "RPM": "Materials", "CBT": "Materials", "CC": "Materials", "EXP": "Materials",
    "OC": "Materials", "SON": "Materials",
    "CTVA": "Materials",  # Corteva — agricultural specialty chemicals
    # ── Utilities ──────────────────────────────────────────────────
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "D": "Utilities",
    "AEP": "Utilities", "EXC": "Utilities", "SRE": "Utilities", "ED": "Utilities",
    "XEL": "Utilities", "WEC": "Utilities", "ES": "Utilities", "EIX": "Utilities",
    "PEG": "Utilities", "ETR": "Utilities", "DTE": "Utilities", "AEE": "Utilities",
    "FE": "Utilities", "PPL": "Utilities", "CMS": "Utilities", "CNP": "Utilities",
    "ATO": "Utilities", "NI": "Utilities", "EVRG": "Utilities", "PNW": "Utilities",
    "LNT": "Utilities", "NRG": "Utilities", "CEG": "Utilities", "PCG": "Utilities",
    "AWK": "Utilities", "AES": "Utilities", "WELL": "Utilities",
    "IDA": "Utilities", "OGE": "Utilities", "BKH": "Utilities", "SWX": "Utilities",
    # ── Real Estate ────────────────────────────────────────────────
    "AMT": "Real Estate", "PLD": "Real Estate", "CCI": "Real Estate",
    "EQIX": "Real Estate", "SPG": "Real Estate", "O": "Real Estate",
    "PSA": "Real Estate", "DLR": "Real Estate", "WELL": "Real Estate",
    "AVB": "Real Estate", "EQR": "Real Estate", "ESS": "Real Estate",
    "MAA": "Real Estate", "UDR": "Real Estate", "CPT": "Real Estate",
    "VTR": "Real Estate", "PEAK": "Real Estate", "HST": "Real Estate",
    "ARE": "Real Estate", "BXP": "Real Estate", "KIM": "Real Estate",
    "REG": "Real Estate", "FRT": "Real Estate", "VICI": "Real Estate",
    "IRM": "Real Estate", "EXR": "Real Estate", "INVH": "Real Estate",
    "SBAC": "Real Estate", "WPC": "Real Estate", "STAG": "Real Estate",
    "EGP": "Real Estate", "AMH": "Real Estate",
    # ── Communication Services ─────────────────────────────────────
    "DIS": "Communication Services", "CMCSA": "Communication Services",
    "CHTR": "Communication Services", "T": "Communication Services",
    "VZ": "Communication Services", "TMUS": "Communication Services",
    "WBD": "Communication Services", "PARA": "Communication Services",
    "NWSA": "Communication Services", "NWS": "Communication Services",
    "FOX": "Communication Services", "FOXA": "Communication Services",
    "IPG": "Communication Services", "OMC": "Communication Services",
    "LYV": "Communication Services", "SIRI": "Communication Services",
    "DISH": "Communication Services", "LUMN": "Communication Services",
    # ── ETFs ───────────────────────────────────────────────────────
    "SPY": "ETF", "QQQ": "ETF", "IWM": "ETF", "IWF": "ETF", "IWD": "ETF",
    "DIA": "ETF", "VOO": "ETF", "VTI": "ETF", "RSP": "ETF",
    "XLK": "ETF", "XLF": "ETF", "XLE": "ETF", "XLV": "ETF", "XLI": "ETF",
    "XLC": "ETF", "XLY": "ETF", "XLP": "ETF", "XLB": "ETF", "XLU": "ETF", "XLRE": "ETF",
    "SMH": "ETF", "XBI": "ETF", "XHB": "ETF", "XRT": "ETF", "KRE": "ETF",
    "KBE": "ETF", "OIH": "ETF", "GDX": "ETF", "GDXJ": "ETF", "XME": "ETF",
    "ITB": "ETF", "IBB": "ETF", "IYR": "ETF", "VNQ": "ETF", "ARKK": "ETF",
    "ARKF": "ETF", "ARKG": "ETF", "IGV": "ETF", "SOXX": "ETF", "HACK": "ETF",
    "CIBR": "ETF", "TAN": "ETF", "ICLN": "ETF", "LIT": "ETF", "REMX": "ETF",
    "JETS": "ETF", "PBW": "ETF", "KWEB": "ETF",
    "EEM": "ETF", "EFA": "ETF", "VWO": "ETF", "IEMG": "ETF", "FXI": "ETF",
    "MCHI": "ETF", "INDA": "ETF", "EWZ": "ETF", "EWJ": "ETF", "EWG": "ETF",
    "EWU": "ETF", "EWY": "ETF", "EWT": "ETF", "EWH": "ETF", "EWS": "ETF",
    "EWA": "ETF", "EWC": "ETF", "EWW": "ETF",
    "GLD": "ETF", "SLV": "ETF", "USO": "ETF", "UNG": "ETF",
    "TLT": "ETF", "IEF": "ETF", "SHY": "ETF", "HYG": "ETF", "LQD": "ETF",
    "AGG": "ETF", "BND": "ETF", "EMB": "ETF", "JNK": "ETF",
    # Volatility / inverse hedges — classified as Hedge so they don't inflate ETF sector concentration
    "VXX": "Hedge", "VIXY": "Hedge", "SVXY": "Hedge", "UVXY": "Hedge",
    "TQQQ": "ETF", "SQQQ": "Hedge", "SPXL": "ETF", "SPXS": "Hedge",
    "SOXL": "ETF", "SOXS": "Hedge", "TNA": "ETF", "TZA": "Hedge",
    "GDXU": "ETF", "KORU": "ETF", "LABU": "ETF",
    "FAS": "ETF", "FAZ": "ETF",
    # ── Crypto-adjacent / Digital ──────────────────────────────────
    "MARA": "Technology", "RIOT": "Technology",
    # ── Previously-missing symbols in portfolio ──────────────────
    "ALLE": "Industrials", "COKE": "Consumer Staples",
    "REM": "Real Estate", "YINN": "ETF",
    "BG": "Consumer Staples", "DELL": "Technology",
    "ERX": "ETF", "GSG": "ETF", "GUSH": "ETF", "XOP": "ETF",
    "DBC": "ETF", "PDBC": "ETF",
    "NIO": "Consumer Discretionary", "SBRA": "Real Estate",
    "MASI": "Healthcare",
    # ── Previously missing — added from sector_concentration_manager ──
    # Technology
    "ANET": "Technology", "APH": "Technology", "SPLK": "Technology",
    "TEL": "Technology", "TTD": "Technology",
    # Financials
    "APO": "Financials", "ARES": "Financials", "BX": "Financials",
    "KKR": "Financials", "ONYX": "Financials", "SOFI": "Financials",
    "TPG": "Financials",
    # Healthcare
    "ALXN": "Healthcare", "TDOC": "Healthcare", "VEEV": "Healthcare",
    # Energy
    "DRIP": "Hedge", "FCEL": "Energy", "GEVO": "Energy",
    "HP": "Energy", "PLUG": "Energy",
    # Consumer Discretionary
    "DASH": "Consumer Discretionary", "LCID": "Consumer Discretionary",
    "PZZA": "Consumer Discretionary", "QSR": "Consumer Discretionary",
    "RIVN": "Consumer Discretionary",
    # Consumer Staples
    "MKC": "Consumer Staples",
    # Industrials
    "KSU": "Industrials", "MMM": "Industrials",
    # Communication Services
    "ATUS": "Communication Services", "BILI": "Communication Services",
    "IAC": "Communication Services", "IQ": "Communication Services",
    "MOMO": "Communication Services",
    # Materials
    "STLD": "Materials",
    # Hedges
    "SDOW": "Hedge",
    # ETFs (commodity baskets — consistent with DBC/PDBC as ETF)
    "COMB": "ETF", "COMT": "ETF",
}

# yfinance sector → GICS-aligned sector name mapping
_YF_SECTOR_NORMALIZE: Dict[str, str] = {
    "technology": "Technology",
    "communication services": "Communication Services",
    "consumer cyclical": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "financial services": "Financials",
    "healthcare": "Healthcare",
    "industrials": "Industrials",
    "basic materials": "Materials",
    "real estate": "Real Estate",
    "energy": "Energy",
    "utilities": "Utilities",
}


def _load_sector_cache() -> Dict[str, str]:
    try:
        if _DYNAMIC_CACHE_PATH.exists():
            return json.loads(_DYNAMIC_CACHE_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_sector_cache(cache: Dict[str, str]) -> None:
    try:
        _DYNAMIC_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DYNAMIC_CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception:
        pass


def get_sector(symbol: str) -> str:
    """Look up the sector for a symbol, with yfinance fallback and disk cache.

    Priority: SECTOR_MAP → disk cache → yfinance live lookup → 'Unknown'.
    """
    sym = symbol.upper().strip()

    static = SECTOR_MAP.get(sym)
    if static:
        return static

    cache = _load_sector_cache()
    cached = cache.get(sym)
    if cached:
        return cached

    try:
        import yfinance as yf
        info = yf.Ticker(sym).info or {}
        raw_sector = (info.get("sector") or "").strip().lower()
        if raw_sector:
            mapped = _YF_SECTOR_NORMALIZE.get(raw_sector, raw_sector.title())
            cache[sym] = mapped
            _save_sector_cache(cache)
            _logger.info("Dynamically resolved sector for %s → %s", sym, mapped)
            return mapped
    except Exception as exc:
        _logger.debug("yfinance sector lookup failed for %s: %s", sym, exc)

    return "Unknown"


def portfolio_sector_exposure(ib: BrokerClient) -> Tuple[Dict[str, float], float]:
    """
    Return (sector_exposure, total_notional) from ib.portfolio().
    sector_exposure[sector] = sum of marketValue for positions in that sector (signed).
    total_notional = sum of abs(marketValue) across all positions.
    """
    sector_exposure: Dict[str, float] = {}
    total_notional = 0.0
    try:
        for item in ib.portfolio():
            sym = getattr(getattr(item, "contract", None), "symbol", "")
            if not isinstance(sym, str) or not sym.strip():
                continue
            sector = get_sector(sym.strip())
            try:
                val = float(getattr(item, "marketValue", 0) or 0)
            except (TypeError, ValueError):
                continue
            sector_exposure[sector] = sector_exposure.get(sector, 0.0) + val
            total_notional += abs(val)
    except Exception:
        pass
    return sector_exposure, total_notional


def check_sector_concentration(
    sector_exposure: Dict[str, float],
    total_notional: float,
    symbol: str,
    side: str,
    notional: float,
    max_concentration_pct: float = 30.0,
) -> bool:
    """
    Return True if adding this position keeps all sector concentrations <= max_concentration_pct.
    side is 'SHORT' or 'LONG'; notional is positive. Short adds negative exposure to the sector.
    max_concentration_pct is 0-100 (e.g. 30 for 30%).
    """
    if max_concentration_pct <= 0:
        return True
    max_frac = max_concentration_pct / 100.0
    sector = get_sector(symbol)
    new_exposure = dict(sector_exposure)
    new_exposure[sector] = new_exposure.get(sector, 0.0) + (-notional if side == "SHORT" else notional)
    new_total = total_notional + notional
    if new_total <= 0:
        return True
    for _s, exp in new_exposure.items():
        if abs(exp) / new_total > max_frac:
            return False
    return True

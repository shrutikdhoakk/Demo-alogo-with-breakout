import argparse, sys, pathlib, pandas as pd
import yfinance as yf
from backtest.pattern_filters import pattern_gate

def read_universe(path: pathlib.Path) -> list[str]:
    df = pd.read_csv(path)
    cols = [c.lower() for c in df.columns]
    if "symbol" in cols:
        sym = df.columns[cols.index("symbol")]
        s = df[sym].astype(str).str.strip()
    else:
        s = df.iloc[:,0].astype(str).str.strip()
    return [x for x in s if x]

def _flatten_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        lvl0 = [str(x).lower() for x in df.columns.get_level_values(0)]
        lvl1 = [str(x).lower() for x in df.columns.get_level_values(1)]
        ohlc = {"open","high","low","close","adj close","volume"}
        hit0 = sum(1 for x in lvl0 if x in ohlc)
        hit1 = sum(1 for x in lvl1 if x in ohlc)
        df.columns = df.columns.get_level_values(1 if hit1 >= hit0 else 0)
    return df

def fetch_ohlc(symbol: str, period: str="300d") -> pd.DataFrame | None:
    try:
        df = yf.download(symbol, period=period, auto_adjust=False, progress=False, group_by="column")
        if df is None or df.empty: return None
        df = _flatten_ohlc(df)
        df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Adj Close":"adj close","Volume":"volume"})
        cols = [c for c in ["open","high","low","close","volume"] if c in df.columns]
        if not {"open","high","low","close"}.issubset(set(cols)): return None
        return df[cols].dropna()
    except Exception:
        return None

def _to_float(x):
    try: return float(x)
    except Exception: return float("nan")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in",  dest="in_csv",  required=True, help="input universe CSV")
    ap.add_argument("--out", dest="out_csv", required=True, help="output filtered CSV (symbol column)")
    ap.add_argument("--max", type=int, default=150, help="max symbols to test (to avoid rate limits)")
    ap.add_argument("--period", default="300d", help="yfinance period window (e.g., 300d, 1y, 2y)")
    ap.add_argument("--loose", action="store_true", help="looser gate: breakout OR squeeze instead of both")
    args = ap.parse_args()

    src = pathlib.Path(args.in_csv)
    dst = pathlib.Path(args.out_csv)
    if not src.exists():
        print(f"FAIL: universe not found -> {src}")
        sys.exit(1)

    uni = read_universe(src)[: args.max]
    passed, rows = [], []
    for sym in uni:
        ohlc = fetch_ohlc(sym, period=args.period)
        if ohlc is None or len(ohlc) < 120:
            rows.append({"symbol":sym,"status":"skip_short_or_bad"})
            continue

        out = pattern_gate(ohlc)
        ok_strict = bool(out.get("candidate_ok", False))

        if args.loose:
            bo = bool(out.get("breakout_hh20", False)) or bool(out.get("breakout_hh50", False))
            squeeze = ( _to_float(out.get("bb_width_pctile")) <= 0.25 ) or ( _to_float(out.get("atr_pctile")) <= 0.35 )
            ok = bool(bo or squeeze or ok_strict)
        else:
            ok = ok_strict

        rows.append({
            "symbol": sym,
            "mode": "loose" if args.loose else "strict",
            "ok": ok,
            "bb_width_pctile": out.get("bb_width_pctile"),
            "atr_pctile": out.get("atr_pctile"),
            "breakout_hh20": out.get("breakout_hh20"),
            "breakout_hh50": out.get("breakout_hh50"),
        })
        if ok: passed.append(sym)

    rep = pd.DataFrame(rows)
    rep_path = dst.with_suffix(".report.csv")
    rep.to_csv(rep_path, index=False)

    pd.DataFrame({"symbol": passed}).to_csv(dst, index=False)
    print(f"OK: {len(passed)}/{len(uni)} passed the gate -> {dst}")
    print(f"Report saved -> {rep_path}")

if __name__ == "__main__":
    main()

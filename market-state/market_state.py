# market_state.py
# ------------------------------------------------------------
# 统一入口：get_market_state(scope, params)
#
# scope：
#   - hs_a           : A股全市场实时快照（多源 fallback：东财 -> 其它源）
#   - industry_board : 行业板块强弱（东财；若也被掐，会返回错误+列名）
#   - sse_summary    : 上交所总貌（收盘后/最近交易日统计）
#   - szse_summary   : 深交所总貌（指定 date，如 "20200619"）
#
# CLI：
#   python market_state.py
#   python market_state.py hs_a '{"raw": true, "raw_rows": 2}'
#   python market_state.py industry_board '{"top_n": 20, "raw": true}'
# ------------------------------------------------------------

import json
from datetime import datetime
from typing import Any, Dict, Optional, Callable, List, Tuple

import numpy as np
import pandas as pd
import akshare as ak


# ---------------- utils ----------------
def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, float) and np.isnan(x):
            return None
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def _pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _call_if_exists(func_name: str, *args, **kwargs):
    """
    AKShare 版本差异很大：有的函数名在某些版本不存在。
    这个 helper：不存在就抛 AttributeError，方便上层 fallback。
    """
    func = getattr(ak, func_name)  # 若不存在会 AttributeError
    return func(*args, **kwargs)


def _fetch_with_fallback(fetchers: List[Tuple[str, Callable[[], pd.DataFrame]]]) -> Tuple[pd.DataFrame, List[str]]:
    """
    依次尝试 fetchers，成功返回 (df, errors)
    全失败则 raise RuntimeError(errors...)
    """
    errors: List[str] = []
    for name, f in fetchers:
        try:
            df = f()
            if isinstance(df, pd.DataFrame) and len(df) > 0:
                return df, errors
            errors.append(f"[{name}] Empty dataframe")
        except Exception as e:
            errors.append(f"[{name}] {type(e).__name__}: {e}")
    raise RuntimeError("All data sources failed:\n" + "\n".join(errors))


# ---------------- summaries ----------------
def _summarize_spot(df: pd.DataFrame, top_n: int = 20) -> Dict[str, Any]:
    """
    对“全市场快照/实时行情”做汇总：
    - 涨跌家数（breadth）
    - 涨跌幅分位数
    - 成交额 top（如果有）
    兼容不同来源字段名。
    """
    code_col = _pick_col(df, ["代码", "股票代码", "symbol", "code"])
    name_col = _pick_col(df, ["名称", "股票简称", "name"])
    pct_col  = _pick_col(df, ["涨跌幅", "涨跌幅%", "涨跌幅(%)", "changepercent", "pct_chg", "涨跌幅(%)"])
    price_col = _pick_col(df, ["最新价", "现价", "price", "trade", "最新"])
    amount_col = _pick_col(df, ["成交额", "amount", "成交额(元)", "turnover", "成交额（元）", "成交额(万)"])

    if not code_col or not name_col or not pct_col:
        return {
            "error": "spot missing key columns",
            "available_cols": list(df.columns),
        }

    x = df.copy()
    x[pct_col] = pd.to_numeric(x[pct_col], errors="coerce")

    breadth = {
        "advance": int((x[pct_col] > 0).sum()),
        "decline": int((x[pct_col] < 0).sum()),
        "flat": int((x[pct_col] == 0).sum()),
        "total": int(len(x)),
    }

    pct = x[pct_col].dropna()

    def q(v, p):
        return _safe_float(v.quantile(p)) if len(v) else None

    pct_quantiles = {"p10": q(pct, 0.10), "p50": q(pct, 0.50), "p90": q(pct, 0.90)}

    # MVP：涨跌停近似（不区分ST/不同板块限制）
    limit_up_like = int((x[pct_col] >= 9.5).sum())
    limit_down_like = int((x[pct_col] <= -9.5).sum())

    top_turnover = None
    turnover_quantiles = None

    if amount_col:
        # 有些来源成交额单位可能是“万”，但我们先不做单位统一（先可用）
        x[amount_col] = pd.to_numeric(x[amount_col], errors="coerce")
        amt = x[amount_col].dropna()
        if len(amt):
            turnover_quantiles = {"p50": q(amt, 0.50), "p90": q(amt, 0.90), "p99": q(amt, 0.99)}

            cols = [code_col, name_col]
            if price_col:
                cols.append(price_col)
            cols += [pct_col, amount_col]

            top_df = (
                x.sort_values(amount_col, ascending=False)
                 .head(top_n)[cols]
                 .copy()
            )

            rename_map = {
                code_col: "code",
                name_col: "name",
                pct_col: "pct_chg",
                amount_col: "amount",
            }
            if price_col:
                rename_map[price_col] = "last"

            top_df = top_df.rename(columns=rename_map)
            for c in ["pct_chg", "amount", "last"]:
                if c in top_df.columns:
                    top_df[c] = top_df[c].map(_safe_float)

            top_turnover = top_df.to_dict(orient="records")

    return {
        "breadth": breadth,
        "pct_chg_quantiles": pct_quantiles,
        "turnover_quantiles": turnover_quantiles,
        "limit_up_like": limit_up_like,
        "limit_down_like": limit_down_like,
        "top_turnover": top_turnover,
    }


def _summarize_industry_board(df: pd.DataFrame, top_n: int = 20) -> Dict[str, Any]:
    """
    行业板块强弱：尽量兼容列名。
    常见：板块名称/涨跌幅/上涨家数/下跌家数/领涨股票/领涨股票-涨跌幅
    """
    board_col = _pick_col(df, ["板块名称", "行业名称", "名称", "board"])
    pct_col = _pick_col(df, ["涨跌幅", "涨跌幅%", "涨跌幅(%)", "pct_chg"])
    if not board_col or not pct_col:
        return {"error": "industry board missing key columns", "available_cols": list(df.columns)}

    x = df.copy()
    x[pct_col] = pd.to_numeric(x[pct_col], errors="coerce")

    top_up = x.sort_values(pct_col, ascending=False).head(top_n)
    top_dn = x.sort_values(pct_col, ascending=True).head(top_n)

    # 尽量把常见列一并带上（存在就带）
    extra_cols = []
    for c in ["上涨家数", "下跌家数", "领涨股票", "领涨股票-涨跌幅"]:
        if c in x.columns:
            extra_cols.append(c)

    def pack(df_part):
        cols = [board_col, pct_col] + extra_cols
        out = df_part[cols].copy()
        rename = {board_col: "board", pct_col: "pct_chg"}
        if "上涨家数" in out.columns: rename["上涨家数"] = "adv"
        if "下跌家数" in out.columns: rename["下跌家数"] = "dec"
        if "领涨股票" in out.columns: rename["领涨股票"] = "leader"
        if "领涨股票-涨跌幅" in out.columns: rename["领涨股票-涨跌幅"] = "leader_pct_chg"
        out = out.rename(columns=rename)
        for c in ["pct_chg", "adv", "dec", "leader_pct_chg"]:
            if c in out.columns:
                out[c] = out[c].map(_safe_float)
        return out.to_dict(orient="records")

    return {"top_gainers": pack(top_up), "top_losers": pack(top_dn)}


# ---------------- fetchers ----------------
def fetch_hs_a(params: Dict[str, Any]) -> Tuple[pd.DataFrame, str, List[str]]:
    """
    A股全市场快照，多源 fallback。
    你现在遇到的就是东财接口被掐连接，所以必须要有备用源。
    """
    fetchers: List[Tuple[str, Callable[[], pd.DataFrame]]] = [
        ("eastmoney_spot_em", lambda: _call_if_exists("stock_zh_a_spot_em")),
        # 下面这些函数名在不同 AKShare 版本存在与否不一，所以用 _call_if_exists 包
        ("sina_spot",        lambda: _call_if_exists("stock_zh_a_spot")),
        ("tencent_spot",     lambda: _call_if_exists("stock_zh_a_spot_tx")),
        ("sina_spot_2",      lambda: _call_if_exists("stock_zh_a_spot_sina")),
    ]
    df, errors = _fetch_with_fallback(fetchers)
    # source 名字用于 meta 里告诉你最后用的是哪个源（便于排查）
    # 简单做法：从 errors 推断不方便，我们直接再试一遍判断来源：不做，改为在失败列表里看即可
    # 这里返回一个固定值不靠谱，因此我们把 errors 也返回，由外层放到 meta。
    return df, "auto_fallback", errors


def fetch_industry_board(params: Dict[str, Any]) -> Tuple[pd.DataFrame, str, List[str]]:
    fetchers: List[Tuple[str, Callable[[], pd.DataFrame]]] = [
        ("eastmoney_industry_board", lambda: _call_if_exists("stock_board_industry_name_em")),
    ]
    df, errors = _fetch_with_fallback(fetchers)
    return df, "eastmoney", errors


# ---------------- main API ----------------
def get_market_state(scope: str = "hs_a", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    params:
      - top_n: int, default 20
      - raw: bool, default False (True: 返回 raw_head 方便你看字段)
      - raw_rows: int, default 5
      - date: str, 给 szse_summary 用，如 "20200619"
    """
    params = params or {}
    top_n = int(params.get("top_n", 20))
    raw = bool(params.get("raw", False))
    raw_rows = int(params.get("raw_rows", 5))

    meta = {
        "scope": scope,
        "asof": _now_str(),
        "source": "akshare",
        "akshare_version": getattr(ak, "__version__", "unknown"),
        "params": params,
    }

    try:
        if scope == "hs_a":
            df, src, errs = fetch_hs_a(params)
            meta["data_source"] = src
            if errs:
                meta["fallback_errors"] = errs

            out: Dict[str, Any] = {
                "meta": meta,
                "shape": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
                "columns": list(df.columns),
                "summary": _summarize_spot(df, top_n=top_n),
            }
            if raw:
                out["raw_head"] = df.head(raw_rows).to_dict(orient="records")
            return out

        elif scope == "industry_board":
            df, src, errs = fetch_industry_board(params)
            meta["data_source"] = src
            if errs:
                meta["fallback_errors"] = errs

            out = {
                "meta": meta,
                "shape": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
                "columns": list(df.columns),
                "summary": _summarize_industry_board(df, top_n=top_n),
            }
            if raw:
                out["raw_head"] = df.head(raw_rows).to_dict(orient="records")
            return out

        elif scope == "sse_summary":
            # 交易所总貌：通常是最近交易日/收盘后统计
            df = _call_if_exists("stock_sse_summary")
            if isinstance(df, pd.DataFrame):
                out = {
                    "meta": meta,
                    "shape": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
                    "columns": list(df.columns),
                    "data": df.to_dict(orient="records"),
                }
                if raw:
                    out["raw_head"] = df.head(raw_rows).to_dict(orient="records")
                return out
            return {"meta": meta, "data": df}

        elif scope == "szse_summary":
            date = str(params.get("date", "")).strip()
            if not date:
                return {"meta": meta, "error": "szse_summary requires params['date'], e.g. '20200619'"}
            df = _call_if_exists("stock_szse_summary", date=date)
            if isinstance(df, pd.DataFrame):
                out = {
                    "meta": meta,
                    "shape": {"rows": int(df.shape[0]), "cols": int(df.shape[1])},
                    "columns": list(df.columns),
                    "data": df.to_dict(orient="records"),
                }
                if raw:
                    out["raw_head"] = df.head(raw_rows).to_dict(orient="records")
                return out
            return {"meta": meta, "data": df}

        else:
            return {
                "meta": meta,
                "error": f"unknown scope: {scope}",
                "supported_scopes": ["hs_a", "industry_board", "sse_summary", "szse_summary"],
            }

    except Exception as e:
        # 把异常也放回去，方便你排查
        return {"meta": meta, "error": f"fetch failed: {type(e).__name__}: {e}"}


# ---------------- CLI ----------------
if __name__ == "__main__":
    import sys

    # 用法：
    #   python market_state.py
    #   python market_state.py hs_a '{"raw": true, "raw_rows": 2}'
    scope = sys.argv[1] if len(sys.argv) > 1 else "hs_a"
    params: Dict[str, Any] = {}

    if len(sys.argv) > 2:
        try:
            params = json.loads(sys.argv[2])
        except Exception:
            print("Second arg must be JSON string, e.g. '{\"top_n\": 30, \"raw\": true}'")
            sys.exit(1)

    res = get_market_state(scope, params)
    print(json.dumps(res, ensure_ascii=False, indent=2))

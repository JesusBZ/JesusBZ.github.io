"""
Backtesting Walk-Forward Multianual Strictly Causal (Fase 4) por Bot:
  - BOT A: 15m/1H (365 días KuCoin)
  - BOT B: 1D (1,940 días KuCoin)
  - BOT C: 4H Perpetuos + Funding Rate Histórico (1,095 días KuCoin + OKX funding history)
  - BOT D: 4H Ensemble Multiclase + Régimen GMM + Guardián (1,095 días KuCoin)

Reutiliza literalmente las funciones e indicadores de producción (`main.py` y
`src/strategies/quant_bots_rules.py`) con caché local en `.cache_history/`.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import concurrent.futures
import json
import math
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

BASE_DIR = pathlib.Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.settings import SETTINGS
from src.data_ingestion.okx_bybit_client import COIN_NAMES, MultiExchangeCryptoOracle
from src.strategies.quant_bots_rules import (
    BotAConfig,
    RiskGatekeeperConfig,
    calc_adx_di,
    calc_atr,
    calc_futures_account_state,
    calc_metrics,
    calc_obv_slope,
    calc_rsi,
    calc_stoch_k,
    calc_structure_and_btc_metrics,
    compute_bollinger,
    compute_gjr_garch_vols,
    compute_macd_pct,
    compute_triple_barrier_labels,
    extract_ta_features_row,
    fit_supervised_3class_ensemble,
    govern_champion_challenger,
    init_bot_a_state,
    step_bot_a_microtrading,
)
import main as prod_main

CACHE_DIR = BASE_DIR / ".cache_history"
REPORT_JSON_PATH = BASE_DIR / "backtest_bots_report.json"
ARTIFACT_MD_PATH = pathlib.Path(
    r"C:\Users\jesus\.gemini\antigravity\brain\21b513cf-2250-40e1-bccf-c08e78b852c2\backtest_bots_report.md"
)

KUCOIN_MAP = {
    "15m": ("15min", 900),
    "1H": ("1hour", 3600),
    "4H": ("4hour", 14400),
    "1D": ("1day", 86400),
}


def _fetch_kucoin_paginated_cached(
    oracle: MultiExchangeCryptoOracle,
    coins: List[str],
    bar: str,
    days: int,
) -> Dict[str, pd.DataFrame]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    kc_type, sec_step = KUCOIN_MAP[bar]
    out: Dict[str, pd.DataFrame] = {}

    def _load_or_fetch(coin: str) -> Tuple[str, pd.DataFrame]:
        cache_fp = CACHE_DIR / f"{bar}_{coin}_{days}d.csv.gz"
        if cache_fp.exists():
            try:
                df_c = pd.read_csv(cache_fp, compression="gzip", index_col=0, parse_dates=True)
                if len(df_c) >= max(200, int((days * 86400 / sec_step) * 0.70)):
                    return coin, df_c
            except Exception:
                pass

        now_s = int(time.time())
        start_s = now_s - int(days) * 86400
        chunk_span = 1400 * sec_step
        rows_by_dt: Dict[pd.Timestamp, Tuple[float, float, float, float, float]] = {}
        cur_end = now_s
        while cur_end > start_s:
            cur_start = max(start_s, cur_end - chunk_span)
            rows = oracle._fetch_kucoin_candles(coin, kc_type, cur_start, cur_end)
            for ts_ms, o_v, h_v, l_v, c_v, v_v in rows:
                dt_k = pd.Timestamp(ts_ms, unit="ms", tz="UTC").tz_localize(None)
                rows_by_dt[dt_k] = (o_v, h_v, l_v, c_v, v_v)
            cur_end = cur_start - sec_step
            time.sleep(0.06)

        sorted_dts = sorted(rows_by_dt.keys())
        df_res = pd.DataFrame(
            [rows_by_dt[dt_k] for dt_k in sorted_dts],
            index=pd.DatetimeIndex(sorted_dts, name="dt"),
            columns=["open", "high", "low", "close", "volume"],
        )
        df_res.to_csv(cache_fp, compression="gzip")
        return coin, df_res

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for c, df in pool.map(_load_or_fetch, coins):
            out[c] = df
    return {c: out[c] for c in coins}


def _fetch_funding_cached(oracle: MultiExchangeCryptoOracle, coins: List[str], days: int = 50) -> Dict[str, pd.Series]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fp = CACHE_DIR / f"funding_okx_{days}d.json.gz"
    import gzip

    if fp.exists():
        try:
            with gzip.open(fp, "rt", encoding="utf-8") as fh:
                raw = json.load(fh)
            return {
                c: pd.Series({pd.Timestamp(k): float(v) for k, v in raw.get(c, {}).items()}).sort_index()
                for c in coins
            }
        except Exception:
            pass

    fr_map = oracle.fetch_funding_history(coins, days=days)
    serial = {c: {ts.strftime("%Y-%m-%d %H:%M"): float(v) for ts, v in s.items()} for c, s in fr_map.items()}
    with gzip.open(fp, "wt", encoding="utf-8") as fh:
        json.dump(serial, fh)
    return fr_map


def _build_causal_rolling_regimes(
    close_df: pd.DataFrame,
    adx_df: pd.DataFrame,
    refit_step: int,
    warmup: int,
    lookback: int,
    btc_col: str = "BTC",
    seed: int = 42,
) -> pd.Series:
    """
    Reajusta el detector GMM de 4 regímenes cada `refit_step` velas usando estrictamente datos <= t-1
    y clasifica las `refit_step` velas siguientes sin filtrar información futura.
    """
    anchor = btc_col if btc_col in close_df.columns else close_df.columns[0]
    btc_s = close_df[anchor].clip(lower=1e-8)
    btc_e50 = btc_s.ewm(span=50, min_periods=5, adjust=False).mean().clip(lower=1e-8)
    btc_roc12 = btc_s.pct_change(12).fillna(0.0)
    f_trend = ((btc_s / btc_e50) - 1.0).fillna(0.0) + 0.55 * btc_roc12

    e50_all = close_df.ewm(span=50, min_periods=5, adjust=False).mean().clip(lower=1e-8)
    f_breadth = (close_df > e50_all).mean(axis=1).fillna(0.5) - 0.5
    rets = close_df.pct_change().fillna(0.0)
    cross_vol = rets.rolling(18, min_periods=4).std().mean(axis=1).fillna(0.015).clip(lower=1e-5)
    f_adx = (adx_df.reindex(close_df.index).ffill().fillna(20.0).mean(axis=1) / 25.0).clip(0.2, 3.0)

    feat_mat = np.column_stack([
        f_trend.values,
        f_breadth.values,
        cross_vol.values * 100.0,
        f_adx.values,
    ])
    cv_q75_causal = cross_vol.rolling(180, min_periods=24).quantile(0.75).shift(1)
    n_rows = len(close_df)
    codes = ["MERCADO_LATERAL"] * n_rows

    for k in range(warmup, n_rows, refit_step):
        w_start = max(0, k - lookback)
        scaler = StandardScaler()
        x_fit = scaler.fit_transform(feat_mat[w_start:k])
        n_comp = min(4, max(2, len(np.unique(x_fit, axis=0))))
        gmm = GaussianMixture(n_components=n_comp, covariance_type="diag", reg_covar=1e-4, max_iter=180, random_state=seed)
        gmm.fit(x_fit)
        raw_centers = scaler.inverse_transform(gmm.means_)

        comp_to_code: Dict[int, str] = {}
        remaining = list(range(n_comp))
        if len(remaining) == 4:
            vol_sorted = sorted((float(raw_centers[m, 2]) for m in remaining), reverse=True)
            hv_idx = max(remaining, key=lambda m: raw_centers[m, 2])
            if vol_sorted[0] >= 2.0 and vol_sorted[0] >= 1.45 * max(vol_sorted[1], 1e-6):
                comp_to_code[hv_idx] = "ALTA_VOLATILIDAD"
                remaining.remove(hv_idx)
            bull_idx = max(remaining, key=lambda m: raw_centers[m, 0] + 0.35 * raw_centers[m, 1])
            comp_to_code[bull_idx] = "TENDENCIA_ALCISTA"
            remaining.remove(bull_idx)
            bear_idx = min(remaining, key=lambda m: raw_centers[m, 0] + 0.35 * raw_centers[m, 1])
            comp_to_code[bear_idx] = "TENDENCIA_BAJISTA"
            remaining.remove(bear_idx)
            for m in remaining:
                comp_to_code[m] = "MERCADO_LATERAL"
        else:
            for m in remaining:
                if raw_centers[m, 0] > 0.01:
                    comp_to_code[m] = "TENDENCIA_ALCISTA"
                elif raw_centers[m, 0] < -0.01:
                    comp_to_code[m] = "TENDENCIA_BAJISTA"
                else:
                    comp_to_code[m] = "MERCADO_LATERAL"

        med_vol = float(np.median(cross_vol.values[w_start:k]))
        k_end = min(n_rows, k + refit_step)
        post = gmm.predict_proba(scaler.transform(feat_mat[k:k_end]))
        for offset, t_idx in enumerate(range(k, k_end)):
            best_c = int(np.argmax(post[offset]))
            code_t = comp_to_code.get(best_c, "MERCADO_LATERAL")
            q75_val = cv_q75_causal.iloc[t_idx]
            thr_base = float(q75_val) if pd.notna(q75_val) else med_vol
            if float(cross_vol.iloc[t_idx]) >= max(0.025, 1.35 * thr_base):
                code_t = "ALTA_VOLATILIDAD"
            codes[t_idx] = code_t

    return pd.Series(codes, index=close_df.index, name="regime_code")


def _bootstrap_expectancy_ci(trade_rets: List[float], n_boot: int = 1000, seed: int = 42) -> Dict[str, Any]:
    if len(trade_rets) < 2:
        val = float(trade_rets[0]) if trade_rets else 0.0
        return {"n_trades": len(trade_rets), "mean_pct": round(val, 4), "ci95_low_pct": round(val, 4), "ci95_high_pct": round(val, 4)}
    arr = np.asarray(trade_rets, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(n_boot, len(arr)))
    means = np.mean(arr[idx], axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return {
        "n_trades": int(len(arr)),
        "mean_pct": round(float(np.mean(arr)), 4),
        "ci95_low_pct": round(float(lo), 4),
        "ci95_high_pct": round(float(hi), 4),
    }


def _compute_extended_metrics(
    eq_list: List[float],
    rets_list: List[float],
    trades: List[Dict[str, Any]],
    invested_flags: List[bool],
    fees_cum: float,
    periods_per_year: float,
    label: str,
) -> Dict[str, Any]:
    eq_arr = np.asarray(eq_list, dtype=float)
    r_arr = np.asarray(rets_list, dtype=float)
    base_m = calc_metrics(eq_arr, r_arr, periods_per_year, label)
    te = prod_main.summarize_bot_trades(trades, [], r_arr)
    closed_rets = [float(t["realized_pnl_pct"]) for t in trades if t.get("realized_pnl_pct") is not None]
    closed_usd = [float(t["realized_pnl_usd"]) for t in trades if t.get("realized_pnl_usd") is not None]
    exp_usd = float(np.mean(closed_usd)) if closed_usd else 0.0
    total_notional = float(sum(float(t.get("notional_usd") or 0.0) for t in trades))
    avg_eq = float(np.mean(eq_arr)) if len(eq_arr) else 1000.0
    years = max(len(r_arr) / periods_per_year, 1e-4)
    turnover_x = total_notional / max(avg_eq, 1.0)
    time_in_mkt_pct = float(np.mean(invested_flags) * 100.0) if invested_flags else 0.0
    boot = _bootstrap_expectancy_ci(closed_rets)
    return {
        **base_m,
        "total_orders": int(len(trades)),
        "closed_exits": int(len(closed_rets)),
        "win_rate_pct": te["win_rate_pct"],
        "profit_factor": te["profit_factor"],
        "expectancy_pct": round(float(np.mean(closed_rets)) if closed_rets else 0.0, 3),
        "expectancy_usd": round(exp_usd, 3),
        "avg_win_pct": te["avg_win_pct"],
        "avg_loss_pct": te["avg_loss_pct"],
        "fees_paid_usd": round(float(fees_cum), 2),
        "turnover_total_x": round(turnover_x, 2),
        "turnover_annual_x": round(turnover_x / years, 2),
        "time_in_market_pct": round(time_in_mkt_pct, 2),
        "bootstrap_expectancy_ci95": boot,
    }


def _compute_70_30_split(
    eq_list: List[float],
    rets_list: List[float],
    date_strs: List[str],
    trades: List[Dict[str, Any]],
    invested_flags: List[bool],
    periods_per_year: float,
    label_prefix: str,
) -> Dict[str, Any]:
    n_rets = len(rets_list)
    if n_rets < 20:
        return {}
    split_r = int(0.70 * n_rets)
    split_ts = date_strs[split_r]

    split_bound = f"{split_ts} 23:59" if len(split_ts) == 10 else split_ts

    eq_is = eq_list[: split_r + 1]
    rets_is = rets_list[:split_r]
    inv_is = invested_flags[:split_r]
    tr_is = [t for t in trades if str(t.get("ts_iso") or "") <= split_bound]
    fees_is = sum(float(t.get("fee_usd") or 0.0) for t in tr_is)

    eq_oos_raw = eq_list[split_r:]
    scale_oos = 1000.0 / max(float(eq_oos_raw[0]), 1e-8)
    eq_oos = [float(v) * scale_oos for v in eq_oos_raw]
    rets_oos = rets_list[split_r:]
    inv_oos = invested_flags[split_r:]
    tr_oos = []
    for t in trades:
        if str(t.get("ts_iso") or "") > split_bound:
            tc = dict(t)
            if tc.get("realized_pnl_usd") is not None:
                tc["realized_pnl_usd"] = float(tc["realized_pnl_usd"]) * scale_oos
            if tc.get("notional_usd") is not None:
                tc["notional_usd"] = float(tc["notional_usd"]) * scale_oos
            if tc.get("fee_usd") is not None:
                tc["fee_usd"] = float(tc["fee_usd"]) * scale_oos
            tr_oos.append(tc)
    fees_oos = sum(float(t.get("fee_usd") or 0.0) for t in tr_oos)

    return {
        "split_boundary": split_ts,
        "in_sample_70": _compute_extended_metrics(eq_is, rets_is, tr_is, inv_is, fees_is, periods_per_year, f"{label_prefix} [IS 70%]"),
        "out_of_sample_30": _compute_extended_metrics(eq_oos, rets_oos, tr_oos, inv_oos, fees_oos, periods_per_year, f"{label_prefix} [OOS 30%]"),
    }


def _equal_weight_benchmark(close_df: pd.DataFrame, eval_indices: List[int], periods_per_year: float, label: str) -> Dict[str, Any]:
    sub = close_df.iloc[eval_indices]
    rets_m = sub.pct_change().fillna(0.0).mean(axis=1).values[1:]
    eq = [1000.0]
    for r in rets_m:
        eq.append(eq[-1] * (1.0 + float(r)))
    metrics = calc_metrics(np.asarray(eq), np.asarray(rets_m), periods_per_year, label)
    split_r = int(0.70 * len(rets_m))
    eq_oos = [1000.0]
    for r in rets_m[split_r:]:
        eq_oos.append(eq_oos[-1] * (1.0 + float(r)))
    metrics["in_sample_70"] = calc_metrics(np.asarray(eq[: split_r + 1]), np.asarray(rets_m[:split_r]), periods_per_year, f"{label} [IS 70%]")
    metrics["out_of_sample_30"] = calc_metrics(np.asarray(eq_oos), np.asarray(rets_m[split_r:]), periods_per_year, f"{label} [OOS 30%]")
    return metrics


def _prepare_bot_a_panel(
    coins: List[str],
    c15: Dict[str, pd.DataFrame],
    c1h: Dict[str, pd.DataFrame],
    reg_series_4h: pd.Series,
) -> Dict[str, Any]:
    close_1h = pd.DataFrame({c: c1h[c]["close"] for c in coins}).ffill().dropna()
    ema21_1h = close_1h.ewm(span=21, adjust=False).mean()
    ema55_1h = close_1h.ewm(span=55, adjust=False).mean()
    breadth_1h_series = (close_1h > ema21_1h).mean(axis=1)
    adx_1h = pd.DataFrame({c: calc_adx_di(c1h[c], 14)[0] for c in coins}).reindex(close_1h.index).bfill()

    # Desfase estricto al tiempo de cierre de la vela 1H (+1h) y 4H (+4h) para evitar look-ahead inter-temporalidad
    ema21_1h_closed = ema21_1h.copy()
    ema21_1h_closed.index = ema21_1h_closed.index + pd.Timedelta(hours=1)
    ema55_1h_closed = ema55_1h.copy()
    ema55_1h_closed.index = ema55_1h_closed.index + pd.Timedelta(hours=1)
    breadth_1h_closed = breadth_1h_series.copy()
    breadth_1h_closed.index = breadth_1h_closed.index + pd.Timedelta(hours=1)
    adx_1h_closed = adx_1h.copy()
    adx_1h_closed.index = adx_1h_closed.index + pd.Timedelta(hours=1)
    reg_4h_closed = reg_series_4h.copy()
    reg_4h_closed.index = reg_4h_closed.index + pd.Timedelta(hours=4)

    close_15m = pd.DataFrame({c: c15[c]["close"] for c in coins}).ffill().dropna()
    open_15m = pd.DataFrame({c: c15[c]["open"] for c in coins}).reindex(close_15m.index).ffill()
    high_15m = pd.DataFrame({c: c15[c]["high"] for c in coins}).reindex(close_15m.index).ffill()
    low_15m = pd.DataFrame({c: c15[c]["low"] for c in coins}).reindex(close_15m.index).ffill()
    vol_15m = pd.DataFrame({c: c15[c]["volume"] for c in coins}).reindex(close_15m.index).ffill().fillna(1.0)
    vol_rel_15m = vol_15m / (vol_15m.rolling(20, min_periods=5).mean() + 1e-9)
    atr_15m = pd.DataFrame({c: calc_atr(c15[c], 14) for c in coins}).reindex(close_15m.index).ffill().bfill()
    rsi_15m = pd.DataFrame({c: calc_rsi(close_15m[c], 14) for c in coins}).bfill()
    ema9_15m = close_15m.ewm(span=9, adjust=False).mean()
    ema21_15m = close_15m.ewm(span=21, adjust=False).mean()
    roc10_15m = (close_15m.pct_change(10) * 100.0).fillna(0.0)
    macd_h_15m = pd.DataFrame({c: compute_macd_pct(close_15m[c])[2] for c in coins})
    bb_pctb_15m = pd.DataFrame({c: compute_bollinger(close_15m[c], 20, 2.0)[3] for c in coins})
    obv_15m = pd.DataFrame({c: calc_obv_slope(close_15m[c], vol_15m[c], 14) for c in coins}, index=close_15m.index)
    ema200_dist_15m = calc_structure_and_btc_metrics(close_15m, high_15m, low_15m, "BTC", 20)["ema200_dist"]

    return {
        "close_15m": close_15m,
        "open_15m": open_15m,
        "high_15m": high_15m,
        "low_15m": low_15m,
        "vol_rel_15m": vol_rel_15m,
        "atr_15m": atr_15m,
        "rsi_15m": rsi_15m,
        "ema9_15m": ema9_15m,
        "ema21_15m": ema21_15m,
        "roc10_15m": roc10_15m,
        "macd_h_15m": macd_h_15m,
        "bb_pctb_15m": bb_pctb_15m,
        "obv_15m": obv_15m,
        "ema200_dist_15m": ema200_dist_15m,
        "ema21_1h": ema21_1h_closed.reindex(close_15m.index, method="ffill").bfill(),
        "ema55_1h": ema55_1h_closed.reindex(close_15m.index, method="ffill").bfill(),
        "breadth_1h": breadth_1h_closed.reindex(close_15m.index, method="ffill").bfill(),
        "adx_1h": adx_1h_closed.reindex(close_15m.index, method="ffill").bfill(),
        "reg_15m": reg_4h_closed.reindex(close_15m.index, method="ffill").fillna("MERCADO_LATERAL"),
    }


def _run_bot_a(panel: Dict[str, Any], coins: List[str], cfg: BotAConfig, collect_diag: bool = False) -> Dict[str, Any]:
    close_15m = panel["close_15m"]
    open_15m = panel["open_15m"]
    high_15m = panel["high_15m"]
    low_15m = panel["low_15m"]
    atr_15m = panel["atr_15m"]
    ema9_15m = panel["ema9_15m"]
    ema21_15m = panel["ema21_15m"]
    ema21_1h = panel["ema21_1h"]
    ema55_1h = panel["ema55_1h"]
    roc10_15m = panel["roc10_15m"]
    macd_h_15m = panel["macd_h_15m"]
    bb_pctb_15m = panel["bb_pctb_15m"]
    rsi_15m = panel["rsi_15m"]
    vol_rel_15m = panel["vol_rel_15m"]
    breadth_1h = panel["breadth_1h"]
    adx_1h = panel["adx_1h"]
    obv_15m = panel["obv_15m"]
    ema200_dist_15m = panel["ema200_dist_15m"]
    reg_15m = panel["reg_15m"]

    # Convertir columnas a numpy para acceso O(1) en bucle 35k barras
    idx = close_15m.index
    c_arr = close_15m.values
    o_arr = open_15m.values
    h_arr = high_15m.values
    l_arr = low_15m.values
    atr_arr = atr_15m.values
    e9_arr = ema9_15m.values
    e21_arr = ema21_15m.values
    e21_1h_arr = ema21_1h.values
    e55_1h_arr = ema55_1h.values
    roc_arr = roc10_15m.values
    mh_arr = macd_h_15m.values
    pb_arr = bb_pctb_15m.values
    rsi_arr = rsi_15m.values
    vrel_arr = vol_rel_15m.values
    b1h_arr = breadth_1h.values
    adx1h_arr = adx_1h.values
    obv_arr = obv_15m.values
    e200d_arr = ema200_dist_15m.values
    reg_arr = reg_15m.values
    reg_mult_map = {"TENDENCIA_ALCISTA": 1.0, "MERCADO_LATERAL": 0.78, "TENDENCIA_BAJISTA": 0.60, "ALTA_VOLATILIDAD": 0.50}

    start_i = 210
    pf_a = init_bot_a_state(coins, base_cap=1000.0)
    pf_a["dates"] = [idx[start_i - 1].strftime("%Y-%m-%d %H:%M")]
    pf_a["inception_utc"] = idx[start_i - 1].strftime("%Y-%m-%d %H:%M UTC")
    invested_flags: List[bool] = []
    regime_bar_counts: Dict[str, int] = {}
    regime_entry_counts: Dict[str, int] = {}
    filter_funnel: Dict[str, int] = {
        "coin_bars_total": 0,
        "pass_allow_trend_regime": 0,
        "pass_vol_edge_atr": 0,
        "pass_adx_1h": 0,
        "pass_htf": 0,
        "pass_ema9_gt_ema21": 0,
        "pass_roc10": 0,
        "pass_macd_exp": 0,
        "pass_rsi_band": 0,
        "pass_vrel_trend": 0,
        "pass_setup_trend_all": 0,
        "pass_setup_rebound_all": 0,
    }
    n_c = len(coins)

    for i in range(start_i, len(idx)):
        p = i - 1
        p2 = i - 2
        ts = idx[i]
        reg_i = str(reg_arr[p])
        prev_n = len(pf_a["trades"])

        if collect_diag:
            regime_bar_counts[reg_i] = regime_bar_counts.get(reg_i, 0) + 1
            allow_t = reg_i not in ("TENDENCIA_BAJISTA", "MERCADO_LATERAL")
            b1h_ok = b1h_arr[p] >= 0.375
            for j in range(n_c):
                filter_funnel["coin_bars_total"] += 1
                px_p = c_arr[p, j]
                atr_p = atr_arr[p, j]
                e9_p = e9_arr[p, j]
                e21_p = e21_arr[p, j]
                mh_p, mh_p2 = mh_arr[p, j], mh_arr[p2, j]
                pb_p, pb_p2 = pb_arr[p, j], pb_arr[p2, j]
                rv_p = rsi_arr[p, j]
                vr_p = vrel_arr[p, j]
                vol_ok = (atr_p / max(px_p, 1e-8)) >= cfg.min_atr_pct
                adx_ok = adx1h_arr[p, j] >= cfg.min_adx_1h_trend
                htf_ok = b1h_ok or (e21_1h_arr[p, j] >= e55_1h_arr[p, j] * 0.995)
                bull_c = px_p > o_arr[p, j]
                if allow_t:
                    filter_funnel["pass_allow_trend_regime"] += 1
                if vol_ok:
                    filter_funnel["pass_vol_edge_atr"] += 1
                if adx_ok:
                    filter_funnel["pass_adx_1h"] += 1
                if htf_ok:
                    filter_funnel["pass_htf"] += 1
                if px_p > e9_p > e21_p:
                    filter_funnel["pass_ema9_gt_ema21"] += 1
                if roc_arr[p, j] > 0.35:
                    filter_funnel["pass_roc10"] += 1
                if mh_p > 0.0 and mh_p > mh_p2:
                    filter_funnel["pass_macd_exp"] += 1
                if 48.0 <= rv_p <= 70.0:
                    filter_funnel["pass_rsi_band"] += 1
                if vr_p >= cfg.min_vol_rel_trend:
                    filter_funnel["pass_vrel_trend"] += 1
                if (
                    allow_t and vol_ok and adx_ok and htf_ok and bull_c
                    and (px_p > e9_p > e21_p) and (roc_arr[p, j] > 0.35)
                    and (mh_p > 0.0 and mh_p > mh_p2) and (48.0 <= rv_p <= 70.0)
                    and (0.50 <= pb_p <= 0.90) and (vr_p >= cfg.min_vol_rel_trend)
                    and (obv_arr[p, j] >= -0.08) and (e200d_arr[p, j] <= 0.35)
                ):
                    filter_funnel["pass_setup_trend_all"] += 1
                if (
                    vol_ok and (pb_p2 < 0.14) and (pb_p > 0.22) and bull_c
                    and (mh_p > mh_p2) and (px_p > e9_p * 0.996)
                    and (rv_p < 46.0) and (vr_p >= cfg.min_vol_rel_rebound)
                    and (obv_arr[p, j] >= -0.18)
                ):
                    filter_funnel["pass_setup_rebound_all"] += 1

        step_bot_a_microtrading(
            state=pf_a,
            ts=ts,
            coins=coins,
            bar_open_prev={coins[j]: float(o_arr[p, j]) for j in range(n_c)},
            bar_close_prev={coins[j]: float(c_arr[p, j]) for j in range(n_c)},
            bar_close_cur={coins[j]: float(c_arr[i, j]) for j in range(n_c)},
            bar_low_cur={coins[j]: float(l_arr[i, j]) for j in range(n_c)},
            bar_high_cur={coins[j]: float(h_arr[i, j]) for j in range(n_c)},
            atr_prev={coins[j]: float(atr_arr[p, j]) for j in range(n_c)},
            ema9_prev={coins[j]: float(e9_arr[p, j]) for j in range(n_c)},
            ema21_prev={coins[j]: float(e21_arr[p, j]) for j in range(n_c)},
            ema21_1h_prev={coins[j]: float(e21_1h_arr[p, j]) for j in range(n_c)},
            ema55_1h_prev={coins[j]: float(e55_1h_arr[p, j]) for j in range(n_c)},
            roc10_prev={coins[j]: float(roc_arr[p, j]) for j in range(n_c)},
            mh_prev={coins[j]: float(mh_arr[p, j]) for j in range(n_c)},
            mh_prev2={coins[j]: float(mh_arr[p2, j]) for j in range(n_c)},
            pb_prev={coins[j]: float(pb_arr[p, j]) for j in range(n_c)},
            pb_prev2={coins[j]: float(pb_arr[p2, j]) for j in range(n_c)},
            rsi_prev={coins[j]: float(rsi_arr[p, j]) for j in range(n_c)},
            vrel_prev={coins[j]: float(vrel_arr[p, j]) for j in range(n_c)},
            breadth_1h=float(b1h_arr[p]),
            cfg=cfg,
            adx_1h_prev={coins[j]: float(adx1h_arr[p, j]) for j in range(n_c)},
            obv_prev={coins[j]: float(obv_arr[p, j]) for j in range(n_c)},
            ema200_dist_prev={coins[j]: float(e200d_arr[p, j]) for j in range(n_c)},
            regime_code=reg_i,
            spread_bps_map=None,
            risk_mult=reg_mult_map.get(reg_i, 0.85),
        )
        pf_a["dates"].append(ts.strftime("%Y-%m-%d %H:%M"))
        invested_flags.append(any(pf_a["units"][c] > 1e-8 for c in coins))
        if collect_diag:
            for tr_new in pf_a["trades"][prev_n:]:
                if tr_new["side_type"] == "BUY":
                    regime_entry_counts[reg_i] = regime_entry_counts.get(reg_i, 0) + 1

    metrics = _compute_extended_metrics(
        pf_a["eq_curve"], pf_a["rets"], pf_a["trades"], invested_flags, pf_a["fees_cum"], 96.0 * 365.0, "BOT A · 15m/1H (365d)"
    )
    split = _compute_70_30_split(
        pf_a["eq_curve"], pf_a["rets"], pf_a["dates"][1:], pf_a["trades"], invested_flags, 96.0 * 365.0, "BOT A"
    )
    bench = _equal_weight_benchmark(close_15m, list(range(start_i - 1, len(idx))), 96.0 * 365.0, "Buy&Hold 1/8 [365d 15m]")
    out = {"metrics": metrics, "split_70_30": split, "benchmark": bench}
    if collect_diag:
        rate_by_reg = {
            reg: {
                "bars": int(cnt),
                "share_pct": round(100.0 * cnt / max(1, sum(regime_bar_counts.values())), 2),
                "buy_entries": int(regime_entry_counts.get(reg, 0)),
                "entry_rate_per_100_bars": round(100.0 * regime_entry_counts.get(reg, 0) / max(1, cnt), 3),
            }
            for reg, cnt in sorted(regime_bar_counts.items())
        }
        out["regime_signal_rate"] = rate_by_reg
        out["filter_funnel"] = filter_funnel
    return out


def _run_bot_b(coins: List[str], c1d: Dict[str, pd.DataFrame], gatekeeper_cfg: RiskGatekeeperConfig) -> Dict[str, Any]:
    d_slice = pd.DataFrame({c: c1d[c]["close"] for c in coins}).ffill().dropna()
    d_hi = pd.DataFrame({c: c1d[c]["high"] for c in coins}).reindex(d_slice.index).ffill()
    d_lo = pd.DataFrame({c: c1d[c]["low"] for c in coins}).reindex(d_slice.index).ffill()
    d_vol = pd.DataFrame({c: c1d[c]["volume"] for c in coins}).reindex(d_slice.index).ffill().fillna(1.0)
    d_vol_rel = d_vol / (d_vol.rolling(20, min_periods=5).mean() + 1e-9)
    d_rets = d_slice.pct_change().dropna()
    d_vols = compute_gjr_garch_vols(d_rets)
    sma20_d = d_slice.rolling(20, min_periods=5).mean().bfill()
    ema12_d = d_slice.ewm(span=12, adjust=False).mean()
    ema26_d = d_slice.ewm(span=26, adjust=False).mean()
    ema50_d = d_slice.ewm(span=50, adjust=False).mean()
    roc14_d = (d_slice.pct_change(14) * 100.0).fillna(0.0)
    peak15_d = d_slice.rolling(15, min_periods=3).max().bfill()
    macd_d_df = pd.DataFrame({c: compute_macd_pct(d_slice[c])[2] for c in coins})
    bb_pb_d = pd.DataFrame({c: compute_bollinger(d_slice[c], 20, 2.0)[3] for c in coins})
    atr_1d = pd.DataFrame({c: calc_atr(pd.DataFrame({"high": d_hi[c], "low": d_lo[c], "close": d_slice[c]}), 14) for c in coins})
    adx_1d = pd.DataFrame({c: calc_adx_di(pd.DataFrame({"high": d_hi[c], "low": d_lo[c], "close": d_slice[c]}), 14)[0] for c in coins})
    obv_1d = pd.DataFrame({c: calc_obv_slope(d_slice[c], d_vol[c], 14) for c in coins}, index=d_slice.index)
    btc_rel_1d = calc_structure_and_btc_metrics(d_slice, d_hi, d_lo, "BTC", 20)["btc_rel"]
    reg_series_1d = _build_causal_rolling_regimes(d_slice, adx_1d, refit_step=30, warmup=120, lookback=730, seed=42)

    start_loc = 121
    eval_dates = d_rets.index[start_loc:]
    anchor_dt = d_rets.index[start_loc - 1]
    pf_b: Dict[str, Any] = {
        "inception_utc": f"{eval_dates[0].strftime('%Y-%m-%d')} 00:00 UTC",
        "last_closed_bar": anchor_dt.strftime("%Y-%m-%d"),
        "cash_usd": 1000.0,
        "fees_cum": 0.0,
        "units": {c: 0.0 for c in coins},
        "entry": {c: 0.0 for c in coins},
        "entry_fee": {c: 0.0 for c in coins},
        "sl": {c: 0.0 for c in coins},
        "tp": {c: 0.0 for c in coins},
        "dates": [anchor_dt.strftime("%Y-%m-%d")],
        "eq_curve": [1000.0],
        "rets": [],
        "trades": [],
    }
    invested_flags: List[bool] = []
    for dt_b in eval_dates:
        prod_main._step_bot_b_closed_bar(
            pf_b, dt_b, coins, d_slice, d_lo, d_hi, d_rets, d_vols, d_vol_rel,
            sma20_d, ema12_d, ema26_d, ema50_d, roc14_d, peak15_d, macd_d_df, bb_pb_d, atr_1d, adx_1d,
            obv_1d=obv_1d, btc_rel_1d=btc_rel_1d, regime_series_1d=reg_series_1d, gatekeeper_cfg=gatekeeper_cfg,
        )
        invested_flags.append(any(pf_b["units"][c] > 1e-8 for c in coins))

    metrics = _compute_extended_metrics(
        pf_b["eq_curve"], pf_b["rets"], pf_b["trades"], invested_flags, pf_b["fees_cum"], 365.0, "BOT B · 1D (1940d)"
    )
    split = _compute_70_30_split(
        pf_b["eq_curve"], pf_b["rets"], pf_b["dates"][1:], pf_b["trades"], invested_flags, 365.0, "BOT B"
    )
    eval_slice_idx = [int(d_slice.index.get_loc(anchor_dt))] + [int(d_slice.index.get_loc(d)) for d in eval_dates]
    bench = _equal_weight_benchmark(d_slice, eval_slice_idx, 365.0, "Buy&Hold 1/8 [1940d 1D]")
    return {"metrics": metrics, "split_70_30": split, "benchmark": bench, "regime_counts_1d": reg_series_1d.loc[eval_dates].value_counts().to_dict()}


def _run_bots_c_d(
    coins: List[str],
    c4h: Dict[str, pd.DataFrame],
    funding_hist: Dict[str, pd.Series],
    gatekeeper_cfg: RiskGatekeeperConfig,
) -> Tuple[Dict[str, Any], Dict[str, Any], pd.Series]:
    close_4h = pd.DataFrame({c: c4h[c]["close"] for c in coins}).ffill().dropna()
    open_4h = pd.DataFrame({c: c4h[c]["open"] for c in coins}).reindex(close_4h.index).ffill()
    high_4h = pd.DataFrame({c: c4h[c]["high"] for c in coins}).reindex(close_4h.index).ffill()
    low_4h = pd.DataFrame({c: c4h[c]["low"] for c in coins}).reindex(close_4h.index).ffill()
    vol_4h = pd.DataFrame({c: c4h[c]["volume"] for c in coins}).reindex(close_4h.index).ffill().fillna(1.0)
    vol_rel_4h = vol_4h / (vol_4h.rolling(20, min_periods=5).mean() + 1e-9)
    atr_4h = pd.DataFrame({c: calc_atr(c4h[c], 14) for c in coins}).reindex(close_4h.index).ffill().bfill()
    rsi_4h = pd.DataFrame({c: calc_rsi(close_4h[c], 14) for c in coins}).bfill()
    stoch_4h = pd.DataFrame({c: calc_stoch_k(c4h[c], 14, 3) for c in coins}).reindex(close_4h.index).bfill()
    ema9_4h = close_4h.ewm(span=9, adjust=False).mean()
    ema21_4h = close_4h.ewm(span=21, adjust=False).mean()
    ema55_4h = close_4h.ewm(span=55, adjust=False).mean()
    roc12_4h = (close_4h.pct_change(12) * 100.0).fillna(0.0)
    roc24_4h = (close_4h.pct_change(24) * 100.0).fillna(0.0)
    macd_h_4h = pd.DataFrame({c: compute_macd_pct(close_4h[c])[2] for c in coins})
    bb_pctb_4h = pd.DataFrame({c: compute_bollinger(close_4h[c], 20, 2.0)[3] for c in coins})
    bb_bw_4h = pd.DataFrame({c: compute_bollinger(close_4h[c], 20, 2.0)[4] for c in coins})

    adx_4h = pd.DataFrame(index=close_4h.index, columns=coins, dtype=float)
    pdi_4h = pd.DataFrame(index=close_4h.index, columns=coins, dtype=float)
    mdi_4h = pd.DataFrame(index=close_4h.index, columns=coins, dtype=float)
    for c in coins:
        a_v, p_v, m_v = calc_adx_di(c4h[c], 14)
        adx_4h[c] = a_v.reindex(close_4h.index).bfill()
        pdi_4h[c] = p_v.reindex(close_4h.index).bfill()
        mdi_4h[c] = m_v.reindex(close_4h.index).bfill()

    obv_4h = pd.DataFrame({c: calc_obv_slope(close_4h[c], vol_4h[c], 14) for c in coins}, index=close_4h.index)
    struct_4h = calc_structure_and_btc_metrics(close_4h, high_4h, low_4h, "BTC", 20)
    ema200_dist_4h = struct_4h["ema200_dist"]
    range_pos_4h = struct_4h["range_pos"]
    rsi_accel_4h = struct_4h["rsi_accel"]
    btc_rel_4h = struct_4h["btc_rel"]
    tb_labels_4h, tb_rets_4h = compute_triple_barrier_labels(
        close_4h, high_4h, low_4h, atr_4h, horizon=4, tp_atr_mult=1.80, sl_atr_mult=1.40, roundtrip_fee=SETTINGS.spot_fee_rate * 2.0
    )

    reg_series_4h = _build_causal_rolling_regimes(close_4h, adx_4h, refit_step=42, warmup=200, lookback=960, seed=42)

    funding_df_4h = pd.DataFrame(0.0001, index=close_4h.index, columns=coins, dtype=float)
    for c in coins:
        s_fr = funding_hist.get(c)
        if isinstance(s_fr, pd.Series) and len(s_fr) > 0:
            aligned = s_fr.reindex(close_4h.index.union(s_fr.index)).sort_index().ffill().reindex(close_4h.index)
            funding_df_4h[c] = aligned.fillna(0.0001)

    eval_start = 420
    anchor_ts = close_4h.index[eval_start - 1]
    pf_c: Dict[str, Any] = {
        "inception_utc": anchor_ts.strftime("%Y-%m-%d %H:%M UTC"),
        "last_closed_bar": anchor_ts.strftime("%Y-%m-%d %H:%M"),
        "bar_step": 0,
        "realized_cash_c": 1000.0,
        "fees_cum": 0.0,
        "units": {c: 0.0 for c in coins},
        "entry": {c: 0.0 for c in coins},
        "entry_fee": {c: 0.0 for c in coins},
        "sl": {c: 0.0 for c in coins},
        "tp": {c: 0.0 for c in coins},
        "peak": {c: 0.0 for c in coins},
        "cooldown_step": {c: -1 for c in coins},
        "dates": [anchor_ts.strftime("%Y-%m-%d %H:%M")],
        "eq_curve": [1000.0],
        "rets": [],
        "trades": [],
    }

    # Pre-extraer tabla de features para entrenamiento O(1) en refits cada 180 barras 4H
    feat_rows_by_bar: Dict[int, Tuple[List[np.ndarray], List[int], List[float]]] = {}
    for ii in range(205, len(close_4h)):
        x_list, yc_list, yr_list = [], [], []
        for c in coins:
            cls_v = tb_labels_4h.iloc[ii][c]
            ret_v = tb_rets_4h.iloc[ii][c]
            if not (np.isnan(cls_v) or np.isnan(ret_v)):
                x_list.append(
                    extract_ta_features_row(
                        ii, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                        roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h,
                        obv_slope_df=obv_4h, ema200_dist_df=ema200_dist_4h,
                        range_pos_df=range_pos_4h, btc_rel_df=btc_rel_4h, rsi_accel_df=rsi_accel_4h,
                    )
                )
                yc_list.append(int(cls_v))
                yr_list.append(float(ret_v))
        if x_list:
            feat_rows_by_bar[ii] = (x_list, yc_list, yr_list)

    def _fit_champ(up_to_bar: int, prev_champ: Optional[Dict[str, Any]], tag: str) -> Dict[str, Any]:
        xs, ycs, yrs = [], [], []
        for ii in range(max(205, up_to_bar - 600), up_to_bar - 5):
            row = feat_rows_by_bar.get(ii)
            if row is not None:
                xs.extend(row[0])
                ycs.extend(row[1])
                yrs.extend(row[2])
        chall = fit_supervised_3class_ensemble(
            np.asarray(xs[-3600:]), np.asarray(ycs[-3600:]), np.asarray(yrs[-3600:]), purge_samples=32, seed=101
        )
        champ, _ = govern_champion_challenger(prev_champ, chall, tag)
        return champ

    champ_d = _fit_champ(eval_start, None, anchor_ts.strftime("%Y-%m-%d %H:%M"))
    pf_d: Dict[str, Any] = {
        "inception_utc": anchor_ts.strftime("%Y-%m-%d %H:%M UTC"),
        "last_closed_bar": anchor_ts.strftime("%Y-%m-%d %H:%M"),
        "cash_usd": 1000.0,
        "fees_cum": 0.0,
        "units": {c: 0.0 for c in coins},
        "entry": {c: 0.0 for c in coins},
        "entry_fee": {c: 0.0 for c in coins},
        "partial_taken": {c: False for c in coins},
        "peak": {c: 0.0 for c in coins},
        "sl": {c: 0.0 for c in coins},
        "tp": {c: 0.0 for c in coins},
        "dates": [anchor_ts.strftime("%Y-%m-%d %H:%M")],
        "eq_curve": [1000.0],
        "rets": [],
        "trades": [],
        "veto_count": 0,
    }

    inv_c: List[bool] = []
    inv_d: List[bool] = []
    retrain_count = 0

    for idx_i in range(eval_start, len(close_4h)):
        prev_ts = close_4h.index[idx_i - 1]
        ts = close_4h.index[idx_i]
        fr_vec = funding_df_4h.loc[prev_ts].values
        prod_main._step_bot_c_closed_bar(
            pf_c, idx_i, coins, close_4h, low_4h, high_4h,
            ema21_4h, ema55_4h, roc24_4h, macd_h_4h, bb_pctb_4h,
            adx_4h, pdi_4h, mdi_4h, atr_4h, vol_rel_4h, fr_vec,
            oi_vol_ratio_vec=None, obv_4h=obv_4h, regime_series_4h=reg_series_4h,
            gatekeeper_cfg=gatekeeper_cfg,
        )
        inv_c.append(any(abs(float(pf_c["units"][c])) > 1e-8 for c in coins))

        if (idx_i - eval_start) > 0 and (idx_i - eval_start) % 180 == 0:
            champ_d = _fit_champ(idx_i, champ_d, ts.strftime("%Y-%m-%d %H:%M"))
            retrain_count += 1

        prod_main._step_bot_d_closed_bar(
            pf_d, idx_i, coins, open_4h, close_4h, low_4h, high_4h,
            ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
            roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, atr_4h, vol_rel_4h,
            champ_d, obv_4h=obv_4h, ema200_dist_4h=ema200_dist_4h,
            range_pos_4h=range_pos_4h, btc_rel_4h=btc_rel_4h, rsi_accel_4h=rsi_accel_4h,
            regime_series_4h=reg_series_4h, regime_probs=None,
            spread_bps_map=None, cross_bps_map=None, gatekeeper_cfg=gatekeeper_cfg,
        )
        inv_d.append(any(float(pf_d["units"][c]) > 1e-8 for c in coins))

    bench_4h = _equal_weight_benchmark(close_4h, list(range(eval_start - 1, len(close_4h))), 6.0 * 365.0, "Buy&Hold 1/8 [1095d 4H]")
    res_c = {
        "metrics": _compute_extended_metrics(pf_c["eq_curve"], pf_c["rets"], pf_c["trades"], inv_c, pf_c["fees_cum"], 6.0 * 365.0, "BOT C · 4H Swap (1095d)"),
        "split_70_30": _compute_70_30_split(pf_c["eq_curve"], pf_c["rets"], pf_c["dates"][1:], pf_c["trades"], inv_c, 6.0 * 365.0, "BOT C"),
        "benchmark": bench_4h,
    }
    res_d = {
        "metrics": _compute_extended_metrics(pf_d["eq_curve"], pf_d["rets"], pf_d["trades"], inv_d, pf_d["fees_cum"], 6.0 * 365.0, "BOT D · 4H Ensemble (1095d)"),
        "split_70_30": _compute_70_30_split(pf_d["eq_curve"], pf_d["rets"], pf_d["dates"][1:], pf_d["trades"], inv_d, 6.0 * 365.0, "BOT D"),
        "benchmark": bench_4h,
        "retrain_count": retrain_count,
        "veto_count": int(pf_d.get("veto_count", 0)),
        "regime_counts_4h": reg_series_4h.iloc[eval_start:].value_counts().to_dict(),
    }
    return res_c, res_d, reg_series_4h


def _format_markdown_report(rep: Dict[str, Any]) -> str:
    lines = [
        "# Backtesting Walk-Forward Multianual por Bot (Fase 4)",
        "",
        f"- **Generado (UTC):** `{rep['generated_utc']}`",
        f"- **Fuente histórica:** KuCoin API v1 (`BTC, ETH, SOL, BNB, XRP, ADA, AVAX, LINK`)",
        "- **Ventanas evaluadas:** BOT A (`15m/1H`, 365 días), BOT B (`1D`, 1,940 días), BOT C y BOT D (`4H`, 1,095 días)",
        "",
        "## 1. Desempeño Global por Bot vs Buy & Hold Equiponderado (Base $1,000.00)",
        "",
        "| Estrategia | Ventana | Retorno Neto | CAGR | Sharpe | Sortino | MaxDD | Calmar | PF | Win Rate | Expectancy/Trade (IC 95% Bootstrap) | Órdenes (Salidas) | Turnover Anual | Comisiones | Tiempo en Mercado | Benchmark B&H |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bk, label in [("bot_a", "BOT A (15m)"), ("bot_b", "BOT B (1D)"), ("bot_c", "BOT C (4H Swap)"), ("bot_d", "BOT D (4H ML)")]:
        m = rep["bots"][bk]["metrics"]
        bm = rep["bots"][bk]["benchmark"]
        ci = m["bootstrap_expectancy_ci95"]
        lines.append(
            f"| {label} | {m['label'].split('(')[-1].rstrip(')')} | {m['total_return_pct']:+.2f}% | "
            f"{m['cagr_pct']:+.2f}% | {m['sharpe']:.2f} | {m['sortino']:.2f} | {m['max_drawdown_pct']:.2f}% | "
            f"{m['calmar']:.2f} | {m['profit_factor']:.2f} | {m['win_rate_pct']:.1f}% | "
            f"{m['expectancy_pct']:+.3f}% [{ci['ci95_low_pct']:+.3f}%, {ci['ci95_high_pct']:+.3f}%] | "
            f"{m['total_orders']} ({m['closed_exits']}) | {m['turnover_annual_x']:.2f}x | ${m['fees_paid_usd']:.2f} | "
            f"{m['time_in_market_pct']:.1f}% | {bm['total_return_pct']:+.2f}% (MaxDD {bm['max_drawdown_pct']:.2f}%) |"
        )

    lines.extend([
        "",
        "## 2. Validación Cronológica 70% In-Sample / 30% Out-of-Sample",
        "",
        "| Bot | Corte 70/30 | IS Retorno | IS Sharpe | IS MaxDD | IS Órdenes | OOS Retorno | OOS Sharpe | OOS MaxDD | OOS PF | OOS Expectancy | OOS B&H Retorno |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for bk, label in [("bot_a", "BOT A"), ("bot_b", "BOT B"), ("bot_c", "BOT C"), ("bot_d", "BOT D")]:
        sp = rep["bots"][bk]["split_70_30"]
        bm = rep["bots"][bk]["benchmark"]
        is_m, oos_m = sp["in_sample_70"], sp["out_of_sample_30"]
        lines.append(
            f"| {label} | `{sp['split_boundary']}` | {is_m['total_return_pct']:+.2f}% | {is_m['sharpe']:.2f} | {is_m['max_drawdown_pct']:.2f}% | "
            f"{is_m['total_orders']} | {oos_m['total_return_pct']:+.2f}% | {oos_m['sharpe']:.2f} | {oos_m['max_drawdown_pct']:.2f}% | "
            f"{oos_m['profit_factor']:.2f} | {oos_m['expectancy_pct']:+.3f}% | {bm['out_of_sample_30']['total_return_pct']:+.2f}% |"
        )

    lines.extend([
        "",
        "## 3. Diagnóstico de Frecuencia de BOT A por Régimen GMM y Embudo de Filtros (365d · 15m)",
        "",
        "| Régimen GMM | Velas 15m | % Tiempo | Entradas BUY | Tasa Entradas / 100 Velas |",
        "|---|---:|---:|---:|---:|",
    ])
    for reg, info in rep["bots"]["bot_a"]["regime_signal_rate"].items():
        lines.append(f"| `{reg}` | {info['bars']} | {info['share_pct']:.2f}% | {info['buy_entries']} | {info['entry_rate_per_100_bars']:.3f} |")

    ff = rep["bots"]["bot_a"]["filter_funnel"]
    tot_cb = max(1, ff["coin_bars_total"])
    lines.extend([
        "",
        f"- **Evaluaciones moneda-vela 15m:** {tot_cb:,}",
        f"- Pasa régimen tendencia (`!Bajista & !Lateral`): **{ff['pass_allow_trend_regime']:,}** ({100.0 * ff['pass_allow_trend_regime'] / tot_cb:.2f}%)",
        f"- Pasa ATR >= {BotAConfig().min_atr_pct*100:.2f}%: **{ff['pass_vol_edge_atr']:,}** ({100.0 * ff['pass_vol_edge_atr'] / tot_cb:.2f}%)",
        f"- Pasa ADX 1H >= {BotAConfig().min_adx_1h_trend:.1f}: **{ff['pass_adx_1h']:,}** ({100.0 * ff['pass_adx_1h'] / tot_cb:.2f}%)",
        f"- Pasa estructura `Close > EMA9 > EMA21`: **{ff['pass_ema9_gt_ema21']:,}** ({100.0 * ff['pass_ema9_gt_ema21'] / tot_cb:.2f}%)",
        f"- Pasa MACD > 0 y creciente: **{ff['pass_macd_exp']:,}** ({100.0 * ff['pass_macd_exp'] / tot_cb:.2f}%)",
        f"- Pasa RSI [48, 70]: **{ff['pass_rsi_band']:,}** ({100.0 * ff['pass_rsi_band'] / tot_cb:.2f}%)",
        f"- Pasa Volumen >= {BotAConfig().min_vol_rel_trend:.2f}x: **{ff['pass_vrel_trend']:,}** ({100.0 * ff['pass_vrel_trend'] / tot_cb:.2f}%)",
        f"- Señal completa `setup_trend`: **{ff['pass_setup_trend_all']:,}** ({100.0 * ff['pass_setup_trend_all'] / tot_cb:.4f}%)",
        f"- Señal completa `setup_bb_reclaim`: **{ff['pass_setup_rebound_all']:,}** ({100.0 * ff['pass_setup_rebound_all'] / tot_cb:.4f}%)",
        "",
        "## 4. Análisis de Sensibilidad Univariante de BOT A (`dataclasses.replace`)",
        "",
        "| Parámetro / Valor | Retorno Neto | CAGR | Sharpe | MaxDD | PF | Win Rate | Órdenes | Expectancy | OOS 30% Ret | Tiempo Invertido |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rep["bot_a_sensitivity"]:
        m = row["metrics"]
        oos = row["oos_30"]
        lines.append(
            f"| `{row['param']}={row['value']}` | {m['total_return_pct']:+.2f}% | {m['cagr_pct']:+.2f}% | {m['sharpe']:.2f} | "
            f"{m['max_drawdown_pct']:.2f}% | {m['profit_factor']:.2f} | {m['win_rate_pct']:.1f}% | {m['total_orders']} | "
            f"{m['expectancy_pct']:+.3f}% | {oos['total_return_pct']:+.2f}% | {m['time_in_market_pct']:.1f}% |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    t0 = time.monotonic()
    coins = list(COIN_NAMES.keys())
    oracle = MultiExchangeCryptoOracle(
        okx_base=SETTINGS.okx_base,
        bybit_base=SETTINGS.bybit_base,
        kucoin_base=SETTINGS.kucoin_base,
    )
    print("=== [FASE 4] DESCARGANDO/CARGANDO CACHÉ KUCOIN + FUNDING OKX ===")
    c15 = _fetch_kucoin_paginated_cached(oracle, coins, "15m", 365)
    c1h = _fetch_kucoin_paginated_cached(oracle, coins, "1H", 365)
    c4h = _fetch_kucoin_paginated_cached(oracle, coins, "4H", 1095)
    c1d = _fetch_kucoin_paginated_cached(oracle, coins, "1D", 1940)
    funding_hist = _fetch_funding_cached(oracle, coins, days=50)
    print(f"Series listas en {time.monotonic() - t0:.1f}s | 15m={len(c15['BTC'])}, 1H={len(c1h['BTC'])}, 4H={len(c4h['BTC'])}, 1D={len(c1d['BTC'])}")

    gatekeeper_cfg = RiskGatekeeperConfig()

    print("=== [FASE 4] EJECUTANDO BOT C y BOT D (4H · 1095d) ===")
    res_c, res_d, reg_series_4h = _run_bots_c_d(coins, c4h, funding_hist, gatekeeper_cfg)
    print(f"BOT C listo: Ret={res_c['metrics']['total_return_pct']:+.2f}% | BOT D listo: Ret={res_d['metrics']['total_return_pct']:+.2f}%")

    print("=== [FASE 4] EJECUTANDO BOT B (1D · 1940d) ===")
    res_b = _run_bot_b(coins, c1d, gatekeeper_cfg)
    print(f"BOT B listo: Ret={res_b['metrics']['total_return_pct']:+.2f}%")

    print("=== [FASE 4] PREPARANDO PANEL BOT A (15m/1H · 365d) Y SENSIBILIDAD ===")
    panel_a = _prepare_bot_a_panel(coins, c15, c1h, reg_series_4h)
    base_cfg_a = BotAConfig()
    res_a = _run_bot_a(panel_a, coins, base_cfg_a, collect_diag=True)
    print(f"BOT A baseline listo: Ret={res_a['metrics']['total_return_pct']:+.2f}% | Orders={res_a['metrics']['total_orders']}")

    sensitivity_grid = [
        ("baseline", "default", {}),
        ("fee_rate", 0.0004, {"fee_rate": 0.0004}),
        ("fee_rate", 0.0012, {"fee_rate": 0.0012}),
        ("fee_rate", 0.0020, {"fee_rate": 0.0020}),
        ("min_vol_rel_trend", 0.95, {"min_vol_rel_trend": 0.95}),
        ("min_vol_rel_trend", 1.08, {"min_vol_rel_trend": 1.08}),
        ("min_vol_rel_trend", 1.25, {"min_vol_rel_trend": 1.25}),
        ("min_adx_1h_trend", 16.0, {"min_adx_1h_trend": 16.0}),
        ("min_adx_1h_trend", 20.0, {"min_adx_1h_trend": 20.0}),
        ("min_adx_1h_trend", 24.0, {"min_adx_1h_trend": 24.0}),
        ("min_atr_pct", 0.0042, {"min_atr_pct": 0.0042}),
        ("min_atr_pct", 0.0060, {"min_atr_pct": 0.0060}),
        ("min_atr_pct", 0.0075, {"min_atr_pct": 0.0075}),
        ("sl_atr_mult", 1.55, {"sl_atr_mult": 1.55}),
        ("sl_atr_mult", 2.00, {"sl_atr_mult": 2.00}),
        ("sl_atr_mult", 2.30, {"sl_atr_mult": 2.30}),
    ]
    sens_results = []
    if "--skip-sensitivity" not in sys.argv:
        for p_name, p_val, kwargs in sensitivity_grid:
            cfg_i = replace(base_cfg_a, **kwargs)
            r_i = _run_bot_a(panel_a, coins, cfg_i, collect_diag=False)
            sens_results.append({
                "param": p_name,
                "value": p_val,
                "cfg": asdict(cfg_i),
                "metrics": r_i["metrics"],
                "oos_30": r_i["split_70_30"]["out_of_sample_30"],
            })

    report = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_seconds": round(time.monotonic() - t0, 1),
        "data_bars": {"15m": len(c15["BTC"]), "1H": len(c1h["BTC"]), "4H": len(c4h["BTC"]), "1D": len(c1d["BTC"])},
        "bots": {"bot_a": res_a, "bot_b": res_b, "bot_c": res_c, "bot_d": res_d},
        "bot_a_sensitivity": sens_results,
    }
    REPORT_JSON_PATH.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    ARTIFACT_MD_PATH.write_text(_format_markdown_report(report), encoding="utf-8")
    print(f"=== [FASE 4] COMPLETADA EN {report['elapsed_seconds']}s -> {REPORT_JSON_PATH} ===")


if __name__ == "__main__":
    main()

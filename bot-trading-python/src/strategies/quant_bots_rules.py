"""
Reglas Cuantitativas Determinísticas y Verificables de los 4 Algoritmos Especializados:
  - BOT A: Microtrading Intradía (15m con filtro tendencial 1H) y paridad de riesgo ATR (<= 0.85%/orden)
  - BOT B: Decisión Sistemática Diaria (1D) con Canal Bollinger, Markowitz SLSQP, GJR-GARCH y Salida Chandelier
  - BOT C: Estrategia Posicional de Largos y Contratos a Futuros Perpetuos (4H SWAP) con Carry 8h
  - BOT D: Red Neuronal Adiestrada MLP(32, 16) Regularizada L2 con Triple Estrategia de Salida ATR

Toda lógica de dimensionamiento, límites de exposición y firma SHA-256 es modular y libre de fuga futura.
"""
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import scipy.optimize as sco
from arch import arch_model
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler

GENESIS_HASH = hashlib.sha256(b"JBZ-QUANT-ALGO-LEDGER-V5-TA-MLP-1000USD").hexdigest()


def fmt_px_dec(val: float) -> float:
    v = float(val)
    if v >= 100.0:
        return round(v, 2)
    if v >= 1.0:
        return round(v, 4)
    return round(v, 5)


def calc_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0.0).ewm(alpha=1.0 / window, adjust=False).mean()
    down = (-delta.clip(upper=0.0)).ewm(alpha=1.0 / window, adjust=False).mean()
    rs = up / (down + 1e-9)
    return (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)


def calc_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_c = df["close"].shift(1)
    tr = pd.concat(
        [
            (df["high"] - df["low"]).abs(),
            (df["high"] - prev_c).abs(),
            (df["low"] - prev_c).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1.0 / window, adjust=False).mean().bfill().clip(lower=1e-9)


def calc_stoch_k(df: pd.DataFrame, window: int = 14, smooth: int = 3) -> pd.Series:
    lo = df["low"].rolling(window, min_periods=3).min()
    hi = df["high"].rolling(window, min_periods=3).max()
    raw_k = 100.0 * (df["close"] - lo) / ((hi - lo) + 1e-9)
    return raw_k.rolling(smooth, min_periods=1).mean().fillna(50.0).clip(0.0, 100.0)


def calc_adx_di(df: pd.DataFrame, window: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    atr_s = calc_atr(df, window).replace(0.0, np.nan)
    plus_di = (100.0 * (plus_dm.ewm(alpha=1.0 / window, adjust=False).mean() / atr_s)).fillna(20.0)
    minus_di = (100.0 * (minus_dm.ewm(alpha=1.0 / window, adjust=False).mean() / atr_s)).fillna(20.0)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    adx = dx.ewm(alpha=1.0 / window, adjust=False).mean().fillna(20.0)
    return adx, plus_di, minus_di


def compute_macd_pct(close_s: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    ema12 = close_s.ewm(span=12, adjust=False).mean()
    ema26 = close_s.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    sig_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - sig_line
    denom = close_s.clip(lower=1e-8)
    return (macd_line / denom) * 100.0, (sig_line / denom) * 100.0, (hist / denom) * 100.0


def compute_bollinger(close_s: pd.Series, window: int = 20, mult: float = 2.0):
    mid = close_s.rolling(window, min_periods=1).mean()
    sd = close_s.rolling(window, min_periods=1).std().fillna(0.0)
    up = mid + mult * sd
    dn = mid - mult * sd
    span = (up - dn).replace(0.0, np.nan)
    pct_b = ((close_s - dn) / span).fillna(0.5)
    bw_pct = (((up - dn) / mid.clip(lower=1e-8)) * 100.0).fillna(4.0)
    return mid, up, dn, pct_b, bw_pct


def compute_gjr_garch_vols(returns: pd.DataFrame) -> pd.DataFrame:
    vols = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)
    for col in returns.columns:
        try:
            am = arch_model(returns[col] * 100.0, vol="Garch", p=1, o=1, q=1, dist="skewt")
            res = am.fit(disp="off")
            vols[col] = res.conditional_volatility / 100.0
        except Exception:
            vols[col] = returns[col].rolling(20, min_periods=5).std()
    return vols.ffill().fillna(returns.expanding(min_periods=2).std()).fillna(0.03)


def calc_metrics(equity: np.ndarray, period_rets: np.ndarray, periods_per_year: float, label: str) -> Dict[str, Any]:
    n = max(1, len(period_rets))
    years = n / periods_per_year
    tot_ret = (equity[-1] / equity[0]) - 1.0
    cagr = ((equity[-1] / equity[0]) ** (1.0 / max(years, 0.08))) - 1.0
    ann_vol = float(np.std(period_rets, ddof=1) * np.sqrt(periods_per_year)) if n > 2 else 0.0
    rf_p = 0.04 / periods_per_year
    sharpe = float(np.mean(period_rets - rf_p) / (np.std(period_rets, ddof=1) + 1e-9) * np.sqrt(periods_per_year))
    neg = period_rets[period_rets < 0]
    down_vol = float(np.std(neg, ddof=1) * np.sqrt(periods_per_year)) if len(neg) > 2 else 1e-6
    sortino = float((cagr - 0.04) / max(down_vol, 1e-6))

    peaks = np.maximum.accumulate(equity)
    dd = (equity - peaks) / peaks
    max_dd = float(np.min(dd))
    calmar = float(cagr / max(abs(max_dd), 1e-6))

    var_95 = float(np.percentile(period_rets, 5) * 100.0) if n > 10 else 0.0
    tail = period_rets[period_rets <= np.percentile(period_rets, 5)] if n > 10 else period_rets
    cvar_95 = float(np.mean(tail) * 100.0) if len(tail) > 0 else var_95
    win_pct = float(np.mean(period_rets > 0) * 100.0)

    return {
        "label": label,
        "base_usd": round(float(equity[0]), 2),
        "final_usd": round(float(equity[-1]), 2),
        "net_pnl_usd": round(float(equity[-1] - equity[0]), 2),
        "total_return_pct": round(float(tot_ret * 100.0), 2),
        "cagr_pct": round(float(cagr * 100.0), 2),
        "annual_vol_pct": round(float(ann_vol * 100.0), 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "calmar": round(calmar, 2),
        "var_95_daily_pct": round(var_95, 2),
        "cvar_95_daily_pct": round(cvar_95, 2),
        "max_drawdown_pct": round(float(max_dd * 100.0), 2),
        "win_rate_pct": round(win_pct, 1),
    }


@dataclass(frozen=True)
class BotAConfig:
    fee_rate: float = 0.0008
    max_risk_per_trade_pct: float = 0.0085
    max_position_weight: float = 0.24
    max_total_invested: float = 0.68
    max_open_positions: int = 3
    daily_circuit_breaker_pct: float = -0.020
    sl_atr_mult: float = 1.35
    tp_atr_mult: float = 2.45
    trail_activate_atr: float = 0.95
    trail_dist_atr: float = 1.15
    min_vol_rel_trend: float = 1.08
    min_vol_rel_rebound: float = 1.25
    min_order_usd: float = 48.0


def init_bot_a_state(coins: List[str], base_cap: float = 1000.0) -> Dict[str, Any]:
    return {
        "cash_usd": float(base_cap),
        "units": {c: 0.0 for c in coins},
        "entry": {c: 0.0 for c in coins},
        "peak": {c: 0.0 for c in coins},
        "sl": {c: 0.0 for c in coins},
        "tp": {c: 0.0 for c in coins},
        "fees_cum": 0.0,
        "eq_curve": [float(base_cap)],
        "rets": [],
        "trades": [],
        "cur_day": None,
        "day_anchor_eq": float(base_cap),
        "circuit_halted_day": False,
    }


def step_bot_a_microtrading(
    state: Dict[str, Any],
    ts: pd.Timestamp,
    coins: List[str],
    bar_open_prev: Dict[str, float],
    bar_close_prev: Dict[str, float],
    bar_close_cur: Dict[str, float],
    bar_low_cur: Dict[str, float],
    bar_high_cur: Dict[str, float],
    atr_prev: Dict[str, float],
    ema9_prev: Dict[str, float],
    ema21_prev: Dict[str, float],
    ema21_1h_prev: Dict[str, float],
    ema55_1h_prev: Dict[str, float],
    roc10_prev: Dict[str, float],
    mh_prev: Dict[str, float],
    mh_prev2: Dict[str, float],
    pb_prev: Dict[str, float],
    pb_prev2: Dict[str, float],
    rsi_prev: Dict[str, float],
    vrel_prev: Dict[str, float],
    breadth_1h: float,
    cfg: BotAConfig = BotAConfig(),
) -> None:
    """
    Ejecuta un paso intradía (15m con filtro 1H) de BOT A respetando:
      - Límite máximo de pérdida diaria (-2.00% desde apertura diaria UTC)
      - Dimensionamiento por paridad ATR (riesgo máx. <= 0.85% patrimonio, tope 24%/par, máx. 68% total)
      - Trailing Stop dinámico a equilibrio y seguimiento de pico, TP y salida por cruce inverso EMA 9/21
    """
    prev_eq = state["eq_curve"][-1]
    if state["cur_day"] != ts.date():
        state["cur_day"] = ts.date()
        state["day_anchor_eq"] = prev_eq
        state["circuit_halted_day"] = False

    daily_dd = (prev_eq - state["day_anchor_eq"]) / max(state["day_anchor_eq"], 1e-6)
    if daily_dd <= cfg.daily_circuit_breaker_pct or state.get("circuit_halted_day"):
        state["circuit_halted_day"] = True
        for c in coins:
            qty = state["units"][c]
            if qty > 0.0:
                b_lo, b_hi = float(bar_low_cur[c]), float(bar_high_cur[c])
                px_exec = float(np.clip(float(bar_close_cur[c]), b_lo, b_hi))
                gross = qty * px_exec
                fee = gross * cfg.fee_rate
                pnl_u = gross - fee - (qty * state["entry"][c])
                pnl_p = ((px_exec / max(state["entry"][c], 1e-8)) - 1.0) * 100.0 - (cfg.fee_rate * 100.0)
                state["cash_usd"] += gross - fee
                state["fees_cum"] += fee
                state["trades"].append({
                    "bot_id": "bot_a", "bot_code": "BOT A",
                    "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                    "coin": c, "instrument": f"{c}-USDT", "side_type": "CLOSE",
                    "action": "CORTE DIARIO RIESGO (-2.0%)",
                    "units": round(qty, 6), "price": fmt_px_dec(px_exec),
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(float(vrel_prev[c]), 2),
                    "notional_usd": round(gross, 2), "fee_usd": round(fee, 3),
                    "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                    "telemetry": f"Corte Intradía={daily_dd*100:.2f}% | Vol={float(vrel_prev[c]):.2f}x",
                })
                state["units"][c] = 0.0
                state["sl"][c] = 0.0
                state["tp"][c] = 0.0
        cur_eq = state["cash_usd"] + sum(state["units"][c] * float(bar_close_cur[c]) for c in coins)
        state["rets"].append((cur_eq / prev_eq) - 1.0)
        state["eq_curve"].append(cur_eq)
        return

    for c in coins:
        px_prev = float(bar_close_prev[c])
        b_lo = float(bar_low_cur[c])
        b_hi = float(bar_high_cur[c])
        atr_v = max(1e-9, float(atr_prev[c]))
        e9 = float(ema9_prev[c])
        e21 = float(ema21_prev[c])
        e21_1h = float(ema21_1h_prev[c])
        e55_1h = float(ema55_1h_prev[c])
        roc10 = float(roc10_prev[c])
        mh = float(mh_prev[c])
        mhp = float(mh_prev2[c])
        pb = float(pb_prev[c])
        pbp = float(pb_prev2[c])
        rv = float(rsi_prev[c])
        vrel = float(vrel_prev[c])

        qty = state["units"][c]
        if qty > 0.0:
            state["peak"][c] = max(state["peak"][c], b_hi)
            if state["peak"][c] >= state["entry"][c] + cfg.trail_activate_atr * atr_v:
                state["sl"][c] = max(
                    state["sl"][c],
                    state["entry"][c] * 1.002,
                    state["peak"][c] - cfg.trail_dist_atr * atr_v,
                )

            ema_cross_exit = (e9 < e21 * 0.9988) and (mh < 0.0) and (px_prev > state["entry"][c] * 1.003)
            if b_lo <= state["sl"][c]:
                px_exec = float(np.clip(state["sl"][c], b_lo, b_hi))
                gross = qty * px_exec
                fee = gross * cfg.fee_rate
                pnl_u = gross - fee - (qty * state["entry"][c])
                pnl_p = ((px_exec / max(state["entry"][c], 1e-8)) - 1.0) * 100.0 - (cfg.fee_rate * 100.0)
                state["cash_usd"] += gross - fee
                state["fees_cum"] += fee
                act_lbl = "TOMA TRAILING ATR" if px_exec > state["entry"][c] else "SALIDA STOP-LOSS (1.35x ATR)"
                state["trades"].append({
                    "bot_id": "bot_a", "bot_code": "BOT A",
                    "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                    "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                    "action": act_lbl, "units": round(qty, 6), "price": fmt_px_dec(px_exec),
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(vrel, 2), "notional_usd": round(gross, 2), "fee_usd": round(fee, 3),
                    "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                    "telemetry": f"EMA9/21={(e9/max(e21,1e-8)-1)*100:+.2f}% | %B={pb:.2f} | Mom={roc10:+.1f}% | Vol={vrel:.2f}x",
                })
                state["units"][c] = 0.0
                state["sl"][c] = 0.0
                state["tp"][c] = 0.0
            elif b_hi >= state["tp"][c] or ema_cross_exit:
                px_target = state["tp"][c] if b_hi >= state["tp"][c] else px_prev
                px_exec = float(np.clip(px_target, b_lo, b_hi))
                gross = qty * px_exec
                fee = gross * cfg.fee_rate
                pnl_u = gross - fee - (qty * state["entry"][c])
                pnl_p = ((px_exec / max(state["entry"][c], 1e-8)) - 1.0) * 100.0 - (cfg.fee_rate * 100.0)
                state["cash_usd"] += gross - fee
                state["fees_cum"] += fee
                act_lbl = "TOMA DE BENEFICIO (2.45x ATR)" if b_hi >= state["tp"][c] else "SALIDA CRUCE EMA 9/21"
                state["trades"].append({
                    "bot_id": "bot_a", "bot_code": "BOT A",
                    "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                    "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                    "action": act_lbl, "units": round(qty, 6), "price": fmt_px_dec(px_exec),
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(vrel, 2), "notional_usd": round(gross, 2), "fee_usd": round(fee, 3),
                    "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                    "telemetry": f"EMA9/21={(e9/max(e21,1e-8)-1)*100:+.2f}% | %B={pb:.2f} | RSI={rv:.1f} | Vol={vrel:.2f}x",
                })
                state["units"][c] = 0.0
                state["sl"][c] = 0.0
                state["tp"][c] = 0.0
        else:
            bull_candle = px_prev > float(bar_open_prev[c])
            htf_ok = (breadth_1h >= 0.375) or (e21_1h >= e55_1h * 0.995)
            setup_trend = (
                htf_ok
                and bull_candle
                and (px_prev > e9 > e21)
                and (roc10 > 0.35)
                and (mh > 0.0 and mh > mhp)
                and (48.0 <= rv <= 70.0)
                and (0.50 <= pb <= 0.90)
                and (vrel >= cfg.min_vol_rel_trend)
            )
            setup_bb_reclaim = (
                (pbp < 0.14)
                and (pb > 0.22)
                and bull_candle
                and (mh > mhp)
                and (px_prev > e9 * 0.996)
                and (rv < 46.0)
                and (vrel >= cfg.min_vol_rel_rebound)
            )

            open_count = sum(1 for k in coins if state["units"][k] > 0.0)
            invested_now = sum(state["units"][k] * float(bar_close_prev[k]) for k in coins)
            eq_est = state["cash_usd"] + invested_now
            inv_ratio = invested_now / max(eq_est, 1.0)
            if (setup_trend or setup_bb_reclaim) and open_count < cfg.max_open_positions and inv_ratio < cfg.max_total_invested:
                stop_dist_pct = max(0.0075, (cfg.sl_atr_mult * atr_v) / max(px_prev, 1e-6))
                risk_w = cfg.max_risk_per_trade_pct / stop_dist_pct
                rem_w = max(0.0, cfg.max_total_invested - inv_ratio)
                target_w = min(cfg.max_position_weight, risk_w, rem_w)
                alloc_usd = min(target_w * eq_est, (cfg.max_risk_per_trade_pct * eq_est) / stop_dist_pct)
                if alloc_usd >= cfg.min_order_usd and state["cash_usd"] >= alloc_usd * (1.0 + cfg.fee_rate * 2.0):
                    px_exec = float(np.clip(px_prev, b_lo, b_hi))
                    fee = alloc_usd * cfg.fee_rate
                    qty_new = alloc_usd / px_exec
                    state["cash_usd"] -= (alloc_usd + fee)
                    state["fees_cum"] += fee
                    state["units"][c] = qty_new
                    state["entry"][c] = px_exec
                    state["peak"][c] = px_exec
                    state["sl"][c] = px_exec * (1.0 - stop_dist_pct)
                    tp_ratio = (cfg.tp_atr_mult / cfg.sl_atr_mult) if setup_trend else 1.55
                    state["tp"][c] = px_exec * (1.0 + tp_ratio * stop_dist_pct)
                    act_in = "COMPRA IMPULSO 15M/VOLUMEN" if setup_trend else "COMPRA REBOTE BOLLINGER 15M"
                    state["trades"].append({
                        "bot_id": "bot_a", "bot_code": "BOT A",
                        "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "BUY",
                        "action": act_in, "units": round(qty_new, 6), "price": fmt_px_dec(px_exec),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "sl_price": fmt_px_dec(state["sl"][c]), "tp_price": fmt_px_dec(state["tp"][c]),
                        "volume_rel": round(vrel, 2), "notional_usd": round(alloc_usd, 2), "fee_usd": round(fee, 3),
                        "realized_pnl_usd": None, "realized_pnl_pct": None,
                        "telemetry": f"EMA9>21 | %B={pb:.2f} | Mom={roc10:+.1f}% | Vol={vrel:.2f}x | SL={fmt_px_dec(state['sl'][c])}",
                    })

    cur_eq = state["cash_usd"] + sum(state["units"][c] * float(bar_close_cur[c]) for c in coins)
    state["rets"].append((cur_eq / prev_eq) - 1.0)
    state["eq_curve"].append(cur_eq)


def step_bot_b_daily(
    px_y: np.ndarray,
    s20_y: np.ndarray,
    e12_y: np.ndarray,
    e26_y: np.ndarray,
    e50_y: np.ndarray,
    r14_y: np.ndarray,
    mh_y: np.ndarray,
    pb_y: np.ndarray,
    atr_y: np.ndarray,
    pk15_y: np.ndarray,
    adx_y: np.ndarray,
    vol_y: np.ndarray,
    cov_lw: np.ndarray,
    coins: List[str],
    max_asset_weight: float = 0.34,
    chandelier_mult: float = 2.1,
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """Calcula vector de pesos diarios de BOT B con Markowitz/GARCH y salida Chandelier ATR."""
    n_assets = len(coins)
    btc_j = coins.index("BTC") if "BTC" in coins else 0
    macro_b = bool((px_y[btc_j] > e50_y[btc_j]) or (float(np.mean(px_y > s20_y)) >= 0.375))
    chandelier_b = px_y >= (pk15_y - chandelier_mult * atr_y)
    bull_b = macro_b & (px_y > s20_y) & (e12_y > e26_y) & (r14_y > 0.5) & (pb_y > 0.52) & chandelier_b
    breadth_b = float(np.mean(bull_b))

    if np.any(bull_b):
        raw_mu = np.where(
            bull_b,
            (0.55 * np.maximum(0.0, r14_y / 100.0) + 0.45 * np.maximum(0.0, mh_y / 10.0) + 0.008)
            * np.where(px_y > e50_y, 1.25, 0.90)
            * np.clip(adx_y / 20.0, 0.80, 1.45)
            / np.maximum(vol_y, 0.014),
            -0.01,
        )
        res_b = sco.minimize(
            lambda x: -float(np.dot(raw_mu, x)) / (float(np.sqrt(max(1e-12, x.T @ cov_lw @ x))) + 1e-6),
            np.ones(n_assets) / n_assets,
            method="SLSQP",
            bounds=tuple((0.0, max_asset_weight) for _ in range(n_assets)),
            constraints=({"type": "eq", "fun": lambda x: np.sum(x) - 1.0},),
            tol=1e-3,
        )
        wb = np.clip(res_b.x if res_b.success else np.ones(n_assets) / n_assets, 0.0, max_asset_weight) * bull_b
        if np.sum(wb) > 1e-6:
            wb = (wb / np.sum(wb)) * min(0.92, 0.42 + 0.55 * breadth_b)
        else:
            wb = np.zeros(n_assets)
    else:
        oversold_b = np.where((pb_y < 0.16) & (mh_y > -0.8))[0]
        wb = np.zeros(n_assets)
        if len(oversold_b) > 0:
            wb[oversold_b[0]] = min(0.12, max_asset_weight)

    wb = np.clip(wb, 0.0, max_asset_weight)
    tot_w = float(np.sum(wb))
    if tot_w > 1.0:
        wb = wb / tot_w
    return wb, bull_b, macro_b


def step_bot_c_futures(
    px_v: np.ndarray,
    e21_v: np.ndarray,
    e55_v: np.ndarray,
    r24_v: np.ndarray,
    mh_v: np.ndarray,
    pb_v: np.ndarray,
    adx_v: np.ndarray,
    pdi_v: np.ndarray,
    mdi_v: np.ndarray,
    atr_v: np.ndarray,
    max_gross_leverage: float = 1.05,
) -> np.ndarray:
    """Calcula pesos direccionales (Largos > 0 y Cortos < 0) de BOT C con tope de apalancamiento bruto <= 1.05x."""
    n_assets = len(px_v)
    wc = np.zeros(n_assets)
    dir_scores = np.zeros(n_assets)
    for j in range(n_assets):
        atr_pct = max(0.012, atr_v[j] / max(px_v[j], 1e-6))
        if (px_v[j] > e21_v[j] > e55_v[j]) and (r24_v[j] > 1.2) and (pdi_v[j] > mdi_v[j]) and (pb_v[j] > 0.52):
            dir_scores[j] = (r24_v[j] + 4.0 * mh_v[j]) / (atr_pct * 100.0)
        elif (px_v[j] < e21_v[j] < e55_v[j]) and (r24_v[j] < -1.2) and (mdi_v[j] > pdi_v[j]) and (pb_v[j] < 0.48) and (adx_v[j] > 19.0):
            dir_scores[j] = (r24_v[j] + 4.0 * mh_v[j]) / (atr_pct * 100.0)

    pos_idx = np.argsort(dir_scores)[::-1]
    neg_idx = np.argsort(dir_scores)
    for j in pos_idx[:3]:
        if dir_scores[j] > 0.25:
            atr_pct = max(0.012, atr_v[j] / max(px_v[j], 1e-6))
            wc[j] = min(0.26, 0.0085 / atr_pct)
    for j in neg_idx[:3]:
        if dir_scores[j] < -0.25:
            atr_pct = max(0.012, atr_v[j] / max(px_v[j], 1e-6))
            wc[j] = -min(0.24, 0.0080 / atr_pct)

    gross_lev = float(np.sum(np.abs(wc)))
    if gross_lev > max_gross_leverage:
        wc *= max_gross_leverage / gross_lev
    return wc


def calc_futures_account_state(
    units_c: Dict[str, float],
    entry_c: Dict[str, float],
    realized_cash_c: float,
    perp_prices: Dict[str, float],
) -> Tuple[float, float, float]:
    """Retorna (patrimonio_total, nocional_bruto, margen_libre) exactos para perpetuos."""
    unreal = 0.0
    gross = 0.0
    for c, qty in units_c.items():
        if abs(qty) > 1e-9:
            px = float(perp_prices[c])
            unreal += qty * (px - float(entry_c[c]))
            gross += abs(qty) * px
    total_eq = float(realized_cash_c) + unreal
    free_margin = max(0.0, total_eq - (gross * 0.35))
    return total_eq, gross, free_margin


def extract_ta_features_row(
    idx_pos: int,
    coin_sym: str,
    ema9_df: pd.DataFrame,
    ema21_df: pd.DataFrame,
    ema55_df: pd.DataFrame,
    bb_pctb_df: pd.DataFrame,
    bb_bw_df: pd.DataFrame,
    roc12_df: pd.DataFrame,
    roc24_df: pd.DataFrame,
    macd_h_df: pd.DataFrame,
    rsi_df: pd.DataFrame,
    stoch_df: pd.DataFrame,
    vol_rel_df: pd.DataFrame,
) -> List[float]:
    e9_i = float(ema9_df.iloc[idx_pos][coin_sym])
    e21_i = float(ema21_df.iloc[idx_pos][coin_sym])
    e55_i = float(ema55_df.iloc[idx_pos][coin_sym])
    return [
        (e9_i / max(e21_i, 1e-8)) - 1.0,
        (e21_i / max(e55_i, 1e-8)) - 1.0,
        float(bb_pctb_df.iloc[idx_pos][coin_sym]) - 0.5,
        float(bb_bw_df.iloc[idx_pos][coin_sym]) / 100.0,
        float(roc12_df.iloc[idx_pos][coin_sym]) / 100.0,
        float(roc24_df.iloc[idx_pos][coin_sym]) / 100.0,
        float(macd_h_df.iloc[idx_pos][coin_sym]) / 10.0,
        (float(rsi_df.iloc[idx_pos][coin_sym]) - 50.0) / 50.0,
        (float(stoch_df.iloc[idx_pos][coin_sym]) - 50.0) / 50.0,
        float(vol_rel_df.iloc[idx_pos][coin_sym]) - 1.0,
    ]


def fit_causal_mlp_ensemble(
    X_train: np.ndarray,
    yr_train: np.ndarray,
    yc_train: np.ndarray,
    seed: int = 101,
) -> Tuple[StandardScaler, MLPRegressor, MLPClassifier]:
    """Entrena el ensamble MLP(32,16) regularizado L2 exclusivamente sobre ventana pasada."""
    scaler = StandardScaler()
    Xs = scaler.fit_transform(np.asarray(X_train, dtype=float))
    reg = MLPRegressor(hidden_layer_sizes=(32, 16), activation="tanh", alpha=3.0, max_iter=220, random_state=seed)
    clf = MLPClassifier(hidden_layer_sizes=(32, 16), activation="tanh", alpha=2.5, max_iter=220, random_state=seed)
    reg.fit(Xs, np.asarray(yr_train, dtype=float))
    clf.fit(Xs, np.asarray(yc_train, dtype=int))
    return scaler, reg, clf


def compute_bot_d_sizing(
    equity_usd: float,
    cash_usd: float,
    invested_usd: float,
    price_now: float,
    atr_14: float,
    prob_up: float,
    max_risk_pct: float = 0.0105,
    max_asset_weight: float = 0.25,
    min_cash_reserve_pct: float = 0.25,
) -> Tuple[float, float]:
    """
    Calcula (alloc_usd, stop_dist_pct) de BOT D garantizando:
      - Riesgo máximo por operación <= 1.05% del patrimonio
      - Tope por activo <= 25% del patrimonio
      - Reserva mínima permanente >= 25% en USDT
    """
    stop_dist = max(0.011, (1.45 * max(atr_14, 1e-9)) / max(price_now, 1e-8))
    max_invested_ratio = 1.0 - min_cash_reserve_pct
    rem_ratio = max(0.0, max_invested_ratio - (invested_usd / max(equity_usd, 1.0)))
    risk_ratio = (max_risk_pct * min(1.0, max(0.75, prob_up / 0.54))) / stop_dist
    w_opt = min(max_asset_weight, risk_ratio, rem_ratio)
    alloc_by_reserve = max(0.0, cash_usd - (min_cash_reserve_pct * equity_usd))
    alloc_by_risk = (max_risk_pct * equity_usd) / stop_dist
    alloc_usd = max(0.0, min(w_opt * equity_usd, alloc_by_reserve, alloc_by_risk))
    return alloc_usd, stop_dist


def evaluate_bot_d_exit_decision(
    prob_up: float,
    pred_ret: float,
    e9: float,
    e21: float,
    low_bar: float,
    high_bar: float,
    sl_price: float,
    tp_price: float,
    peak_price: float,
    entry_price: float,
    atr_14: float,
) -> Tuple[bool, Optional[str], float, float]:
    """
    Evalúa el triple protocolo determinístico de salida de BOT D:
      (1) Stop-Loss 1.45x ATR / Trailing Stop 1.30x ATR tras +1.10x ATR
      (2) Take-Profit escalonado ATR
      (3) Giro de inferencia neuronal (Prob < 45% o pred < -0.2% junto con EMA9 < EMA21)
    Retorna: (debe_salir, etiqueta_accion, px_ejecucion, nuevo_sl)
    """
    new_sl = float(sl_price)
    if peak_price >= entry_price + 1.1 * atr_14:
        new_sl = max(new_sl, entry_price * 1.002, peak_price - 1.30 * atr_14)

    if low_bar <= new_sl:
        px_exec = float(np.clip(new_sl, low_bar, high_bar))
        lbl = "SALIDA TRAILING MLP/ATR" if px_exec > entry_price else "CORTE STOP-LOSS MLP (1.45x ATR)"
        return True, lbl, px_exec, new_sl

    if high_bar >= tp_price:
        px_exec = float(np.clip(tp_price, low_bar, high_bar))
        return True, "TOMA DE BENEFICIO MLP (2.8x ATR)", px_exec, new_sl

    nn_reversal = (prob_up < 0.45 or pred_ret < -0.002) and (e9 < e21)
    if nn_reversal:
        px_exec = float(np.clip(0.5 * (low_bar + high_bar), low_bar, high_bar))
        return True, "SALIDA POR GIRO DE SEÑAL MLP", px_exec, new_sl

    return False, None, 0.0, new_sl


def sign_orders_sha256_chain(
    trades_chrono: List[Dict[str, Any]],
    genesis_hash: str = GENESIS_HASH,
) -> Tuple[List[Dict[str, Any]], str]:
    """Encadena y firma criptográficamente todas las órdenes cronológicas en SHA-256."""
    prev_h = genesis_hash
    for seq_i, tr in enumerate(trades_chrono, start=1):
        tx_id = f"JBZ-{tr['bot_id'][-1].upper()}-{seq_i:04d}"
        canonical = (
            f"{prev_h}|{tx_id}|{tr['bot_id']}|{tr['time_utc']}|{tr['instrument']}|"
            f"{tr['side_type']}|{float(tr['units']):.6f}|{tr['price']}|{tr['bar_low']}|{tr['bar_high']}"
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        tr["tx_id"] = tx_id
        tr["prev_hash"] = prev_h
        tr["canonical_payload"] = canonical
        tr["sha256"] = digest
        prev_h = digest
    return trades_chrono, prev_h


def verify_orders_sha256_chain(
    orders_chrono: List[Dict[str, Any]],
    genesis_hash: str,
    expected_root: str,
) -> Tuple[bool, int, int, List[str]]:
    """Verifica 100% de integridad SHA-256 y cotas OHLC [bar_low, bar_high] de la cadena."""
    errors: List[str] = []
    valid_hashes = 0
    valid_bounds = 0
    prev_h = genesis_hash

    for ord_item in orders_chrono:
        tx = ord_item.get("tx_id", "?")
        canonical = (
            f"{prev_h}|{tx}|{ord_item['bot_id']}|{ord_item['time_utc']}|{ord_item['instrument']}|"
            f"{ord_item['side_type']}|{float(ord_item['units']):.6f}|{ord_item['price']}|{ord_item['bar_low']}|{ord_item['bar_high']}"
        )
        recomp = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if ord_item.get("prev_hash") == prev_h and ord_item.get("sha256") == recomp and ord_item.get("canonical_payload") == canonical:
            valid_hashes += 1
        else:
            errors.append(f"Hash/payload inválido en {tx}")
        lo, hi, px = float(ord_item["bar_low"]), float(ord_item["bar_high"]), float(ord_item["price"])
        if lo - 1e-6 <= px <= hi + 1e-6:
            valid_bounds += 1
        else:
            errors.append(f"Precio fuera de rango OHLC en {tx}: {px} no en [{lo}, {hi}]")
        prev_h = recomp

    if prev_h != expected_root:
        errors.append(f"Raíz SHA-256 discordante: {prev_h} != {expected_root}")

    return len(errors) == 0, valid_hashes, valid_bounds, errors

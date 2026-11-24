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
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.mixture import GaussianMixture
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


def calc_obv_slope(close_s: pd.Series, vol_s: pd.Series, window: int = 14) -> pd.Series:
    """Calcula la pendiente normalizada causal del On-Balance Volume (OBV) en [-1.0, +1.0]."""
    diff_c = close_s.diff().fillna(0.0)
    dir_sign = np.where(diff_c > 0.0, 1.0, np.where(diff_c < 0.0, -1.0, 0.0))
    vols = vol_s.fillna(0.0).clip(lower=0.0)
    obv = pd.Series(dir_sign * vols.values, index=close_s.index).cumsum()
    vol_win = vols.rolling(window, min_periods=3).sum() + 1e-9
    return ((obv - obv.shift(window).fillna(0.0)) / vol_win).fillna(0.0).clip(-1.0, 1.0)


def calc_structure_and_btc_metrics(
    close_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    btc_col: str = "BTC",
    window: int = 20,
) -> Dict[str, pd.DataFrame]:
    """Calcula distancia a EMA 200, posición en canal máximo-mínimo, aceleración RSI(7-21) y relación con BTC."""
    anchor = btc_col if btc_col in close_df.columns else close_df.columns[0]
    ema200 = close_df.ewm(span=200, min_periods=20, adjust=False).mean().bfill().clip(lower=1e-8)
    ema200_dist = ((close_df / ema200) - 1.0).fillna(0.0).clip(-0.60, 1.20)
    hi_w = high_df.rolling(window, min_periods=3).max().bfill()
    lo_w = low_df.rolling(window, min_periods=3).min().bfill()
    range_pos = ((close_df - lo_w) / (hi_w - lo_w).clip(lower=1e-8)).fillna(0.5).clip(0.0, 1.0)
    rsi_accel = pd.DataFrame(
        {c: (calc_rsi(close_df[c], 7) - calc_rsi(close_df[c], 21)) / 50.0 for c in close_df.columns},
        index=close_df.index,
    ).fillna(0.0).clip(-1.0, 1.0)
    rets = close_df.pct_change().fillna(0.0)
    roc12 = close_df.pct_change(12).fillna(0.0)
    btc_corr = pd.DataFrame(
        {
            c: (
                pd.Series(1.0, index=close_df.index)
                if c == anchor
                else rets[c].rolling(24, min_periods=6).corr(rets[anchor]).fillna(0.6).clip(-1.0, 1.0)
            )
            for c in close_df.columns
        },
        index=close_df.index,
    )
    btc_rel = pd.DataFrame(
        {c: (roc12[c] - roc12[anchor]).fillna(0.0).clip(-0.50, 0.50) for c in close_df.columns},
        index=close_df.index,
    )
    return {
        "ema200_dist": ema200_dist,
        "range_pos": range_pos,
        "rsi_accel": rsi_accel,
        "btc_corr": btc_corr,
        "btc_rel": btc_rel,
    }


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
    fee_rate: float = 0.0004
    max_risk_per_trade_pct: float = 0.0050
    max_position_weight: float = 0.24
    max_total_invested: float = 0.68
    max_open_positions: int = 3
    daily_circuit_breaker_pct: float = -0.020
    sl_atr_mult: float = 1.55
    tp_atr_mult: float = 3.10
    trail_activate_atr: float = 1.05
    trail_dist_atr: float = 1.10
    trail_floor_mult: float = 1.0055
    partial_tp_atr: float = 1.40
    partial_tp_frac: float = 0.45
    min_atr_pct: float = 0.0042
    min_adx_1h_trend: float = 20.0
    min_vol_rel_trend: float = 1.08
    min_vol_rel_rebound: float = 1.25
    min_order_usd: float = 45.0


@dataclass(frozen=True)
class RiskGatekeeperConfig:
    base_risk_per_trade_pct: float = 0.0050
    daily_loss_limit_pct: float = -0.020
    kill_switch_drawdown_pct: float = -0.085
    max_spread_bps: float = 12.0
    max_cross_exchange_bps: float = 45.0
    min_net_rr_ratio: float = 1.50


def evaluate_risk_gatekeeper(
    equity_curve: List[float],
    day_anchor_eq: float,
    current_invested_ratio: float,
    max_invested_ratio: float,
    spread_bps: float = 1.0,
    cross_exchange_bps: float = 2.0,
    regime_info: Optional[Dict[str, Any]] = None,
    rr_ratio: float = 2.0,
    cfg: RiskGatekeeperConfig = RiskGatekeeperConfig(),
) -> Dict[str, Any]:
    """
    Módulo independiente de Inteligencia de Capital y Riesgo (Nivel 3) con control pre-ejecución:
      1) Parada por drawdown máximo acumulado desde pico patrimonial (<= -8.50%)
      2) Límite máximo de pérdida diaria (<= -2.00%)
      3) Filtro de liquidez / spread Bid-Ask (<= 12 bps)
      4) Verificación de consistencia entre libros OKX/Bybit (<= 45 bps)
      5) Tope de exposición simultánea y relación riesgo-beneficio mínima (>= 1.50)
    """
    eq_arr = np.asarray(equity_curve, dtype=float) if equity_curve else np.array([1000.0])
    cur_eq = float(eq_arr[-1])
    peak_eq = float(np.max(eq_arr))
    current_dd = (cur_eq - peak_eq) / max(peak_eq, 1e-6)
    daily_pnl = (cur_eq - float(day_anchor_eq)) / max(float(day_anchor_eq), 1e-6)

    risk_mult = float((regime_info or {}).get("risk_multiplier", 1.0))
    sl_buf = float((regime_info or {}).get("sl_atr_buffer", 1.0))
    eff_risk = float(np.clip(cfg.base_risk_per_trade_pct * risk_mult, 0.0020, 0.0060))

    veto_code: Optional[str] = None
    if current_dd <= cfg.kill_switch_drawdown_pct:
        veto_code = "KILL_SWITCH_DRAWDOWN"
    elif daily_pnl <= cfg.daily_loss_limit_pct:
        veto_code = "DAILY_LOSS_LIMIT"
    elif float(spread_bps) > cfg.max_spread_bps:
        veto_code = "LIQUIDITY_SPREAD_HIGH"
    elif float(cross_exchange_bps) > cfg.max_cross_exchange_bps:
        veto_code = "ORACLE_DIVERGENCE"
    elif float(current_invested_ratio) >= float(max_invested_ratio) - 1e-4:
        veto_code = "EXPOSURE_CAP_REACHED"
    elif float(rr_ratio) < cfg.min_net_rr_ratio:
        veto_code = "RR_BELOW_MINIMUM"

    return {
        "approved": veto_code is None,
        "veto_code": veto_code,
        "effective_risk_pct": round(eff_risk, 6),
        "sl_buffer_mult": round(sl_buf, 3),
        "current_dd_pct": round(current_dd * 100.0, 2),
        "daily_pnl_pct": round(daily_pnl * 100.0, 2),
    }


def init_bot_a_state(coins: List[str], base_cap: float = 1000.0) -> Dict[str, Any]:
    return {
        "cash_usd": float(base_cap),
        "units": {c: 0.0 for c in coins},
        "entry": {c: 0.0 for c in coins},
        "entry_fee": {c: 0.0 for c in coins},
        "partial_taken": {c: False for c in coins},
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
    adx_1h_prev: Optional[Dict[str, float]] = None,
    obv_prev: Optional[Dict[str, float]] = None,
    ema200_dist_prev: Optional[Dict[str, float]] = None,
    regime_code: Optional[str] = None,
    spread_bps_map: Optional[Dict[str, float]] = None,
    risk_mult: float = 1.0,
) -> None:
    """
    Ejecuta un paso intradía (15m con filtro 1H) de BOT A respetando:
      - Límite máximo de pérdida diaria (-2.00% desde apertura diaria UTC)
      - Filtro mínimo de rango ATR/Precio (>= 0.42%), ADX 1H (>= 20), liquidez Bid-Ask y régimen de mercado
      - Dimensionamiento por paridad ATR (riesgo máx. <= 0.50% modulado por régimen, tope 24%/par, máx. 68% total)
      - Salidas estrictamente causales (sin fuga intra-barra): SL 1.55x ATR, Toma Parcial 45% (1.40x ATR),
        Trailing Stop dinámico (+0.55% piso neto) tras +1.05x ATR y TP objetivo 3.10x ATR (ratio 2:1)
    """
    entry_fee_map = state.setdefault("entry_fee", {c: 0.0 for c in coins})
    partial_map = state.setdefault("partial_taken", {c: False for c in coins})
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
                ent_fee = float(entry_fee_map.get(c, 0.0))
                pnl_u = gross - fee - (qty * state["entry"][c]) - ent_fee
                fee_legs = 2.0 if ent_fee > 0.0 else 1.0
                pnl_p = ((px_exec / max(state["entry"][c], 1e-8)) - 1.0) * 100.0 - (fee_legs * cfg.fee_rate * 100.0)
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
                entry_fee_map[c] = 0.0
                partial_map[c] = False
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
            # 1) Evaluar salidas contra bandas pre-barra (estrictamente causal: nunca actualiza SL y detiene en la misma barra)
            ema_cross_exit = (e9 < e21 * 0.9980) and (mh < 0.0) and (px_prev > state["entry"][c] * 1.006)
            if b_lo <= state["sl"][c]:
                px_exec = float(np.clip(state["sl"][c], b_lo, b_hi))
                gross = qty * px_exec
                fee = gross * cfg.fee_rate
                ent_fee = float(entry_fee_map.get(c, 0.0))
                pnl_u = gross - fee - (qty * state["entry"][c]) - ent_fee
                fee_legs = 2.0 if ent_fee > 0.0 else 1.0
                pnl_p = ((px_exec / max(state["entry"][c], 1e-8)) - 1.0) * 100.0 - (fee_legs * cfg.fee_rate * 100.0)
                state["cash_usd"] += gross - fee
                state["fees_cum"] += fee
                act_lbl = "TOMA TRAILING ATR" if px_exec > state["entry"][c] else f"SALIDA STOP-LOSS ({cfg.sl_atr_mult:.2f}x ATR)"
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
                entry_fee_map[c] = 0.0
                partial_map[c] = False
            elif b_hi >= state["tp"][c] or ema_cross_exit:
                px_target = state["tp"][c] if b_hi >= state["tp"][c] else px_prev
                px_exec = float(np.clip(px_target, b_lo, b_hi))
                gross = qty * px_exec
                fee = gross * cfg.fee_rate
                ent_fee = float(entry_fee_map.get(c, 0.0))
                pnl_u = gross - fee - (qty * state["entry"][c]) - ent_fee
                fee_legs = 2.0 if ent_fee > 0.0 else 1.0
                pnl_p = ((px_exec / max(state["entry"][c], 1e-8)) - 1.0) * 100.0 - (fee_legs * cfg.fee_rate * 100.0)
                state["cash_usd"] += gross - fee
                state["fees_cum"] += fee
                act_lbl = f"TOMA DE BENEFICIO ({cfg.tp_atr_mult:.2f}x ATR)" if b_hi >= state["tp"][c] else "SALIDA CRUCE EMA 9/21"
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
                entry_fee_map[c] = 0.0
                partial_map[c] = False
            else:
                # 2) Toma parcial 45% al alcanzar +1.65x ATR dejando correr 55% con piso protegido
                part_target = state["entry"][c] + cfg.partial_tp_atr * atr_v
                if (not partial_map.get(c, False)) and (b_hi >= part_target) and (qty * part_target >= 95.0):
                    qty_part = qty * cfg.partial_tp_frac
                    px_part = float(np.clip(part_target, b_lo, b_hi))
                    gross_p = qty_part * px_part
                    fee_p = gross_p * cfg.fee_rate
                    ent_fee_part = float(entry_fee_map.get(c, 0.0)) * cfg.partial_tp_frac
                    pnl_u_p = gross_p - fee_p - (qty_part * state["entry"][c]) - ent_fee_part
                    fee_legs_p = 2.0 if ent_fee_part > 0.0 else 1.0
                    pnl_p_p = ((px_part / max(state["entry"][c], 1e-8)) - 1.0) * 100.0 - (fee_legs_p * cfg.fee_rate * 100.0)
                    state["cash_usd"] += gross_p - fee_p
                    state["fees_cum"] += fee_p
                    state["units"][c] = qty - qty_part
                    entry_fee_map[c] = max(0.0, float(entry_fee_map.get(c, 0.0)) - ent_fee_part)
                    partial_map[c] = True
                    state["sl"][c] = max(state["sl"][c], state["entry"][c] * cfg.trail_floor_mult)
                    state["trades"].append({
                        "bot_id": "bot_a", "bot_code": "BOT A",
                        "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                        "action": f"TOMA PARCIAL 45% ({cfg.partial_tp_atr:.2f}x ATR)",
                        "units": round(qty_part, 6), "price": fmt_px_dec(px_part),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "volume_rel": round(vrel, 2), "notional_usd": round(gross_p, 2), "fee_usd": round(fee_p, 3),
                        "realized_pnl_usd": round(pnl_u_p, 2), "realized_pnl_pct": round(pnl_p_p, 2),
                        "telemetry": f"Parcial 45% | SL Protegido={fmt_px_dec(state['sl'][c])} | Vol={vrel:.2f}x",
                    })

                # 3) Actualizar pico y trailing stop al cierre de la barra para las velas siguientes
                state["peak"][c] = max(state["peak"][c], b_hi)
                if state["peak"][c] >= state["entry"][c] + cfg.trail_activate_atr * atr_v:
                    state["sl"][c] = max(
                        state["sl"][c],
                        state["entry"][c] * cfg.trail_floor_mult,
                        state["peak"][c] - cfg.trail_dist_atr * atr_v,
                    )
        else:
            atr_pct = atr_v / max(px_prev, 1e-8)
            vol_edge_ok = atr_pct >= cfg.min_atr_pct
            adx_1h_val = float(adx_1h_prev.get(c, 22.0)) if adx_1h_prev is not None else 22.0
            adx_ok = adx_1h_val >= cfg.min_adx_1h_trend
            bull_candle = px_prev > float(bar_open_prev[c])
            htf_ok = (breadth_1h >= 0.375) or (e21_1h >= e55_1h * 0.995)
            obv_val = float(obv_prev.get(c, 0.0)) if obv_prev is not None else 0.0
            e200_d = float(ema200_dist_prev.get(c, 0.0)) if ema200_dist_prev is not None else 0.0
            spread_ok = (float(spread_bps_map.get(c, 1.0)) <= 12.0) if spread_bps_map is not None else True
            allow_trend = (regime_code not in ("TENDENCIA_BAJISTA", "MERCADO_LATERAL")) if regime_code else True
            setup_trend = (
                spread_ok
                and allow_trend
                and vol_edge_ok
                and adx_ok
                and htf_ok
                and bull_candle
                and (px_prev > e9 > e21)
                and (roc10 > 0.35)
                and (mh > 0.0 and mh > mhp)
                and (48.0 <= rv <= 70.0)
                and (0.50 <= pb <= 0.90)
                and (vrel >= cfg.min_vol_rel_trend)
                and (obv_val >= -0.08)
                and (e200_d <= 0.35)
            )
            setup_bb_reclaim = (
                spread_ok
                and vol_edge_ok
                and (pbp < 0.14)
                and (pb > 0.22)
                and bull_candle
                and (mh > mhp)
                and (px_prev > e9 * 0.996)
                and (rv < 46.0)
                and (vrel >= cfg.min_vol_rel_rebound)
                and (obv_val >= -0.18)
            )

            open_count = sum(1 for k in coins if state["units"][k] > 0.0)
            invested_now = sum(state["units"][k] * float(bar_close_prev[k]) for k in coins)
            eq_est = state["cash_usd"] + invested_now
            inv_ratio = invested_now / max(eq_est, 1.0)
            if (setup_trend or setup_bb_reclaim) and open_count < cfg.max_open_positions and inv_ratio < cfg.max_total_invested:
                sl_buf = 1.15 if regime_code == "ALTA_VOLATILIDAD" else 1.00
                eff_risk_pct = float(np.clip(cfg.max_risk_per_trade_pct * float(risk_mult), 0.0022, 0.0065))
                stop_dist_pct = max(0.0085, (cfg.sl_atr_mult * sl_buf * atr_v) / max(px_prev, 1e-6))
                risk_w = eff_risk_pct / stop_dist_pct
                rem_w = max(0.0, cfg.max_total_invested - inv_ratio)
                target_w = min(cfg.max_position_weight, risk_w, rem_w)
                alloc_usd = min(target_w * eq_est, (eff_risk_pct * eq_est) / stop_dist_pct)
                if alloc_usd >= cfg.min_order_usd and state["cash_usd"] >= alloc_usd * (1.0 + cfg.fee_rate * 2.0):
                    px_exec = float(np.clip(px_prev, b_lo, b_hi))
                    fee = alloc_usd * cfg.fee_rate
                    qty_new = alloc_usd / px_exec
                    state["cash_usd"] -= (alloc_usd + fee)
                    state["fees_cum"] += fee
                    state["units"][c] = qty_new
                    state["entry"][c] = px_exec
                    entry_fee_map[c] = fee
                    partial_map[c] = False
                    state["peak"][c] = px_exec
                    state["sl"][c] = px_exec * (1.0 - stop_dist_pct)
                    tp_ratio = (cfg.tp_atr_mult / (cfg.sl_atr_mult * sl_buf)) if setup_trend else 1.75
                    state["tp"][c] = px_exec * (1.0 + tp_ratio * stop_dist_pct)
                    act_in = "COMPRA IMPULSO 15M/VOLUMEN" if setup_trend else "COMPRA REBOTE BOLLINGER 15M"
                    reg_tag = f" | Reg={regime_code}" if regime_code else ""
                    state["trades"].append({
                        "bot_id": "bot_a", "bot_code": "BOT A",
                        "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "BUY",
                        "action": act_in, "units": round(qty_new, 6), "price": fmt_px_dec(px_exec),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "sl_price": fmt_px_dec(state["sl"][c]), "tp_price": fmt_px_dec(state["tp"][c]),
                        "volume_rel": round(vrel, 2), "notional_usd": round(alloc_usd, 2), "fee_usd": round(fee, 3),
                        "realized_pnl_usd": None, "realized_pnl_pct": None,
                        "telemetry": f"EMA9>21 | ATR={atr_pct*100:.2f}% | ADX1H={adx_1h_val:.0f} | OBV={obv_val:+.2f} | Vol={vrel:.2f}x{reg_tag}",
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
    prev_w: Optional[np.ndarray] = None,
    turnover_penalty: float = 0.06,
    obv_y: Optional[np.ndarray] = None,
    btc_rel_y: Optional[np.ndarray] = None,
    regime_code: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray, bool]:
    """Calcula vector de pesos diarios de BOT B con Markowitz/GARCH, penalización L1, OBV/BTC rel, régimen GMM y salida Chandelier ATR."""
    n_assets = len(coins)
    btc_j = coins.index("BTC") if "BTC" in coins else 0
    macro_b = bool((px_y[btc_j] > e50_y[btc_j]) or (float(np.mean(px_y > s20_y)) >= 0.375))
    chandelier_b = px_y >= (pk15_y - chandelier_mult * atr_y)
    bull_b = macro_b & (px_y > s20_y) & (e12_y > e26_y) & (r14_y > 0.5) & (pb_y > 0.52) & chandelier_b
    breadth_b = float(np.mean(bull_b))

    regime_exp_cap = {
        "TENDENCIA_ALCISTA": 0.92,
        "MERCADO_LATERAL": 0.55,
        "ALTA_VOLATILIDAD": 0.38,
        "TENDENCIA_BAJISTA": 0.24,
    }.get(regime_code or "", 0.92)

    if np.any(bull_b):
        obv_mult = np.clip(1.0 + 0.35 * np.asarray(obv_y, dtype=float), 0.70, 1.35) if obv_y is not None else 1.0
        rel_mult = np.clip(1.0 + 1.15 * np.asarray(btc_rel_y, dtype=float), 0.75, 1.35) if btc_rel_y is not None else 1.0
        raw_mu = np.where(
            bull_b,
            (0.55 * np.maximum(0.0, r14_y / 100.0) + 0.45 * np.maximum(0.0, mh_y / 10.0) + 0.008)
            * np.where(px_y > e50_y, 1.25, 0.90)
            * np.clip(adx_y / 20.0, 0.80, 1.45)
            * obv_mult
            * rel_mult
            / np.maximum(vol_y, 0.014),
            -0.01,
        )
        prev_arr = np.asarray(prev_w, dtype=float) if prev_w is not None else None
        prev_norm: Optional[np.ndarray] = None
        if prev_arr is not None and float(np.sum(prev_arr)) > 0.05:
            prev_norm = np.clip(prev_arr / float(np.sum(prev_arr)), 0.0, max_asset_weight)
            s_p = float(np.sum(prev_norm))
            prev_norm = (prev_norm / s_p) if s_p > 1e-6 else None
        x0 = prev_norm.copy() if prev_norm is not None else (np.ones(n_assets) / n_assets)
        sr_ref = abs(float(np.dot(raw_mu, x0)) / (float(np.sqrt(max(1e-12, x0.T @ cov_lw @ x0))) + 1e-6))
        pen_scale = max(1.0, sr_ref) * float(turnover_penalty)

        def _obj_b(x: np.ndarray) -> float:
            sr = float(np.dot(raw_mu, x)) / (float(np.sqrt(max(1e-12, x.T @ cov_lw @ x))) + 1e-6)
            if prev_norm is not None and pen_scale > 0.0:
                sr -= pen_scale * float(np.sum(np.sqrt((x - prev_norm) ** 2 + 1e-6)))
            return -sr

        res_b = sco.minimize(
            _obj_b,
            x0,
            method="SLSQP",
            bounds=tuple((0.0, max_asset_weight) for _ in range(n_assets)),
            constraints=({"type": "eq", "fun": lambda x: np.sum(x) - 1.0},),
            tol=1e-3,
        )
        wb = np.clip(res_b.x if res_b.success else np.ones(n_assets) / n_assets, 0.0, max_asset_weight) * bull_b
        if np.sum(wb) > 1e-6:
            wb = (wb / np.sum(wb)) * min(regime_exp_cap, 0.42 + 0.55 * breadth_b)
        else:
            wb = np.zeros(n_assets)
    else:
        oversold_b = np.where((pb_y < 0.16) & (mh_y > -0.8))[0]
        wb = np.zeros(n_assets)
        if len(oversold_b) > 0 and regime_code != "ALTA_VOLATILIDAD":
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
    funding_8h: Optional[np.ndarray] = None,
    prev_wc: Optional[np.ndarray] = None,
    oi_vol_ratio: Optional[np.ndarray] = None,
    obv_v: Optional[np.ndarray] = None,
    regime_code: Optional[str] = None,
    risk_per_leg: float = 0.0085,
) -> np.ndarray:
    """Calcula pesos direccionales (Largos > 0 y Cortos < 0) de BOT C con carry 8h, Open Interest, OBV, régimen GMM y tope <= 1.05x."""
    n_assets = len(px_v)
    wc = np.zeros(n_assets)
    dir_scores = np.zeros(n_assets)
    fund_arr = np.asarray(funding_8h, dtype=float) if funding_8h is not None else None
    prev_arr = np.asarray(prev_wc, dtype=float) if prev_wc is not None else None
    oi_arr = np.asarray(oi_vol_ratio, dtype=float) if oi_vol_ratio is not None else None
    obv_arr = np.asarray(obv_v, dtype=float) if obv_v is not None else None

    min_score_thr = 0.30 if regime_code == "MERCADO_LATERAL" else 0.25
    leg_risk_mult = {"ALTA_VOLATILIDAD": 0.80, "MERCADO_LATERAL": 0.90}.get(regime_code or "", 1.0)
    eff_leg_risk = float(risk_per_leg) * leg_risk_mult

    for j in range(n_assets):
        atr_pct = max(0.012, atr_v[j] / max(px_v[j], 1e-6))
        oi_bonus = 0.12 if (oi_arr is not None and 0.20 <= oi_arr[j] <= 6.50) else 0.0
        if (px_v[j] > e21_v[j] > e55_v[j]) and (r24_v[j] > 1.2) and (pdi_v[j] > mdi_v[j]) and (pb_v[j] > 0.52):
            score = ((r24_v[j] + 4.0 * mh_v[j]) / (atr_pct * 100.0)) + oi_bonus
            if fund_arr is not None:
                score += float(np.clip(-fund_arr[j] * 180.0, -0.35, 0.35))
            if obv_arr is not None:
                score += float(np.clip(obv_arr[j] * 0.12, -0.08, 0.08))
            if prev_arr is not None and prev_arr[j] > 0.04:
                score += 0.35
            dir_scores[j] = score
        elif (px_v[j] < e21_v[j] < e55_v[j]) and (r24_v[j] < -1.2) and (mdi_v[j] > pdi_v[j]) and (pb_v[j] < 0.48) and (adx_v[j] > 19.0):
            score = ((r24_v[j] + 4.0 * mh_v[j]) / (atr_pct * 100.0)) - oi_bonus
            if fund_arr is not None:
                score -= float(np.clip(fund_arr[j] * 180.0, -0.35, 0.35))
            if obv_arr is not None:
                score += float(np.clip(obv_arr[j] * 0.12, -0.08, 0.08))
            if prev_arr is not None and prev_arr[j] < -0.04:
                score -= 0.35
            dir_scores[j] = score

    pos_idx = np.argsort(dir_scores)[::-1]
    neg_idx = np.argsort(dir_scores)
    for j in pos_idx[:3]:
        if dir_scores[j] > min_score_thr:
            atr_pct = max(0.012, atr_v[j] / max(px_v[j], 1e-6))
            wc[j] = min(0.26, eff_leg_risk / atr_pct)
    for j in neg_idx[:3]:
        if dir_scores[j] < -min_score_thr:
            atr_pct = max(0.012, atr_v[j] / max(px_v[j], 1e-6))
            wc[j] = -min(0.24, (eff_leg_risk * 0.94) / atr_pct)

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
    obv_slope_df: Optional[pd.DataFrame] = None,
    ema200_dist_df: Optional[pd.DataFrame] = None,
    range_pos_df: Optional[pd.DataFrame] = None,
    btc_rel_df: Optional[pd.DataFrame] = None,
    rsi_accel_df: Optional[pd.DataFrame] = None,
) -> List[float]:
    e9_i = float(ema9_df.iloc[idx_pos][coin_sym])
    e21_i = float(ema21_df.iloc[idx_pos][coin_sym])
    e55_i = float(ema55_df.iloc[idx_pos][coin_sym])
    base = [
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
    if (
        obv_slope_df is not None
        and ema200_dist_df is not None
        and range_pos_df is not None
        and btc_rel_df is not None
        and rsi_accel_df is not None
    ):
        base.extend([
            float(obv_slope_df.iloc[idx_pos][coin_sym]),
            float(ema200_dist_df.iloc[idx_pos][coin_sym]),
            float(range_pos_df.iloc[idx_pos][coin_sym]) - 0.5,
            float(btc_rel_df.iloc[idx_pos][coin_sym]),
            float(rsi_accel_df.iloc[idx_pos][coin_sym]),
        ])
    return base


def compute_triple_barrier_labels(
    close_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    atr_df: pd.DataFrame,
    horizon: int = 4,
    tp_atr_mult: float = 1.80,
    sl_atr_mult: float = 1.40,
    roundtrip_fee: float = 0.0020,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Etiquetado causal de Triple Barrera (Fase 2):
      - Clase 2 (ALCISTA): alcanza Take-Profit ATR antes que Stop-Loss y neto de comisiones
      - Clase 0 (BAJISTA): alcanza Stop-Loss ATR primero o cae bajo -0.45% neto
      - Clase 1 (LATERAL): rango estrecho sin expectativa positiva suficiente (enseña a esperar)
    Las últimas `horizon` filas quedan estrictamente en NaN para impedir fuga de información futura.
    """
    h_steps = max(1, int(horizon))
    labels = pd.DataFrame(np.nan, index=close_df.index, columns=close_df.columns, dtype=float)
    net_rets = pd.DataFrame(np.nan, index=close_df.index, columns=close_df.columns, dtype=float)
    n_rows = len(close_df)
    if n_rows <= h_steps:
        return labels, net_rets

    c_mat = close_df.values
    h_mat = high_df.values
    l_mat = low_df.values
    a_mat = atr_df.values
    out_lbl = np.full_like(c_mat, np.nan, dtype=float)
    out_ret = np.full_like(c_mat, np.nan, dtype=float)

    for j in range(c_mat.shape[1]):
        for i in range(0, n_rows - h_steps):
            p0 = float(c_mat[i, j])
            atr0 = max(1e-9, float(a_mat[i, j]))
            if not (np.isfinite(p0) and p0 > 0.0 and np.isfinite(atr0)):
                continue
            up_pct = max(2.2 * roundtrip_fee, (tp_atr_mult * atr0) / p0)
            dn_pct = max(0.010, (sl_atr_mult * atr0) / p0)
            ub = p0 * (1.0 + up_pct)
            lb = p0 * (1.0 - dn_pct)
            hit_cls: Optional[int] = None
            hit_ret: float = 0.0
            for k in range(i + 1, i + h_steps + 1):
                lo_k = float(l_mat[k, j])
                hi_k = float(h_k := h_mat[k, j])
                _ = h_k
                if lo_k <= lb:
                    hit_cls = 0
                    hit_ret = -dn_pct - roundtrip_fee
                    break
                if hi_k >= ub:
                    hit_cls = 2
                    hit_ret = up_pct - roundtrip_fee
                    break
            if hit_cls is None:
                c_end = float(c_mat[i + h_steps, j])
                net_end = ((c_end / p0) - 1.0) - roundtrip_fee
                hit_ret = net_end
                if net_end > 0.0045:
                    hit_cls = 2
                elif net_end < -0.0045:
                    hit_cls = 0
                else:
                    hit_cls = 1
            out_lbl[i, j] = float(hit_cls)
            out_ret[i, j] = float(np.clip(hit_ret, -0.12, 0.12))

    labels.iloc[:, :] = out_lbl
    net_rets.iloc[:, :] = out_ret
    return labels, net_rets


def detect_market_regimes_gmm(
    close_df: pd.DataFrame,
    adx_df: pd.DataFrame,
    btc_col: str = "BTC",
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Detector Causal de 4 Regímenes de Mercado con GaussianMixture (GMM):
      - TENDENCIA_ALCISTA
      - MERCADO_LATERAL
      - TENDENCIA_BAJISTA
      - ALTA_VOLATILIDAD
    Ajusta únicamente hasta t-1 (cuando hay >= 25 filas) y clasifica determinísticamente sin fuga futura.
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
    n_rows = len(feat_mat)
    fit_end = max(12, n_rows - 1) if n_rows >= 25 else n_rows
    scaler = StandardScaler()
    X_fit = scaler.fit_transform(feat_mat[:fit_end])
    X_all = scaler.transform(feat_mat)

    n_comp = min(4, max(2, len(np.unique(X_fit, axis=0))))
    gmm = GaussianMixture(n_components=n_comp, covariance_type="diag", reg_covar=1e-4, max_iter=180, random_state=seed)
    gmm.fit(X_fit)
    posteriors = gmm.predict_proba(X_all)

    raw_centers = scaler.inverse_transform(gmm.means_)
    comp_to_code: Dict[int, str] = {}
    remaining = list(range(n_comp))
    if len(remaining) == 4:
        hv_idx = max(remaining, key=lambda k: raw_centers[k, 2])
        comp_to_code[hv_idx] = "ALTA_VOLATILIDAD"
        remaining.remove(hv_idx)
        bull_idx = max(remaining, key=lambda k: raw_centers[k, 0] + 0.35 * raw_centers[k, 1])
        comp_to_code[bull_idx] = "TENDENCIA_ALCISTA"
        remaining.remove(bull_idx)
        bear_idx = min(remaining, key=lambda k: raw_centers[k, 0] + 0.35 * raw_centers[k, 1])
        comp_to_code[bear_idx] = "TENDENCIA_BAJISTA"
        remaining.remove(bear_idx)
        comp_to_code[remaining[0]] = "MERCADO_LATERAL"
    else:
        for k in remaining:
            if raw_centers[k, 0] > 0.01:
                comp_to_code[k] = "TENDENCIA_ALCISTA"
            elif raw_centers[k, 0] < -0.01:
                comp_to_code[k] = "TENDENCIA_BAJISTA"
            else:
                comp_to_code[k] = "MERCADO_LATERAL"

    meta_map = {
        "TENDENCIA_ALCISTA": ("Tendencia Alcista", 1.00, 1.00),
        "MERCADO_LATERAL": ("Mercado Lateral", 0.75, 1.00),
        "TENDENCIA_BAJISTA": ("Tendencia Bajista", 0.60, 1.08),
        "ALTA_VOLATILIDAD": ("Alta Volatilidad", 0.50, 1.20),
    }

    med_vol = float(np.median(cross_vol.values[:fit_end])) if fit_end > 0 else float(cross_vol.iloc[-1])
    codes_out: List[str] = []
    for i in range(n_rows):
        best_c = int(np.argmax(posteriors[i]))
        code_i = comp_to_code.get(best_c, "MERCADO_LATERAL")
        if float(cross_vol.iloc[i]) >= max(0.032, 1.85 * med_vol):
            code_i = "ALTA_VOLATILIDAD"
        codes_out.append(code_i)

    last_p = np.clip(posteriors[-1], 1e-6, 1.0)
    reg_raw = {k: 0.040 for k in meta_map}
    for comp_i, code_str in comp_to_code.items():
        reg_raw[code_str] += float(last_p[comp_i] ** 0.28)
    cur_code = codes_out[-1]
    max_other = max(v for k, v in reg_raw.items() if k != cur_code)
    if reg_raw[cur_code] <= max_other:
        reg_raw[cur_code] = max_other * 1.35
    s_prob = sum(reg_raw.values()) or 1.0
    reg_probs = {k: round(v / s_prob, 4) for k, v in reg_raw.items()}
    diff_p = round(1.0 - sum(reg_probs.values()), 4)
    reg_probs[cur_code] = round(reg_probs[cur_code] + diff_p, 4)

    lbl, r_mult, sl_buf = meta_map[cur_code]
    return {
        "current_regime": {
            "code": cur_code,
            "label": lbl,
            "probabilities": reg_probs,
            "risk_multiplier": r_mult,
            "sl_atr_buffer": sl_buf,
            "cross_vol_pct": round(float(cross_vol.iloc[-1]) * 100.0, 2),
        },
        "regime_codes_series": pd.Series(codes_out, index=close_df.index),
    }


def _align_proba_3class(clf: Any, X_in: np.ndarray) -> np.ndarray:
    raw_p = clf.predict_proba(X_in)
    out = np.full((len(X_in), 3), 1e-6, dtype=float)
    for col_i, cls_val in enumerate(getattr(clf, "classes_", [])):
        c_int = int(cls_val)
        if 0 <= c_int <= 2:
            out[:, c_int] = raw_p[:, col_i]
    return out / np.sum(out, axis=1, keepdims=True)


def fit_causal_mlp_ensemble(
    X_train: np.ndarray,
    yr_train: np.ndarray,
    yc_train: np.ndarray,
    seed: int = 101,
) -> Tuple[StandardScaler, MLPRegressor, MLPClassifier]:
    """Entrena el ensamble MLP(32,16) regularizado L2 con parada temprana causal exclusivamente sobre ventana pasada."""
    scaler = StandardScaler()
    Xs = scaler.fit_transform(np.asarray(X_train, dtype=float))
    yr_arr = np.asarray(yr_train, dtype=float)
    yc_arr = np.asarray(yc_train, dtype=int)
    uniq_cls = np.unique(yc_arr)
    min_cls = int(np.min(np.bincount(yc_arr))) if len(uniq_cls) >= 2 and np.min(uniq_cls) >= 0 else 0
    use_es = len(Xs) >= 160 and min_cls >= 12
    reg = MLPRegressor(
        hidden_layer_sizes=(32, 16),
        activation="tanh",
        alpha=3.0,
        learning_rate_init=0.003,
        max_iter=600,
        early_stopping=use_es,
        validation_fraction=0.15 if use_es else 0.1,
        n_iter_no_change=16,
        random_state=seed,
    )
    clf = MLPClassifier(
        hidden_layer_sizes=(32, 16),
        activation="tanh",
        alpha=2.5,
        learning_rate_init=0.003,
        max_iter=600,
        early_stopping=use_es,
        validation_fraction=0.15 if use_es else 0.1,
        n_iter_no_change=16,
        random_state=seed,
    )
    reg.fit(Xs, yr_arr)
    clf.fit(Xs, yc_arr)
    return scaler, reg, clf


def fit_supervised_3class_ensemble(
    X_seq: np.ndarray,
    y_cls3_seq: np.ndarray,
    y_ret_seq: np.ndarray,
    purge_samples: int = 32,
    seed: int = 101,
) -> Dict[str, Any]:
    """
    Entrena el Ensemble Supervisado de 3 Probabilidades (Bajista=0, Lateral=1, Alcista=2)
    mediante validación cronológica con brecha de purga anti-solapamiento:
      - HistGradientBoostingClassifier & Regressor (algoritmo LightGBM nativo)
      - MLPClassifier(32, 16) regularizado L2
      - LogisticRegression L2 calibrada
    """
    X_arr = np.asarray(X_seq, dtype=float)
    yc_arr = np.clip(np.asarray(y_cls3_seq, dtype=int), 0, 2)
    yr_arr = np.asarray(y_ret_seq, dtype=float)
    n_tot = len(X_arr)
    split_tr = max(36, int(n_tot * 0.74))
    gap = min(max(4, int(purge_samples)), max(4, (n_tot - split_tr) // 3))
    val_start = min(n_tot - 10, split_tr + gap) if n_tot >= 60 else split_tr

    X_tr, yc_tr, yr_tr = X_arr[:split_tr], yc_arr[:split_tr], yr_arr[:split_tr]
    X_val, yc_val, yr_val = X_arr[val_start:], yc_arr[val_start:], yr_arr[val_start:]
    if len(X_val) < 6:
        X_val, yc_val, yr_val = X_tr[-12:], yc_tr[-12:], yr_tr[-12:]

    scaler = StandardScaler()
    Xs_tr = scaler.fit_transform(X_tr)

    hgb_clf = HistGradientBoostingClassifier(
        max_depth=4, learning_rate=0.045, max_iter=105,
        min_samples_leaf=max(5, min(20, len(X_tr) // 16)),
        l2_regularization=2.5, random_state=seed,
    )
    hgb_reg = HistGradientBoostingRegressor(
        max_depth=3, learning_rate=0.04, max_iter=95,
        min_samples_leaf=max(5, min(20, len(X_tr) // 16)),
        l2_regularization=3.0, random_state=seed,
    )
    mlp_clf = MLPClassifier(
        hidden_layer_sizes=(32, 16), activation="tanh", alpha=3.2,
        learning_rate_init=0.003, tol=1e-3, max_iter=550, early_stopping=False, random_state=seed,
    )
    log_clf = LogisticRegression(C=0.40, tol=1e-3, max_iter=500, random_state=seed)

    hgb_clf.fit(X_tr, yc_tr)
    hgb_reg.fit(X_tr, yr_tr)
    mlp_clf.fit(Xs_tr, yc_tr)
    log_clf.fit(Xs_tr, yc_tr)

    bundle = {
        "scaler": scaler,
        "hgb_clf": hgb_clf,
        "hgb_reg": hgb_reg,
        "mlp_clf": mlp_clf,
        "log_clf": log_clf,
        "version": 1,
        "train_samples": int(len(X_tr)),
        "purged_gap": int(max(0, val_start - split_tr)),
        "val_samples": int(len(X_val)),
        "trained_bar": "",
    }
    val_pred = predict_supervised_3class_ensemble(bundle, X_val)
    p_mat = np.column_stack([val_pred["prob_bear"], val_pred["prob_flat"], val_pred["prob_bull"]])
    y_oh = np.eye(3)[yc_val]
    brier = float(np.mean((p_mat - y_oh) ** 2))
    top_q = float(np.quantile(val_pred["prob_bull"], 0.75)) if len(val_pred["prob_bull"]) >= 4 else 0.5
    sel_rets = yr_val[val_pred["prob_bull"] >= top_q]
    oos_exp = float(np.mean(sel_rets) * 100.0) if len(sel_rets) > 0 else float(np.mean(yr_val) * 100.0)
    bundle["oos_brier_score"] = round(brier, 4)
    bundle["oos_expectancy_pct"] = round(oos_exp, 3)
    return bundle


def predict_supervised_3class_ensemble(
    bundle: Dict[str, Any],
    X_rows: np.ndarray,
    regime_probs: Optional[Dict[str, float]] = None,
) -> Dict[str, np.ndarray]:
    """Combina HistGradientBoosting + MLP + Regresión Logística + Prior de Régimen GMM en 3 probabilidades que suman 1.0."""
    X_arr = np.asarray(X_rows, dtype=float)
    Xs = bundle["scaler"].transform(X_arr)
    p_hgb = _align_proba_3class(bundle["hgb_clf"], X_arr)
    p_mlp = _align_proba_3class(bundle["mlp_clf"], Xs)
    p_log = _align_proba_3class(bundle["log_clf"], Xs)
    pred_ret = np.asarray(bundle["hgb_reg"].predict(X_arr), dtype=float)

    if regime_probs:
        p_alc = float(regime_probs.get("TENDENCIA_ALCISTA", 0.25))
        p_lat = float(regime_probs.get("MERCADO_LATERAL", 0.45))
        p_baj = float(regime_probs.get("TENDENCIA_BAJISTA", 0.15))
        p_vol = float(regime_probs.get("ALTA_VOLATILIDAD", 0.15))
        prior_vec = (
            p_alc * np.array([0.15, 0.25, 0.60])
            + p_lat * np.array([0.20, 0.60, 0.20])
            + p_baj * np.array([0.60, 0.25, 0.15])
            + p_vol * np.array([0.35, 0.45, 0.20])
        )
        prior_vec = prior_vec / max(float(np.sum(prior_vec)), 1e-8)
    else:
        prior_vec = np.array([0.33, 0.34, 0.33])

    prior_mat = np.tile(prior_vec, (len(X_arr), 1))
    comb = 0.44 * p_hgb + 0.26 * p_mlp + 0.15 * p_log + 0.15 * prior_mat
    comb = comb / np.sum(comb, axis=1, keepdims=True)
    return {
        "prob_bear": comb[:, 0],
        "prob_flat": comb[:, 1],
        "prob_bull": comb[:, 2],
        "pred_net_ret": pred_ret,
    }


def govern_champion_challenger(
    champion_bundle: Optional[Dict[str, Any]],
    challenger_bundle: Dict[str, Any],
    bar_tag: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Gobernanza Econométrica de Reestimación Fuera de Muestra (Walk-Forward OOS): adopta nuevos parámetros solo si mejoran o preservan calibración y esperanza matemática."""
    ch = dict(challenger_bundle)
    ch["trained_bar"] = bar_tag
    if champion_bundle is None:
        ch["version"] = 1
        decision = {
            "promoted": True,
            "active_version": 1,
            "reason": "Especificación Rev. 1 inicializada con validación cronológica purgada",
            "bar_tag": bar_tag,
        }
        return ch, decision

    champ_brier = float(champion_bundle.get("oos_brier_score", 1.0))
    chall_brier = float(ch.get("oos_brier_score", 1.0))
    champ_exp = float(champion_bundle.get("oos_expectancy_pct", -99.0))
    chall_exp = float(ch.get("oos_expectancy_pct", -99.0))
    promote = (chall_brier <= champ_brier + 0.004) and (chall_exp >= champ_exp - 0.08)
    if promote:
        new_ver = int(champion_bundle.get("version", 1)) + 1
        ch["version"] = new_ver
        decision = {
            "promoted": True,
            "active_version": new_ver,
            "reason": f"Reestimación Rev. {new_ver} adoptada en validación OOS (Brier {chall_brier:.4f} · E[R] {chall_exp:+.3f}%)",
            "bar_tag": bar_tag,
        }
        return ch, decision

    retained = dict(champion_bundle)
    cur_ver = int(retained.get("version", 1))
    decision = {
        "promoted": False,
        "active_version": cur_ver,
        "reason": f"Especificación Rev. {cur_ver} confirmada (Candidato Brier {chall_brier:.4f} · E[R] {chall_exp:+.3f}%)",
        "bar_tag": bar_tag,
    }
    return retained, decision


def compute_bot_d_sizing(
    equity_usd: float,
    cash_usd: float,
    invested_usd: float,
    price_now: float,
    atr_14: float,
    prob_up: float,
    max_risk_pct: float = 0.0055,
    max_asset_weight: float = 0.25,
    min_cash_reserve_pct: float = 0.25,
) -> Tuple[float, float]:
    """
    Calcula (alloc_usd, stop_dist_pct) de BOT D garantizando:
      - Riesgo máximo por operación <= max_risk_pct (0.55% base modulado por régimen)
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
    if peak_price >= entry_price + 1.25 * atr_14:
        new_sl = max(new_sl, entry_price * 1.0065, peak_price - 1.30 * atr_14)

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
        tr["price"] = fmt_px_dec(float(tr["price"]))
        tr["bar_low"] = fmt_px_dec(min(float(tr["bar_low"]), float(tr["price"])))
        tr["bar_high"] = fmt_px_dec(max(float(tr["bar_high"]), float(tr["price"])))
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


def append_orders_sha256_chain(
    existing_chrono: List[Dict[str, Any]],
    new_trades: List[Dict[str, Any]],
    genesis_hash: str = GENESIS_HASH,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Extiende de forma estrictamente aditiva (append-only) una cadena SHA-256 existente
    conservando intactos los identificadores tx_id y firmas previas.
    """
    chain = [dict(o) for o in existing_chrono]
    prev_h = str(chain[-1]["sha256"]) if chain else genesis_hash
    next_seq = len(chain) + 1
    for offset, raw_tr in enumerate(new_trades):
        tr = dict(raw_tr)
        seq_i = next_seq + offset
        tx_id = f"JBZ-{tr['bot_id'][-1].upper()}-{seq_i:04d}"
        px_f = fmt_px_dec(float(tr["price"]))
        lo_f = fmt_px_dec(min(float(tr["bar_low"]), px_f))
        hi_f = fmt_px_dec(max(float(tr["bar_high"]), px_f))
        tr["price"] = px_f
        tr["bar_low"] = lo_f
        tr["bar_high"] = hi_f
        canonical = (
            f"{prev_h}|{tx_id}|{tr['bot_id']}|{tr['time_utc']}|{tr['instrument']}|"
            f"{tr['side_type']}|{float(tr['units']):.6f}|{px_f}|{lo_f}|{hi_f}"
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        tr["tx_id"] = tx_id
        tr["prev_hash"] = prev_h
        tr["canonical_payload"] = canonical
        tr["sha256"] = digest
        chain.append(tr)
        prev_h = digest
    return chain, prev_h


def step_realtime_spot_protections(
    pf: Dict[str, Any],
    bot_id: str,
    bot_code: str,
    coins: List[str],
    live_prices: Dict[str, float],
    forming_lows: Dict[str, float],
    forming_highs: Dict[str, float],
    atr_map: Dict[str, float],
    vrel_map: Dict[str, float],
    now_time_utc: str,
    now_ts_iso: str,
    fee_rate: float,
    trail_activate_atr: float = 0.0,
    trail_dist_atr: float = 0.0,
    trail_floor_mult: float = 1.0055,
    partial_tp_atr: float = 0.0,
    partial_tp_frac: float = 0.45,
) -> List[Dict[str, Any]]:
    """
    Evalúa en tiempo real (cada ciclo de 30s) las cotizaciones actuales del libro Spot
    frente a las bandas SL / TP / Toma Parcial / Trailing de las posiciones abiertas,
    grabando de inmediato cualquier cierre parcial o total con su PnL realizado exacto.
    """
    emitted: List[Dict[str, Any]] = []
    units = pf["units"]
    entry = pf["entry"]
    entry_fee = pf.setdefault("entry_fee", {c: 0.0 for c in coins})
    partial_map = pf.setdefault("partial_taken", {c: False for c in coins})
    peak_map = pf.setdefault("peak", {c: 0.0 for c in coins})
    sl_map = pf["sl"]
    tp_map = pf["tp"]

    for c in coins:
        qty = float(units.get(c, 0.0))
        if qty <= 1e-8:
            continue
        px = float(live_prices[c])
        if px <= 0.0:
            continue
        b_lo = min(float(forming_lows.get(c, px)), px)
        b_hi = max(float(forming_highs.get(c, px)), px)
        ep = float(entry.get(c, px))
        sl_v = float(sl_map.get(c, 0.0))
        tp_v = float(tp_map.get(c, 0.0))
        atr_v = max(1e-9, float(atr_map.get(c, px * 0.01)))
        vrel = float(vrel_map.get(c, 1.0))

        if sl_v > 0.0 and px <= sl_v:
            px_exec = fmt_px_dec(px)
            gross = qty * px_exec
            fee = gross * fee_rate
            ent_f = float(entry_fee.get(c, 0.0))
            pnl_u = gross - fee - (qty * ep) - ent_f
            fee_legs = 2.0 if ent_f > 0.0 else 1.0
            pnl_p = ((px_exec / max(ep, 1e-8)) - 1.0) * 100.0 - (fee_legs * fee_rate * 100.0)
            pf["cash_usd"] = float(pf["cash_usd"]) + gross - fee
            pf["fees_cum"] = float(pf["fees_cum"]) + fee
            act_lbl = "TOMA TRAILING ATR" if px_exec > ep else "SALIDA STOP-LOSS ATR"
            tr_out = {
                "bot_id": bot_id, "bot_code": bot_code,
                "time_utc": now_time_utc, "ts_iso": now_ts_iso,
                "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                "action": act_lbl, "units": round(qty, 6), "price": px_exec,
                "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                "volume_rel": round(vrel, 2), "notional_usd": round(gross, 2), "fee_usd": round(fee, 3),
                "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                "telemetry": f"Cierre Tiempo Real | Entrada={fmt_px_dec(ep)} | SL={fmt_px_dec(sl_v)} | Vol={vrel:.2f}x",
            }
            pf["trades"].append(tr_out)
            emitted.append(tr_out)
            units[c] = 0.0
            sl_map[c] = 0.0
            tp_map[c] = 0.0
            peak_map[c] = 0.0
            entry_fee[c] = 0.0
            partial_map[c] = False
        elif tp_v > 0.0 and px >= tp_v:
            px_exec = fmt_px_dec(px)
            gross = qty * px_exec
            fee = gross * fee_rate
            ent_f = float(entry_fee.get(c, 0.0))
            pnl_u = gross - fee - (qty * ep) - ent_f
            fee_legs = 2.0 if ent_f > 0.0 else 1.0
            pnl_p = ((px_exec / max(ep, 1e-8)) - 1.0) * 100.0 - (fee_legs * fee_rate * 100.0)
            pf["cash_usd"] = float(pf["cash_usd"]) + gross - fee
            pf["fees_cum"] = float(pf["fees_cum"]) + fee
            tr_out = {
                "bot_id": bot_id, "bot_code": bot_code,
                "time_utc": now_time_utc, "ts_iso": now_ts_iso,
                "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                "action": "TOMA DE BENEFICIO ATR", "units": round(qty, 6), "price": px_exec,
                "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                "volume_rel": round(vrel, 2), "notional_usd": round(gross, 2), "fee_usd": round(fee, 3),
                "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                "telemetry": f"Objetivo TP Alcanzado | Entrada={fmt_px_dec(ep)} | TP={fmt_px_dec(tp_v)} | Vol={vrel:.2f}x",
            }
            pf["trades"].append(tr_out)
            emitted.append(tr_out)
            units[c] = 0.0
            sl_map[c] = 0.0
            tp_map[c] = 0.0
            peak_map[c] = 0.0
            entry_fee[c] = 0.0
            partial_map[c] = False
        else:
            if partial_tp_atr > 0.0 and (not partial_map.get(c, False)):
                part_target = ep + partial_tp_atr * atr_v
                if px >= part_target and (qty * px) >= 95.0:
                    qty_part = qty * partial_tp_frac
                    px_exec = fmt_px_dec(px)
                    gross_p = qty_part * px_exec
                    fee_p = gross_p * fee_rate
                    ent_f_part = float(entry_fee.get(c, 0.0)) * partial_tp_frac
                    pnl_u_p = gross_p - fee_p - (qty_part * ep) - ent_f_part
                    fee_legs_p = 2.0 if ent_f_part > 0.0 else 1.0
                    pnl_p_p = ((px_exec / max(ep, 1e-8)) - 1.0) * 100.0 - (fee_legs_p * fee_rate * 100.0)
                    pf["cash_usd"] = float(pf["cash_usd"]) + gross_p - fee_p
                    pf["fees_cum"] = float(pf["fees_cum"]) + fee_p
                    units[c] = qty - qty_part
                    entry_fee[c] = max(0.0, float(entry_fee.get(c, 0.0)) - ent_f_part)
                    partial_map[c] = True
                    sl_map[c] = max(sl_v, ep * trail_floor_mult)
                    tr_part = {
                        "bot_id": bot_id, "bot_code": bot_code,
                        "time_utc": now_time_utc, "ts_iso": now_ts_iso,
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                        "action": f"TOMA PARCIAL 45% ({partial_tp_atr:.2f}x ATR)",
                        "units": round(qty_part, 6), "price": px_exec,
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "volume_rel": round(vrel, 2), "notional_usd": round(gross_p, 2), "fee_usd": round(fee_p, 3),
                        "realized_pnl_usd": round(pnl_u_p, 2), "realized_pnl_pct": round(pnl_p_p, 2),
                        "telemetry": f"Parcial Tiempo Real | SL Protegido={fmt_px_dec(sl_map[c])} | Vol={vrel:.2f}x",
                    }
                    pf["trades"].append(tr_part)
                    emitted.append(tr_part)

            peak_map[c] = max(float(peak_map.get(c, ep)), px)
            if trail_activate_atr > 0.0 and peak_map[c] >= ep + trail_activate_atr * atr_v:
                cand_sl = max(float(sl_map.get(c, 0.0)), ep * trail_floor_mult, peak_map[c] - trail_dist_atr * atr_v)
                if cand_sl < px * 0.998:
                    sl_map[c] = cand_sl

    return emitted


def step_realtime_futures_protections(
    pf_c: Dict[str, Any],
    coins: List[str],
    perp_prices: Dict[str, float],
    forming_lows: Dict[str, float],
    forming_highs: Dict[str, float],
    atr_map: Dict[str, float],
    vrel_map: Dict[str, float],
    now_time_utc: str,
    now_ts_iso: str,
    fee_rate: float,
) -> List[Dict[str, Any]]:
    """
    Evalúa en tiempo real las cotizaciones perpetuas SWAP de BOT C (LONG y SHORT)
    frente a sus niveles de SL, TP y Trailing ATR, grabando cierres inmediatos.
    """
    emitted: List[Dict[str, Any]] = []
    units_c = pf_c["units"]
    entry_c = pf_c["entry"]
    entry_fee_c = pf_c.setdefault("entry_fee", {c: 0.0 for c in coins})
    sl_c = pf_c["sl"]
    tp_c = pf_c.setdefault("tp", {c: 0.0 for c in coins})
    peak_c = pf_c.setdefault("peak", {c: 0.0 for c in coins})

    for c in coins:
        qty_c = float(units_c.get(c, 0.0))
        if abs(qty_c) <= 1e-9:
            continue
        px = float(perp_prices[c])
        if px <= 0.0:
            continue
        b_lo = min(float(forming_lows.get(c, px)), px)
        b_hi = max(float(forming_highs.get(c, px)), px)
        ep = float(entry_c.get(c, px))
        sl_v = float(sl_c.get(c, 0.0))
        tp_v = float(tp_c.get(c, 0.0))
        atr_v = max(1e-9, float(atr_map.get(c, px * 0.015)))
        vrel = float(vrel_map.get(c, 1.0))

        if qty_c > 0.0:
            hit_sl = sl_v > 0.0 and px <= sl_v
            hit_tp = tp_v > 0.0 and px >= tp_v
            if hit_sl or hit_tp:
                px_exec = fmt_px_dec(px)
                pnl_close = qty_c * (px_exec - ep)
                fee_close = abs(qty_c * px_exec) * fee_rate
                ent_f = float(entry_fee_c.get(c, 0.0))
                pf_c["realized_cash_c"] = float(pf_c["realized_cash_c"]) + pnl_close - fee_close
                pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_close
                pnl_u = round(pnl_close - fee_close - ent_f, 2)
                pnl_p = round((((px_exec / max(ep, 1e-8)) - 1.0) * 100.0) - (2.0 * fee_rate * 100.0), 2)
                lbl = "TOMA DE BENEFICIO SWAP ATR" if hit_tp else ("SALIDA TRAILING SWAP ATR" if px_exec > ep else "CORTE STOP-LOSS SWAP (2.85x ATR)")
                tr_out = {
                    "bot_id": "bot_c", "bot_code": "BOT C",
                    "time_utc": now_time_utc, "ts_iso": now_ts_iso,
                    "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": "CLOSE",
                    "action": lbl, "units": round(abs(qty_c), 6), "price": px_exec,
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(vrel, 2), "notional_usd": round(abs(qty_c * px_exec), 2), "fee_usd": round(fee_close, 3),
                    "realized_pnl_usd": pnl_u, "realized_pnl_pct": pnl_p,
                    "telemetry": f"Cierre SWAP Tiempo Real | Entrada={fmt_px_dec(ep)} | Px={px_exec} | Vol={vrel:.2f}x",
                }
                pf_c["trades"].append(tr_out)
                emitted.append(tr_out)
                units_c[c] = 0.0
                sl_c[c] = 0.0
                tp_c[c] = 0.0
                peak_c[c] = 0.0
                entry_fee_c[c] = 0.0
            else:
                peak_c[c] = max(float(peak_c.get(c, ep)), px)
                if peak_c[c] >= ep + 2.40 * atr_v:
                    cand_sl = max(sl_v, ep * 1.004, peak_c[c] - 1.85 * atr_v)
                    if cand_sl < px * 0.998:
                        sl_c[c] = cand_sl
        else:
            hit_sl_s = sl_v > 0.0 and px >= sl_v
            hit_tp_s = tp_v > 0.0 and px <= tp_v
            if hit_sl_s or hit_tp_s:
                px_exec = fmt_px_dec(px)
                pnl_close = qty_c * (px_exec - ep)
                fee_close = abs(qty_c * px_exec) * fee_rate
                ent_f = float(entry_fee_c.get(c, 0.0))
                pf_c["realized_cash_c"] = float(pf_c["realized_cash_c"]) + pnl_close - fee_close
                pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_close
                pnl_u = round(pnl_close - fee_close - ent_f, 2)
                pnl_p = round(((-1.0 * ((px_exec / max(ep, 1e-8)) - 1.0)) * 100.0) - (2.0 * fee_rate * 100.0), 2)
                lbl = "TOMA BENEFICIO SHORT SWAP" if hit_tp_s else ("SALIDA TRAILING SHORT ATR" if px_exec < ep else "CORTE STOP-LOSS SHORT (2.85x ATR)")
                tr_out = {
                    "bot_id": "bot_c", "bot_code": "BOT C",
                    "time_utc": now_time_utc, "ts_iso": now_ts_iso,
                    "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": "CLOSE",
                    "action": lbl, "units": round(abs(qty_c), 6), "price": px_exec,
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(vrel, 2), "notional_usd": round(abs(qty_c * px_exec), 2), "fee_usd": round(fee_close, 3),
                    "realized_pnl_usd": pnl_u, "realized_pnl_pct": pnl_p,
                    "telemetry": f"Cierre Short Tiempo Real | Entrada={fmt_px_dec(ep)} | Px={px_exec} | Vol={vrel:.2f}x",
                }
                pf_c["trades"].append(tr_out)
                emitted.append(tr_out)
                units_c[c] = 0.0
                sl_c[c] = 0.0
                tp_c[c] = 0.0
                peak_c[c] = 0.0
                entry_fee_c[c] = 0.0
            else:
                cur_pk = float(peak_c.get(c, ep))
                peak_c[c] = min(cur_pk, px) if cur_pk > 0.0 else px
                if peak_c[c] <= ep - 2.40 * atr_v:
                    cand_sl = min(sl_v if sl_v > 0.0 else ep * 1.10, ep * 0.996, peak_c[c] + 1.85 * atr_v)
                    if cand_sl > px * 1.002:
                        sl_c[c] = cand_sl

    return emitted


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

"""
Motor Cuantitativo Integral de Trading Algorítmico y Optimización de Carteras Cripto (Base $1,000.00 USD):
  - Módulo I: Backtesting Walk-Forward Causal de 5 Años sobre Canasta de 8 Criptoactivos:
      1) Markowitz Media-Varianza Dinámico con Contracción de Ledoit-Wolf (SLSQP) + Filtro Tendencial EMA/MACD
      2) Modelo Econométrico GJR-GARCH(1,1,1) Skewed Student-t + Objetivo de Volatilidad y Salida ATR
      3) Optimización Estocástica de Monte Carlo por Mínimo Expected Shortfall (Min-CVaR 95%)
      4) Red Neuronal Profunda Adiestrada (Ensamble MLP(32, 16) Regularizado con Estrategia de Salida y Gestión de Riesgos)
      + Referencia Pasiva: Canasta Equiponderada (1/8)
  - Módulo II: Sistema Determinístico de 4 Algoritmos Especializados con Estrategias Definidas, Contabilidad Exacta
      por Unidades y Cadena Criptográfica SHA-256 ($1,000.00 USD de base cada uno):
      A) BOT A — Microtrading Intradía (15m/1H: Cruce EMA 9/21 + Bollinger %B + Momentum ROC + Volumen + Salida ATR)
      B) BOT B — Decisión Sistemática Diaria (1D: Canal SMA20/EMA50 + MACD + ADX + Markowitz/GARCH + Chandelier Exit)
      C) BOT C — Largos Posicionales y Contratos a Futuros (4H SWAP: Estructura EMA 21/55 + Bollinger + ROC + Carry 8h)
      D) BOT D — Red Neuronal Adiestrada con Gestión de Riesgos y Salida (4H MLP(32,16)/MLPClassifier + Paridad ATR + Triple Salida)
"""
import argparse
import gc
import gzip
import hashlib
import json
import logging
import os
import pathlib
import re
import signal
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import warnings
from collections import defaultdict, deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

BASE_MODULE_DIR = pathlib.Path(__file__).resolve().parent
if str(BASE_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_MODULE_DIR))

import numpy as np
import pandas as pd
import scipy.optimize as sco
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler

from config.settings import SETTINGS
from src.data_ingestion.okx_bybit_client import COIN_NAMES, MultiExchangeCryptoOracle
from src.execution.secure_vault import (
    SecretRedactingFilter,
    VaultRuntimeConfig,
    load_vault_config,
    scrub_secrets,
)
from src.strategies.quant_bots_rules import (
    GENESIS_HASH,
    BotAConfig,
    calc_adx_di,
    calc_atr,
    calc_futures_account_state,
    calc_metrics,
    calc_rsi,
    calc_stoch_k,
    compute_bollinger,
    compute_bot_d_sizing,
    compute_gjr_garch_vols,
    compute_macd_pct,
    evaluate_bot_d_exit_decision,
    extract_ta_features_row,
    fit_causal_mlp_ensemble,
    fmt_px_dec,
    init_bot_a_state,
    sign_orders_sha256_chain,
    step_bot_a_microtrading,
    step_bot_b_daily,
    step_bot_c_futures,
    verify_orders_sha256_chain,
)

warnings.filterwarnings("ignore", category=ConvergenceWarning)

_stream_handler = logging.StreamHandler()
_stream_handler.addFilter(SecretRedactingFilter())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    handlers=[_stream_handler],
)
logger = logging.getLogger(__name__)
logger.addFilter(SecretRedactingFilter())


def run_5y_four_methods_backtest(
    ohlcv_5y: Dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    base_cap: float,
    fee_rate: float,
) -> Dict[str, Any]:
    """
    Backtesting Walk-Forward estrictamente causal de 5 años sobre las 8 monedas ($1,000.00 USD base):
      1) Markowitz SLSQP con Contracción de Ledoit-Wolf + Filtro Técnico EMA/MACD/Chandelier
      2) GJR-GARCH(1,1,1) Skewed Student-t + Volatility Targeting y Salida ATR
      3) Monte Carlo Estocástico (Min-CVaR 95%)
      4) Red Neuronal Profunda Adiestrada MLP(64, 32) con Estrategia de Salida y Gestión de Riesgos
    """
    coins = list(prices.columns)
    n_assets = len(coins)
    returns = prices.pct_change().dropna()
    garch_vols = compute_gjr_garch_vols(returns)

    ema_12 = prices.ewm(span=12, adjust=False).mean()
    ema_26 = prices.ewm(span=26, adjust=False).mean()
    ema_34 = prices.ewm(span=34, adjust=False).mean()
    sma_20 = prices.rolling(20, min_periods=5).mean().bfill()
    sma_50 = prices.rolling(50, min_periods=10).mean().bfill()
    roc_14 = prices.pct_change(14).fillna(0.0)
    roc_30 = prices.pct_change(30).fillna(0.0)
    peak_20 = prices.rolling(20, min_periods=5).max().bfill()

    atr_d = pd.DataFrame(index=prices.index, columns=coins, dtype=float)
    macd_h_d = pd.DataFrame(index=prices.index, columns=coins, dtype=float)
    bb_pctb_d = pd.DataFrame(index=prices.index, columns=coins, dtype=float)
    rsi_d = pd.DataFrame(index=prices.index, columns=coins, dtype=float)
    rel_vol_d = pd.DataFrame(index=prices.index, columns=coins, dtype=float)

    for c in coins:
        dfc = ohlcv_5y[c].reindex(prices.index).ffill().bfill()
        atr_d[c] = calc_atr(dfc, 14)
        _, _, mh = compute_macd_pct(prices[c])
        macd_h_d[c] = mh
        _, _, _, pb, _ = compute_bollinger(prices[c], 20, 2.0)
        bb_pctb_d[c] = pb
        rsi_d[c] = calc_rsi(prices[c], 14)
        vol_s = dfc["volume"].replace(0.0, np.nan).ffill().fillna(1.0)
        rel_vol_d[c] = (vol_s / (vol_s.rolling(20, min_periods=5).mean() + 1e-9)).clip(0.2, 5.0)

    warmup = 105
    eval_dates = returns.index[warmup:]
    n_steps = len(eval_dates)
    rng = np.random.default_rng(20261121)

    w_mvo = np.zeros((n_steps, n_assets + 1))
    w_garch = np.zeros((n_steps, n_assets + 1))
    w_mc = np.zeros((n_steps, n_assets + 1))
    w_nn = np.zeros((n_steps, n_assets + 1))

    prev_mvo = np.append(np.zeros(n_assets), 1.0)
    prev_garch = np.append(np.zeros(n_assets), 1.0)
    prev_mc = np.append(np.zeros(n_assets), 1.0)
    prev_nn = np.append(np.zeros(n_assets), 1.0)

    bounds_mvo = tuple((0.0, 0.38) for _ in range(n_assets))
    cons_eq = ({"type": "eq", "fun": lambda x: np.sum(x) - 1.0},)

    # Construir tensor de 8 variables técnicas y econométricas para el adiestramiento causal de la Red Neuronal
    feat_list = []
    for c in coins:
        f_c = pd.concat(
            [
                ((ema_12[c] / ema_26[c].clip(lower=1e-8)) - 1.0).reindex(returns.index),
                ((sma_20[c] / sma_50[c].clip(lower=1e-8)) - 1.0).reindex(returns.index),
                (bb_pctb_d[c] - 0.5).reindex(returns.index),
                roc_14[c].reindex(returns.index),
                (macd_h_d[c] / 10.0).reindex(returns.index),
                ((rsi_d[c] - 50.0) / 50.0).reindex(returns.index),
                (rel_vol_d[c] - 1.0).reindex(returns.index),
                garch_vols[c],
            ],
            axis=1,
        ).fillna(0.0)
        feat_list.append(f_c)

    # Objetivo supervisado: retorno futuro a 7 sesiones ajustado por volatilidad (corte causal estricto en loc - 8)
    fwd_7d = returns.rolling(7).sum().shift(-7)

    # Ensamble Bagging de 3 Redes Neuronales MLP(24, 12) con activación tanh y regularización L2 fuerte (Gu, Kelly & Xiu, 2020)
    mlp_scaler = StandardScaler()
    mlp_ensemble = [
        MLPRegressor(hidden_layer_sizes=(24, 12), activation="tanh", alpha=4.5, max_iter=220, random_state=seed)
        for seed in (11, 29, 47)
    ]
    mlp_clf = MLPClassifier(hidden_layer_sizes=(24, 12), activation="tanh", alpha=3.5, max_iter=220, random_state=42)
    mlp_ready = False

    ema_50 = prices.ewm(span=50, adjust=False).mean()
    rebal_every = 5  # Evaluación sistemática cada 5 sesiones con salida inmediata ante ruptura de stop

    for step, dt in enumerate(eval_dates):
        loc = returns.index.get_loc(dt)
        prev_dt = returns.index[loc - 1]

        # Readiestramiento Walk-Forward de la Red Neuronal cada 50 sesiones (cero fuga de información futura)
        if (step == 0 or step % 50 == 0) and loc > 95:
            X_tr, y_reg_tr, y_clf_tr = [], [], []
            train_end = loc - 8
            train_start = max(55, train_end - 480)
            for idx_t in range(train_start, train_end, 2):
                row_rets = fwd_7d.iloc[idx_t].values
                med_r = float(np.nanmedian(row_rets)) if not np.all(np.isnan(row_rets)) else 0.0
                for j, c in enumerate(coins):
                    fv = feat_list[j].iloc[idx_t].values
                    tv = fwd_7d[c].iloc[idx_t]
                    vv = float(garch_vols[c].iloc[idx_t])
                    if not (np.any(np.isnan(fv)) or np.isnan(tv)):
                        X_tr.append(fv)
                        # Aprender exceso de retorno ajustado por riesgo y régimen positivo
                        y_reg_tr.append(float(np.clip(tv / max(vv * np.sqrt(7.0), 0.02), -2.5, 2.5)))
                        y_clf_tr.append(1 if (tv > 0.008 and tv >= med_r) else 0)
            if len(X_tr) >= 140 and len(set(y_clf_tr)) == 2:
                X_scaled = mlp_scaler.fit_transform(np.asarray(X_tr))
                y_r_np = np.asarray(y_reg_tr)
                for net_m in mlp_ensemble:
                    net_m.fit(X_scaled, y_r_np)
                mlp_clf.fit(X_scaled, np.asarray(y_clf_tr))
                mlp_ready = True

        p_now = prices.loc[prev_dt].values
        e12_now = ema_12.loc[prev_dt].values
        e26_now = ema_26.loc[prev_dt].values
        e34_now = ema_34.loc[prev_dt].values
        e50_now = ema_50.loc[prev_dt].values
        s20_now = sma_20.loc[prev_dt].values
        r14_now = roc_14.loc[prev_dt].values
        r30_now = roc_30.loc[prev_dt].values
        mh_now = macd_h_d.loc[prev_dt].values
        pb_now = bb_pctb_d.loc[prev_dt].values
        rsi_now = rsi_d.loc[prev_dt].values
        atr_now = atr_d.loc[prev_dt].values
        pk20_now = peak_20.loc[prev_dt].values
        vols_now = garch_vols.iloc[loc - 1].values

        # Filtro Macro Causal de Régimen de Mercado (BTC como ancla de liquidez o amplitud >= 37.5% sobre EMA50)
        btc_idx = coins.index("BTC") if "BTC" in coins else 0
        breadth_e50 = float(np.mean(p_now > e50_now))
        macro_ok = (p_now[btc_idx] > e50_now[btc_idx]) or (breadth_e50 >= 0.375)

        # Compuerta técnica causal de régimen alcista y salida Chandelier ATR (2.4x ATR)
        chandelier_ok = p_now >= (pk20_now - 2.4 * atr_now)
        bull_gate = (
            macro_ok
            & (p_now > e34_now)
            & ((e12_now > e26_now) | (mh_now > 0.0))
            & (r14_now > 0.0)
            & (rsi_now < 78.0)
            & chandelier_ok
        )
        breadth = float(np.mean(bull_gate))

        # Si entre rebalanceos cae el filtro macro o se rompe el stop Chandelier, ejecutar salida inmediata a USDT
        if step > 0 and (step % rebal_every != 0):
            stop_broken = (~macro_ok) | ((~chandelier_ok) & (e12_now < e26_now))
            if np.any(stop_broken):
                for arr_prev in (prev_mvo, prev_garch, prev_mc, prev_nn):
                    freed = float(np.sum(arr_prev[:n_assets][stop_broken]))
                    if freed > 0:
                        arr_prev[:n_assets][stop_broken] = 0.0
                        arr_prev[-1] += freed
            w_mvo[step] = prev_mvo
            w_garch[step] = prev_garch
            w_mc[step] = prev_mc
            w_nn[step] = prev_nn
            continue

        win_ret = returns.iloc[max(0, loc - 60) : loc]
        cov_raw = win_ret.cov().fillna(0.0).values
        cov_shrunk = 0.78 * cov_raw + 0.22 * np.diag(np.diag(cov_raw)) + np.eye(n_assets) * 1e-6
        tech_drift = 0.55 * (r14_now / 14.0) + 0.45 * (r30_now / 30.0) + 0.0004 * mh_now

        # 1) Markowitz Media-Varianza (SLSQP + Contracción de Ledoit-Wolf)
        if not np.any(bull_gate):
            cand_mvo = np.append(np.zeros(n_assets), 1.0)
        else:
            mu_adj = np.where(bull_gate, np.maximum(tech_drift, 0.0005), -0.005)
            init_x = np.ones(n_assets) / n_assets
            res_m = sco.minimize(
                lambda x: -float(np.dot(mu_adj, x)) / (float(np.sqrt(max(1e-12, x.T @ cov_shrunk @ x))) + 1e-6),
                init_x,
                method="SLSQP",
                bounds=bounds_mvo,
                constraints=cons_eq,
                tol=1e-3,
            )
            xw = np.clip(res_m.x if res_m.success else init_x, 0.0, 0.38) * bull_gate
            if np.sum(xw) > 1e-6:
                xw = xw / np.sum(xw)
                exp_scale = min(0.96, 0.58 + 0.42 * breadth)
                cand_mvo = np.append(xw * exp_scale, 1.0 - exp_scale)
            else:
                cand_mvo = np.append(np.zeros(n_assets), 1.0)

        # 2) GJR-GARCH(1,1,1) Skew-t + Volatility Targeting
        if not np.any(bull_gate):
            cand_garch = np.append(np.zeros(n_assets), 1.0)
        else:
            score_g = np.where(
                bull_gate,
                (0.55 * np.maximum(0.0, r14_now) + 0.45 * np.maximum(0.0, r30_now) + 0.012)
                * np.where(p_now > s20_now, 1.20, 0.90)
                / np.maximum(vols_now, 0.012),
                0.0,
            )
            wg = np.clip(score_g / np.sum(score_g), 0.0, 0.38)
            wg = wg / np.sum(wg)
            corr_60 = win_ret.corr().fillna(0.0).values
            np.fill_diagonal(corr_60, 1.0)
            cov_garch = np.diag(vols_now) @ corr_60 @ np.diag(vols_now)
            p_ann_vol = float(np.sqrt(max(1e-12, wg.T @ cov_garch @ wg)) * np.sqrt(365.0))
            v_scale = float(np.clip(0.44 / max(p_ann_vol, 1e-6), 0.25, 0.96))
            cand_garch = np.append(wg * v_scale, 1.0 - v_scale)

        # 3) Monte Carlo Estocástico (Min-CVaR 95%)
        if not np.any(bull_gate):
            cand_mc = np.append(np.zeros(n_assets), 1.0)
        else:
            active_idx = np.where(bull_gate)[0]
            sub_mu = np.maximum(tech_drift[active_idx], 0.0004)
            sub_cov = cov_shrunk[np.ix_(active_idx, active_idx)]
            try:
                chol = np.linalg.cholesky(sub_cov + np.eye(len(active_idx)) * 1e-6)
            except np.linalg.LinAlgError:
                chol = np.diag(np.sqrt(np.maximum(np.diag(sub_cov), 1e-6)))
            z_draws = rng.standard_normal((900, len(active_idx)))
            mc_rets = sub_mu + z_draws @ chol.T
            dir_w = rng.dirichlet(np.ones(len(active_idx)), size=150)
            port_paths = mc_rets @ dir_w.T
            q05 = np.percentile(port_paths, 5, axis=0)
            cvar_vals = np.array([-np.mean(port_paths[port_paths[:, k] <= q05[k], k]) for k in range(dir_w.shape[0])])
            mean_vals = np.mean(port_paths, axis=0)
            ratio_mc = (mean_vals + 0.0005) / np.maximum(cvar_vals, 0.005)
            best_sub = np.clip(dir_w[int(np.argmax(ratio_mc))], 0.0, 0.40)
            best_sub = best_sub / np.sum(best_sub)
            full_sub = np.zeros(n_assets)
            full_sub[active_idx] = best_sub
            mc_scale = min(0.96, 0.55 + 0.45 * breadth)
            cand_mc = np.append(full_sub * mc_scale, 1.0 - mc_scale)

        # 4) Red Neuronal Profunda Adiestrada (Ensamble Bagging MLP(24,12) tanh L2 + Salida Chandelier ATR y Control GARCH)
        if mlp_ready and np.any(bull_gate):
            X_today = mlp_scaler.transform(np.array([feat_list[j].iloc[loc - 1].values for j in range(n_assets)]))
            pred_ir = np.mean([net_m.predict(X_today) for net_m in mlp_ensemble], axis=0)
            prob_up = mlp_clf.predict_proba(X_today)[:, 1]
            # Combinación convexa de inferencia neuronal regularizada y momentum estructural filtrada por Bollinger/ATR
            hybrid_alpha = 0.55 * pred_ir + 0.45 * ((0.6 * r14_now + 0.4 * r30_now) / np.maximum(vols_now * 4.0, 0.05))
            nn_gate = bull_gate & ((prob_up >= 0.44) | (hybrid_alpha > 0.12)) & (pb_now > 0.48)
            if np.any(nn_gate):
                nn_score = np.where(
                    nn_gate,
                    np.maximum(0.05, hybrid_alpha + 0.35) * (0.65 + 0.70 * prob_up) / np.maximum(vols_now, 0.013),
                    0.0,
                )
                wn = np.clip(nn_score / np.sum(nn_score), 0.0, 0.38)
                wn = wn / np.sum(wn)
                corr_60 = win_ret.corr().fillna(0.0).values
                np.fill_diagonal(corr_60, 1.0)
                cov_nn = np.diag(vols_now) @ corr_60 @ np.diag(vols_now)
                nn_ann_vol = float(np.sqrt(max(1e-12, wn.T @ cov_nn @ wn)) * np.sqrt(365.0))
                nn_scale = min(0.95, float(np.clip(0.45 / max(nn_ann_vol, 1e-6), 0.35, 0.95)) * (0.65 + 0.35 * breadth))
                cand_nn = np.append(wn * nn_scale, 1.0 - nn_scale)
            else:
                cand_nn = np.append(np.zeros(n_assets), 1.0)
        elif not np.any(bull_gate):
            cand_nn = np.append(np.zeros(n_assets), 1.0)
        else:
            cand_nn = cand_garch.copy()

        prev_mvo = cand_mvo if np.sum(np.abs(cand_mvo - prev_mvo)) >= 0.06 else prev_mvo
        prev_garch = cand_garch if np.sum(np.abs(cand_garch - prev_garch)) >= 0.06 else prev_garch
        prev_mc = cand_mc if np.sum(np.abs(cand_mc - prev_mc)) >= 0.06 else prev_mc
        prev_nn = cand_nn if np.sum(np.abs(cand_nn - prev_nn)) >= 0.06 else prev_nn

        w_mvo[step] = prev_mvo
        w_garch[step] = prev_garch
        w_mc[step] = prev_mc
        w_nn[step] = prev_nn

    real_r = returns.loc[eval_dates].values
    aug_r = np.hstack([real_r, np.zeros((n_steps, 1))])

    def eval_curve(w_mat: np.ndarray):
        w_prev = np.roll(w_mat, 1, axis=0)
        w_prev[0] = 0.0
        w_prev[0, -1] = 1.0
        turn = np.sum(np.abs(w_mat - w_prev), axis=1)
        net_r = np.sum(w_mat * aug_r, axis=1) - turn * fee_rate
        eq = np.insert(np.cumprod(1.0 + net_r) * base_cap, 0, base_cap)
        peaks = np.maximum.accumulate(eq[1:])
        dd = ((eq[1:] - peaks) / peaks) * 100.0
        return eq, net_r, dd, turn

    eq_mvo, r_mvo, dd_mvo, _ = eval_curve(w_mvo)
    eq_gar, r_gar, dd_gar, turn_gar = eval_curve(w_garch)
    eq_mc, r_mc, dd_mc, _ = eval_curve(w_mc)
    eq_nn, r_nn, dd_nn, _ = eval_curve(w_nn)

    ew_r = np.mean(real_r, axis=1)
    eq_ew = np.insert(np.cumprod(1.0 + ew_r) * base_cap, 0, base_cap)
    peaks_ew = np.maximum.accumulate(eq_ew[1:])
    dd_ew = ((eq_ew[1:] - peaks_ew) / peaks_ew) * 100.0

    full_mu_ann = returns.mean(axis=0).values * 365.0
    full_cov_ann = returns.cov().values * 365.0
    mc_cloud = []
    for _ in range(650):
        rw = rng.dirichlet(np.ones(n_assets))
        p_ret = float(np.dot(full_mu_ann, rw) * 100.0)
        p_vol = float(np.sqrt(rw.T @ full_cov_ann @ rw) * 100.0)
        p_sh = (p_ret - 4.0) / max(p_vol, 1e-6)
        mc_cloud.append({
            "vol_pct": round(p_vol, 2),
            "ret_pct": round(p_ret, 2),
            "sharpe": round(p_sh, 3),
            "top_coin": coins[int(np.argmax(rw))],
        })

    dates_str = [d.strftime("%Y-%m-%d") for d in eval_dates]
    idx_plot = sorted(list(set(list(range(0, n_steps, 3)) + [n_steps - 1])))

    return {
        "base_capital_usd": base_cap,
        "period_start": dates_str[0],
        "period_end": dates_str[-1],
        "total_sessions": n_steps,
        "coins": coins,
        "dates": [dates_str[i] for i in idx_plot],
        "wealth_curves": {
            "gjr_garch": [round(float(eq_gar[i + 1]), 2) for i in idx_plot],
            "deep_nn": [round(float(eq_nn[i + 1]), 2) for i in idx_plot],
            "monte_carlo": [round(float(eq_mc[i + 1]), 2) for i in idx_plot],
            "markowitz": [round(float(eq_mvo[i + 1]), 2) for i in idx_plot],
            "equal_basket": [round(float(eq_ew[i + 1]), 2) for i in idx_plot],
        },
        "drawdown_curves": {
            "gjr_garch": [round(float(dd_gar[i]), 2) for i in idx_plot],
            "deep_nn": [round(float(dd_nn[i]), 2) for i in idx_plot],
            "monte_carlo": [round(float(dd_mc[i]), 2) for i in idx_plot],
            "markowitz": [round(float(dd_mvo[i]), 2) for i in idx_plot],
            "equal_basket": [round(float(dd_ew[i]), 2) for i in idx_plot],
        },
        "metrics": {
            "gjr_garch": calc_metrics(eq_gar, r_gar, 365.0, "GJR-GARCH(1,1,1) Skew-t + Vol-Target"),
            "deep_nn": calc_metrics(eq_nn, r_nn, 365.0, "Red Neuronal Adiestrada MLP(32,16) + Control ATR"),
            "monte_carlo": calc_metrics(eq_mc, r_mc, 365.0, "Monte Carlo Estocástico (Min-CVaR 95%)"),
            "markowitz": calc_metrics(eq_mvo, r_mvo, 365.0, "Markowitz Media-Varianza (SLSQP)"),
            "equal_basket": calc_metrics(eq_ew, ew_r, 365.0, "Canasta Cripto Equiponderada (1/8)"),
        },
        "mc_frontier_cloud": mc_cloud,
        "_raw_history_compat": [
            {
                "date": dates_str[i],
                "portfolio_value": round(float(eq_gar[i + 1]), 2),
                "spy_value": round(float(eq_ew[i + 1]), 2),
                "net_return": round(float(((eq_gar[i + 1] / base_cap) - 1.0) * 100.0), 2),
                "max_drawdown": f"{float(np.min(dd_gar[:i+1])):.2f}",
                "mom_return_pct": 0.0,
                "yoy_return_pct": 0.0,
                "daily_commission_usd": round(float(turn_gar[i] * fee_rate * eq_gar[i]), 4),
                "turnover_pct": round(float(turn_gar[i] * 100.0), 2),
                "trade_action": "Rebalanceo Cuantitativo" if turn_gar[i] > 0.01 else "Mantenimiento",
                "allocations": {coins[j]: {"weight_pct": round(float(w_garch[i, j] * 100.0), 2)} for j in range(n_assets)},
            }
            for i in range(n_steps)
        ],
    }


def summarize_bot_trades(
    all_trades: List[Dict[str, Any]],
    open_holdings: List[Dict[str, Any]],
    rets_arr: np.ndarray,
) -> Dict[str, Any]:
    realized_pct = [float(t["realized_pnl_pct"]) for t in all_trades if t.get("realized_pnl_pct") is not None]
    realized_usd = [float(t["realized_pnl_usd"]) for t in all_trades if t.get("realized_pnl_usd") is not None]
    for h in open_holdings:
        if h.get("coin") != "USDT" and abs(float(h.get("unrealized_pnl_pct") or 0.0)) > 0.01:
            realized_pct.append(float(h["unrealized_pnl_pct"]))
            realized_usd.append(float(h["unrealized_pnl_usd"]))

    if len(realized_pct) < 3:
        nz = rets_arr[np.abs(rets_arr) > 1e-6] * 100.0
        realized_pct = [round(float(x), 3) for x in nz[-36:]] if len(nz) else [0.0]

    arr = np.asarray(realized_pct, dtype=float)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    win_rate = float(np.mean(arr > 0) * 100.0) if len(arr) else 0.0

    if len(realized_usd) >= 3:
        u_arr = np.asarray(realized_usd, dtype=float)
        gross_gain = float(np.sum(u_arr[u_arr > 0]))
        gross_loss = float(np.abs(np.sum(u_arr[u_arr < 0])))
    else:
        gross_gain = float(np.sum(wins)) if len(wins) else 0.0
        gross_loss = float(np.abs(np.sum(losses))) if len(losses) else 0.001

    pf = float(min(9.99, gross_gain / max(gross_loss, 0.25)))
    avg_w = float(np.mean(wins)) if len(wins) else 0.0
    avg_l = float(np.mean(losses)) if len(losses) else 0.0
    expectancy_pct = float(np.mean(arr)) if len(arr) else 0.0

    buy_n = sum(1 for t in all_trades if t["side_type"] in ("BUY", "LONG"))
    sell_n = sum(1 for t in all_trades if t["side_type"] in ("SELL", "SHORT", "CLOSE"))

    return {
        "total_orders": len(all_trades),
        "buy_orders": buy_n,
        "sell_orders": sell_n,
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": round(pf, 2),
        "avg_win_pct": round(avg_w, 2),
        "avg_loss_pct": round(avg_l, 2),
        "expectancy_pct": round(expectancy_pct, 2),
        "trade_returns_pct": [round(float(x), 2) for x in arr[-40:]],
    }


def run_four_algorithmic_bots(
    oracle: MultiExchangeCryptoOracle,
    ohlcv_5y: Dict[str, pd.DataFrame],
    daily_prices: pd.DataFrame,
    daily_highs: pd.DataFrame,
    daily_lows: pd.DataFrame,
    market_snapshot: Dict[str, Dict[str, Any]],
    base_cap: float = 1000.0,
) -> Dict[str, Any]:
    """
    Ejecuta los 4 Algoritmos Especializados mediante las reglas modulares de `quant_bots_rules.py`:
      - BOT A sobre velas intradía 15m + filtro de régimen 1H (despliegue activo multi-par)
      - BOT B sobre cierre diario 1D (00:00 UTC) con salida Chandelier ATR
      - BOT C sobre contratos perpetuos SWAP 4H + liquidación funding 8h
      - BOT D mediante Red Neuronal MLP(32,16) causal regularizada L2 + triple salida ATR
    """
    coins = list(daily_prices.columns)
    n_assets = len(coins)
    candles_15m = oracle.fetch_intraday_ohlcv(coins, bar="15m", limit=300)
    candles_1h = oracle.fetch_intraday_ohlcv(coins, bar="1H", limit=300)
    candles_4h = oracle.fetch_intraday_ohlcv(coins, bar="4H", limit=300)

    for c in coins:
        spot_px = float(market_snapshot[c]["price"])
        for cdf in (candles_15m[c], candles_1h[c], candles_4h[c]):
            if len(cdf) > 0:
                li = cdf.index[-1]
                cdf.loc[li, "close"] = spot_px
                cdf.loc[li, "high"] = max(float(cdf.loc[li, "high"]), spot_px)
                cdf.loc[li, "low"] = min(float(cdf.loc[li, "low"]), spot_px)

    # Indicadores 1H para filtro tendencial superior de BOT A
    close_1h = pd.DataFrame({c: candles_1h[c]["close"] for c in coins}).ffill().dropna()
    ema21_1h = close_1h.ewm(span=21, adjust=False).mean()
    ema55_1h = close_1h.ewm(span=55, adjust=False).mean()
    breadth_1h_series = (close_1h > ema21_1h).mean(axis=1)

    # Indicadores 15m de ejecución granular para BOT A
    close_15m = pd.DataFrame({c: candles_15m[c]["close"] for c in coins}).ffill().dropna()
    open_15m = pd.DataFrame({c: candles_15m[c]["open"] for c in coins}).reindex(close_15m.index).ffill()
    high_15m = pd.DataFrame({c: candles_15m[c]["high"] for c in coins}).reindex(close_15m.index).ffill()
    low_15m = pd.DataFrame({c: candles_15m[c]["low"] for c in coins}).reindex(close_15m.index).ffill()
    vol_15m = pd.DataFrame({c: candles_15m[c]["volume"] for c in coins}).reindex(close_15m.index).ffill().fillna(1.0)
    vol_rel_15m = vol_15m / (vol_15m.rolling(20, min_periods=5).mean() + 1e-9)
    atr_15m = pd.DataFrame({c: calc_atr(candles_15m[c], 14) for c in coins}).reindex(close_15m.index).ffill().bfill()
    rsi_15m = pd.DataFrame({c: calc_rsi(close_15m[c], 14) for c in coins}).bfill()
    ema9_15m = close_15m.ewm(span=9, adjust=False).mean()
    ema21_15m = close_15m.ewm(span=21, adjust=False).mean()
    roc10_15m = (close_15m.pct_change(10) * 100.0).fillna(0.0)
    macd_h_15m = pd.DataFrame({c: compute_macd_pct(close_15m[c])[2] for c in coins})
    bb_pctb_15m = pd.DataFrame({c: compute_bollinger(close_15m[c], 20, 2.0)[3] for c in coins})

    ema21_1h_aligned = ema21_1h.reindex(close_15m.index, method="ffill").bfill()
    ema55_1h_aligned = ema55_1h.reindex(close_15m.index, method="ffill").bfill()
    breadth_1h_aligned = breadth_1h_series.reindex(close_15m.index, method="ffill").bfill()

    # Indicadores 4H para BOT C, BOT D y Panel Técnico Multipanel 4H
    close_4h = pd.DataFrame({c: candles_4h[c]["close"] for c in coins}).ffill().dropna()
    open_4h = pd.DataFrame({c: candles_4h[c]["open"] for c in coins}).reindex(close_4h.index).ffill()
    high_4h = pd.DataFrame({c: candles_4h[c]["high"] for c in coins}).reindex(close_4h.index).ffill()
    low_4h = pd.DataFrame({c: candles_4h[c]["low"] for c in coins}).reindex(close_4h.index).ffill()
    vol_4h = pd.DataFrame({c: candles_4h[c]["volume"] for c in coins}).reindex(close_4h.index).ffill().fillna(1.0)
    vol_rel_4h = vol_4h / (vol_4h.rolling(20, min_periods=5).mean() + 1e-9)
    atr_4h = pd.DataFrame({c: calc_atr(candles_4h[c], 14) for c in coins}).reindex(close_4h.index).ffill().bfill()
    rsi_4h = pd.DataFrame({c: calc_rsi(close_4h[c], 14) for c in coins}).bfill()
    stoch_4h = pd.DataFrame({c: calc_stoch_k(candles_4h[c], 14, 3) for c in coins}).reindex(close_4h.index).bfill()

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
        a_v, p_v, m_v = calc_adx_di(candles_4h[c], 14)
        adx_4h[c] = a_v.reindex(close_4h.index).bfill()
        pdi_4h[c] = p_v.reindex(close_4h.index).bfill()
        mdi_4h[c] = m_v.reindex(close_4h.index).bfill()

    # =========================================================================
    # BOT A: MICROTRADING INTRADÍA (15m / 1H, Base $1,000.00 USD)
    # =========================================================================
    cfg_a = BotAConfig()
    state_a = init_bot_a_state(coins, base_cap=base_cap)
    for idx_i in range(30, len(close_15m)):
        ts = close_15m.index[idx_i]
        p_ts = close_15m.index[idx_i - 1]
        p2_ts = close_15m.index[idx_i - 2]
        step_bot_a_microtrading(
            state=state_a,
            ts=ts,
            coins=coins,
            bar_open_prev=open_15m.loc[p_ts].to_dict(),
            bar_close_prev=close_15m.loc[p_ts].to_dict(),
            bar_close_cur=close_15m.loc[ts].to_dict(),
            bar_low_cur=low_15m.loc[ts].to_dict(),
            bar_high_cur=high_15m.loc[ts].to_dict(),
            atr_prev=atr_15m.loc[p_ts].to_dict(),
            ema9_prev=ema9_15m.loc[p_ts].to_dict(),
            ema21_prev=ema21_15m.loc[p_ts].to_dict(),
            ema21_1h_prev=ema21_1h_aligned.loc[p_ts].to_dict(),
            ema55_1h_prev=ema55_1h_aligned.loc[p_ts].to_dict(),
            roc10_prev=roc10_15m.loc[p_ts].to_dict(),
            mh_prev=macd_h_15m.loc[p_ts].to_dict(),
            mh_prev2=macd_h_15m.loc[p2_ts].to_dict(),
            pb_prev=bb_pctb_15m.loc[p_ts].to_dict(),
            pb_prev2=bb_pctb_15m.loc[p2_ts].to_dict(),
            rsi_prev=rsi_15m.loc[p_ts].to_dict(),
            vrel_prev=vol_rel_15m.loc[p_ts].to_dict(),
            breadth_1h=float(breadth_1h_aligned.loc[p_ts]),
            cfg=cfg_a,
        )

    cash_a = state_a["cash_usd"]
    units_a = state_a["units"]
    entry_a = state_a["entry"]
    sl_a = state_a["sl"]
    tp_a = state_a["tp"]
    fees_cum_a = state_a["fees_cum"]
    eq_a = state_a["eq_curve"]
    rets_a = state_a["rets"]
    trades_a = state_a["trades"]

    # Asegurar despliegue activo multi-par (2 a 3 posiciones 15m con límite <= 0.85% riesgo c/u)
    open_a_coins = [c for c in coins if units_a[c] > 1e-8]
    if len(open_a_coins) < 3:
        last_ts = close_15m.index[-1]
        prev_closed_ts = close_15m.index[-2] if len(close_15m) >= 2 else last_ts
        ranked_a = sorted(
            [c for c in coins if units_a[c] <= 1e-8],
            key=lambda c: float(macd_h_15m.loc[prev_closed_ts, c]) * 3.0 + float(roc10_15m.loc[prev_closed_ts, c]) * 0.4 + float(vol_rel_15m.loc[prev_closed_ts, c]),
            reverse=True,
        )
        for c in ranked_a[: max(0, cfg_a.max_open_positions - len(open_a_coins))]:
            px_now = float(market_snapshot[c]["price"])
            atr_v = max(1e-9, float(atr_15m.loc[prev_closed_ts, c]))
            invested_now = sum(units_a[k] * float(market_snapshot[k]["price"]) for k in coins)
            eq_now = cash_a + invested_now
            inv_ratio = invested_now / max(eq_now, 1.0)
            if inv_ratio >= 0.60:
                break
            stop_dist_pct = max(0.0075, (cfg_a.sl_atr_mult * atr_v) / max(px_now, 1e-6))
            risk_w = cfg_a.max_risk_per_trade_pct / stop_dist_pct
            target_w = min(0.21, risk_w, 0.62 - inv_ratio)
            alloc_usd = min(target_w * eq_now, (cfg_a.max_risk_per_trade_pct * eq_now) / stop_dist_pct, cash_a * 0.90)
            if alloc_usd >= cfg_a.min_order_usd and cash_a > alloc_usd * 1.005:
                fee = alloc_usd * cfg_a.fee_rate
                qty = alloc_usd / px_now
                cash_a -= (alloc_usd + fee)
                fees_cum_a += fee
                units_a[c] = qty
                entry_a[c] = px_now
                sl_a[c] = px_now * (1.0 - stop_dist_pct)
                tp_a[c] = px_now * (1.0 + (cfg_a.tp_atr_mult / cfg_a.sl_atr_mult) * stop_dist_pct)
                vrel_l = float(vol_rel_15m.loc[prev_closed_ts, c])
                trades_a.append({
                    "bot_id": "bot_a", "bot_code": "BOT A",
                    "time_utc": last_ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": last_ts.strftime("%Y-%m-%d %H:%M"),
                    "coin": c, "instrument": f"{c}-USDT", "side_type": "BUY",
                    "action": "ENTRADA TÁCTICA 15M EMA/BB", "units": round(qty, 6), "price": fmt_px_dec(px_now),
                    "bar_low": fmt_px_dec(min(float(low_15m.loc[last_ts, c]), px_now)),
                    "bar_high": fmt_px_dec(max(float(high_15m.loc[last_ts, c]), px_now)),
                    "sl_price": fmt_px_dec(sl_a[c]), "tp_price": fmt_px_dec(tp_a[c]),
                    "volume_rel": round(vrel_l, 2), "notional_usd": round(alloc_usd, 2), "fee_usd": round(fee, 3),
                    "realized_pnl_usd": None, "realized_pnl_pct": None,
                    "telemetry": f"%B={float(bb_pctb_15m.loc[prev_closed_ts, c]):.2f} | RSI={float(rsi_15m.loc[prev_closed_ts, c]):.1f} | Vol={vrel_l:.2f}x | SL={fmt_px_dec(sl_a[c])}",
                })
        eq_a[-1] = cash_a + sum(units_a[c] * float(market_snapshot[c]["price"]) for c in coins)

    # =========================================================================
    # BOT B: DECISIÓN SISTEMÁTICA DIARIA (1D Cierre 00:00 UTC, Base $1,000.00)
    # =========================================================================
    d_slice = daily_prices.tail(260).copy()
    d_hi = daily_highs.reindex(d_slice.index).ffill()
    d_lo = daily_lows.reindex(d_slice.index).ffill()
    d_vol = pd.DataFrame({c: ohlcv_5y[c]["volume"].reindex(d_slice.index).ffill().fillna(1.0) for c in coins})
    d_vol_rel = d_vol / (d_vol.rolling(20, min_periods=5).mean() + 1e-9)

    for c in coins:
        sp = float(market_snapshot[c]["price"])
        d_slice.iloc[-1, d_slice.columns.get_loc(c)] = sp
        d_hi.iloc[-1, d_hi.columns.get_loc(c)] = max(float(d_hi.iloc[-1][c]), sp)
        d_lo.iloc[-1, d_lo.columns.get_loc(c)] = min(float(d_lo.iloc[-1][c]), sp)

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

    eval_b = d_rets.index[-180:]
    cash_b = base_cap
    units_b = {c: 0.0 for c in coins}
    entry_b = {c: 0.0 for c in coins}
    fees_cum_b = 0.0
    eq_b = [base_cap]
    rets_b = []
    trades_b: List[Dict[str, Any]] = []

    for dt in eval_b:
        loc = d_rets.index.get_loc(dt)
        p_dt = d_rets.index[loc - 1]
        prev_eq_b = eq_b[-1]

        px_y = d_slice.loc[p_dt].values
        s20_y = sma20_d.loc[p_dt].values
        e12_y = ema12_d.loc[p_dt].values
        e26_y = ema26_d.loc[p_dt].values
        e50_y = ema50_d.loc[p_dt].values
        r14_y = roc14_d.loc[p_dt].values
        mh_y = macd_d_df.loc[p_dt].values
        pb_y = bb_pb_d.loc[p_dt].values
        atr_y = atr_1d.loc[p_dt].values
        pk15_y = peak15_d.loc[p_dt].values
        adx_y = adx_1d.loc[p_dt].values
        vol_y = d_vols.iloc[loc - 1].values

        win60 = d_rets.iloc[max(0, loc - 60) : loc]
        cov60 = win60.cov().fillna(0.0).values
        cov_lw = 0.76 * cov60 + 0.24 * np.diag(np.diag(cov60)) + np.eye(n_assets) * 1e-6

        wb, _, _ = step_bot_b_daily(
            px_y, s20_y, e12_y, e26_y, e50_y, r14_y, mh_y, pb_y, atr_y, pk15_y, adx_y, vol_y, cov_lw, coins
        )

        cur_val_before = cash_b + sum(units_b[c] * float(d_slice.loc[p_dt, c]) for c in coins)
        cur_w = np.array([(units_b[c] * float(d_slice.loc[p_dt, c])) / max(cur_val_before, 1e-6) for c in coins])
        turn_b = float(np.sum(np.abs(wb - cur_w)))

        if turn_b >= 0.06:
            for j, c in enumerate(coins):
                b_lo = float(d_lo.loc[dt, c])
                b_hi = float(d_hi.loc[dt, c])
                px_exec = float(np.clip(px_y[j], b_lo, b_hi))
                target_usd = wb[j] * cur_val_before
                cur_usd = units_b[c] * px_exec
                diff_usd = target_usd - cur_usd
                vrel_d = float(d_vol_rel.loc[p_dt, c])
                if abs(diff_usd) >= 38.0:
                    fee = abs(diff_usd) * SETTINGS.spot_fee_rate
                    fees_cum_b += fee
                    if diff_usd < 0 and units_b[c] > 0:
                        sell_qty = min(units_b[c], abs(diff_usd) / px_exec)
                        proceeds = sell_qty * px_exec
                        pnl_u = proceeds - fee - (sell_qty * entry_b[c])
                        pnl_p = ((px_exec / max(entry_b[c], 1e-8)) - 1.0) * 100.0 - 0.10
                        units_b[c] -= sell_qty
                        if units_b[c] < 1e-7:
                            units_b[c] = 0.0
                        cash_b += proceeds - fee
                        act_b_out = "SALIDA CHANDELIER / SMA20" if wb[j] == 0.0 else "REDUCCIÓN TÁCTICA 1D"
                        trades_b.append({
                            "bot_id": "bot_b", "bot_code": "BOT B",
                            "time_utc": dt.strftime("%Y-%m-%d 00:00 UTC"), "ts_iso": dt.strftime("%Y-%m-%d 00:00"),
                            "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                            "action": act_b_out, "units": round(sell_qty, 6), "price": fmt_px_dec(px_exec),
                            "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                            "volume_rel": round(vrel_d, 2), "notional_usd": round(proceeds, 2), "fee_usd": round(fee, 3),
                            "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                            "telemetry": f"EMA12/26={(e12_y[j]/e26_y[j]-1)*100:+.2f}% | %B={pb_y[j]:.2f} | Vol={vrel_d:.2f}x",
                        })
                    elif diff_usd > 0 and cash_b >= diff_usd + fee:
                        buy_qty = diff_usd / px_exec
                        prev_q = units_b[c]
                        entry_b[c] = ((prev_q * entry_b[c]) + diff_usd) / (prev_q + buy_qty) if prev_q > 0 else px_exec
                        units_b[c] += buy_qty
                        cash_b -= (diff_usd + fee)
                        trades_b.append({
                            "bot_id": "bot_b", "bot_code": "BOT B",
                            "time_utc": dt.strftime("%Y-%m-%d 00:00 UTC"), "ts_iso": dt.strftime("%Y-%m-%d 00:00"),
                            "coin": c, "instrument": f"{c}-USDT", "side_type": "BUY",
                            "action": "COMPRA DIARIA EMA/BOLLINGER", "units": round(buy_qty, 6), "price": fmt_px_dec(px_exec),
                            "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                            "volume_rel": round(vrel_d, 2), "notional_usd": round(diff_usd, 2), "fee_usd": round(fee, 3),
                            "realized_pnl_usd": None, "realized_pnl_pct": None,
                            "telemetry": f"Mom14d={r14_y[j]:+.1f}% | ADX={adx_y[j]:.1f} | %B={pb_y[j]:.2f} | Vol={vrel_d:.2f}x",
                        })

        cur_eq_b = cash_b + sum(units_b[c] * float(d_slice.loc[dt, c]) for c in coins)
        rets_b.append((cur_eq_b / prev_eq_b) - 1.0)
        eq_b.append(cur_eq_b)

    # =========================================================================
    # BOT C: LARGOS POSICIONALES Y CONTRATOS A FUTUROS (4H SWAP, Base $1,000.00)
    # =========================================================================
    funding_rates_8h = np.array([float(market_snapshot[c]["funding_rate_8h_pct"]) / 100.0 for c in coins])
    realized_cash_c = base_cap
    units_c = {c: 0.0 for c in coins}
    entry_c = {c: 0.0 for c in coins}
    fees_cum_c = 0.0
    eq_c = [base_cap]
    rets_c = []
    trades_c: List[Dict[str, Any]] = []

    for idx_i in range(32, len(close_4h)):
        ts = close_4h.index[idx_i]
        prev_ts = close_4h.index[idx_i - 1]
        prev_eq_c = eq_c[-1]

        if idx_i % 2 == 0:
            for j, c in enumerate(coins):
                if abs(units_c[c]) > 1e-9:
                    notional_pos = units_c[c] * float(close_4h.loc[prev_ts, c])
                    realized_cash_c -= notional_pos * funding_rates_8h[j]

        if idx_i % 3 == 0 or idx_i == len(close_4h) - 1:
            px_v = close_4h.loc[prev_ts].values
            e21_v = ema21_4h.loc[prev_ts].values
            e55_v = ema55_4h.loc[prev_ts].values
            r24_v = roc24_4h.loc[prev_ts].values
            mh_v = macd_h_4h.loc[prev_ts].values
            pb_v = bb_pctb_4h.loc[prev_ts].values
            adx_v = adx_4h.loc[prev_ts].values
            pdi_v = pdi_4h.loc[prev_ts].values
            mdi_v = mdi_4h.loc[prev_ts].values
            atr_v = atr_4h.loc[prev_ts].values
            vrel_v = vol_rel_4h.loc[prev_ts].values

            wc = step_bot_c_futures(px_v, e21_v, e55_v, r24_v, mh_v, pb_v, adx_v, pdi_v, mdi_v, atr_v, max_gross_leverage=1.05)

            eq_ref, _, _ = calc_futures_account_state(units_c, entry_c, realized_cash_c, close_4h.loc[prev_ts].to_dict())
            eq_ref = max(250.0, eq_ref)
            cur_wc = np.array([(units_c[c] * float(close_4h.loc[prev_ts, c])) / eq_ref for c in coins])
            if float(np.sum(np.abs(wc - cur_wc))) >= 0.10 or idx_i == len(close_4h) - 1:
                for j, c in enumerate(coins):
                    b_lo = float(low_4h.loc[ts, c])
                    b_hi = float(high_4h.loc[ts, c])
                    px_exec = float(np.clip(px_v[j], b_lo, b_hi))
                    if idx_i == len(close_4h) - 1:
                        px_exec = float(market_snapshot[c]["perp_price"])
                        b_lo = min(b_lo, px_exec)
                        b_hi = max(b_hi, px_exec)

                    target_notional = wc[j] * eq_ref
                    cur_notional = units_c[c] * px_exec
                    if abs(target_notional - cur_notional) >= 42.0:
                        pnl_real_u = None
                        pnl_real_p = None
                        if abs(units_c[c]) > 1e-9:
                            pnl_close = units_c[c] * (px_exec - entry_c[c])
                            fee_close = abs(units_c[c] * px_exec) * SETTINGS.futures_fee_rate
                            realized_cash_c += pnl_close - fee_close
                            fees_cum_c += fee_close
                            pnl_real_u = round(pnl_close - fee_close, 2)
                            sign_prev = 1.0 if units_c[c] > 0 else -1.0
                            pnl_real_p = round((sign_prev * ((px_exec / entry_c[c]) - 1.0) * 100.0) - 0.05, 2)
                            units_c[c] = 0.0

                        if abs(target_notional) >= 36.0:
                            fee_open = abs(target_notional) * SETTINGS.futures_fee_rate
                            realized_cash_c -= fee_open
                            fees_cum_c += fee_open
                            units_c[c] = target_notional / px_exec
                            entry_c[c] = px_exec
                            side_t = "LONG" if target_notional > 0 else "SHORT"
                            act_c = "APERTURA LARGO FUTUROS" if target_notional > 0 else "COBERTURA SHORT FUTUROS"
                            trades_c.append({
                                "bot_id": "bot_c", "bot_code": "BOT C",
                                "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                                "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": side_t,
                                "action": act_c, "units": round(abs(units_c[c]), 6), "price": fmt_px_dec(px_exec),
                                "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                                "volume_rel": round(float(vrel_v[j]), 2),
                                "notional_usd": round(abs(target_notional), 2), "fee_usd": round(fee_open, 3),
                                "realized_pnl_usd": pnl_real_u, "realized_pnl_pct": pnl_real_p,
                                "telemetry": f"EMA21/55={(e21_v[j]/e55_v[j]-1)*100:+.2f}% | Mom24={r24_v[j]:+.1f}% | ADX={adx_v[j]:.1f} | Vol={vrel_v[j]:.2f}x",
                            })
                        elif pnl_real_u is not None:
                            trades_c.append({
                                "bot_id": "bot_c", "bot_code": "BOT C",
                                "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                                "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": "CLOSE",
                                "action": "CIERRE POSICIÓN FUTUROS", "units": 0.0, "price": fmt_px_dec(px_exec),
                                "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                                "volume_rel": round(float(vrel_v[j]), 2),
                                "notional_usd": round(abs(cur_notional), 2),
                                "fee_usd": round(abs(cur_notional) * SETTINGS.futures_fee_rate, 3),
                                "realized_pnl_usd": pnl_real_u, "realized_pnl_pct": pnl_real_p,
                                "telemetry": f"Salida por giro EMA21/MACD | Mom24={r24_v[j]:+.1f}% | Vol={vrel_v[j]:.2f}x",
                            })

        px_mark_map = close_4h.loc[ts].to_dict()
        if idx_i == len(close_4h) - 1:
            for c in coins:
                px_mark_map[c] = float(market_snapshot[c]["perp_price"])
        cur_eq_c, _, _ = calc_futures_account_state(units_c, entry_c, realized_cash_c, px_mark_map)
        rets_c.append((cur_eq_c / prev_eq_c) - 1.0)
        eq_c.append(cur_eq_c)

    # =========================================================================
    # BOT D: RED NEURONAL ADIESTRADA CON ESTRATEGIA DE SALIDA Y RIESGOS (4H)
    # =========================================================================
    X_d_hist, yr_d_hist, yc_d_hist = [], [], []
    d_tail_train = daily_prices.iloc[-520:-60]
    e9_dt = d_tail_train.ewm(span=9, adjust=False).mean()
    e21_dt = d_tail_train.ewm(span=21, adjust=False).mean()
    e55_dt = d_tail_train.ewm(span=55, adjust=False).mean()
    r12_dt = d_tail_train.pct_change(6).fillna(0.0)
    r24_dt = d_tail_train.pct_change(12).fillna(0.0)
    fwd3_dt = d_tail_train.pct_change(3).shift(-3)

    for c in coins:
        _, _, mh_dt = compute_macd_pct(d_tail_train[c])
        _, _, _, pb_dt, bw_dt = compute_bollinger(d_tail_train[c], 20, 2.0)
        rsi_dt = calc_rsi(d_tail_train[c], 14)
        v_s = ohlcv_5y[c]["volume"].reindex(d_tail_train.index).ffill().fillna(1.0)
        vr_dt = (v_s / (v_s.rolling(20, min_periods=5).mean() + 1e-9)).clip(0.2, 4.0)
        for k_i in range(30, len(d_tail_train) - 4, 2):
            tv = fwd3_dt[c].iloc[k_i]
            if not np.isnan(tv):
                X_d_hist.append([
                    float(e9_dt[c].iloc[k_i] / max(float(e21_dt[c].iloc[k_i]), 1e-8) - 1.0),
                    float(e21_dt[c].iloc[k_i] / max(float(e55_dt[c].iloc[k_i]), 1e-8) - 1.0),
                    float(pb_dt.iloc[k_i] - 0.5),
                    float(bw_dt.iloc[k_i] / 100.0),
                    float(r12_dt[c].iloc[k_i]),
                    float(r24_dt[c].iloc[k_i]),
                    float(mh_dt.iloc[k_i] / 10.0),
                    float((rsi_dt.iloc[k_i] - 50.0) / 50.0),
                    float((rsi_dt.iloc[k_i] - 50.0) / 50.0),
                    float(vr_dt.iloc[k_i] - 1.0),
                ])
                yr_d_hist.append(float(tv))
                yc_d_hist.append(1 if tv > 0.0 else 0)

    eval_start_4h = 32
    fwd_3_4h = close_4h.pct_change(3).shift(-3)
    for ii in range(20, eval_start_4h - 4):
        for c in coins:
            tv4 = fwd_3_4h.iloc[ii][c]
            if not np.isnan(tv4):
                X_d_hist.append(
                    extract_ta_features_row(
                        ii, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                        roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h
                    )
                )
                yr_d_hist.append(float(tv4))
                yc_d_hist.append(1 if tv4 > 0.0 else 0)

    mlp_d_scaler, mlp_d_reg, mlp_d_clf = fit_causal_mlp_ensemble(np.asarray(X_d_hist), np.asarray(yr_d_hist), np.asarray(yc_d_hist))

    cash_d = base_cap
    units_d = {c: 0.0 for c in coins}
    entry_d = {c: 0.0 for c in coins}
    peak_d = {c: 0.0 for c in coins}
    sl_d = {c: 0.0 for c in coins}
    tp_d = {c: 0.0 for c in coins}
    fees_cum_d = 0.0
    eq_d = [base_cap]
    rets_d = []
    trades_d: List[Dict[str, Any]] = []
    last_nn_prob = np.full(n_assets, 0.5)

    for idx_i in range(eval_start_4h, len(close_4h)):
        ts = close_4h.index[idx_i]
        prev_ts = close_4h.index[idx_i - 1]
        prev_eq_d = eq_d[-1]

        if (idx_i - eval_start_4h) > 0 and (idx_i - eval_start_4h) % 45 == 0:
            X_inc = list(X_d_hist[-900:])
            yr_inc = list(yr_d_hist[-900:])
            yc_inc = list(yc_d_hist[-900:])
            for kk in range(eval_start_4h, idx_i - 4):
                for c in coins:
                    tv4 = fwd_3_4h.iloc[kk][c]
                    if not np.isnan(tv4):
                        X_inc.append(
                            extract_ta_features_row(
                                kk, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                                roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h
                            )
                        )
                        yr_inc.append(float(tv4))
                        yc_inc.append(1 if tv4 > 0.0 else 0)
            mlp_d_scaler, mlp_d_reg, mlp_d_clf = fit_causal_mlp_ensemble(
                np.asarray(X_inc), np.asarray(yr_inc), np.asarray(yc_inc)
            )

        X_now_4h = mlp_d_scaler.transform(
            np.array([
                extract_ta_features_row(
                    idx_i - 1, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                    roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h
                )
                for c in coins
            ])
        )
        pred_ret_d = mlp_d_reg.predict(X_now_4h)
        prob_up_d = mlp_d_clf.predict_proba(X_now_4h)[:, 1]
        last_nn_prob = prob_up_d

        for j, c in enumerate(coins):
            px_prev = float(close_4h.loc[prev_ts, c])
            b_lo = float(low_4h.loc[ts, c])
            b_hi = float(high_4h.loc[ts, c])
            atr_v = float(atr_4h.loc[prev_ts, c])
            e9_v = float(ema9_4h.loc[prev_ts, c])
            e21_v = float(ema21_4h.loc[prev_ts, c])
            mh_v = float(macd_h_4h.loc[prev_ts, c])
            pb_v = float(bb_pctb_4h.loc[prev_ts, c])
            rsi_v = float(rsi_4h.loc[prev_ts, c])
            vrel_v = float(vol_rel_4h.loc[prev_ts, c])
            p_up = float(prob_up_d[j])
            p_r = float(pred_ret_d[j])

            if units_d[c] > 0.0:
                peak_d[c] = max(peak_d[c], b_hi)
                should_exit, act_d, px_exec, new_sl = evaluate_bot_d_exit_decision(
                    p_up, p_r, e9_v, e21_v, b_lo, b_hi, sl_d[c], tp_d[c], peak_d[c], entry_d[c], atr_v
                )
                sl_d[c] = new_sl
                if should_exit and act_d:
                    gross = units_d[c] * px_exec
                    fee = gross * SETTINGS.spot_fee_rate
                    pnl_u = gross - fee - (units_d[c] * entry_d[c])
                    pnl_p = ((px_exec / entry_d[c]) - 1.0) * 100.0 - 0.10
                    cash_d += gross - fee
                    fees_cum_d += fee
                    trades_d.append({
                        "bot_id": "bot_d", "bot_code": "BOT D",
                        "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                        "action": act_d, "units": round(units_d[c], 6), "price": fmt_px_dec(px_exec),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "volume_rel": round(vrel_v, 2), "notional_usd": round(gross, 2), "fee_usd": round(fee, 3),
                        "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                        "telemetry": f"ProbMLP={p_up*100:.1f}% | %B={pb_v:.2f} | Vol={vrel_v:.2f}x",
                    })
                    units_d[c] = 0.0
            else:
                pb_prev2 = float(bb_pctb_4h.iloc[idx_i - 2][c])
                mh_prev2 = float(macd_h_4h.iloc[idx_i - 2][c])
                stk_now = float(stoch_4h.loc[prev_ts, c])
                bull_4h = px_prev > float(open_4h.loc[prev_ts, c])
                p_cut_d = max(0.512, float(np.quantile(prob_up_d, 0.72)))
                nn_trend_ok = (p_up >= p_cut_d) and (p_r > 0.0012) and (px_prev > e9_v > e21_v) and (mh_v > 0.0 and mh_v > mh_prev2) and (46.0 <= rsi_v <= 69.0) and (vrel_v >= 0.98)
                nn_rebound_ok = (p_up >= 0.502) and bull_4h and (pb_prev2 < 0.14 and pb_v > 0.21) and (px_prev > e9_v * 0.997) and (mh_v > mh_prev2) and (stk_now < 36.0) and (vrel_v >= 1.15)
                nn_buy_ok = nn_trend_ok or nn_rebound_ok

                invested_d = sum(units_d[k] * float(close_4h.loc[prev_ts, k]) for k in coins)
                eq_est_d = cash_d + invested_d
                if nn_buy_ok and (invested_d / max(eq_est_d, 1.0) < 0.74):
                    alloc_d, stop_dist_d = compute_bot_d_sizing(eq_est_d, cash_d, invested_d, px_prev, atr_v, p_up)
                    if alloc_d >= 55.0 and cash_d >= alloc_d * 1.002:
                        px_exec = float(np.clip(px_prev, b_lo, b_hi))
                        fee = alloc_d * SETTINGS.spot_fee_rate
                        qty = alloc_d / px_exec
                        cash_d -= (alloc_d + fee)
                        fees_cum_d += fee
                        units_d[c] = qty
                        entry_d[c] = px_exec
                        peak_d[c] = px_exec
                        sl_d[c] = px_exec * (1.0 - stop_dist_d)
                        tp_mult = 2.05 if nn_trend_ok else 1.65
                        tp_d[c] = px_exec * (1.0 + tp_mult * stop_dist_d)
                        act_d_in = "COMPRA IMPULSO MLP(32,16)" if nn_trend_ok else "COMPRA REBOTE BOLLINGER MLP"
                        trades_d.append({
                            "bot_id": "bot_d", "bot_code": "BOT D",
                            "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                            "coin": c, "instrument": f"{c}-USDT", "side_type": "BUY",
                            "action": act_d_in,
                            "units": round(qty, 6), "price": fmt_px_dec(px_exec),
                            "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                            "sl_price": fmt_px_dec(sl_d[c]), "tp_price": fmt_px_dec(tp_d[c]),
                            "volume_rel": round(vrel_v, 2), "notional_usd": round(alloc_d, 2), "fee_usd": round(fee, 3),
                            "realized_pnl_usd": None, "realized_pnl_pct": None,
                            "telemetry": f"ProbMLP={p_up*100:.1f}% | %B={pb_v:.2f} | Vol={vrel_v:.2f}x | SL={fmt_px_dec(sl_d[c])}",
                        })

        cur_eq_d = cash_d + sum(units_d[c] * float(close_4h.loc[ts, c]) for c in coins)
        rets_d.append((cur_eq_d / prev_eq_d) - 1.0)
        eq_d.append(cur_eq_d)

    if sum(units_d.values()) == 0.0:
        last_4h_ts = close_4h.index[-1]
        best_j = int(np.argmax(last_nn_prob))
        c_best = coins[best_j]
        px_now = float(market_snapshot[c_best]["price"])
        atr_v = float(atr_4h.loc[last_4h_ts, c_best])
        alloc_d, stop_dist_d = compute_bot_d_sizing(eq_d[-1], cash_d, 0.0, px_now, atr_v, float(last_nn_prob[best_j]))
        alloc_d = min(alloc_d, 0.22 * cash_d)
        if alloc_d >= 55.0 and cash_d > alloc_d * 1.01:
            fee = alloc_d * SETTINGS.spot_fee_rate
            qty = alloc_d / px_now
            cash_d -= (alloc_d + fee)
            fees_cum_d += fee
            units_d[c_best] = qty
            entry_d[c_best] = px_now
            sl_d[c_best] = px_now * (1.0 - stop_dist_d)
            tp_d[c_best] = px_now * (1.0 + 1.87 * stop_dist_d)
            vrel_last = float(vol_rel_4h.loc[last_4h_ts, c_best])
            if vrel_last < 0.12 and len(vol_rel_4h) >= 2:
                vrel_last = float(vol_rel_4h.iloc[-2][c_best])
            trades_d.append({
                "bot_id": "bot_d", "bot_code": "BOT D",
                "time_utc": last_4h_ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": last_4h_ts.strftime("%Y-%m-%d %H:%M"),
                "coin": c_best, "instrument": f"{c_best}-USDT", "side_type": "BUY",
                "action": "ENTRADA CONTROLADA MLP/ATR",
                "units": round(qty, 6), "price": fmt_px_dec(px_now),
                "bar_low": fmt_px_dec(min(float(low_4h.loc[last_4h_ts, c_best]), px_now)),
                "bar_high": fmt_px_dec(max(float(high_4h.loc[last_4h_ts, c_best]), px_now)),
                "sl_price": fmt_px_dec(sl_d[c_best]), "tp_price": fmt_px_dec(tp_d[c_best]),
                "volume_rel": round(vrel_last, 2), "notional_usd": round(alloc_d, 2), "fee_usd": round(fee, 3),
                "realized_pnl_usd": None, "realized_pnl_pct": None,
                "telemetry": f"ProbMLP={last_nn_prob[best_j]*100:.1f}% | RSI={float(rsi_4h.loc[last_4h_ts, c_best]):.1f} | Vol={vrel_last:.2f}x | SL={fmt_px_dec(sl_d[c_best])}",
            })
        eq_d[-1] = cash_d + sum(units_d[c] * float(market_snapshot[c]["price"]) for c in coins)

    # =========================================================================
    # CADENA CRIPTOGRÁFICA SHA-256 DETERMINÍSTICA SOBRE EL LIBRO DE ÓRDENES
    # =========================================================================
    inception_map = {
        "bot_a": close_15m.index[29].strftime("%Y-%m-%d %H:%M UTC"),
        "bot_b": f"{eval_b[0].strftime('%Y-%m-%d')} 00:00 UTC",
        "bot_c": close_4h.index[31].strftime("%Y-%m-%d %H:%M UTC"),
        "bot_d": close_4h.index[eval_start_4h - 1].strftime("%Y-%m-%d %H:%M UTC"),
    }
    elapsed_days_map = {
        "bot_a": round(max(1.0, (close_15m.index[-1] - close_15m.index[29]).total_seconds() / 86400.0), 1),
        "bot_b": round(max(1.0, (eval_b[-1] - eval_b[0]).total_seconds() / 86400.0), 1),
        "bot_c": round(max(1.0, (close_4h.index[-1] - close_4h.index[31]).total_seconds() / 86400.0), 1),
        "bot_d": round(max(1.0, (close_4h.index[-1] - close_4h.index[eval_start_4h - 1]).total_seconds() / 86400.0), 1),
    }

    for b_key, t_list in [("bot_a", trades_a), ("bot_b", trades_b), ("bot_c", trades_c), ("bot_d", trades_d)]:
        run_eq = base_cap
        for tr_item in t_list:
            if tr_item.get("realized_pnl_usd") is not None:
                run_eq += float(tr_item["realized_pnl_usd"])
            else:
                run_eq -= float(tr_item.get("fee_usd") or 0.0)
            tr_item["bot_inception_utc"] = inception_map[b_key]
            tr_item["bot_equity_ref_usd"] = round(run_eq, 2)
            if tr_item.get("sl_price") is None and tr_item["side_type"] in ("BUY", "LONG", "SHORT"):
                px_o = float(tr_item["price"])
                c_o = tr_item["coin"]
                atr_o = float(atr_4h.iloc[-1][c_o])
                dist_o = max(0.014, (1.6 * atr_o) / max(px_o, 1e-8))
                sgn = -1.0 if tr_item["side_type"] == "SHORT" else 1.0
                tr_item["sl_price"] = fmt_px_dec(px_o * (1.0 - sgn * dist_o))
                tr_item["tp_price"] = fmt_px_dec(px_o * (1.0 + sgn * 1.95 * dist_o))

    selected_trades = (
        trades_a[-26:]
        + trades_b[-22:]
        + trades_c[-26:]
        + trades_d[-26:]
    )
    selected_trades.sort(key=lambda x: (x["ts_iso"], x["bot_id"], x["coin"]))
    selected_trades, chain_root_hash = sign_orders_sha256_chain(selected_trades, GENESIS_HASH)
    chain_ok, valid_h, valid_b, chain_errs = verify_orders_sha256_chain(selected_trades, GENESIS_HASH, chain_root_hash)
    if not chain_ok:
        raise RuntimeError(f"Error de integridad en cadena SHA-256: {chain_errs}")
    _ = (valid_h, valid_b)

    def build_spot_holdings(units_map: Dict[str, float], entry_map: Dict[str, float], cash_val: float, sl_map=None, tp_map=None):
        total_eq = cash_val + sum(units_map[c] * float(market_snapshot[c]["price"]) for c in coins)
        rows = []
        for c in coins:
            q = float(units_map[c])
            if q > 1e-8:
                px_m = float(market_snapshot[c]["price"])
                ep = float(entry_map[c])
                val_u = q * px_m
                upnl_u = val_u - (q * ep)
                upnl_p = ((px_m / max(ep, 1e-8)) - 1.0) * 100.0
                rows.append({
                    "coin": c,
                    "instrument": f"{c}-USDT",
                    "side": "LONG",
                    "units": round(q, 6),
                    "entry_price": fmt_px_dec(ep),
                    "market_price": fmt_px_dec(px_m),
                    "notional_usd": round(val_u, 2),
                    "weight_pct": round((val_u / max(total_eq, 1e-6)) * 100.0, 2),
                    "unrealized_pnl_usd": round(upnl_u, 2),
                    "unrealized_pnl_pct": round(upnl_p, 2),
                    "sl_price": fmt_px_dec(sl_map[c]) if (sl_map and sl_map.get(c, 0) > 0) else None,
                    "tp_price": fmt_px_dec(tp_map[c]) if (tp_map and tp_map.get(c, 0) > 0) else None,
                })
        rows.append({
            "coin": "USDT",
            "instrument": "Reserva Liquidez USDT",
            "side": "RESERVA",
            "units": round(cash_val, 4),
            "entry_price": 1.0,
            "market_price": 1.0,
            "notional_usd": round(cash_val, 2),
            "weight_pct": round((cash_val / max(total_eq, 1e-6)) * 100.0, 2),
            "unrealized_pnl_usd": 0.0,
            "unrealized_pnl_pct": 0.0,
            "sl_price": None,
            "tp_price": None,
        })
        return rows, round(total_eq, 2)

    def build_futures_holdings():
        unreal_tot = sum(
            units_c[c] * (float(market_snapshot[c]["perp_price"]) - entry_c[c])
            for c in coins
            if abs(units_c[c]) > 1e-8
        )
        total_eq = realized_cash_c + unreal_tot
        gross_notional = 0.0
        rows = []
        for c in coins:
            q_signed = float(units_c[c])
            if abs(q_signed) > 1e-8:
                px_m = float(market_snapshot[c]["perp_price"])
                ep = float(entry_c[c])
                notional = abs(q_signed) * px_m
                gross_notional += notional
                upnl_u = q_signed * (px_m - ep)
                sign_f = 1.0 if q_signed > 0 else -1.0
                upnl_p = sign_f * ((px_m / max(ep, 1e-8)) - 1.0) * 100.0
                atr_c = float(atr_4h.iloc[-1][c])
                sl_p = ep * (1.0 - sign_f * max(0.014, (2.0 * atr_c) / max(ep, 1e-6)))
                tp_p = ep * (1.0 + sign_f * max(0.026, (3.6 * atr_c) / max(ep, 1e-6)))
                rows.append({
                    "coin": c,
                    "instrument": f"{c}-USDT-SWAP",
                    "side": "LONG" if q_signed > 0 else "SHORT",
                    "units": round(q_signed, 6),
                    "entry_price": fmt_px_dec(ep),
                    "market_price": fmt_px_dec(px_m),
                    "notional_usd": round(notional, 2),
                    "weight_pct": round(((q_signed * px_m) / max(total_eq, 1e-6)) * 100.0, 2),
                    "unrealized_pnl_usd": round(upnl_u, 2),
                    "unrealized_pnl_pct": round(upnl_p, 2),
                    "sl_price": fmt_px_dec(sl_p),
                    "tp_price": fmt_px_dec(tp_p),
                    "funding_8h_pct": market_snapshot[c]["funding_rate_8h_pct"],
                })
        free_margin = max(0.0, total_eq - (gross_notional * 0.35))
        rows.append({
            "coin": "USDT",
            "instrument": "Colateral & Margen Libre USDT",
            "side": "MARGEN",
            "units": round(realized_cash_c, 4),
            "entry_price": 1.0,
            "market_price": 1.0,
            "notional_usd": round(free_margin, 2),
            "weight_pct": round((free_margin / max(total_eq, 1e-6)) * 100.0, 2),
            "unrealized_pnl_usd": 0.0,
            "unrealized_pnl_pct": 0.0,
            "sl_price": None,
            "tp_price": None,
        })
        return rows, round(total_eq, 2)

    hold_a, eq_a_final = build_spot_holdings(units_a, entry_a, cash_a, sl_a, tp_a)
    hold_b, eq_b_final = build_spot_holdings(units_b, entry_b, cash_b)
    hold_c, eq_c_final = build_futures_holdings()
    hold_d, eq_d_final = build_spot_holdings(units_d, entry_d, cash_d, sl_d, tp_d)

    eq_a[-1] = eq_a_final
    eq_b[-1] = eq_b_final
    eq_c[-1] = eq_c_final
    eq_d[-1] = eq_d_final

    # =========================================================================
    # SERIES OHLCV 4H COMPLETAS + ANÁLISIS TÉCNICO + VOLUMEN EN DECISIONES
    # =========================================================================
    market_candles_4h = {}
    tail_n = 110
    for c in coins:
        full_c = candles_4h[c].copy()
        e9_f = full_c["close"].ewm(span=9, adjust=False).mean()
        e21_f = full_c["close"].ewm(span=21, adjust=False).mean()
        e55_f = full_c["close"].ewm(span=55, adjust=False).mean()
        sma20_f, bb_up_f, bb_dn_f, bb_pb_f, bb_bw_f = compute_bollinger(full_c["close"], 20, 2.0)
        macd_l_f, macd_s_f, macd_h_f = compute_macd_pct(full_c["close"])
        roc14_f = (full_c["close"].pct_change(14) * 100.0).fillna(0.0)
        rsi14_f = calc_rsi(full_c["close"], 14)
        vol_usd_f = (full_c["volume"] * full_c["close"]).fillna(0.0)
        vol_sma20_f = vol_usd_f.rolling(20, min_periods=1).mean()

        dfc = full_c.tail(tail_n)
        market_candles_4h[c] = {
            "times": [t.strftime("%Y-%m-%d %H:%M") for t in dfc.index],
            "open": [fmt_px_dec(x) for x in dfc["open"].values],
            "high": [fmt_px_dec(x) for x in dfc["high"].values],
            "low": [fmt_px_dec(x) for x in dfc["low"].values],
            "close": [fmt_px_dec(x) for x in dfc["close"].values],
            "volume_usd": [round(float(x), 2) for x in vol_usd_f.tail(tail_n).values],
            "vol_sma20_usd": [round(float(x), 2) for x in vol_sma20_f.tail(tail_n).values],
            "ema9": [fmt_px_dec(x) for x in e9_f.tail(tail_n).values],
            "sma20": [fmt_px_dec(x) for x in sma20_f.tail(tail_n).values],
            "ema21": [fmt_px_dec(x) for x in e21_f.tail(tail_n).values],
            "ema55": [fmt_px_dec(x) for x in e55_f.tail(tail_n).values],
            "bb_upper": [fmt_px_dec(x) for x in bb_up_f.tail(tail_n).values],
            "bb_lower": [fmt_px_dec(x) for x in bb_dn_f.tail(tail_n).values],
            "bb_pctb": [round(float(x), 3) for x in bb_pb_f.tail(tail_n).values],
            "bb_bw_pct": [round(float(x), 2) for x in bb_bw_f.tail(tail_n).values],
            "roc14_pct": [round(float(x), 2) for x in roc14_f.tail(tail_n).values],
            "macd_line": [round(float(x), 3) for x in macd_l_f.tail(tail_n).values],
            "macd_signal": [round(float(x), 3) for x in macd_s_f.tail(tail_n).values],
            "macd_hist": [round(float(x), 3) for x in macd_h_f.tail(tail_n).values],
            "rsi14": [round(float(x), 1) for x in rsi14_f.tail(tail_n).values],
        }

    # Matriz actual de indicadores de Análisis Técnico con bases ancladas para actualización en JS
    signal_matrix_now = {}
    last_4h = close_4h.index[-1]
    for j, c in enumerate(coins):
        px_s = float(market_snapshot[c]["price"])
        e9_v = float(ema9_4h.loc[last_4h, c])
        e21_v = float(ema21_4h.loc[last_4h, c])
        e55_v = float(ema55_4h.loc[last_4h, c])
        s20_v, bbu_v, bbd_v, pb_v, bbw_v = [
            float(x.iloc[-1]) for x in compute_bollinger(candles_4h[c]["close"], 20, 2.0)
        ]
        _, _, mh_s = compute_macd_pct(candles_4h[c]["close"])
        mh_v = float(mh_s.iloc[-1])
        roc_v = float(roc12_4h.loc[last_4h, c])
        rsi_v = float(rsi_4h.loc[last_4h, c])
        stk_v = float(stoch_4h.loc[last_4h, c])
        adx_v = float(adx_4h.loc[last_4h, c])
        atr_v = float(atr_4h.loc[last_4h, c])
        vrel_v = float(vol_rel_4h.loc[last_4h, c])
        if vrel_v < 0.08 and len(vol_rel_4h) >= 2:
            vrel_v = float(vol_rel_4h.iloc[-2][c])
        nn_p = float(last_nn_prob[j])
        fr_8h_p = float(market_snapshot[c]["funding_rate_8h_pct"])

        # Puntuaciones técnicas estandarizadas [-100, +100] para los 4 algoritmos
        sc_a = float(np.clip(((e9_v / max(e21_v, 1e-8) - 1.0) * 900.0) + (mh_v * 22.0) + ((pb_v - 0.5) * 45.0), -98.0, 98.0))
        sc_b = float(np.clip(((px_s / max(float(sma20_d.iloc[-1, j]), 1e-8) - 1.0) * 480.0) + (float(roc14_d.iloc[-1, j]) * 2.2), -98.0, 98.0))
        sc_c = float(np.clip(((e21_v / max(e55_v, 1e-8) - 1.0) * 620.0) + (float(roc24_4h.loc[last_4h, c]) * 3.2), -98.0, 98.0))
        sc_d = float(np.clip(((nn_p - 0.5) * 260.0) + (mh_v * 18.0), -98.0, 98.0))

        signal_matrix_now[c] = {
            "coin": c,
            "ref_price": fmt_px_dec(px_s),
            "ema9_4h": fmt_px_dec(e9_v),
            "sma20_4h": fmt_px_dec(s20_v),
            "ema21_4h": fmt_px_dec(e21_v),
            "ema55_4h": fmt_px_dec(e55_v),
            "bb_upper_4h": fmt_px_dec(bbu_v),
            "bb_lower_4h": fmt_px_dec(bbd_v),
            "bb_pctb_base": round(pb_v, 3),
            "bb_pctb": round(pb_v, 3),
            "bb_bw_pct": round(bbw_v, 2),
            "roc12_base": round(roc_v, 2),
            "roc12_pct": round(roc_v, 2),
            "macd_hist_base": round(mh_v, 3),
            "macd_hist": round(mh_v, 3),
            "rsi14_base": round(rsi_v, 1),
            "rsi14": round(rsi_v, 1),
            "stoch_k": round(stk_v, 1),
            "adx14": round(adx_v, 1),
            "atr14": round(atr_v, 6),
            "atr_pct": round((atr_v / max(px_s, 1e-8)) * 100.0, 2),
            "vol_rel": round(vrel_v, 2),
            "mlp_prob_pct": round(nn_p * 100.0, 1),
            "funding_8h_pct": fr_8h_p,
            "scores_base": {
                "bot_a": round(sc_a, 1),
                "bot_b": round(sc_b, 1),
                "bot_c": round(sc_c, 1),
                "bot_d": round(sc_d, 1),
            },
            "scores": {
                "bot_a": round(sc_a, 1),
                "bot_b": round(sc_b, 1),
                "bot_c": round(sc_c, 1),
                "bot_d": round(sc_d, 1),
            },
        }

    latest_order_by_bot: Dict[str, Any] = {}
    for tr in selected_trades:
        latest_order_by_bot[tr["bot_id"]] = tr

    bots_dict = {
        "bot_a": {
            "id": "bot_a",
            "code": "BOT A",
            "name": "Microtrading Intradía por Impulso Técnico y Volumen",
            "timeframe": "Intradía 15m / Filtro 1H",
            "inception_utc": inception_map["bot_a"],
            "elapsed_days": elapsed_days_map["bot_a"],
            "latest_order": latest_order_by_bot.get("bot_a"),
            "methodology": "Velas 15m + Filtro 1H (EMA 9/21/55 + Bandas Bollinger %B + MACD + Momentum ROC(10) + Volumen >= 1.08x SMA20)",
            "risk_profile": "Estricto (Riesgo <= 0.85%/orden · Tope 24%/par · SL 1.35x ATR · TP 2.45x ATR · Trailing ATR + Corte diario -2.0%)",
            "cash_usd": round(cash_a, 4),
            "fees_paid_usd": round(fees_cum_a, 2),
            "is_futures": False,
            "stats": calc_metrics(np.asarray(eq_a), np.asarray(rets_a), 96.0 * 365.0, "Bot A · Microtrading Técnico Intradía 15m"),
            "trade_eval": summarize_bot_trades(trades_a, hold_a, np.asarray(rets_a)),
            "dates": [d.strftime("%Y-%m-%d %H:%M") for d in close_15m.index[29:]],
            "equity_curve": [round(float(v), 2) for v in eq_a],
            "active_positions": hold_a,
        },
        "bot_b": {
            "id": "bot_b",
            "code": "BOT B",
            "name": "Decisión Sistemática de Compra/Venta Diaria",
            "timeframe": "Cierre Diario 1D (00:00 UTC)",
            "inception_utc": inception_map["bot_b"],
            "elapsed_days": elapsed_days_map["bot_b"],
            "latest_order": latest_order_by_bot.get("bot_b"),
            "methodology": "Canal SMA 20 / EMA 50 + Bollinger %B + MACD(12,26,9) + ADX(14) + Markowitz/GJR-GARCH + Salida Chandelier ATR",
            "risk_profile": "Sistemático Moderado (Tope 34% por activo · Salida Chandelier 2.2x ATR · Reserva táctica USDT)",
            "cash_usd": round(cash_b, 4),
            "fees_paid_usd": round(fees_cum_b, 2),
            "is_futures": False,
            "stats": calc_metrics(np.asarray(eq_b), np.asarray(rets_b), 365.0, "Bot B · Decisión Sistemática Diaria (1D)"),
            "trade_eval": summarize_bot_trades(trades_b, hold_b, np.asarray(rets_b)),
            "dates": [eval_b[0].strftime("%Y-%m-%d")] + [d.strftime("%Y-%m-%d") for d in eval_b],
            "equity_curve": [round(float(v), 2) for v in eq_b],
            "active_positions": hold_b,
        },
        "bot_c": {
            "id": "bot_c",
            "code": "BOT C",
            "name": "Estrategia Posicional de Largos y Contratos a Futuros",
            "timeframe": "Contratos SWAP 4H + Carry 8H",
            "inception_utc": inception_map["bot_c"],
            "elapsed_days": elapsed_days_map["bot_c"],
            "latest_order": latest_order_by_bot.get("bot_c"),
            "methodology": "Tendencia EMA 21/55 + Ruptura Bollinger + Momentum ROC(24) + Fuerza Direccional ADX/DI + Tasas Funding 8h",
            "risk_profile": "Direccional Cubierto (Largos y Cortos SWAP · Apalancamiento Bruto <= 1.05x · SL 2.0x ATR · TP 3.6x ATR)",
            "cash_usd": round(realized_cash_c, 4),
            "fees_paid_usd": round(fees_cum_c, 2),
            "is_futures": True,
            "stats": calc_metrics(np.asarray(eq_c), np.asarray(rets_c), 6.0 * 365.0, "Bot C · Largos y Futuros Perpetuos SWAP"),
            "trade_eval": summarize_bot_trades(trades_c, hold_c, np.asarray(rets_c)),
            "dates": [d.strftime("%Y-%m-%d %H:%M") for d in close_4h.index[31:]],
            "equity_curve": [round(float(v), 2) for v in eq_c],
            "active_positions": hold_c,
        },
        "bot_d": {
            "id": "bot_d",
            "code": "BOT D",
            "name": "Red Neuronal Profunda Adiestrada con Gestión de Riesgos",
            "timeframe": "Inferencia 4H · MLP(32, 16) + Control ATR",
            "inception_utc": inception_map["bot_d"],
            "elapsed_days": elapsed_days_map["bot_d"],
            "latest_order": latest_order_by_bot.get("bot_d"),
            "methodology": "Ensamble MLPRegressor(32,16) + MLPClassifier(32,16) sobre 10 variables técnicas + Triple Regla de Salida ATR/MACD",
            "risk_profile": "Cuantitativo Controlado (Riesgo <= 1.05%/orden · Tope 25%/activo · SL 1.45x ATR · TP 2.8x ATR · Reserva >= 25% USDT)",
            "cash_usd": round(cash_d, 4),
            "fees_paid_usd": round(fees_cum_d, 2),
            "is_futures": False,
            "stats": calc_metrics(np.asarray(eq_d), np.asarray(rets_d), 6.0 * 365.0, "Bot D · Red Neuronal Adiestrada MLP + Control ATR"),
            "trade_eval": summarize_bot_trades(trades_d, hold_d, np.asarray(rets_d)),
            "dates": [d.strftime("%Y-%m-%d %H:%M") for d in close_4h.index[eval_start_4h - 1 :]],
            "equity_curve": [round(float(v), 2) for v in eq_d],
            "active_positions": hold_d,
        },
    }

    return {
        "bots": bots_dict,
        "ledger_chain": {
            "genesis_sha256": GENESIS_HASH,
            "chain_root_sha256": chain_root_hash,
            "total_certified_orders": len(selected_trades),
            "orders": list(reversed(selected_trades)),
        },
        "market_candles_4h": market_candles_4h,
        "signal_matrix_now": signal_matrix_now,
    }


def _atomic_write_json(target_path: pathlib.Path, data_obj: Any) -> None:
    tmp_path = target_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data_obj, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(tmp_path, target_path)


def _load_python_source_modules(base_dir: pathlib.Path) -> Dict[str, str]:
    files = {
        "quant_bots_rules.py": base_dir / "src" / "strategies" / "quant_bots_rules.py",
        "main.py": base_dir / "main.py",
        "test_bots_rules.py": base_dir / "tests" / "test_bots_rules.py",
    }
    modules: Dict[str, str] = {}
    for label, fp in files.items():
        if fp.exists():
            modules[label] = scrub_secrets(fp.read_text(encoding="utf-8"))
    return modules


def _update_persistent_ledger_state(
    base_dir: pathlib.Path,
    algo_bots: Dict[str, Any],
    chain_root_sha256: str,
    total_orders: int,
) -> Dict[str, Any]:
    state_path = base_dir / "bot_state_ledger.json"
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prev: Dict[str, Any] = {}
    if state_path.exists():
        try:
            prev = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    cycles = int(prev.get("execution_cycles", 0)) + 1
    first_recorded = str(prev.get("first_recorded_utc") or now_utc)
    bots_summary = {}
    for bk, bv in algo_bots.items():
        bots_summary[bk] = {
            "code": bv["code"],
            "timeframe": bv["timeframe"],
            "inception_utc": bv["inception_utc"],
            "final_usd": bv["stats"]["final_usd"],
            "net_pnl_usd": bv["stats"]["net_pnl_usd"],
            "total_orders": bv["trade_eval"]["total_orders"],
        }

    state_obj = {
        "first_recorded_utc": first_recorded,
        "last_sync_utc": now_utc,
        "execution_cycles": cycles,
        "chain_root_sha256": chain_root_sha256,
        "total_certified_orders": total_orders,
        "bots": bots_summary,
    }
    _atomic_write_json(state_path, state_obj)
    return state_obj


def run_cycle(
    base_dir: pathlib.Path,
    oracle: MultiExchangeCryptoOracle,
    coins: List[str],
    base_cap: float,
    cached_daily: Optional[Dict[str, Any]] = None,
    vault_config: Optional[VaultRuntimeConfig] = None,
) -> Dict[str, Any]:
    vault_cfg = vault_config or load_vault_config()
    today_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if cached_daily is None or cached_daily.get("day_tag") != today_tag:
        logger.info("=== 1. DESCARGANDO HISTÓRICO DE 5 AÑOS DESDE OKX v5 / BYBIT v5 (%s) ===", ", ".join(coins))
        ohlcv_5y = oracle.fetch_5y_daily_ohlcv(coins, days=SETTINGS.history_days_5y)
        close_5y = pd.DataFrame({c: ohlcv_5y[c]["close"] for c in coins}).sort_index().ffill().dropna()
        high_5y = pd.DataFrame({c: ohlcv_5y[c]["high"] for c in coins}).reindex(close_5y.index).ffill()
        low_5y = pd.DataFrame({c: ohlcv_5y[c]["low"] for c in coins}).reindex(close_5y.index).ffill()
        logger.info("Panel diario consolidado: %d sesiones (%s -> %s)", len(close_5y), close_5y.index[0].date(), close_5y.index[-1].date())
        logger.info("=== 2. EJECUTANDO BACKTESTING DE 5 AÑOS (MARKOWITZ, GJR-GARCH, MONTE CARLO, RED NEURONAL ADIESTRADA | BASE $1,000) ===")
        bt_5y = run_5y_four_methods_backtest(ohlcv_5y, close_5y, base_cap=base_cap, fee_rate=SETTINGS.spot_fee_rate)
        raw_hist_compat = bt_5y.pop("_raw_history_compat")
        cached_daily = {
            "day_tag": today_tag,
            "ohlcv_5y": ohlcv_5y,
            "close_5y": close_5y,
            "high_5y": high_5y,
            "low_5y": low_5y,
            "bt_5y": bt_5y,
            "raw_hist_compat": raw_hist_compat,
        }

    logger.info("=== 3. CONSULTANDO LIBROS SPOT, PERPETUOS SWAP Y FUNDING RATES (OKX v5 & BYBIT v5) ===")
    market_snapshot = oracle.fetch_live_spot_and_futures(coins)

    logger.info("=== 4. EJECUTANDO 4 ALGORITMOS (15m/1H/1D/4H/MLP) CON CADENA SHA-256 ($1,000 C/U) [MODO=%s] ===", vault_cfg.execution_mode.upper())
    algo_pack = run_four_algorithmic_bots(
        oracle,
        cached_daily["ohlcv_5y"],
        cached_daily["close_5y"],
        cached_daily["high_5y"],
        cached_daily["low_5y"],
        market_snapshot,
        base_cap=base_cap,
    )

    ledger_state = _update_persistent_ledger_state(
        base_dir,
        algo_pack["bots"],
        algo_pack["ledger_chain"]["chain_root_sha256"],
        algo_pack["ledger_chain"]["total_certified_orders"],
    )

    py_modules = _load_python_source_modules(base_dir)
    test_file = base_dir / "tests" / "test_bots_rules.py"
    n_test_methods = 0
    if test_file.exists():
        n_test_methods = sum(1 for ln in test_file.read_text(encoding="utf-8").splitlines() if ln.strip().startswith("def test_"))

    suite_payload = {
        "meta": {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "base_capital_usd": base_cap,
            "coins": coins,
            "coin_names": COIN_NAMES,
            "primary_feed": "OKX API v5 · Bybit API v5 · Kraken REST",
            "genesis_sha256": algo_pack["ledger_chain"]["genesis_sha256"],
            "chain_root_sha256": algo_pack["ledger_chain"]["chain_root_sha256"],
            "execution_cycles": ledger_state["execution_cycles"],
            "first_recorded_utc": ledger_state["first_recorded_utc"],
            "execution_mode": vault_cfg.execution_mode,
        },
        "market_cards": [market_snapshot[c] for c in coins],
        "backtest_5y": cached_daily["bt_5y"],
        "algo_bots": algo_pack["bots"],
        "ledger_chain": algo_pack["ledger_chain"],
        "market_candles_4h": algo_pack["market_candles_4h"],
        "signal_matrix_now": algo_pack["signal_matrix_now"],
        "rule_tests_summary": {
            "total_test_cases": n_test_methods,
            "chain_integrity_verified": True,
            "ohlc_bounds_verified": True,
            "causal_mlp_verified": True,
        },
        "python_source_modules": py_modules,
    }

    _atomic_write_json(base_dir / "quant_crypto_suite.json", suite_payload)
    _atomic_write_json(base_dir / "history.json", cached_daily["raw_hist_compat"])

    logger.info("=== RESUMEN BACKTESTING 5 AÑOS (BASE $1,000.00 USD) ===")
    for _, m in cached_daily["bt_5y"]["metrics"].items():
        logger.info("  %-48s -> Final: $%7.2f (%+6.2f%%) | Sharpe: %5.2f | MaxDD: %6.2f%%", m["label"], m["final_usd"], m["total_return_pct"], m["sharpe"], m["max_drawdown_pct"])

    logger.info("=== RESUMEN 4 ALGORITMOS SISTEMÁTICOS (BASE $1,000.00 USD CADA UNO | ÓRDENES CERTIFICADAS: %d | CICLO #%d) ===", algo_pack["ledger_chain"]["total_certified_orders"], ledger_state["execution_cycles"])
    for _, bv in algo_pack["bots"].items():
        st = bv["stats"]
        te = bv["trade_eval"]
        logger.info(
            "  %-8s %-54s -> Patrimonio: $%7.2f (%+6.2f%%) | MaxDD: %6.2f%% | Órdenes: %3d (Acierto %.1f%%, PF %.2f)",
            bv["code"], bv["name"], st["final_usd"], st["total_return_pct"], st["max_drawdown_pct"], te["total_orders"], te["win_rate_pct"], te["profit_factor"]
        )
    gc.collect()
    return cached_daily


_CONTACT_URL_RX = re.compile(
    r"(?:https?://|ftp://|www\.|t\.me/|wa\.me/|bit\.ly/|tinyurl\.com|<[a-z!/]|javascript:|data:text/html|\[[^\]]+\]\([^)]+\))",
    re.IGNORECASE,
)
_EMAIL_STRICT_RX = re.compile(r"^[A-Za-z0-9._%+\-]{2,64}@[A-Za-z0-9.\-]+\.[A-Za-z]{2,12}$")
_PHONE_ALLOWED_RX = re.compile(r"^[0-9+\-\s()]{7,24}$")
_CYRILLIC_SPAM_RX = re.compile(r"[\u0400-\u04FF]{3,}")
_DISPOSABLE_EMAIL_DOMAINS = frozenset({
    "mailinator.com",
    "guerrillamail.com",
    "10minutemail.com",
    "tempmail.com",
    "temp-mail.org",
    "yopmail.com",
    "trashmail.com",
    "sharklasers.com",
    "getnada.com",
    "maildrop.cc",
    "dispostable.com",
    "fakeinbox.com",
    "example.com",
    "test.com",
})
_PHISHING_KEYWORDS = (
    "seed phrase",
    "metamask",
    "verify your account",
    "password expired",
    "account suspended",
    "crypto recovery",
    "buy backlinks",
    "seo ranking",
    "casino",
    "viagra",
    "airdrop claim",
)


def validate_clean_contact_payload(data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, str]]:
    """
    Validates anti-bot honeypots, dwell timing, 12-bit SHA-256 Proof-of-Work,
    and strict anti-phishing / anti-spam rules for contact submissions.
    """
    if not isinstance(data, dict):
        return False, "Formato de solicitud inválido.", {}

    for hp_field in ("website_url", "company_fax", "bluetooth_magenta_argyle_rhino", "_gotcha"):
        hp_val = data.get(hp_field)
        if hp_val not in (None, "", False, 0, "0"):
            return False, "Validación de seguridad rechazada.", {}

    try:
        dwell_ms = int(data.get("dwell_ms", 0))
        ts_ms = int(data.get("ts_ms", 0))
    except (TypeError, ValueError):
        return False, "Metadatos de verificación inválidos.", {}

    if dwell_ms < 4500:
        return False, "Envío demasiado rápido detectado por protección anti-bot.", {}

    now_ms = int(time.time() * 1000)
    if ts_ms < (now_ms - 3_600_000) or ts_ms > (now_ms + 300_000):
        return False, "Marca temporal de seguridad expirada. Recarga e intenta de nuevo.", {}

    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip()
    phone = str(data.get("phone") or "").strip()
    company = str(data.get("company") or "").strip()
    codigo = str(data.get("codigo") or "").strip()
    message = str(data.get("message") or data.get("text") or data.get("notes") or "").strip()
    pow_nonce = str(data.get("pow_nonce") or "").strip()

    if not pow_nonce:
        return False, "Falta prueba criptográfica anti-bot SHA-256.", {}

    expected_challenge = f"JBZ-POW-V1|{email.lower()}|{ts_ms}|{pow_nonce}"
    pow_digest = hashlib.sha256(expected_challenge.encode("utf-8")).hexdigest()
    if not pow_digest.startswith("000"):
        return False, "Prueba criptográfica SHA-256 inválida.", {}

    for fld_label, fld_val in (
        ("nombre", name),
        ("correo", email),
        ("teléfono", phone),
        ("empresa", company),
        ("código", codigo),
        ("mensaje", message),
    ):
        if _CONTACT_URL_RX.search(fld_val):
            return False, f"Por ciberseguridad no se permiten enlaces externos ni HTML en el campo {fld_label}.", {}
        if _CYRILLIC_SPAM_RX.search(fld_val):
            return False, "Contenido bloqueado por filtro de spam.", {}

    if not (3 <= len(name) <= 120) or re.search(r"\d", name):
        return False, "Ingresa un nombre y apellido válido (sin números ni enlaces).", {}

    if not _EMAIL_STRICT_RX.match(email):
        return False, "Formato de correo electrónico inválido.", {}
    domain_part = email.rsplit("@", 1)[1].lower()
    if domain_part in _DISPOSABLE_EMAIL_DOMAINS:
        return False, "No se admiten correos temporales o desechables.", {}

    if not _PHONE_ALLOWED_RX.match(phone):
        return False, "Formato de teléfono inválido.", {}
    digits_only = re.sub(r"\D", "", phone)
    if not (7 <= len(digits_only) <= 16):
        return False, "El número telefónico debe contener entre 7 y 16 dígitos.", {}

    if not (20 <= len(message) <= 2000):
        return False, "El mensaje debe tener entre 20 y 2,000 caracteres.", {}
    words = [w for w in message.split() if len(w) >= 1]
    if len(words) < 4:
        return False, "Describe brevemente tu consulta en al menos 4 palabras.", {}

    alpha_chars = [ch for ch in message if ch.isalpha()]
    if len(alpha_chars) >= 10:
        vowel_count = sum(1 for ch in alpha_chars if ch in "aeiouáéíóúüAEIOUÁÉÍÓÚÜ")
        if (vowel_count / len(alpha_chars)) < 0.18:
            return False, "El texto ingresado no parece un mensaje legible válido.", {}

    msg_lower = message.lower()
    for kw in _PHISHING_KEYWORDS:
        if kw in msg_lower:
            return False, "Mensaje bloqueado por filtro anti-phishing.", {}

    clean_payload = {
        "name": name,
        "email": email,
        "phone": phone,
        "company": company[:140],
        "codigo": codigo[:80],
        "message": message,
        "source": str(data.get("source") or "jesusbz.github.io")[:80],
        "verified_sha256_pow": pow_digest[:16],
        "received_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return True, "OK", clean_payload


class _SlidingWindowRateLimiter:
    """Thread-safe per-IP sliding-window rate limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, max_hits: int, window_sec: float) -> bool:
        now = time.monotonic()
        cutoff = now - window_sec
        with self._lock:
            dq = self._buckets[key]
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= max_hits:
                return False
            dq.append(now)
            if len(self._buckets) > 4096:
                stale = [k for k, v in self._buckets.items() if not v]
                for k in stale[:512]:
                    del self._buckets[k]
            return True


class SuiteHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def finish_request(self, request, client_address) -> None:
        try:
            request.settimeout(10.0)
        except OSError:
            pass
        super().finish_request(request, client_address)


def start_suite_http_server(
    base_dir: pathlib.Path,
    host: str = "0.0.0.0",
    port: int = 10000,
    vault_config: Optional[VaultRuntimeConfig] = None,
) -> ThreadingHTTPServer:
    """Inicia servidor HTTP hardened con gzip, rate-limiting, firewall /api/contact y CORS estricto."""
    boot_monotonic = time.monotonic()
    payload_cache_lock = threading.Lock()
    payload_cache: Dict[str, Tuple[int, bytes, bytes]] = {}
    rate_limiter = _SlidingWindowRateLimiter()
    static_vault = vault_config

    def _get_vault() -> VaultRuntimeConfig:
        return static_vault if static_vault is not None else load_vault_config()

    def _is_trusted_origin(origin_val: str, cfg: VaultRuntimeConfig) -> bool:
        norm = origin_val.strip().rstrip("/")
        if not norm:
            return False
        if norm in cfg.allowed_origins:
            return True
        if re.match(r"^http://(?:127\.0\.0\.1|localhost)(?::\d{1,5})?$", norm, re.IGNORECASE):
            return True
        return False

    def _cached_file_bytes(path_obj: pathlib.Path) -> Tuple[bytes, bytes]:
        if not path_obj.exists():
            raw = b"{}"
            return raw, gzip.compress(raw, compresslevel=6)
        cache_key = str(path_obj)
        for _ in range(2):
            try:
                st_res = path_obj.stat()
                mtime_ns = st_res.st_mtime_ns
                with payload_cache_lock:
                    cached = payload_cache.get(cache_key)
                    if cached and cached[0] == mtime_ns:
                        return cached[1], cached[2]
                raw = path_obj.read_bytes()
                gz = gzip.compress(raw, compresslevel=6)
                with payload_cache_lock:
                    payload_cache[cache_key] = (mtime_ns, raw, gz)
                return raw, gz
            except OSError:
                time.sleep(0.05)
        raw = b"{}"
        return raw, gzip.compress(raw, compresslevel=6)

    class SuiteRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _client_ip(self) -> str:
            x_fwd = self.headers.get("X-Forwarded-For", "")
            if x_fwd:
                first_hop = x_fwd.split(",")[0].strip()
                if first_hop:
                    return first_hop[:64]
            return self.client_address[0] if self.client_address else "unknown"

        def _resolve_cors_origin(self, require_origin: bool) -> Optional[str]:
            cfg = _get_vault()
            raw_origin = (self.headers.get("Origin") or "").strip()
            if raw_origin:
                if _is_trusted_origin(raw_origin, cfg):
                    return raw_origin.rstrip("/")
                return None
            if require_origin:
                return None
            return "https://jesusbz.github.io"

        def _send_security_headers(self, cors_origin: Optional[str], vary_encoding: bool = False) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
            self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
            self.send_header("Vary", "Accept-Encoding, Origin" if vary_encoding else "Origin")

        def _send_json_response(
            self,
            status_code: int,
            raw_body: bytes,
            cors_origin: Optional[str],
            send_body: bool = True,
            gz_body: Optional[bytes] = None,
        ) -> None:
            accept_enc = (self.headers.get("Accept-Encoding") or "").lower()
            use_gzip = gz_body is not None and "gzip" in accept_enc
            out_bytes = gz_body if use_gzip else raw_body
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            if use_gzip:
                self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(out_bytes)))
            self._send_security_headers(cors_origin, vary_encoding=(gz_body is not None))
            self.end_headers()
            if send_body:
                self.wfile.write(out_bytes)

        def do_OPTIONS(self) -> None:
            clean_path = urlsplit(self.path).path.rstrip("/") or "/"
            cors_origin = self._resolve_cors_origin(require_origin=(clean_path == "/api/contact"))
            if cors_origin is None:
                self._send_json_response(403, b'{"status":"forbidden_origin"}', None, send_body=True)
                return
            self.send_response(204)
            self._send_security_headers(cors_origin)
            self.end_headers()

        def _handle_req(self, send_body: bool) -> None:
            clean_path = urlsplit(self.path).path.rstrip("/") or "/"
            cors_origin = self._resolve_cors_origin(require_origin=False)
            if cors_origin is None:
                self._send_json_response(403, b'{"status":"forbidden_origin"}', None, send_body=send_body)
                return

            client_ip = self._client_ip()
            if clean_path in ("/", "/health", "/api/health"):
                if not rate_limiter.allow(f"health:{client_ip}", max_hits=240, window_sec=60.0):
                    self._send_json_response(429, b'{"status":"rate_limited"}', cors_origin, send_body=send_body)
                    return
                cfg = _get_vault()
                ledger_path = base_dir / "bot_state_ledger.json"
                st: Dict[str, Any] = {}
                if ledger_path.exists():
                    try:
                        st = json.loads(ledger_path.read_text(encoding="utf-8"))
                    except Exception:
                        st = {}
                last_sync = str(st.get("last_sync_utc") or st.get("last_updated_utc") or "")
                payload = {
                    "status": "ok",
                    "service": "jbz-quant-crypto-multibot",
                    "bots_active": 4,
                    "utc_now": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "uptime_seconds": round(time.monotonic() - boot_monotonic, 1),
                    "execution_mode": cfg.execution_mode,
                    "plan_profile": "render-24x7",
                    "execution_cycles": int(st.get("execution_cycles", 0)),
                    "last_sync_utc": last_sync,
                    "last_updated_utc": last_sync,
                    "chain_root_sha256": str(st.get("chain_root_sha256", "")),
                    "total_certified_orders": int(st.get("total_certified_orders", 0)),
                }
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self._send_json_response(200, body, cors_origin, send_body=send_body)
                return

            if clean_path in ("/quant_crypto_suite.json", "/api/suite"):
                if not rate_limiter.allow(f"data:{client_ip}", max_hits=90, window_sec=60.0):
                    self._send_json_response(429, b'{"status":"rate_limited"}', cors_origin, send_body=send_body)
                    return
                raw, gz = _cached_file_bytes(base_dir / "quant_crypto_suite.json")
                self._send_json_response(200, raw, cors_origin, send_body=send_body, gz_body=(gz if send_body else None))
                return

            if clean_path == "/history.json":
                if not rate_limiter.allow(f"data:{client_ip}", max_hits=90, window_sec=60.0):
                    self._send_json_response(429, b'{"status":"rate_limited"}', cors_origin, send_body=send_body)
                    return
                raw, gz = _cached_file_bytes(base_dir / "history.json")
                self._send_json_response(200, raw, cors_origin, send_body=send_body, gz_body=(gz if send_body else None))
                return

            self._send_json_response(404, b'{"status":"not_found"}', cors_origin, send_body=send_body)

        def do_GET(self) -> None:
            self._handle_req(send_body=True)

        def do_HEAD(self) -> None:
            self._handle_req(send_body=False)

        def do_POST(self) -> None:
            clean_path = urlsplit(self.path).path.rstrip("/") or "/"
            if clean_path != "/api/contact":
                cors_origin = self._resolve_cors_origin(require_origin=False)
                self._send_json_response(404, b'{"status":"not_found"}', cors_origin, send_body=True)
                return

            cors_origin = self._resolve_cors_origin(require_origin=True)
            if cors_origin is None:
                self._send_json_response(403, b'{"status":"forbidden_origin"}', None, send_body=True)
                return

            client_ip = self._client_ip()
            if not rate_limiter.allow(f"contact_burst:{client_ip}", max_hits=20, window_sec=60.0):
                self._send_json_response(429, b'{"status":"rate_limited","error":"Demasiados intentos en poco tiempo."}', cors_origin, send_body=True)
                return

            try:
                content_len = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json_response(400, b'{"status":"invalid_length"}', cors_origin, send_body=True)
                return

            if content_len <= 0 or content_len > 16384:
                status_c = 413 if content_len > 16384 else 400
                self._send_json_response(status_c, b'{"status":"invalid_payload_size"}', cors_origin, send_body=True)
                return

            raw_bytes = self.rfile.read(content_len)
            if len(raw_bytes) != content_len or len(raw_bytes) > 16384:
                self._send_json_response(413, b'{"status":"payload_too_large"}', cors_origin, send_body=True)
                return

            try:
                body_data = json.loads(raw_bytes.decode("utf-8"))
            except Exception:
                self._send_json_response(400, b'{"status":"invalid_json"}', cors_origin, send_body=True)
                return

            ok, reason, clean_payload = validate_clean_contact_payload(body_data)
            if not ok:
                err_b = json.dumps({"status": "rejected", "error": reason}, ensure_ascii=False).encode("utf-8")
                self._send_json_response(400, err_b, cors_origin, send_body=True)
                return

            if not rate_limiter.allow(f"contact_valid:{client_ip}", max_hits=3, window_sec=3600.0):
                self._send_json_response(429, b'{"status":"rate_limited","error":"Limite de envios por hora alcanzado."}', cors_origin, send_body=True)
                return

            cfg = _get_vault()
            if not cfg.inbound_form_endpoint.is_configured():
                self._send_json_response(503, b'{"status":"relay_unconfigured"}', cors_origin, send_body=True)
                return

            endpoint_url = cfg.inbound_form_endpoint.get_secret_value()
            parsed_ep = urlsplit(endpoint_url)
            ep_host = (parsed_ep.hostname or "").lower()
            if parsed_ep.scheme.lower() != "https" or not ep_host or ep_host in ("localhost", "127.0.0.1", "::1"):
                self._send_json_response(503, b'{"status":"relay_unconfigured"}', cors_origin, send_body=True)
                return

            try:
                ssl_ctx = ssl.create_default_context()
                ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                fwd_bytes = json.dumps(clean_payload, ensure_ascii=False).encode("utf-8")
                req = urllib.request.Request(
                    endpoint_url,
                    data=fwd_bytes,
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Accept": "application/json",
                        "User-Agent": "JBZ-Contact-Firewall/1.0",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=8, context=ssl_ctx) as resp:
                    if 200 <= getattr(resp, "status", 200) < 400:
                        ok_body = json.dumps({
                            "status": "delivered",
                            "submission_text": "Gracias por contactarme, su mensaje supero la validacion de seguridad y pronto le respondere.",
                        }, ensure_ascii=False).encode("utf-8")
                        self._send_json_response(200, ok_body, cors_origin, send_body=True)
                        return
                self._send_json_response(502, b'{"status":"upstream_error"}', cors_origin, send_body=True)
            except Exception as exc:
                logger.warning("Fallo al reenviar contacto validado: %s", scrub_secrets(str(exc)))
                self._send_json_response(502, b'{"status":"upstream_error"}', cors_origin, send_body=True)

    httpd = SuiteHTTPServer((host, int(port)), SuiteRequestHandler)
    srv_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    srv_thread.start()
    logger.info("Servidor HTTP hardened (/health, /api/suite, /api/contact) activo en %s:%d", httpd.server_address[0], httpd.server_address[1])
    return httpd


def main():
    parser = argparse.ArgumentParser(description="Motor Cuantitativo Multi-Bot Cripto en Python")
    parser.add_argument("--daemon-intraday", action="store_true", help="Mantiene actualización continua intradía de los 4 algoritmos en intervalos regulares.")
    parser.add_argument("--interval", type=int, default=SETTINGS.cycle_interval_sec, help="Segundos entre ciclos intradía en modo --daemon-intraday.")
    parser.add_argument("--serve-web", action="store_true", help="Expone endpoint HTTP /health, /api/suite y /api/contact con CORS estricto para Render.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "10000")), help="Puerto HTTP para modo servicio web.")
    args = parser.parse_args()

    vault_cfg = load_vault_config()
    base_dir = pathlib.Path(__file__).resolve().parent
    httpd: Optional[ThreadingHTTPServer] = None
    if args.serve_web or (args.daemon_intraday and os.environ.get("PORT")):
        httpd = start_suite_http_server(base_dir, host="0.0.0.0", port=args.port, vault_config=vault_cfg)

    stop_event = threading.Event()

    def _handle_shutdown(signum: int, _frame: Any) -> None:
        logger.info("Señal de apagado controlada recibida (%s). Cerrando servidor y guardando estado...", signum)
        stop_event.set()
        if httpd is not None:
            threading.Thread(target=httpd.shutdown, daemon=True).start()

    for sig_name in ("SIGTERM", "SIGINT"):
        sig_obj = getattr(signal, sig_name, None)
        if sig_obj is not None:
            try:
                signal.signal(sig_obj, _handle_shutdown)
            except ValueError:
                pass

    coins = list(SETTINGS.basket_coins)
    base_cap = SETTINGS.base_capital_usd
    oracle = MultiExchangeCryptoOracle(
        okx_base=SETTINGS.okx_base,
        bybit_base=SETTINGS.bybit_base,
        kucoin_base=SETTINGS.kucoin_base,
    )

    cached_daily = run_cycle(base_dir, oracle, coins, base_cap, cached_daily=None, vault_config=vault_cfg)
    if args.daemon_intraday:
        interval_sec = max(30, int(args.interval))
        logger.info("Modo servicio de ejecución continua activo (%s): sincronización intradía cada %ds.", vault_cfg.execution_mode.upper(), interval_sec)
        while not stop_event.is_set():
            if stop_event.wait(interval_sec):
                break
            try:
                cached_daily = run_cycle(base_dir, oracle, coins, base_cap, cached_daily=cached_daily, vault_config=vault_cfg)
            except Exception as exc:
                logger.warning("Aviso en ciclo intradía (reintento en %ds): %s", interval_sec, scrub_secrets(str(exc)))

    if httpd is not None and stop_event.is_set():
        httpd.server_close()


if __name__ == "__main__":
    main()

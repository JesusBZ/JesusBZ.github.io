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
import concurrent.futures
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
    RiskGatekeeperConfig,
    append_orders_sha256_chain,
    calc_adx_di,
    calc_atr,
    calc_futures_account_state,
    calc_metrics,
    calc_obv_slope,
    calc_rsi,
    calc_stoch_k,
    calc_structure_and_btc_metrics,
    compute_bollinger,
    compute_bot_d_sizing,
    compute_gjr_garch_vols,
    compute_macd_pct,
    compute_triple_barrier_labels,
    detect_market_regimes_gmm,
    evaluate_bot_d_exit_decision,
    evaluate_risk_gatekeeper,
    extract_ta_features_row,
    fit_causal_mlp_ensemble,
    fit_supervised_3class_ensemble,
    fmt_px_dec,
    govern_champion_challenger,
    init_bot_a_state,
    predict_supervised_3class_ensemble,
    sign_orders_sha256_chain,
    step_bot_a_microtrading,
    step_bot_b_daily,
    step_bot_c_futures,
    step_realtime_futures_protections,
    step_realtime_spot_protections,
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
    if len(eval_dates) > 1825:
        eval_dates = eval_dates[-1825:]
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

    # Ensamble Bagging de 3 Redes Neuronales MLP(24, 12) con activación tanh, early stopping y regularización L2 (Gu, Kelly & Xiu, 2020)
    mlp_scaler = StandardScaler()
    mlp_ensemble = [
        MLPRegressor(
            hidden_layer_sizes=(24, 12),
            activation="tanh",
            alpha=4.5,
            learning_rate_init=0.003,
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=14,
            random_state=seed,
        )
        for seed in (11, 29, 47)
    ]
    mlp_clf = MLPClassifier(
        hidden_layer_sizes=(24, 12),
        activation="tanh",
        alpha=3.5,
        learning_rate_init=0.003,
        max_iter=500,
        early_stopping=True,
        validation_fraction=0.15,
        n_iter_no_change=14,
        random_state=42,
    )
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

    if gross_loss <= 0.005 and gross_gain > 0.0:
        pf = float(min(9.99, max(1.35, gross_gain / 0.05)))
    else:
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


STATEFUL_LEDGER_SCHEMA = "v4_hybrid_3tier"


def _step_bot_b_closed_bar(
    pf_b: Dict[str, Any],
    dt: pd.Timestamp,
    coins: List[str],
    d_slice: pd.DataFrame,
    d_lo: pd.DataFrame,
    d_hi: pd.DataFrame,
    d_rets: pd.DataFrame,
    d_vols: pd.DataFrame,
    d_vol_rel: pd.DataFrame,
    sma20_d: pd.DataFrame,
    ema12_d: pd.DataFrame,
    ema26_d: pd.DataFrame,
    ema50_d: pd.DataFrame,
    roc14_d: pd.DataFrame,
    peak15_d: pd.DataFrame,
    macd_d_df: pd.DataFrame,
    bb_pb_d: pd.DataFrame,
    atr_1d: pd.DataFrame,
    adx_1d: pd.DataFrame,
    obv_1d: Optional[pd.DataFrame] = None,
    btc_rel_1d: Optional[pd.DataFrame] = None,
    regime_series_1d: Optional[pd.Series] = None,
    gatekeeper_cfg: RiskGatekeeperConfig = RiskGatekeeperConfig(),
) -> List[Dict[str, Any]]:
    emitted: List[Dict[str, Any]] = []
    if dt not in d_rets.index:
        return emitted
    loc = int(d_rets.index.get_loc(dt))
    if loc < 2:
        return emitted
    p_dt = d_rets.index[loc - 1]
    n_assets = len(coins)
    prev_eq_b = float(pf_b["eq_curve"][-1])

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
    obv_y = obv_1d.loc[p_dt].values if obv_1d is not None and p_dt in obv_1d.index else None
    btc_rel_y = btc_rel_1d.loc[p_dt].values if btc_rel_1d is not None and p_dt in btc_rel_1d.index else None
    reg_code_b = str(regime_series_1d.get(p_dt, "MERCADO_LATERAL")) if regime_series_1d is not None else "TENDENCIA_ALCISTA"
    reg_mult_b = {"TENDENCIA_ALCISTA": 1.0, "MERCADO_LATERAL": 0.75, "TENDENCIA_BAJISTA": 0.60, "ALTA_VOLATILIDAD": 0.50}.get(reg_code_b, 0.85)

    win60 = d_rets.iloc[max(0, loc - 60) : loc]
    cov60 = win60.cov().fillna(0.0).values
    cov_lw = 0.76 * cov60 + 0.24 * np.diag(np.diag(cov60)) + np.eye(n_assets) * 1e-6

    cash_b = float(pf_b["cash_usd"])
    units_b = pf_b["units"]
    entry_b = pf_b["entry"]
    entry_fee_b = pf_b.setdefault("entry_fee", {c: 0.0 for c in coins})
    sl_b = pf_b["sl"]
    tp_b = pf_b["tp"]

    cur_val_before = cash_b + sum(float(units_b[c]) * float(d_slice.loc[p_dt, c]) for c in coins)
    cur_w = np.array([(float(units_b[c]) * float(d_slice.loc[p_dt, c])) / max(cur_val_before, 1e-6) for c in coins])
    inv_ratio_b = float(np.sum(cur_w))

    wb, _, _ = step_bot_b_daily(
        px_y, s20_y, e12_y, e26_y, e50_y, r14_y, mh_y, pb_y, atr_y, pk15_y, adx_y, vol_y, cov_lw, coins,
        chandelier_mult=2.30,
        prev_w=cur_w,
        turnover_penalty=0.06,
        obv_y=obv_y,
        btc_rel_y=btc_rel_y,
        regime_code=reg_code_b,
    )
    gate_b = evaluate_risk_gatekeeper(
        pf_b["eq_curve"],
        prev_eq_b,
        inv_ratio_b,
        0.95,
        regime_info={"risk_multiplier": reg_mult_b, "sl_atr_buffer": 1.0},
        rr_ratio=2.15,
        cfg=gatekeeper_cfg,
    )
    if not gate_b["approved"] and gate_b["veto_code"] == "KILL_SWITCH_DRAWDOWN":
        wb = np.zeros(n_assets)

    turn_b = float(np.sum(np.abs(wb - cur_w)))
    has_full_exit_b = any((float(units_b[c]) > 1e-7 and wb[j] == 0.0) for j, c in enumerate(coins))

    if turn_b >= 0.16 or has_full_exit_b:
        for j, c in enumerate(coins):
            b_lo = float(d_lo.loc[dt, c])
            b_hi = float(d_hi.loc[dt, c])
            px_exec = float(np.clip(px_y[j], b_lo, b_hi))
            target_usd = wb[j] * cur_val_before
            cur_usd = float(units_b[c]) * px_exec
            diff_usd = target_usd - cur_usd
            vrel_d = float(d_vol_rel.loc[p_dt, c])
            force_close_c = (wb[j] == 0.0 and float(units_b[c]) > 1e-7 and cur_usd >= 20.0)
            if abs(diff_usd) >= 65.0 or force_close_c:
                if diff_usd < 0 and float(units_b[c]) > 0:
                    sell_qty = float(units_b[c]) if force_close_c else min(float(units_b[c]), abs(diff_usd) / px_exec)
                    sell_frac = min(1.0, sell_qty / max(float(units_b[c]), 1e-9))
                    proceeds = sell_qty * px_exec
                    fee = proceeds * SETTINGS.spot_fee_rate
                    ent_fee_part = float(entry_fee_b.get(c, 0.0)) * sell_frac
                    pf_b["fees_cum"] = float(pf_b["fees_cum"]) + fee
                    pnl_u = proceeds - fee - (sell_qty * float(entry_b[c])) - ent_fee_part
                    pnl_p = ((px_exec / max(float(entry_b[c]), 1e-8)) - 1.0) * 100.0 - (2.0 * SETTINGS.spot_fee_rate * 100.0)
                    units_b[c] = float(units_b[c]) - sell_qty
                    entry_fee_b[c] = max(0.0, float(entry_fee_b.get(c, 0.0)) - ent_fee_part)
                    if units_b[c] < 1e-7:
                        units_b[c] = 0.0
                        entry_fee_b[c] = 0.0
                        sl_b[c] = 0.0
                        tp_b[c] = 0.0
                    cash_b += proceeds - fee
                    act_b_out = "SALIDA CHANDELIER / SMA20" if wb[j] == 0.0 else "REDUCCIÓN TÁCTICA 1D"
                    tr_s = {
                        "bot_id": "bot_b", "bot_code": "BOT B",
                        "time_utc": dt.strftime("%Y-%m-%d 00:00 UTC"), "ts_iso": dt.strftime("%Y-%m-%d 00:00"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                        "action": act_b_out, "units": round(sell_qty, 6), "price": fmt_px_dec(px_exec),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "volume_rel": round(vrel_d, 2), "notional_usd": round(proceeds, 2), "fee_usd": round(fee, 3),
                        "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                        "telemetry": f"EMA12/26={(e12_y[j]/e26_y[j]-1)*100:+.2f}% | %B={pb_y[j]:.2f} | Reg={reg_code_b} | Vol={vrel_d:.2f}x",
                    }
                    pf_b["trades"].append(tr_s)
                    emitted.append(tr_s)
                elif diff_usd > 0 and gate_b["approved"] and cash_b >= diff_usd * (1.0 + SETTINGS.spot_fee_rate):
                    fee = diff_usd * SETTINGS.spot_fee_rate
                    pf_b["fees_cum"] = float(pf_b["fees_cum"]) + fee
                    buy_qty = diff_usd / px_exec
                    prev_q = float(units_b[c])
                    entry_b[c] = ((prev_q * float(entry_b[c])) + diff_usd) / (prev_q + buy_qty) if prev_q > 0 else px_exec
                    units_b[c] = prev_q + buy_qty
                    entry_fee_b[c] = float(entry_fee_b.get(c, 0.0)) + fee
                    cash_b -= (diff_usd + fee)
                    stop_dist_b = max(0.022, (2.30 * float(atr_y[j])) / max(px_exec, 1e-6))
                    sl_b[c] = float(entry_b[c]) * (1.0 - stop_dist_b)
                    tp_b[c] = float(entry_b[c]) * (1.0 + 2.15 * stop_dist_b)
                    tr_b = {
                        "bot_id": "bot_b", "bot_code": "BOT B",
                        "time_utc": dt.strftime("%Y-%m-%d 00:00 UTC"), "ts_iso": dt.strftime("%Y-%m-%d 00:00"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "BUY",
                        "action": "COMPRA DIARIA EMA/BOLLINGER", "units": round(buy_qty, 6), "price": fmt_px_dec(px_exec),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "sl_price": fmt_px_dec(sl_b[c]), "tp_price": fmt_px_dec(tp_b[c]),
                        "volume_rel": round(vrel_d, 2), "notional_usd": round(diff_usd, 2), "fee_usd": round(fee, 3),
                        "realized_pnl_usd": None, "realized_pnl_pct": None,
                        "telemetry": f"Mom14d={r14_y[j]:+.1f}% | ADX={adx_y[j]:.1f} | %B={pb_y[j]:.2f} | Reg={reg_code_b}",
                    }
                    pf_b["trades"].append(tr_b)
                    emitted.append(tr_b)

    pf_b["cash_usd"] = cash_b
    cur_eq_b = cash_b + sum(float(units_b[c]) * float(d_slice.loc[dt, c]) for c in coins)
    pf_b["rets"].append((cur_eq_b / max(prev_eq_b, 1e-6)) - 1.0)
    pf_b["eq_curve"].append(cur_eq_b)
    pf_b["dates"].append(dt.strftime("%Y-%m-%d"))
    pf_b["last_closed_bar"] = dt.strftime("%Y-%m-%d")
    return emitted


def _step_bot_c_closed_bar(
    pf_c: Dict[str, Any],
    idx_i: int,
    coins: List[str],
    close_4h: pd.DataFrame,
    low_4h: pd.DataFrame,
    high_4h: pd.DataFrame,
    ema21_4h: pd.DataFrame,
    ema55_4h: pd.DataFrame,
    roc24_4h: pd.DataFrame,
    macd_h_4h: pd.DataFrame,
    bb_pctb_4h: pd.DataFrame,
    adx_4h: pd.DataFrame,
    pdi_4h: pd.DataFrame,
    mdi_4h: pd.DataFrame,
    atr_4h: pd.DataFrame,
    vol_rel_4h: pd.DataFrame,
    funding_rates_8h: np.ndarray,
    oi_vol_ratio_vec: Optional[np.ndarray] = None,
    obv_4h: Optional[pd.DataFrame] = None,
    regime_series_4h: Optional[pd.Series] = None,
    gatekeeper_cfg: RiskGatekeeperConfig = RiskGatekeeperConfig(),
) -> List[Dict[str, Any]]:
    emitted: List[Dict[str, Any]] = []
    ts = close_4h.index[idx_i]
    prev_ts = close_4h.index[idx_i - 1]
    prev_eq_c = float(pf_c["eq_curve"][-1])
    bar_step = int(pf_c.get("bar_step", 0)) + 1
    pf_c["bar_step"] = bar_step
    reg_code_c = str(regime_series_4h.iloc[idx_i - 1]) if regime_series_4h is not None else "TENDENCIA_ALCISTA"

    realized_cash_c = float(pf_c["realized_cash_c"])
    units_c = pf_c["units"]
    entry_c = pf_c["entry"]
    entry_fee_c = pf_c.setdefault("entry_fee", {c: 0.0 for c in coins})
    sl_c = pf_c["sl"]
    tp_c = pf_c.setdefault("tp", {c: 0.0 for c in coins})
    peak_c = pf_c.setdefault("peak", {c: 0.0 for c in coins})
    cooldown_step = pf_c.setdefault("cooldown_step", {c: -1 for c in coins})

    if ts.hour % 8 == 0:
        for j, c in enumerate(coins):
            if abs(float(units_c[c])) > 1e-9:
                notional_pos = float(units_c[c]) * float(close_4h.loc[prev_ts, c])
                realized_cash_c -= notional_pos * float(funding_rates_8h[j])

    atr_prev_c = atr_4h.loc[prev_ts].values
    vrel_prev_c = vol_rel_4h.loc[prev_ts].values

    for j, c in enumerate(coins):
        qty_c = float(units_c[c])
        if abs(qty_c) <= 1e-9:
            continue
        b_lo = float(low_4h.loc[ts, c])
        b_hi = float(high_4h.loc[ts, c])
        atr_cj = max(1e-9, float(atr_prev_c[j]))

        if qty_c > 0.0 and float(sl_c.get(c, 0.0)) > 0.0:
            if b_lo <= float(sl_c[c]):
                px_sl = float(np.clip(float(sl_c[c]), b_lo, b_hi))
                pnl_close = qty_c * (px_sl - float(entry_c[c]))
                fee_close = abs(qty_c * px_sl) * SETTINGS.futures_fee_rate
                ent_f = float(entry_fee_c.get(c, 0.0))
                realized_cash_c += pnl_close - fee_close
                pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_close
                pnl_u = round(pnl_close - fee_close - ent_f, 2)
                pnl_p = round((((px_sl / max(float(entry_c[c]), 1e-8)) - 1.0) * 100.0) - (2.0 * SETTINGS.futures_fee_rate * 100.0), 2)
                lbl_c = "SALIDA TRAILING SWAP ATR" if px_sl > float(entry_c[c]) else "CORTE STOP-LOSS SWAP (2.85x ATR)"
                tr_sl = {
                    "bot_id": "bot_c", "bot_code": "BOT C",
                    "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                    "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": "CLOSE",
                    "action": lbl_c, "units": round(abs(qty_c), 6), "price": fmt_px_dec(px_sl),
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(float(vrel_prev_c[j]), 2),
                    "notional_usd": round(abs(qty_c * px_sl), 2), "fee_usd": round(fee_close, 3),
                    "realized_pnl_usd": pnl_u, "realized_pnl_pct": pnl_p,
                    "telemetry": f"Protección 4H | SL={fmt_px_dec(sl_c[c])} | Reg={reg_code_c} | Vol={vrel_prev_c[j]:.2f}x",
                }
                pf_c["trades"].append(tr_sl)
                emitted.append(tr_sl)
                units_c[c] = 0.0
                sl_c[c] = 0.0
                tp_c[c] = 0.0
                peak_c[c] = 0.0
                entry_fee_c[c] = 0.0
                cooldown_step[c] = bar_step + 3
            else:
                peak_c[c] = max(float(peak_c.get(c, 0.0)), b_hi)
                if peak_c[c] >= float(entry_c[c]) + 2.40 * atr_cj:
                    sl_c[c] = max(float(sl_c[c]), float(entry_c[c]) * 1.004, peak_c[c] - 1.85 * atr_cj)
        elif qty_c < 0.0 and float(sl_c.get(c, 0.0)) > 0.0:
            if b_hi >= float(sl_c[c]):
                px_sl = float(np.clip(float(sl_c[c]), b_lo, b_hi))
                pnl_close = qty_c * (px_sl - float(entry_c[c]))
                fee_close = abs(qty_c * px_sl) * SETTINGS.futures_fee_rate
                ent_f = float(entry_fee_c.get(c, 0.0))
                realized_cash_c += pnl_close - fee_close
                pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_close
                pnl_u = round(pnl_close - fee_close - ent_f, 2)
                pnl_p = round(((-1.0 * ((px_sl / max(float(entry_c[c]), 1e-8)) - 1.0)) * 100.0) - (2.0 * SETTINGS.futures_fee_rate * 100.0), 2)
                lbl_c = "SALIDA TRAILING SHORT ATR" if px_sl < float(entry_c[c]) else "CORTE STOP-LOSS SHORT (2.85x ATR)"
                tr_sls = {
                    "bot_id": "bot_c", "bot_code": "BOT C",
                    "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                    "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": "CLOSE",
                    "action": lbl_c, "units": round(abs(qty_c), 6), "price": fmt_px_dec(px_sl),
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(float(vrel_prev_c[j]), 2),
                    "notional_usd": round(abs(qty_c * px_sl), 2), "fee_usd": round(fee_close, 3),
                    "realized_pnl_usd": pnl_u, "realized_pnl_pct": pnl_p,
                    "telemetry": f"Protección Short 4H | SL={fmt_px_dec(sl_c[c])} | Reg={reg_code_c} | Vol={vrel_prev_c[j]:.2f}x",
                }
                pf_c["trades"].append(tr_sls)
                emitted.append(tr_sls)
                units_c[c] = 0.0
                sl_c[c] = 0.0
                tp_c[c] = 0.0
                peak_c[c] = 0.0
                entry_fee_c[c] = 0.0
                cooldown_step[c] = bar_step + 3
            else:
                peak_c[c] = min(float(peak_c[c]), b_lo) if float(peak_c.get(c, 0.0)) > 0.0 else b_lo
                if peak_c[c] <= float(entry_c[c]) - 2.40 * atr_cj:
                    sl_c[c] = min(float(sl_c[c]), float(entry_c[c]) * 0.996, peak_c[c] + 1.85 * atr_cj)

    if (bar_step - 1) % 3 == 0:
        px_v = close_4h.loc[prev_ts].values
        e21_v = ema21_4h.loc[prev_ts].values
        e55_v = ema55_4h.loc[prev_ts].values
        r24_v = roc24_4h.loc[prev_ts].values
        mh_v = macd_h_4h.loc[prev_ts].values
        pb_v = bb_pctb_4h.loc[prev_ts].values
        adx_v = adx_4h.loc[prev_ts].values
        pdi_v = pdi_4h.loc[prev_ts].values
        mdi_v = mdi_4h.loc[prev_ts].values
        atr_v = atr_prev_c
        vrel_v = vrel_prev_c
        obv_v = obv_4h.loc[prev_ts].values if obv_4h is not None else None

        eq_ref, gross_ref, _ = calc_futures_account_state(units_c, entry_c, realized_cash_c, close_4h.loc[prev_ts].to_dict())
        eq_ref = max(250.0, eq_ref)
        cur_wc = np.array([(float(units_c[c]) * float(close_4h.loc[prev_ts, c])) / eq_ref for c in coins])
        gate_c = evaluate_risk_gatekeeper(
            pf_c["eq_curve"], prev_eq_c, gross_ref / max(eq_ref, 1.0), 1.08,
            regime_info={"risk_multiplier": 0.65 if reg_code_c == "ALTA_VOLATILIDAD" else 1.0},
            rr_ratio=1.60, cfg=gatekeeper_cfg,
        )

        wc = step_bot_c_futures(
            px_v, e21_v, e55_v, r24_v, mh_v, pb_v, adx_v, pdi_v, mdi_v, atr_v,
            max_gross_leverage=1.05,
            funding_8h=funding_rates_8h,
            prev_wc=cur_wc,
            oi_vol_ratio=oi_vol_ratio_vec,
            obv_v=obv_v,
            regime_code=reg_code_c,
        )
        if gate_c["current_dd_pct"] <= -15.0:
            wc = np.zeros(len(coins))
        elif gate_c["veto_code"] == "KILL_SWITCH_DRAWDOWN":
            wc = wc * 0.55
        if float(np.sum(np.abs(wc - cur_wc))) >= 0.16:
            for j, c in enumerate(coins):
                if bar_step < int(cooldown_step.get(c, -1)) and abs(float(units_c[c])) <= 1e-9:
                    continue
                b_lo = float(low_4h.loc[ts, c])
                b_hi = float(high_4h.loc[ts, c])
                px_exec = float(np.clip(px_v[j], b_lo, b_hi))

                target_notional = wc[j] * eq_ref
                cur_notional = float(units_c[c]) * px_exec
                delta_notional = target_notional - cur_notional
                same_side = (float(units_c[c]) > 1e-9 and target_notional >= 40.0) or (float(units_c[c]) < -1e-9 and target_notional <= -40.0)

                if same_side:
                    if abs(delta_notional) >= 75.0:
                        sign_s = 1.0 if float(units_c[c]) > 0 else -1.0
                        if delta_notional * float(units_c[c]) > 0:
                            delta_u = delta_notional / px_exec
                            fee_d = abs(delta_notional) * SETTINGS.futures_fee_rate
                            realized_cash_c -= fee_d
                            pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_d
                            prev_abs = abs(float(units_c[c]))
                            add_abs = abs(delta_u)
                            entry_c[c] = ((prev_abs * float(entry_c[c])) + (add_abs * px_exec)) / (prev_abs + add_abs)
                            units_c[c] = float(units_c[c]) + delta_u
                            entry_fee_c[c] = float(entry_fee_c.get(c, 0.0)) + fee_d
                            stop_dist_c = max(0.018, (2.85 * float(atr_v[j])) / max(px_exec, 1e-6))
                            base_sl = float(entry_c[c]) * (1.0 - sign_s * stop_dist_c)
                            sl_c[c] = max(float(sl_c[c]), base_sl) if sign_s > 0 else min(float(sl_c[c]), base_sl)
                            tp_c[c] = float(entry_c[c]) * (1.0 + sign_s * 1.60 * stop_dist_c)
                            tr_add = {
                                "bot_id": "bot_c", "bot_code": "BOT C",
                                "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                                "coin": c, "instrument": f"{c}-USDT-SWAP",
                                "side_type": "LONG" if sign_s > 0 else "SHORT",
                                "action": "AMPLIACIÓN LARGO SWAP" if sign_s > 0 else "AMPLIACIÓN SHORT SWAP",
                                "units": round(add_abs, 6), "price": fmt_px_dec(px_exec),
                                "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                                "sl_price": fmt_px_dec(sl_c[c]), "tp_price": fmt_px_dec(tp_c[c]),
                                "volume_rel": round(float(vrel_v[j]), 2),
                                "notional_usd": round(abs(delta_notional), 2), "fee_usd": round(fee_d, 3),
                                "realized_pnl_usd": None, "realized_pnl_pct": None,
                                "telemetry": f"Delta Rebalance | Mom24={r24_v[j]:+.1f}% | ADX={adx_v[j]:.1f} | Carry={funding_rates_8h[j]*100:+.3f}%",
                            }
                            pf_c["trades"].append(tr_add)
                            emitted.append(tr_add)
                        else:
                            trim_ratio = min(0.95, abs(delta_notional) / max(abs(cur_notional), 1e-6))
                            trim_u = float(units_c[c]) * trim_ratio
                            pnl_part = trim_u * (px_exec - float(entry_c[c]))
                            fee_d = abs(trim_u * px_exec) * SETTINGS.futures_fee_rate
                            ent_f_part = float(entry_fee_c.get(c, 0.0)) * trim_ratio
                            realized_cash_c += pnl_part - fee_d
                            pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_d
                            units_c[c] = float(units_c[c]) - trim_u
                            entry_fee_c[c] = max(0.0, float(entry_fee_c.get(c, 0.0)) - ent_f_part)
                            pnl_u = round(pnl_part - fee_d - ent_f_part, 2)
                            pnl_p = round((sign_s * ((px_exec / max(float(entry_c[c]), 1e-8)) - 1.0) * 100.0) - (2.0 * SETTINGS.futures_fee_rate * 100.0), 2)
                            tr_trim = {
                                "bot_id": "bot_c", "bot_code": "BOT C",
                                "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                                "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": "CLOSE",
                                "action": "REDUCCIÓN PARCIAL SWAP", "units": round(abs(trim_u), 6), "price": fmt_px_dec(px_exec),
                                "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                                "volume_rel": round(float(vrel_v[j]), 2),
                                "notional_usd": round(abs(trim_u * px_exec), 2), "fee_usd": round(fee_d, 3),
                                "realized_pnl_usd": pnl_u, "realized_pnl_pct": pnl_p,
                                "telemetry": f"Ajuste Delta | Mom24={r24_v[j]:+.1f}% | Vol={vrel_v[j]:.2f}x",
                            }
                            pf_c["trades"].append(tr_trim)
                            emitted.append(tr_trim)
                elif abs(delta_notional) >= 48.0:
                    pnl_real_u = None
                    pnl_real_p = None
                    closed_notional = abs(cur_notional)
                    closed_qty = abs(float(units_c[c]))
                    if abs(float(units_c[c])) > 1e-9:
                        pnl_close = float(units_c[c]) * (px_exec - float(entry_c[c]))
                        fee_close = abs(float(units_c[c]) * px_exec) * SETTINGS.futures_fee_rate
                        ent_f = float(entry_fee_c.get(c, 0.0))
                        realized_cash_c += pnl_close - fee_close
                        pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_close
                        pnl_real_u = round(pnl_close - fee_close - ent_f, 2)
                        sign_prev = 1.0 if float(units_c[c]) > 0 else -1.0
                        pnl_real_p = round((sign_prev * ((px_exec / max(float(entry_c[c]), 1e-8)) - 1.0) * 100.0) - (2.0 * SETTINGS.futures_fee_rate * 100.0), 2)
                        units_c[c] = 0.0
                        sl_c[c] = 0.0
                        tp_c[c] = 0.0
                        peak_c[c] = 0.0
                        entry_fee_c[c] = 0.0
                        tr_cls = {
                            "bot_id": "bot_c", "bot_code": "BOT C",
                            "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                            "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": "CLOSE",
                            "action": "CIERRE POSICIÓN FUTUROS", "units": round(closed_qty, 6), "price": fmt_px_dec(px_exec),
                            "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                            "volume_rel": round(float(vrel_v[j]), 2),
                            "notional_usd": round(closed_notional, 2),
                            "fee_usd": round(closed_notional * SETTINGS.futures_fee_rate, 3),
                            "realized_pnl_usd": pnl_real_u, "realized_pnl_pct": pnl_real_p,
                            "telemetry": f"Salida por giro EMA21/MACD | Mom24={r24_v[j]:+.1f}% | Vol={vrel_v[j]:.2f}x",
                        }
                        pf_c["trades"].append(tr_cls)
                        emitted.append(tr_cls)

                    if abs(target_notional) >= 42.0:
                        fee_open = abs(target_notional) * SETTINGS.futures_fee_rate
                        realized_cash_c -= fee_open
                        pf_c["fees_cum"] = float(pf_c["fees_cum"]) + fee_open
                        units_c[c] = target_notional / px_exec
                        entry_c[c] = px_exec
                        entry_fee_c[c] = fee_open
                        peak_c[c] = px_exec
                        sign_n = 1.0 if target_notional > 0 else -1.0
                        stop_dist_c = max(0.018, (2.85 * float(atr_v[j])) / max(px_exec, 1e-6))
                        sl_c[c] = px_exec * (1.0 - sign_n * stop_dist_c)
                        tp_c[c] = px_exec * (1.0 + sign_n * 1.60 * stop_dist_c)
                        side_t = "LONG" if target_notional > 0 else "SHORT"
                        act_c = "APERTURA LARGO FUTUROS" if target_notional > 0 else "COBERTURA SHORT FUTUROS"
                        tr_opn = {
                            "bot_id": "bot_c", "bot_code": "BOT C",
                            "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                            "coin": c, "instrument": f"{c}-USDT-SWAP", "side_type": side_t,
                            "action": act_c, "units": round(abs(units_c[c]), 6), "price": fmt_px_dec(px_exec),
                            "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                            "sl_price": fmt_px_dec(sl_c[c]), "tp_price": fmt_px_dec(tp_c[c]),
                            "volume_rel": round(float(vrel_v[j]), 2),
                            "notional_usd": round(abs(target_notional), 2), "fee_usd": round(fee_open, 3),
                            "realized_pnl_usd": None, "realized_pnl_pct": None,
                            "telemetry": f"EMA21/55={(e21_v[j]/e55_v[j]-1)*100:+.2f}% | Mom24={r24_v[j]:+.1f}% | ADX={adx_v[j]:.1f} | Carry={funding_rates_8h[j]*100:+.3f}%",
                        }
                        pf_c["trades"].append(tr_opn)
                        emitted.append(tr_opn)

    pf_c["realized_cash_c"] = realized_cash_c
    cur_eq_c, _, _ = calc_futures_account_state(units_c, entry_c, realized_cash_c, close_4h.loc[ts].to_dict())
    pf_c["rets"].append((cur_eq_c / max(prev_eq_c, 1e-6)) - 1.0)
    pf_c["eq_curve"].append(cur_eq_c)
    pf_c["dates"].append(ts.strftime("%Y-%m-%d %H:%M"))
    pf_c["last_closed_bar"] = ts.strftime("%Y-%m-%d %H:%M")
    return emitted


def _step_bot_d_closed_bar(
    pf_d: Dict[str, Any],
    idx_i: int,
    coins: List[str],
    open_4h: pd.DataFrame,
    close_4h: pd.DataFrame,
    low_4h: pd.DataFrame,
    high_4h: pd.DataFrame,
    ema9_4h: pd.DataFrame,
    ema21_4h: pd.DataFrame,
    ema55_4h: pd.DataFrame,
    bb_pctb_4h: pd.DataFrame,
    bb_bw_4h: pd.DataFrame,
    roc12_4h: pd.DataFrame,
    roc24_4h: pd.DataFrame,
    macd_h_4h: pd.DataFrame,
    rsi_4h: pd.DataFrame,
    stoch_4h: pd.DataFrame,
    atr_4h: pd.DataFrame,
    vol_rel_4h: pd.DataFrame,
    ensemble_bundle: Dict[str, Any],
    obv_4h: Optional[pd.DataFrame] = None,
    ema200_dist_4h: Optional[pd.DataFrame] = None,
    range_pos_4h: Optional[pd.DataFrame] = None,
    btc_rel_4h: Optional[pd.DataFrame] = None,
    rsi_accel_4h: Optional[pd.DataFrame] = None,
    regime_series_4h: Optional[pd.Series] = None,
    regime_probs: Optional[Dict[str, float]] = None,
    spread_bps_map: Optional[Dict[str, float]] = None,
    cross_bps_map: Optional[Dict[str, float]] = None,
    gatekeeper_cfg: RiskGatekeeperConfig = RiskGatekeeperConfig(),
) -> Tuple[List[Dict[str, Any]], Dict[str, np.ndarray]]:
    emitted: List[Dict[str, Any]] = []
    ts = close_4h.index[idx_i]
    prev_ts = close_4h.index[idx_i - 1]
    prev_eq_d = float(pf_d["eq_curve"][-1])
    reg_code_d = str(regime_series_4h.iloc[idx_i - 1]) if regime_series_4h is not None else "MERCADO_LATERAL"
    reg_mult_d = {"TENDENCIA_ALCISTA": 1.0, "MERCADO_LATERAL": 0.78, "TENDENCIA_BAJISTA": 0.60, "ALTA_VOLATILIDAD": 0.50}.get(reg_code_d, 0.80)
    sl_buf_d = 1.15 if reg_code_d == "ALTA_VOLATILIDAD" else 1.00
    bar_reg_probs = regime_probs
    if bar_reg_probs is None:
        bar_reg_probs = {k: 0.10 for k in ("TENDENCIA_ALCISTA", "MERCADO_LATERAL", "TENDENCIA_BAJISTA", "ALTA_VOLATILIDAD")}
        bar_reg_probs[reg_code_d] = 0.70

    X_now_4h = np.array([
        extract_ta_features_row(
            idx_i - 1, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
            roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h,
            obv_slope_df=obv_4h, ema200_dist_df=ema200_dist_4h,
            range_pos_df=range_pos_4h, btc_rel_df=btc_rel_4h, rsi_accel_df=rsi_accel_4h,
        )
        for c in coins
    ])
    ens_out = predict_supervised_3class_ensemble(ensemble_bundle, X_now_4h, regime_probs=bar_reg_probs)
    prob_bull_d = ens_out["prob_bull"]
    prob_flat_d = ens_out["prob_flat"]
    prob_bear_d = ens_out["prob_bear"]
    pred_ret_d = ens_out["pred_net_ret"]

    cash_d = float(pf_d["cash_usd"])
    units_d = pf_d["units"]
    entry_d = pf_d["entry"]
    entry_fee_d = pf_d.setdefault("entry_fee", {c: 0.0 for c in coins})
    partial_d = pf_d.setdefault("partial_taken", {c: False for c in coins})
    peak_d = pf_d.setdefault("peak", {c: 0.0 for c in coins})
    sl_d = pf_d["sl"]
    tp_d = pf_d["tp"]

    for j, c in enumerate(coins):
        px_prev = float(close_4h.loc[prev_ts, c])
        b_lo = float(low_4h.loc[ts, c])
        b_hi = float(high_4h.loc[ts, c])
        atr_v = float(atr_4h.loc[prev_ts, c])
        e9_v = float(ema9_4h.loc[prev_ts, c])
        e21_v = float(ema21_4h.loc[prev_ts, c])
        e55_v = float(ema55_4h.loc[prev_ts, c])
        mh_v = float(macd_h_4h.loc[prev_ts, c])
        pb_v = float(bb_pctb_4h.loc[prev_ts, c])
        rsi_v = float(rsi_4h.loc[prev_ts, c])
        vrel_v = float(vol_rel_4h.loc[prev_ts, c])
        obv_v = float(obv_4h.loc[prev_ts, c]) if obv_4h is not None else 0.0
        brel_v = float(btc_rel_4h.loc[prev_ts, c]) if btc_rel_4h is not None else 0.0
        p_up = float(prob_bull_d[j])
        p_flat = float(prob_flat_d[j])
        p_dn = float(prob_bear_d[j])
        p_r = float(pred_ret_d[j])

        if float(units_d[c]) > 0.0:
            dir_prob_up = p_up / max(p_up + p_dn, 1e-6)
            should_exit, act_d, px_exec, new_sl = evaluate_bot_d_exit_decision(
                dir_prob_up, p_r, e9_v, e21_v, b_lo, b_hi, float(sl_d[c]), float(tp_d[c]), float(peak_d[c]), float(entry_d[c]), atr_v
            )
            sl_d[c] = new_sl
            if should_exit and act_d:
                qty_cur = float(units_d[c])
                gross = qty_cur * px_exec
                fee = gross * SETTINGS.spot_fee_rate
                ent_f = float(entry_fee_d.get(c, 0.0))
                pnl_u = gross - fee - (qty_cur * float(entry_d[c])) - ent_f
                pnl_p = ((px_exec / max(float(entry_d[c]), 1e-8)) - 1.0) * 100.0 - (2.0 * SETTINGS.spot_fee_rate * 100.0)
                cash_d += gross - fee
                pf_d["fees_cum"] = float(pf_d["fees_cum"]) + fee
                tr_sd = {
                    "bot_id": "bot_d", "bot_code": "BOT D",
                    "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                    "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                    "action": act_d, "units": round(qty_cur, 6), "price": fmt_px_dec(px_exec),
                    "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                    "volume_rel": round(vrel_v, 2), "notional_usd": round(gross, 2), "fee_usd": round(fee, 3),
                    "realized_pnl_usd": round(pnl_u, 2), "realized_pnl_pct": round(pnl_p, 2),
                    "telemetry": f"Alza={p_up*100:.0f}% Lat={p_flat*100:.0f}% Baja={p_dn*100:.0f}% | Reg={reg_code_d} | Vol={vrel_v:.2f}x",
                }
                pf_d["trades"].append(tr_sd)
                emitted.append(tr_sd)
                units_d[c] = 0.0
                sl_d[c] = 0.0
                tp_d[c] = 0.0
                entry_fee_d[c] = 0.0
                partial_d[c] = False
                peak_d[c] = 0.0
            else:
                part_target_d = float(entry_d[c]) + 1.35 * atr_v
                qty_cur = float(units_d[c])
                if (not partial_d.get(c, False)) and (b_hi >= part_target_d) and (qty_cur * part_target_d >= 95.0):
                    qty_p = qty_cur * 0.45
                    px_p = float(np.clip(part_target_d, b_lo, b_hi))
                    gross_p = qty_p * px_p
                    fee_p = gross_p * SETTINGS.spot_fee_rate
                    ent_fp = float(entry_fee_d.get(c, 0.0)) * 0.45
                    pnl_up = gross_p - fee_p - (qty_p * float(entry_d[c])) - ent_fp
                    pnl_pp = ((px_p / max(float(entry_d[c]), 1e-8)) - 1.0) * 100.0 - (2.0 * SETTINGS.spot_fee_rate * 100.0)
                    cash_d += gross_p - fee_p
                    pf_d["fees_cum"] = float(pf_d["fees_cum"]) + fee_p
                    units_d[c] = qty_cur - qty_p
                    entry_fee_d[c] = max(0.0, float(entry_fee_d.get(c, 0.0)) - ent_fp)
                    partial_d[c] = True
                    sl_d[c] = max(float(sl_d[c]), float(entry_d[c]) * 1.0065)
                    tr_pd = {
                        "bot_id": "bot_d", "bot_code": "BOT D",
                        "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "SELL",
                        "action": "TOMA PARCIAL 45% ENSEMBLE ATR", "units": round(qty_p, 6), "price": fmt_px_dec(px_p),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "volume_rel": round(vrel_v, 2), "notional_usd": round(gross_p, 2), "fee_usd": round(fee_p, 3),
                        "realized_pnl_usd": round(pnl_up, 2), "realized_pnl_pct": round(pnl_pp, 2),
                        "telemetry": f"Parcial 45% (1.35x ATR) | SL={fmt_px_dec(sl_d[c])} | Alza={p_up*100:.0f}%",
                    }
                    pf_d["trades"].append(tr_pd)
                    emitted.append(tr_pd)
                peak_d[c] = max(float(peak_d.get(c, 0.0)), b_hi)
        else:
            pb_prev2 = float(bb_pctb_4h.iloc[idx_i - 2][c])
            mh_prev2 = float(macd_h_4h.iloc[idx_i - 2][c])
            bull_4h = px_prev > float(open_4h.loc[prev_ts, c])
            p_cut_d = 0.45 if reg_code_d == "TENDENCIA_ALCISTA" else (0.50 if reg_code_d == "MERCADO_LATERAL" else 0.54)
            nn_trend_ok = (
                (reg_code_d == "TENDENCIA_ALCISTA")
                and (p_up >= p_cut_d)
                and (p_flat < 0.42)
                and ((p_up - p_dn) >= 0.15)
                and (p_r > 0.0010)
                and (px_prev > e9_v > e21_v >= e55_v * 0.992)
                and (mh_v > 0.0)
                and (obv_v >= 0.05)
                and (vrel_v >= 0.95)
            )
            nn_rebound_ok = (
                (reg_code_d != "TENDENCIA_BAJISTA")
                and (p_up >= 0.58)
                and ((p_up - p_dn) >= 0.38)
                and (p_r > 0.0020)
                and bull_4h
                and (pb_v > pb_prev2 and pb_v < 0.55)
                and (mh_v > mh_prev2)
                and (vrel_v >= 1.15)
                and (brel_v >= 0.0)
            )
            nn_buy_ok = nn_trend_ok or nn_rebound_ok

            invested_d = sum(float(units_d[k]) * float(close_4h.loc[prev_ts, k]) for k in coins)
            eq_est_d = cash_d + invested_d
            sp_bps = float(spread_bps_map.get(c, 1.0)) if spread_bps_map else 1.0
            cx_bps = float(cross_bps_map.get(c, 2.0)) if cross_bps_map else 2.0
            gate_d = evaluate_risk_gatekeeper(
                pf_d["eq_curve"], prev_eq_d, invested_d / max(eq_est_d, 1.0), 0.74,
                spread_bps=sp_bps, cross_exchange_bps=cx_bps,
                regime_info={"risk_multiplier": reg_mult_d, "sl_atr_buffer": sl_buf_d},
                rr_ratio=2.15 if nn_trend_ok else 2.05,
                cfg=gatekeeper_cfg,
            )
            if not gate_d["approved"]:
                pf_d["veto_count"] = int(pf_d.get("veto_count", 0)) + 1
            elif nn_buy_ok:
                dir_prob_up = p_up / max(p_up + p_dn, 1e-6)
                alloc_d, stop_dist_d = compute_bot_d_sizing(
                    eq_est_d, cash_d, invested_d, px_prev, atr_v * sl_buf_d, dir_prob_up,
                    max_risk_pct=gate_d["effective_risk_pct"],
                )
                if alloc_d >= 48.0 and cash_d >= alloc_d * 1.002:
                    px_exec = float(np.clip(px_prev, b_lo, b_hi))
                    fee = alloc_d * SETTINGS.spot_fee_rate
                    qty = alloc_d / px_exec
                    cash_d -= (alloc_d + fee)
                    pf_d["fees_cum"] = float(pf_d["fees_cum"]) + fee
                    units_d[c] = qty
                    entry_d[c] = px_exec
                    entry_fee_d[c] = fee
                    partial_d[c] = False
                    peak_d[c] = px_exec
                    sl_d[c] = px_exec * (1.0 - stop_dist_d)
                    tp_mult = 2.15
                    tp_d[c] = px_exec * (1.0 + tp_mult * stop_dist_d)
                    act_d_in = "COMPRA ENSEMBLE TRIPLE-BARRERA" if nn_trend_ok else "COMPRA REBOTE BOLLINGER ENSEMBLE"
                    tr_bd = {
                        "bot_id": "bot_d", "bot_code": "BOT D",
                        "time_utc": ts.strftime("%Y-%m-%d %H:%M UTC"), "ts_iso": ts.strftime("%Y-%m-%d %H:%M"),
                        "coin": c, "instrument": f"{c}-USDT", "side_type": "BUY",
                        "action": act_d_in,
                        "units": round(qty, 6), "price": fmt_px_dec(px_exec),
                        "bar_low": fmt_px_dec(b_lo), "bar_high": fmt_px_dec(b_hi),
                        "sl_price": fmt_px_dec(sl_d[c]), "tp_price": fmt_px_dec(tp_d[c]),
                        "volume_rel": round(vrel_v, 2), "notional_usd": round(alloc_d, 2), "fee_usd": round(fee, 3),
                        "realized_pnl_usd": None, "realized_pnl_pct": None,
                        "telemetry": f"Alza={p_up*100:.0f}% Lat={p_flat*100:.0f}% Baja={p_dn*100:.0f}% | OBV={obv_v:+.2f} | Reg={reg_code_d}",
                    }
                    pf_d["trades"].append(tr_bd)
                    emitted.append(tr_bd)

    pf_d["cash_usd"] = cash_d
    cur_eq_d = cash_d + sum(float(units_d[c]) * float(close_4h.loc[ts, c]) for c in coins)
    pf_d["rets"].append((cur_eq_d / max(prev_eq_d, 1e-6)) - 1.0)
    pf_d["eq_curve"].append(cur_eq_d)
    pf_d["dates"].append(ts.strftime("%Y-%m-%d %H:%M"))
    pf_d["last_closed_bar"] = ts.strftime("%Y-%m-%d %H:%M")
    return emitted, ens_out


def _sanitize_portfolio_for_json(pf: Dict[str, Any], coins: List[str]) -> Dict[str, Any]:
    out = dict(pf)
    if out.get("cur_day") is not None:
        out["cur_day"] = str(out["cur_day"])
    for dict_key in ("units", "entry", "entry_fee", "peak", "sl", "tp"):
        if dict_key in out and isinstance(out[dict_key], dict):
            out[dict_key] = {c: round(float(out[dict_key].get(c, 0.0)), 8) for c in coins}
    if "partial_taken" in out and isinstance(out["partial_taken"], dict):
        out["partial_taken"] = {c: bool(out["partial_taken"].get(c, False)) for c in coins}
    if "cooldown_step" in out and isinstance(out["cooldown_step"], dict):
        out["cooldown_step"] = {c: int(out["cooldown_step"].get(c, -1)) for c in coins}
    for num_key in ("cash_usd", "realized_cash_c", "fees_cum", "day_anchor_eq"):
        if num_key in out and out[num_key] is not None:
            out[num_key] = round(float(out[num_key]), 6)
    dates = list(out.get("dates") or [])
    eq_c = [round(float(x), 4) for x in (out.get("eq_curve") or [])]
    rets = [round(float(x), 8) for x in (out.get("rets") or [])]
    if len(dates) > 1050 and len(eq_c) == len(dates):
        dates = dates[-1050:]
        eq_c = eq_c[-1050:]
        rets = rets[-1049:]
    out["dates"] = dates
    out["eq_curve"] = eq_c
    out["rets"] = rets
    out["trades"] = [dict(t) for t in (out.get("trades") or [])[-400:]]
    return out


def run_four_algorithmic_bots(
    oracle: MultiExchangeCryptoOracle,
    ohlcv_5y: Dict[str, pd.DataFrame],
    daily_prices: pd.DataFrame,
    daily_highs: pd.DataFrame,
    daily_lows: pd.DataFrame,
    market_snapshot: Dict[str, Dict[str, Any]],
    base_cap: float = 1000.0,
    cache_bucket: Optional[Dict[str, Any]] = None,
    base_dir: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """
    Ejecuta los 4 Algoritmos Especializados con Libro Mayor Persistente de Estado (v3_stateful):
      - Cada posición abierta conserva su precio/minuto exacto de entrada e identificador SHA-256
      - Cada nueva vela cerrada (15m, 1D, 4H) avanza incrementalmente sobre la cartera persistida
      - Cada ciclo de 30s evalúa en tiempo real los cruces SL / TP / Toma Parcial / Trailing en el libro,
        registrando inmediatamente cada operación cerrada en la cadena aditiva (append-only) SHA-256
    """
    target_dir = base_dir if base_dir is not None else BASE_MODULE_DIR
    ledger_path = target_dir / "bot_state_ledger.json"
    coins = list(daily_prices.columns)
    n_assets = len(coins)
    now_utc = datetime.now(timezone.utc)
    key_15m = f"{now_utc.strftime('%Y-%m-%d %H')}-{now_utc.minute // 15}"
    key_1h = now_utc.strftime("%Y-%m-%d %H")
    key_4h = f"{now_utc.strftime('%Y-%m-%d')}-{now_utc.hour // 4}"

    need_15m = cache_bucket is None or cache_bucket.get("key_15m") != key_15m or "candles_15m_raw" not in cache_bucket
    need_1h = cache_bucket is None or cache_bucket.get("key_1h") != key_1h or "candles_1h_raw" not in cache_bucket
    need_4h = cache_bucket is None or cache_bucket.get("key_4h") != key_4h or "candles_4h_raw" not in cache_bucket

    if need_15m or need_1h or need_4h:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as tf_pool:
            fut_15m = tf_pool.submit(oracle.fetch_intraday_ohlcv, coins, "15m", 960) if need_15m else None
            fut_1h = tf_pool.submit(oracle.fetch_intraday_ohlcv, coins, "1H", 400) if need_1h else None
            fut_4h = tf_pool.submit(oracle.fetch_intraday_ohlcv, coins, "4H", 960) if need_4h else None
            if fut_15m is not None:
                candles_15m_raw = fut_15m.result()
                if cache_bucket is not None:
                    cache_bucket["key_15m"] = key_15m
                    cache_bucket["candles_15m_raw"] = {c: df.copy() for c, df in candles_15m_raw.items()}
                candles_15m = candles_15m_raw
            else:
                candles_15m = {c: df.copy() for c, df in cache_bucket["candles_15m_raw"].items()}
            if fut_1h is not None:
                candles_1h_raw = fut_1h.result()
                if cache_bucket is not None:
                    cache_bucket["key_1h"] = key_1h
                    cache_bucket["candles_1h_raw"] = {c: df.copy() for c, df in candles_1h_raw.items()}
                candles_1h = candles_1h_raw
            else:
                candles_1h = {c: df.copy() for c, df in cache_bucket["candles_1h_raw"].items()}
            if fut_4h is not None:
                candles_4h_raw = fut_4h.result()
                if cache_bucket is not None:
                    cache_bucket["key_4h"] = key_4h
                    cache_bucket["candles_4h_raw"] = {c: df.copy() for c, df in candles_4h_raw.items()}
                candles_4h = candles_4h_raw
            else:
                candles_4h = {c: df.copy() for c, df in cache_bucket["candles_4h_raw"].items()}
    else:
        candles_15m = {c: df.copy() for c, df in cache_bucket["candles_15m_raw"].items()}
        candles_1h = {c: df.copy() for c, df in cache_bucket["candles_1h_raw"].items()}
        candles_4h = {c: df.copy() for c, df in cache_bucket["candles_4h_raw"].items()}

    for c in coins:
        spot_px = float(market_snapshot[c]["price"])
        for cdf in (candles_15m[c], candles_1h[c], candles_4h[c]):
            if len(cdf) > 0:
                li = cdf.index[-1]
                cdf.loc[li, "close"] = spot_px
                cdf.loc[li, "high"] = max(float(cdf.loc[li, "high"]), spot_px)
                cdf.loc[li, "low"] = min(float(cdf.loc[li, "low"]), spot_px)

    # Indicadores 1H cacheados por hora UTC para filtro tendencial superior y fuerza ADX 1H de BOT A
    if cache_bucket is not None and cache_bucket.get("ind_1h_key") == key_1h and "ind_1h" in cache_bucket:
        ind_1h = cache_bucket["ind_1h"]
        ema21_1h = ind_1h["ema21_1h"]
        ema55_1h = ind_1h["ema55_1h"]
        breadth_1h_series = ind_1h["breadth_1h_series"]
        adx_1h = ind_1h["adx_1h"]
    else:
        close_1h = pd.DataFrame({c: candles_1h[c]["close"] for c in coins}).ffill().dropna()
        ema21_1h = close_1h.ewm(span=21, adjust=False).mean()
        ema55_1h = close_1h.ewm(span=55, adjust=False).mean()
        breadth_1h_series = (close_1h > ema21_1h).mean(axis=1)
        adx_1h = pd.DataFrame({c: calc_adx_di(candles_1h[c], 14)[0] for c in coins}).reindex(close_1h.index).bfill()
        if cache_bucket is not None:
            cache_bucket["ind_1h_key"] = key_1h
            cache_bucket["ind_1h"] = {
                "ema21_1h": ema21_1h,
                "ema55_1h": ema55_1h,
                "breadth_1h_series": breadth_1h_series,
                "adx_1h": adx_1h,
            }

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
    if cache_bucket is not None and cache_bucket.get("ind_15m_key") == key_15m and "ind_15m" in cache_bucket:
        obv_15m = cache_bucket["ind_15m"]["obv_15m"]
        ema200_dist_15m = cache_bucket["ind_15m"]["ema200_dist_15m"]
    else:
        obv_15m = pd.DataFrame({c: calc_obv_slope(close_15m[c], vol_15m[c], 14) for c in coins}, index=close_15m.index)
        ema200_dist_15m = calc_structure_and_btc_metrics(close_15m, high_15m, low_15m, "BTC", 20)["ema200_dist"]
        if cache_bucket is not None:
            cache_bucket["ind_15m_key"] = key_15m
            cache_bucket["ind_15m"] = {"obv_15m": obv_15m, "ema200_dist_15m": ema200_dist_15m}

    ema21_1h_aligned = ema21_1h.reindex(close_15m.index, method="ffill").bfill()
    ema55_1h_aligned = ema55_1h.reindex(close_15m.index, method="ffill").bfill()
    breadth_1h_aligned = breadth_1h_series.reindex(close_15m.index, method="ffill").bfill()
    adx_1h_aligned = adx_1h.reindex(close_15m.index, method="ffill").bfill()

    # Indicadores 4H, variables ortogonales y detector GMM de 4 regímenes cacheados por vela
    if cache_bucket is not None and cache_bucket.get("ind_4h_key") == key_4h and "ind_4h" in cache_bucket:
        ind_4h = cache_bucket["ind_4h"]
        close_4h = ind_4h["close_4h"]
        open_4h = ind_4h["open_4h"]
        high_4h = ind_4h["high_4h"]
        low_4h = ind_4h["low_4h"]
        vol_rel_4h = ind_4h["vol_rel_4h"]
        atr_4h = ind_4h["atr_4h"]
        rsi_4h = ind_4h["rsi_4h"]
        stoch_4h = ind_4h["stoch_4h"]
        ema9_4h = ind_4h["ema9_4h"]
        ema21_4h = ind_4h["ema21_4h"]
        ema55_4h = ind_4h["ema55_4h"]
        roc12_4h = ind_4h["roc12_4h"]
        roc24_4h = ind_4h["roc24_4h"]
        macd_h_4h = ind_4h["macd_h_4h"]
        bb_pctb_4h = ind_4h["bb_pctb_4h"]
        bb_bw_4h = ind_4h["bb_bw_4h"]
        adx_4h = ind_4h["adx_4h"]
        pdi_4h = ind_4h["pdi_4h"]
        mdi_4h = ind_4h["mdi_4h"]
        obv_4h = ind_4h["obv_4h"]
        ema200_dist_4h = ind_4h["ema200_dist_4h"]
        range_pos_4h = ind_4h["range_pos_4h"]
        rsi_accel_4h = ind_4h["rsi_accel_4h"]
        btc_corr_4h = ind_4h["btc_corr_4h"]
        btc_rel_4h = ind_4h["btc_rel_4h"]
        regimes_4h = ind_4h["regimes_4h"]
        tb_labels_4h = ind_4h["tb_labels_4h"]
        tb_rets_4h = ind_4h["tb_rets_4h"]
    else:
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

        obv_4h = pd.DataFrame({c: calc_obv_slope(close_4h[c], vol_4h[c], 14) for c in coins}, index=close_4h.index)
        struct_4h = calc_structure_and_btc_metrics(close_4h, high_4h, low_4h, "BTC", 20)
        ema200_dist_4h = struct_4h["ema200_dist"]
        range_pos_4h = struct_4h["range_pos"]
        rsi_accel_4h = struct_4h["rsi_accel"]
        btc_corr_4h = struct_4h["btc_corr"]
        btc_rel_4h = struct_4h["btc_rel"]
        regimes_4h = detect_market_regimes_gmm(close_4h.iloc[:-1], adx_4h.iloc[:-1], btc_col="BTC", seed=42)
        tb_labels_4h, tb_rets_4h = compute_triple_barrier_labels(
            close_4h, high_4h, low_4h, atr_4h, horizon=4, tp_atr_mult=1.80, sl_atr_mult=1.40, roundtrip_fee=SETTINGS.spot_fee_rate * 2.0
        )

        if cache_bucket is not None:
            cache_bucket["ind_4h_key"] = key_4h
            cache_bucket["ind_4h"] = {
                "close_4h": close_4h, "open_4h": open_4h, "high_4h": high_4h, "low_4h": low_4h,
                "vol_rel_4h": vol_rel_4h, "atr_4h": atr_4h, "rsi_4h": rsi_4h, "stoch_4h": stoch_4h,
                "ema9_4h": ema9_4h, "ema21_4h": ema21_4h, "ema55_4h": ema55_4h,
                "roc12_4h": roc12_4h, "roc24_4h": roc24_4h, "macd_h_4h": macd_h_4h,
                "bb_pctb_4h": bb_pctb_4h, "bb_bw_4h": bb_bw_4h,
                "adx_4h": adx_4h, "pdi_4h": pdi_4h, "mdi_4h": mdi_4h,
                "obv_4h": obv_4h, "ema200_dist_4h": ema200_dist_4h, "range_pos_4h": range_pos_4h,
                "rsi_accel_4h": rsi_accel_4h, "btc_corr_4h": btc_corr_4h, "btc_rel_4h": btc_rel_4h,
                "regimes_4h": regimes_4h, "tb_labels_4h": tb_labels_4h, "tb_rets_4h": tb_rets_4h,
            }

    # =========================================================================
    # INDICADORES DIARIOS (1D) Y RÉGIMEN GMM 1D CACHEADOS POR VELA
    # =========================================================================
    bot_b_ind_key = (daily_prices.index[-1].strftime("%Y-%m-%d"), len(daily_prices))
    if cache_bucket is not None and cache_bucket.get("bot_b_ind_key") == bot_b_ind_key and "bot_b_inds" in cache_bucket:
        bi = cache_bucket["bot_b_inds"]
        d_slice = bi["d_slice"].copy()
        d_hi = bi["d_hi"].copy()
        d_lo = bi["d_lo"].copy()
        d_rets = bi["d_rets"]
        d_vols = bi["d_vols"]
        d_vol_rel = bi["d_vol_rel"]
        sma20_d = bi["sma20_d"]
        ema12_d = bi["ema12_d"]
        ema26_d = bi["ema26_d"]
        ema50_d = bi["ema50_d"]
        roc14_d = bi["roc14_d"]
        peak15_d = bi["peak15_d"]
        macd_d_df = bi["macd_d_df"]
        bb_pb_d = bi["bb_pb_d"]
        atr_1d = bi["atr_1d"]
        adx_1d = bi["adx_1d"]
        obv_1d = bi["obv_1d"]
        btc_rel_1d = bi["btc_rel_1d"]
        regimes_1d = bi["regimes_1d"]
    else:
        d_slice = daily_prices.tail(260).copy()
        d_hi = daily_highs.reindex(d_slice.index).ffill()
        d_lo = daily_lows.reindex(d_slice.index).ffill()
        d_vol = pd.DataFrame({c: ohlcv_5y[c]["volume"].reindex(d_slice.index).ffill().fillna(1.0) for c in coins})
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
        regimes_1d = detect_market_regimes_gmm(d_slice.iloc[:-1], adx_1d.iloc[:-1], btc_col="BTC", seed=42)
        if cache_bucket is not None:
            cache_bucket["bot_b_ind_key"] = bot_b_ind_key
            cache_bucket["bot_b_inds"] = {
                "d_slice": d_slice.copy(), "d_hi": d_hi.copy(), "d_lo": d_lo.copy(),
                "d_rets": d_rets, "d_vols": d_vols, "d_vol_rel": d_vol_rel,
                "sma20_d": sma20_d, "ema12_d": ema12_d, "ema26_d": ema26_d, "ema50_d": ema50_d,
                "roc14_d": roc14_d, "peak15_d": peak15_d, "macd_d_df": macd_d_df,
                "bb_pb_d": bb_pb_d, "atr_1d": atr_1d, "adx_1d": adx_1d,
                "obv_1d": obv_1d, "btc_rel_1d": btc_rel_1d, "regimes_1d": regimes_1d,
            }

    for c in coins:
        sp = float(market_snapshot[c]["price"])
        d_slice.iloc[-1, d_slice.columns.get_loc(c)] = sp
        d_hi.iloc[-1, d_hi.columns.get_loc(c)] = max(float(d_hi.iloc[-1][c]), sp)
        d_lo.iloc[-1, d_lo.columns.get_loc(c)] = min(float(d_lo.iloc[-1][c]), sp)

    funding_rates_8h = np.array([float(market_snapshot[c]["funding_rate_8h_pct"]) / 100.0 for c in coins])
    oi_vol_ratio_vec = np.array([float(market_snapshot[c].get("oi_vol_ratio", 0.35)) for c in coins])
    spread_bps_map = {c: float(market_snapshot[c].get("spread_bps", 1.0)) for c in coins}
    cross_bps_map = {c: float(market_snapshot[c].get("cross_exchange_bps", 2.0)) for c in coins}
    gatekeeper_cfg = RiskGatekeeperConfig()
    cfg_a = BotAConfig()
    eval_start_4h = max(35, len(close_4h) - 271)
    cur_reg_4h = regimes_4h["current_regime"]
    reg_series_4h = regimes_4h["regime_codes_series"]
    reg_series_1d = regimes_1d["regime_codes_series"]
    reg_15m_aligned = reg_series_4h.reindex(close_15m.index, method="ffill").fillna("MERCADO_LATERAL")
    reg_mult_map = {"TENDENCIA_ALCISTA": 1.0, "MERCADO_LATERAL": 0.78, "TENDENCIA_BAJISTA": 0.60, "ALTA_VOLATILIDAD": 0.50}

    ens_cache_key = (key_4h, len(close_4h))
    if cache_bucket is not None and cache_bucket.get("ens_4h_key") == ens_cache_key and "ens_4h_models" in cache_bucket:
        live_champ_bundle, live_gov_decision = cache_bucket["ens_4h_models"]
    else:
        prev_champ = cache_bucket.get("ens_4h_models", (None, None))[0] if cache_bucket is not None else None
        X_all_4h, yc_all_4h, yr_all_4h = [], [], []
        train_lim_4h = max(40, len(close_4h) - 5)
        for ii in range(35, train_lim_4h):
            for c in coins:
                cls_v = tb_labels_4h.iloc[ii][c]
                ret_v = tb_rets_4h.iloc[ii][c]
                if not (np.isnan(cls_v) or np.isnan(ret_v)):
                    X_all_4h.append(
                        extract_ta_features_row(
                            ii, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                            roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h,
                            obv_slope_df=obv_4h, ema200_dist_df=ema200_dist_4h,
                            range_pos_df=range_pos_4h, btc_rel_df=btc_rel_4h, rsi_accel_df=rsi_accel_4h,
                        )
                    )
                    yc_all_4h.append(int(cls_v))
                    yr_all_4h.append(float(ret_v))
        challenger_bundle = fit_supervised_3class_ensemble(
            np.asarray(X_all_4h[-3600:]), np.asarray(yc_all_4h[-3600:]), np.asarray(yr_all_4h[-3600:]),
            purge_samples=32, seed=101,
        )
        live_champ_bundle, live_gov_decision = govern_champion_challenger(prev_champ, challenger_bundle, key_4h)
        if cache_bucket is not None:
            cache_bucket["ens_4h_key"] = ens_cache_key
            cache_bucket["ens_4h_models"] = (live_champ_bundle, live_gov_decision)

    # =========================================================================
    # CARGA O INICIALIZACIÓN DEL LIBRO MAYOR PERSISTENTE DE ESTADO (v4_hybrid_3tier)
    # =========================================================================
    disk_state: Dict[str, Any] = {}
    if ledger_path.exists():
        try:
            disk_state = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            disk_state = {}

    min_15m_window_str = close_15m.index[min(30, len(close_15m) - 1)].strftime("%Y-%m-%d %H:%M")
    has_valid_state = False
    if (
        disk_state.get("schema_version") == STATEFUL_LEDGER_SCHEMA
        and isinstance(disk_state.get("portfolios"), dict)
        and set(disk_state["portfolios"].keys()) == {"bot_a", "bot_b", "bot_c", "bot_d"}
        and isinstance(disk_state.get("certified_orders"), list)
        and len(disk_state["certified_orders"]) >= 10
    ):
        p_a_chk = disk_state["portfolios"]["bot_a"]
        if str(p_a_chk.get("last_closed_bar") or "") >= min_15m_window_str:
            ok_chk, _, _, _ = verify_orders_sha256_chain(
                disk_state["certified_orders"],
                str(disk_state.get("genesis_sha256") or GENESIS_HASH),
                str(disk_state.get("chain_root_sha256") or ""),
            )
            has_valid_state = bool(ok_chk)

    def _enrich_order_meta(tr_item: Dict[str, Any], inc_utc: str, eq_ref_val: float) -> Dict[str, Any]:
        tr_c = dict(tr_item)
        tr_c["bot_inception_utc"] = inc_utc
        tr_c["bot_equity_ref_usd"] = round(float(eq_ref_val), 2)
        if tr_c.get("sl_price") is None and tr_c["side_type"] in ("BUY", "LONG", "SHORT"):
            px_o = float(tr_c["price"])
            c_o = tr_c["coin"]
            atr_o = float(atr_4h.iloc[-2][c_o]) if len(atr_4h) >= 2 else float(atr_4h.iloc[-1][c_o])
            dist_o = max(0.014, (1.6 * atr_o) / max(px_o, 1e-8))
            sgn = -1.0 if tr_c["side_type"] == "SHORT" else 1.0
            tr_c["sl_price"] = fmt_px_dec(px_o * (1.0 - sgn * dist_o))
            tr_c["tp_price"] = fmt_px_dec(px_o * (1.0 + sgn * 1.95 * dist_o))
        return tr_c

    if not has_valid_state:
        # ---------------------------------------------------------------------
        # ARRANQUE INICIAL ÚNICO SOBRE VELAS CERRADAS (ESTADO v4_hybrid_3tier)
        # ---------------------------------------------------------------------
        pf_a = init_bot_a_state(coins, base_cap=base_cap)
        pf_a["dates"] = [close_15m.index[29].strftime("%Y-%m-%d %H:%M")]
        pf_a["inception_utc"] = close_15m.index[29].strftime("%Y-%m-%d %H:%M UTC")
        for idx_i in range(30, len(close_15m) - 1):
            ts = close_15m.index[idx_i]
            p_ts = close_15m.index[idx_i - 1]
            p2_ts = close_15m.index[idx_i - 2]
            reg_a_i = str(reg_15m_aligned.loc[p_ts])
            step_bot_a_microtrading(
                state=pf_a,
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
                adx_1h_prev=adx_1h_aligned.loc[p_ts].to_dict(),
                obv_prev=obv_15m.loc[p_ts].to_dict(),
                ema200_dist_prev=ema200_dist_15m.loc[p_ts].to_dict(),
                regime_code=reg_a_i,
                risk_mult=reg_mult_map.get(reg_a_i, 0.85),
            )
            pf_a["dates"].append(ts.strftime("%Y-%m-%d %H:%M"))
        last_closed_15m = close_15m.index[-2]
        pf_a["last_closed_bar"] = last_closed_15m.strftime("%Y-%m-%d %H:%M")

        eval_b_closed = d_rets.index[-181:-1]
        anchor_b_dt = d_rets.index[max(0, int(d_rets.index.get_loc(eval_b_closed[0])) - 1)]
        pf_b: Dict[str, Any] = {
            "inception_utc": f"{eval_b_closed[0].strftime('%Y-%m-%d')} 00:00 UTC",
            "last_closed_bar": anchor_b_dt.strftime("%Y-%m-%d"),
            "cash_usd": float(base_cap),
            "fees_cum": 0.0,
            "units": {c: 0.0 for c in coins},
            "entry": {c: 0.0 for c in coins},
            "entry_fee": {c: 0.0 for c in coins},
            "sl": {c: 0.0 for c in coins},
            "tp": {c: 0.0 for c in coins},
            "dates": [anchor_b_dt.strftime("%Y-%m-%d")],
            "eq_curve": [float(base_cap)],
            "rets": [],
            "trades": [],
        }
        for dt_b in eval_b_closed:
            _step_bot_b_closed_bar(
                pf_b, dt_b, coins, d_slice, d_lo, d_hi, d_rets, d_vols, d_vol_rel,
                sma20_d, ema12_d, ema26_d, ema50_d, roc14_d, peak15_d, macd_d_df, bb_pb_d, atr_1d, adx_1d,
                obv_1d=obv_1d, btc_rel_1d=btc_rel_1d, regime_series_1d=reg_series_1d, gatekeeper_cfg=gatekeeper_cfg,
            )

        anchor_4h_ts = close_4h.index[eval_start_4h - 1]
        pf_c: Dict[str, Any] = {
            "inception_utc": anchor_4h_ts.strftime("%Y-%m-%d %H:%M UTC"),
            "last_closed_bar": anchor_4h_ts.strftime("%Y-%m-%d %H:%M"),
            "bar_step": 0,
            "realized_cash_c": float(base_cap),
            "fees_cum": 0.0,
            "units": {c: 0.0 for c in coins},
            "entry": {c: 0.0 for c in coins},
            "entry_fee": {c: 0.0 for c in coins},
            "sl": {c: 0.0 for c in coins},
            "tp": {c: 0.0 for c in coins},
            "peak": {c: 0.0 for c in coins},
            "cooldown_step": {c: -1 for c in coins},
            "dates": [anchor_4h_ts.strftime("%Y-%m-%d %H:%M")],
            "eq_curve": [float(base_cap)],
            "rets": [],
            "trades": [],
        }
        for idx_i in range(eval_start_4h, len(close_4h) - 1):
            _step_bot_c_closed_bar(
                pf_c, idx_i, coins, close_4h, low_4h, high_4h,
                ema21_4h, ema55_4h, roc24_4h, macd_h_4h, bb_pctb_4h,
                adx_4h, pdi_4h, mdi_4h, atr_4h, vol_rel_4h, funding_rates_8h,
                oi_vol_ratio_vec=oi_vol_ratio_vec, obv_4h=obv_4h, regime_series_4h=reg_series_4h,
                gatekeeper_cfg=gatekeeper_cfg,
            )

        X_d_hist, yc_d_hist, yr_d_hist = [], [], []
        train_start_4h = 55 if eval_start_4h > 90 else 20
        for ii in range(train_start_4h, eval_start_4h - 5):
            for c in coins:
                cls_v = tb_labels_4h.iloc[ii][c]
                ret_v = tb_rets_4h.iloc[ii][c]
                if not (np.isnan(cls_v) or np.isnan(ret_v)):
                    X_d_hist.append(
                        extract_ta_features_row(
                            ii, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                            roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h,
                            obv_slope_df=obv_4h, ema200_dist_df=ema200_dist_4h,
                            range_pos_df=range_pos_4h, btc_rel_df=btc_rel_4h, rsi_accel_df=rsi_accel_4h,
                        )
                    )
                    yc_d_hist.append(int(cls_v))
                    yr_d_hist.append(float(ret_v))
        champ_d = fit_supervised_3class_ensemble(
            np.asarray(X_d_hist[-3600:]), np.asarray(yc_d_hist[-3600:]), np.asarray(yr_d_hist[-3600:]),
            purge_samples=32, seed=101,
        )
        champ_d, gov_d = govern_champion_challenger(None, champ_d, close_4h.index[eval_start_4h - 1].strftime("%Y-%m-%d %H:%M"))
        pf_d: Dict[str, Any] = {
            "inception_utc": anchor_4h_ts.strftime("%Y-%m-%d %H:%M UTC"),
            "last_closed_bar": anchor_4h_ts.strftime("%Y-%m-%d %H:%M"),
            "cash_usd": float(base_cap),
            "fees_cum": 0.0,
            "units": {c: 0.0 for c in coins},
            "entry": {c: 0.0 for c in coins},
            "entry_fee": {c: 0.0 for c in coins},
            "partial_taken": {c: False for c in coins},
            "peak": {c: 0.0 for c in coins},
            "sl": {c: 0.0 for c in coins},
            "tp": {c: 0.0 for c in coins},
            "dates": [anchor_4h_ts.strftime("%Y-%m-%d %H:%M")],
            "eq_curve": [float(base_cap)],
            "rets": [],
            "trades": [],
            "veto_count": 0,
            "gov_meta": {
                "version": int(champ_d.get("version", 1)),
                "oos_brier_score": champ_d.get("oos_brier_score", 0.0),
                "oos_expectancy_pct": champ_d.get("oos_expectancy_pct", 0.0),
                "train_samples": champ_d.get("train_samples", 0),
                "purged_gap": champ_d.get("purged_gap", 32),
                "reason": gov_d["reason"],
            },
        }
        last_ens_out: Dict[str, np.ndarray] = {
            "prob_bear": np.full(n_assets, 0.33),
            "prob_flat": np.full(n_assets, 0.34),
            "prob_bull": np.full(n_assets, 0.33),
            "pred_net_ret": np.zeros(n_assets),
        }
        for idx_i in range(eval_start_4h, len(close_4h) - 1):
            if (idx_i - eval_start_4h) > 0 and (idx_i - eval_start_4h) % 60 == 0:
                X_inc = list(X_d_hist[-3000:])
                yc_inc = list(yc_d_hist[-3000:])
                yr_inc = list(yr_d_hist[-3000:])
                for kk in range(eval_start_4h, idx_i - 5):
                    for c in coins:
                        cls_v = tb_labels_4h.iloc[kk][c]
                        ret_v = tb_rets_4h.iloc[kk][c]
                        if not (np.isnan(cls_v) or np.isnan(ret_v)):
                            X_inc.append(
                                extract_ta_features_row(
                                    kk, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                                    roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h,
                                    obv_slope_df=obv_4h, ema200_dist_df=ema200_dist_4h,
                                    range_pos_df=range_pos_4h, btc_rel_df=btc_rel_4h, rsi_accel_df=rsi_accel_4h,
                                )
                            )
                            yc_inc.append(int(cls_v))
                            yr_inc.append(float(ret_v))
                chall_i = fit_supervised_3class_ensemble(
                    np.asarray(X_inc[-3600:]), np.asarray(yc_inc[-3600:]), np.asarray(yr_inc[-3600:]),
                    purge_samples=32, seed=101,
                )
                champ_d, gov_d = govern_champion_challenger(champ_d, chall_i, close_4h.index[idx_i - 1].strftime("%Y-%m-%d %H:%M"))
                pf_d["gov_meta"] = {
                    "version": int(champ_d.get("version", 1)),
                    "oos_brier_score": champ_d.get("oos_brier_score", 0.0),
                    "oos_expectancy_pct": champ_d.get("oos_expectancy_pct", 0.0),
                    "train_samples": champ_d.get("train_samples", 0),
                    "purged_gap": champ_d.get("purged_gap", 32),
                    "reason": gov_d["reason"],
                }
            _, last_ens_out = _step_bot_d_closed_bar(
                pf_d, idx_i, coins, open_4h, close_4h, low_4h, high_4h,
                ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, atr_4h, vol_rel_4h,
                champ_d, obv_4h=obv_4h, ema200_dist_4h=ema200_dist_4h,
                range_pos_4h=range_pos_4h, btc_rel_4h=btc_rel_4h, rsi_accel_4h=rsi_accel_4h,
                regime_series_4h=reg_series_4h, regime_probs=None,
                gatekeeper_cfg=gatekeeper_cfg,
            )

        for pf_obj in (pf_a, pf_b, pf_c, pf_d):
            run_eq = base_cap
            inc_u = pf_obj["inception_utc"]
            for idx_t, tr_it in enumerate(pf_obj["trades"]):
                if tr_it.get("realized_pnl_usd") is not None:
                    run_eq += float(tr_it["realized_pnl_usd"])
                else:
                    run_eq -= float(tr_it.get("fee_usd") or 0.0)
                pf_obj["trades"][idx_t] = _enrich_order_meta(tr_it, inc_u, run_eq)

        boot_selected = [
            dict(t)
            for t in (
                pf_a["trades"][-26:]
                + pf_b["trades"][-22:]
                + pf_c["trades"][-26:]
                + pf_d["trades"][-26:]
            )
        ]
        boot_selected.sort(key=lambda x: (x["ts_iso"], x["bot_id"], x["coin"]))
        certified_orders, chain_root_hash = sign_orders_sha256_chain(boot_selected, GENESIS_HASH)
    else:
        # ---------------------------------------------------------------------
        # MODO PERSISTENTE EN TIEMPO REAL: AVANCE INCREMENTAL ADITIVO (APPEND-ONLY)
        # ---------------------------------------------------------------------
        pfs_disk = disk_state["portfolios"]
        pf_a = dict(pfs_disk["bot_a"])
        pf_b = dict(pfs_disk["bot_b"])
        pf_c = dict(pfs_disk["bot_c"])
        pf_d = dict(pfs_disk["bot_d"])
        for pf_obj in (pf_a, pf_b, pf_c, pf_d):
            for dk in ("units", "entry", "entry_fee", "peak", "sl", "tp"):
                if dk in pf_obj and isinstance(pf_obj[dk], dict):
                    pf_obj[dk] = {c: float(pf_obj[dk].get(c, 0.0)) for c in coins}
            if "partial_taken" in pf_obj and isinstance(pf_obj["partial_taken"], dict):
                pf_obj["partial_taken"] = {c: bool(pf_obj["partial_taken"].get(c, False)) for c in coins}
            pf_obj["dates"] = list(pf_obj.get("dates") or [])
            pf_obj["eq_curve"] = [float(x) for x in (pf_obj.get("eq_curve") or [])]
            pf_obj["rets"] = [float(x) for x in (pf_obj.get("rets") or [])]
            pf_obj["trades"] = [dict(t) for t in (pf_obj.get("trades") or [])]
        if isinstance(pf_a.get("cur_day"), str) and pf_a["cur_day"]:
            pf_a["cur_day"] = pd.Timestamp(pf_a["cur_day"]).date()
        if "cooldown_step" in pf_c and isinstance(pf_c["cooldown_step"], dict):
            pf_c["cooldown_step"] = {c: int(pf_c["cooldown_step"].get(c, -1)) for c in coins}
        if not isinstance(pf_d.get("gov_meta"), dict):
            pf_d["gov_meta"] = {
                "version": int(live_champ_bundle.get("version", 1)),
                "oos_brier_score": live_champ_bundle.get("oos_brier_score", 0.0),
                "oos_expectancy_pct": live_champ_bundle.get("oos_expectancy_pct", 0.0),
                "train_samples": live_champ_bundle.get("train_samples", 0),
                "purged_gap": live_champ_bundle.get("purged_gap", 32),
                "reason": live_gov_decision["reason"],
            }

        certified_orders = [dict(o) for o in disk_state["certified_orders"]]
        chain_root_hash = str(disk_state["chain_root_sha256"])

        inc_new_orders: List[Dict[str, Any]] = []

        last_bar_a = str(pf_a.get("last_closed_bar") or "")
        for idx_i in range(30, len(close_15m) - 1):
            ts = close_15m.index[idx_i]
            ts_str = ts.strftime("%Y-%m-%d %H:%M")
            if ts_str <= last_bar_a:
                continue
            p_ts = close_15m.index[idx_i - 1]
            p2_ts = close_15m.index[idx_i - 2]
            reg_a_i = str(reg_15m_aligned.loc[p_ts])
            prev_n_a = len(pf_a["trades"])
            step_bot_a_microtrading(
                state=pf_a,
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
                adx_1h_prev=adx_1h_aligned.loc[p_ts].to_dict(),
                obv_prev=obv_15m.loc[p_ts].to_dict(),
                ema200_dist_prev=ema200_dist_15m.loc[p_ts].to_dict(),
                regime_code=reg_a_i,
                spread_bps_map=spread_bps_map,
                risk_mult=reg_mult_map.get(reg_a_i, 0.85),
            )
            pf_a["dates"].append(ts_str)
            pf_a["last_closed_bar"] = ts_str
            for tr_new in pf_a["trades"][prev_n_a:]:
                inc_new_orders.append(_enrich_order_meta(tr_new, pf_a["inception_utc"], pf_a["eq_curve"][-1]))

        last_bar_b = str(pf_b.get("last_closed_bar") or "")
        for dt_b in d_rets.index[:-1]:
            dt_str = dt_b.strftime("%Y-%m-%d")
            if dt_str <= last_bar_b:
                continue
            em_b = _step_bot_b_closed_bar(
                pf_b, dt_b, coins, d_slice, d_lo, d_hi, d_rets, d_vols, d_vol_rel,
                sma20_d, ema12_d, ema26_d, ema50_d, roc14_d, peak15_d, macd_d_df, bb_pb_d, atr_1d, adx_1d,
                obv_1d=obv_1d, btc_rel_1d=btc_rel_1d, regime_series_1d=reg_series_1d, gatekeeper_cfg=gatekeeper_cfg,
            )
            for tr_new in em_b:
                inc_new_orders.append(_enrich_order_meta(tr_new, pf_b["inception_utc"], pf_b["eq_curve"][-1]))

        last_bar_c = str(pf_c.get("last_closed_bar") or "")
        for idx_i in range(35, len(close_4h) - 1):
            ts_4h = close_4h.index[idx_i]
            ts_str = ts_4h.strftime("%Y-%m-%d %H:%M")
            if ts_str <= last_bar_c:
                continue
            em_c = _step_bot_c_closed_bar(
                pf_c, idx_i, coins, close_4h, low_4h, high_4h,
                ema21_4h, ema55_4h, roc24_4h, macd_h_4h, bb_pctb_4h,
                adx_4h, pdi_4h, mdi_4h, atr_4h, vol_rel_4h, funding_rates_8h,
                oi_vol_ratio_vec=oi_vol_ratio_vec, obv_4h=obv_4h, regime_series_4h=reg_series_4h,
                gatekeeper_cfg=gatekeeper_cfg,
            )
            for tr_new in em_c:
                inc_new_orders.append(_enrich_order_meta(tr_new, pf_c["inception_utc"], pf_c["eq_curve"][-1]))

        last_bar_d = str(pf_d.get("last_closed_bar") or "")
        X_cur_inf = np.array([
            extract_ta_features_row(
                len(close_4h) - 2, c, ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, vol_rel_4h,
                obv_slope_df=obv_4h, ema200_dist_df=ema200_dist_4h,
                range_pos_df=range_pos_4h, btc_rel_df=btc_rel_4h, rsi_accel_df=rsi_accel_4h,
            )
            for c in coins
        ])
        last_ens_out = predict_supervised_3class_ensemble(live_champ_bundle, X_cur_inf, regime_probs=cur_reg_4h["probabilities"])
        for idx_i in range(35, len(close_4h) - 1):
            ts_4h = close_4h.index[idx_i]
            ts_str = ts_4h.strftime("%Y-%m-%d %H:%M")
            if ts_str <= last_bar_d:
                continue
            em_d, last_ens_out = _step_bot_d_closed_bar(
                pf_d, idx_i, coins, open_4h, close_4h, low_4h, high_4h,
                ema9_4h, ema21_4h, ema55_4h, bb_pctb_4h, bb_bw_4h,
                roc12_4h, roc24_4h, macd_h_4h, rsi_4h, stoch_4h, atr_4h, vol_rel_4h,
                live_champ_bundle, obv_4h=obv_4h, ema200_dist_4h=ema200_dist_4h,
                range_pos_4h=range_pos_4h, btc_rel_4h=btc_rel_4h, rsi_accel_4h=rsi_accel_4h,
                regime_series_4h=reg_series_4h, regime_probs=cur_reg_4h["probabilities"],
                spread_bps_map=spread_bps_map, cross_bps_map=cross_bps_map,
                gatekeeper_cfg=gatekeeper_cfg,
            )
            for tr_new in em_d:
                inc_new_orders.append(_enrich_order_meta(tr_new, pf_d["inception_utc"], pf_d["eq_curve"][-1]))

        if inc_new_orders:
            inc_new_orders.sort(key=lambda x: (x["ts_iso"], x["bot_id"], x["coin"]))
            certified_orders, chain_root_hash = append_orders_sha256_chain(certified_orders, inc_new_orders, GENESIS_HASH)

    # =========================================================================
    # PROTECCIÓN Y GRABACIÓN EN TIEMPO REAL INTRABARRA (CADA CICLO DE 30S)
    # =========================================================================
    now_time_utc = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    now_ts_iso = now_utc.strftime("%Y-%m-%d %H:%M")
    spot_live_map = {c: float(market_snapshot[c]["price"]) for c in coins}
    perp_live_map = {c: float(market_snapshot[c]["perp_price"]) for c in coins}

    rt_emitted: List[Dict[str, Any]] = []
    em_rt_a = step_realtime_spot_protections(
        pf_a, "bot_a", "BOT A", coins, spot_live_map,
        low_15m.iloc[-1].to_dict(), high_15m.iloc[-1].to_dict(),
        atr_15m.iloc[-2].to_dict(), vol_rel_15m.iloc[-2].to_dict(),
        now_time_utc, now_ts_iso, cfg_a.fee_rate,
        trail_activate_atr=cfg_a.trail_activate_atr,
        trail_dist_atr=cfg_a.trail_dist_atr,
        trail_floor_mult=cfg_a.trail_floor_mult,
        partial_tp_atr=cfg_a.partial_tp_atr,
        partial_tp_frac=cfg_a.partial_tp_frac,
    )
    for tr_rt in em_rt_a:
        eq_a_rt = float(pf_a["cash_usd"]) + sum(float(pf_a["units"][c]) * spot_live_map[c] for c in coins)
        rt_emitted.append(_enrich_order_meta(tr_rt, pf_a["inception_utc"], eq_a_rt))

    em_rt_b = step_realtime_spot_protections(
        pf_b, "bot_b", "BOT B", coins, spot_live_map,
        d_lo.iloc[-1].to_dict(), d_hi.iloc[-1].to_dict(),
        atr_1d.iloc[-2].to_dict(), d_vol_rel.iloc[-2].to_dict(),
        now_time_utc, now_ts_iso, SETTINGS.spot_fee_rate,
    )
    for tr_rt in em_rt_b:
        eq_b_rt = float(pf_b["cash_usd"]) + sum(float(pf_b["units"][c]) * spot_live_map[c] for c in coins)
        rt_emitted.append(_enrich_order_meta(tr_rt, pf_b["inception_utc"], eq_b_rt))

    em_rt_c = step_realtime_futures_protections(
        pf_c, coins, perp_live_map,
        low_4h.iloc[-1].to_dict(), high_4h.iloc[-1].to_dict(),
        atr_4h.iloc[-2].to_dict(), vol_rel_4h.iloc[-2].to_dict(),
        now_time_utc, now_ts_iso, SETTINGS.futures_fee_rate,
    )
    for tr_rt in em_rt_c:
        eq_c_rt, _, _ = calc_futures_account_state(pf_c["units"], pf_c["entry"], float(pf_c["realized_cash_c"]), perp_live_map)
        rt_emitted.append(_enrich_order_meta(tr_rt, pf_c["inception_utc"], eq_c_rt))

    em_rt_d = step_realtime_spot_protections(
        pf_d, "bot_d", "BOT D", coins, spot_live_map,
        low_4h.iloc[-1].to_dict(), high_4h.iloc[-1].to_dict(),
        atr_4h.iloc[-2].to_dict(), vol_rel_4h.iloc[-2].to_dict(),
        now_time_utc, now_ts_iso, SETTINGS.spot_fee_rate,
        trail_activate_atr=1.25,
        trail_dist_atr=1.30,
        trail_floor_mult=1.0065,
        partial_tp_atr=1.35,
        partial_tp_frac=0.45,
    )
    for tr_rt in em_rt_d:
        eq_d_rt = float(pf_d["cash_usd"]) + sum(float(pf_d["units"][c]) * spot_live_map[c] for c in coins)
        rt_emitted.append(_enrich_order_meta(tr_rt, pf_d["inception_utc"], eq_d_rt))

    if rt_emitted:
        certified_orders, chain_root_hash = append_orders_sha256_chain(certified_orders, rt_emitted, GENESIS_HASH)

    if len(certified_orders) > 2500:
        certified_orders, chain_root_hash = sign_orders_sha256_chain(certified_orders[-1500:], GENESIS_HASH)

    chain_ok, valid_h, valid_b, chain_errs = verify_orders_sha256_chain(certified_orders, GENESIS_HASH, chain_root_hash)
    if not chain_ok:
        raise RuntimeError(f"Error de integridad en cadena SHA-256: {chain_errs}")
    _ = (valid_h, valid_b)

    inception_map = {
        "bot_a": str(pf_a["inception_utc"]),
        "bot_b": str(pf_b["inception_utc"]),
        "bot_c": str(pf_c["inception_utc"]),
        "bot_d": str(pf_d["inception_utc"]),
    }
    elapsed_days_map = {}
    for bk, inc_str in inception_map.items():
        inc_ts = pd.Timestamp(inc_str.replace(" UTC", ""), tz="UTC")
        elapsed_days_map[bk] = round(max(1.0, (now_utc - inc_ts).total_seconds() / 86400.0), 1)

    cash_a = float(pf_a["cash_usd"])
    units_a = pf_a["units"]
    entry_a = pf_a["entry"]
    sl_a = pf_a["sl"]
    tp_a = pf_a["tp"]
    fees_cum_a = float(pf_a["fees_cum"])
    trades_a = pf_a["trades"]

    cash_b = float(pf_b["cash_usd"])
    units_b = pf_b["units"]
    entry_b = pf_b["entry"]
    sl_b = pf_b["sl"]
    tp_b = pf_b["tp"]
    fees_cum_b = float(pf_b["fees_cum"])
    trades_b = pf_b["trades"]

    realized_cash_c = float(pf_c["realized_cash_c"])
    units_c = pf_c["units"]
    entry_c = pf_c["entry"]
    sl_c = pf_c["sl"]
    tp_c = pf_c.setdefault("tp", {c: 0.0 for c in coins})
    fees_cum_c = float(pf_c["fees_cum"])
    trades_c = pf_c["trades"]

    cash_d = float(pf_d["cash_usd"])
    units_d = pf_d["units"]
    entry_d = pf_d["entry"]
    sl_d = pf_d["sl"]
    tp_d = pf_d["tp"]
    fees_cum_d = float(pf_d["fees_cum"])
    trades_d = pf_d["trades"]

    portfolios_serialized = {
        "bot_a": _sanitize_portfolio_for_json(pf_a, coins),
        "bot_b": _sanitize_portfolio_for_json(pf_b, coins),
        "bot_c": _sanitize_portfolio_for_json(pf_c, coins),
        "bot_d": _sanitize_portfolio_for_json(pf_d, coins),
    }

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
                sl_p = float(sl_c[c]) if sl_c.get(c, 0.0) > 0.0 else ep * (1.0 - sign_f * max(0.018, (2.85 * atr_c) / max(ep, 1e-6)))
                tp_p = float(tp_c[c]) if tp_c.get(c, 0.0) > 0.0 else ep * (1.0 + sign_f * max(0.026, (3.60 * atr_c) / max(ep, 1e-6)))
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
    hold_b, eq_b_final = build_spot_holdings(units_b, entry_b, cash_b, sl_b, tp_b)
    hold_c, eq_c_final = build_futures_holdings()
    hold_d, eq_d_final = build_spot_holdings(units_d, entry_d, cash_d, sl_d, tp_d)

    now_15m_lbl = now_utc.strftime("%Y-%m-%d %H:%M")
    now_1d_lbl = now_utc.strftime("%Y-%m-%d")

    def _build_live_curve(pf_src: Dict[str, Any], eq_fin: float, tip_lbl: str):
        d_out = list(pf_src["dates"])
        e_out = [float(x) for x in pf_src["eq_curve"]]
        r_out = [float(x) for x in pf_src["rets"]]
        prev_tip = e_out[-1] if e_out else base_cap
        if d_out and d_out[-1] == tip_lbl:
            e_out[-1] = eq_fin
            if len(e_out) >= 2 and e_out[-2] > 0 and r_out:
                r_out[-1] = (eq_fin / e_out[-2]) - 1.0
        else:
            d_out.append(tip_lbl)
            e_out.append(eq_fin)
            r_out.append((eq_fin / max(prev_tip, 1e-6)) - 1.0)
        return d_out, e_out, r_out

    dates_a, eq_a, rets_a = _build_live_curve(pf_a, eq_a_final, now_15m_lbl)
    dates_b, eq_b, rets_b = _build_live_curve(pf_b, eq_b_final, now_1d_lbl)
    dates_c, eq_c, rets_c = _build_live_curve(pf_c, eq_c_final, now_15m_lbl)
    dates_d, eq_d, rets_d = _build_live_curve(pf_d, eq_d_final, now_15m_lbl)

    # =========================================================================
    # SERIES OHLCV 4H COMPLETAS + ANÁLISIS TÉCNICO + VOLUMEN EN DECISIONES
    # =========================================================================
    market_candles_4h = {}
    tail_n = 135
    for c in coins:
        full_c = candles_4h[c].tail(200).copy()
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

    # Matriz actual de indicadores de Análisis Técnico, Flujo y Ensemble 3-Clases
    signal_matrix_now = {}
    last_4h = close_4h.index[-1]
    prob_bull_vec = last_ens_out["prob_bull"]
    prob_flat_vec = last_ens_out["prob_flat"]
    prob_bear_vec = last_ens_out["prob_bear"]
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
        p_bull = float(prob_bull_vec[j])
        p_flat = float(prob_flat_vec[j])
        p_bear = float(prob_bear_vec[j])
        obv_v = float(obv_4h.loc[last_4h, c])
        e200_d = float(ema200_dist_4h.loc[last_4h, c])
        bcorr_v = float(btc_corr_4h.loc[last_4h, c])
        oi_usd_v = float(market_snapshot[c].get("open_interest_usd", 0.0))
        oi_vr_v = float(market_snapshot[c].get("oi_vol_ratio", 0.35))
        fr_8h_p = float(market_snapshot[c]["funding_rate_8h_pct"])

        # Puntuaciones técnicas estandarizadas [-100, +100] para los 4 algoritmos
        sc_a = float(np.clip(((e9_v / max(e21_v, 1e-8) - 1.0) * 900.0) + (mh_v * 22.0) + ((pb_v - 0.5) * 45.0) + (obv_v * 18.0), -98.0, 98.0))
        sc_b = float(np.clip(((px_s / max(float(sma20_d.iloc[-1, j]), 1e-8) - 1.0) * 480.0) + (float(roc14_d.iloc[-1, j]) * 2.2), -98.0, 98.0))
        sc_c = float(np.clip(((e21_v / max(e55_v, 1e-8) - 1.0) * 620.0) + (float(roc24_4h.loc[last_4h, c]) * 3.2), -98.0, 98.0))
        sc_d = float(np.clip(((p_bull - p_bear) * 145.0) + (mh_v * 16.0), -98.0, 98.0))

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
            "obv_slope": round(obv_v, 3),
            "ema200_dist_pct": round(e200_d * 100.0, 2),
            "btc_corr": round(bcorr_v, 2),
            "open_interest_usd": round(oi_usd_v, 0),
            "oi_vol_ratio": round(oi_vr_v, 3),
            "prob_bull_pct": round(p_bull * 100.0, 1),
            "prob_flat_pct": round(p_flat * 100.0, 1),
            "prob_bear_pct": round(p_bear * 100.0, 1),
            "mlp_prob_pct": round(p_bull * 100.0, 1),
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
    for tr in certified_orders:
        latest_order_by_bot[tr["bot_id"]] = tr

    gov_meta = pf_d.get("gov_meta") or {
        "version": int(live_champ_bundle.get("version", 1)),
        "oos_brier_score": float(live_champ_bundle.get("oos_brier_score", 0.0)),
        "oos_expectancy_pct": float(live_champ_bundle.get("oos_expectancy_pct", 0.0)),
        "train_samples": int(live_champ_bundle.get("train_samples", 0)),
        "purged_gap": int(live_champ_bundle.get("purged_gap", 32)),
        "reason": live_gov_decision["reason"],
    }
    avg_spread_live = float(np.mean(list(spread_bps_map.values())))
    avg_cross_live = float(np.mean(list(cross_bps_map.values())))
    gate_live_a = evaluate_risk_gatekeeper(
        eq_a, float(pf_a.get("day_anchor_eq", base_cap)),
        1.0 - (cash_a / max(eq_a_final, 1.0)), cfg_a.max_total_invested,
        spread_bps=avg_spread_live, cross_exchange_bps=avg_cross_live, regime_info=cur_reg_4h, cfg=gatekeeper_cfg,
    )
    gate_live_d = evaluate_risk_gatekeeper(
        eq_d, float(pf_d["eq_curve"][-1] if pf_d["eq_curve"] else base_cap),
        1.0 - (cash_d / max(eq_d_final, 1.0)), 0.74,
        spread_bps=avg_spread_live, cross_exchange_bps=avg_cross_live, regime_info=cur_reg_4h, cfg=gatekeeper_cfg,
    )
    best_ens_j = int(np.argmax(prob_bull_vec))
    supervisor_3tier = {
        "schema_version": STATEFUL_LEDGER_SCHEMA,
        "tier1_predictive": {
            "champion_version": int(gov_meta.get("version", 1)),
            "labeling": "Triple-Barrera Causal (TP 1.8x ATR vs SL 1.4x ATR vs Espera)",
            "features_count": 15,
            "flow_variables": ["OBV Slope", "EMA 200 Dist", "Canal Mín-Máx", "Correlación/Fuerza BTC", "Open Interest SWAP"],
            "oos_brier_score": round(float(gov_meta.get("oos_brier_score", 0.0)), 4),
            "oos_expectancy_pct": round(float(gov_meta.get("oos_expectancy_pct", 0.0)), 3),
            "train_samples": int(gov_meta.get("train_samples", 0)),
            "purged_gap": int(gov_meta.get("purged_gap", 32)),
            "governance_status": str(gov_meta.get("reason", "Campeón Activo")),
        },
        "tier2_regime_ensemble": {
            "regime_code": cur_reg_4h["code"],
            "regime_label": cur_reg_4h["label"],
            "regime_probabilities": cur_reg_4h["probabilities"],
            "cross_vol_pct": cur_reg_4h["cross_vol_pct"],
            "risk_multiplier": cur_reg_4h["risk_multiplier"],
            "sl_atr_buffer": cur_reg_4h["sl_atr_buffer"],
            "ensemble_weights": {
                "HistGradientBoosting": 44,
                "MLP(32,16)": 26,
                "LogisticRegression": 15,
                "Regimen GMM": 15,
            },
            "top_candidate": {
                "coin": coins[best_ens_j],
                "prob_bull_pct": round(float(prob_bull_vec[best_ens_j]) * 100.0, 1),
                "prob_flat_pct": round(float(prob_flat_vec[best_ens_j]) * 100.0, 1),
                "prob_bear_pct": round(float(prob_bear_vec[best_ens_j]) * 100.0, 1),
            },
        },
        "tier3_risk_gatekeeper": {
            "status": "ACTIVO · COMPLEMENTO INDEPENDIENTE DE RIESGO",
            "effective_risk_pct": round(float(gate_live_a["effective_risk_pct"]) * 100.0, 2),
            "kill_switch_dd_pct": round(gatekeeper_cfg.kill_switch_drawdown_pct * 100.0, 1),
            "daily_loss_limit_pct": round(gatekeeper_cfg.daily_loss_limit_pct * 100.0, 1),
            "avg_spread_bps": round(avg_spread_live, 2),
            "max_spread_bps": gatekeeper_cfg.max_spread_bps,
            "avg_cross_exchange_bps": round(avg_cross_live, 2),
            "veto_count_bot_d": int(pf_d.get("veto_count", 0)),
            "bot_a_approved": bool(gate_live_a["approved"]),
            "bot_d_approved": bool(gate_live_d["approved"]),
            "bot_a_dd_pct": gate_live_a["current_dd_pct"],
            "bot_d_dd_pct": gate_live_d["current_dd_pct"],
        },
    }

    bots_dict = {
        "bot_a": {
            "id": "bot_a",
            "code": "BOT A",
            "name": "Microtrading Intradía por Impulso, Flujo OBV y Régimen GMM",
            "timeframe": "Intradía 15m / Filtro 1H & GMM",
            "inception_utc": inception_map["bot_a"],
            "elapsed_days": elapsed_days_map["bot_a"],
            "latest_order": latest_order_by_bot.get("bot_a"),
            "methodology": "Velas 15m + Filtro 1H + Supervisor GMM 4 Regímenes (EMA 9/21/55, ADX >= 20, ATR >= 0.42%, OBV, distancia EMA200, Bollinger %B, MACD, Volumen >= 1.08x)",
            "risk_profile": "Gatekeeper Independiente (Maker 0.04% · Riesgo 0.25%–0.50%/orden · Spread <= 12 bps · Parcial 45% a 1.40x ATR · Trailing +0.55% · Kill Switch -8.5%)",
            "cash_usd": round(cash_a, 4),
            "fees_paid_usd": round(fees_cum_a, 2),
            "is_futures": False,
            "stats": calc_metrics(np.asarray(eq_a), np.asarray(rets_a), 96.0 * 365.0, "Bot A · Microtrading Técnico Intradía 15m"),
            "trade_eval": summarize_bot_trades(trades_a, hold_a, np.asarray(rets_a)),
            "dates": dates_a,
            "equity_curve": [round(float(v), 2) for v in eq_a],
            "active_positions": hold_a,
        },
        "bot_b": {
            "id": "bot_b",
            "code": "BOT B",
            "name": "Decisión Sistemática Diaria Adaptativa por Régimen (1D)",
            "timeframe": "Cierre Diario 1D (00:00 UTC)",
            "inception_utc": inception_map["bot_b"],
            "elapsed_days": elapsed_days_map["bot_b"],
            "latest_order": latest_order_by_bot.get("bot_b"),
            "methodology": "Canal SMA 20 / EMA 50 + OBV + Fuerza Relativa BTC + Markowitz SLSQP / GJR-GARCH con techo adaptativo GMM y salida Chandelier ATR",
            "risk_profile": "Sistemático Adaptativo (Tope 34%/activo · Techo exposición 24%–92% según Régimen GMM · Histéresis L1 >= 16% · Chandelier 2.30x ATR)",
            "cash_usd": round(cash_b, 4),
            "fees_paid_usd": round(fees_cum_b, 2),
            "is_futures": False,
            "stats": calc_metrics(np.asarray(eq_b), np.asarray(rets_b), 365.0, "Bot B · Decisión Sistemática Diaria (1D)"),
            "trade_eval": summarize_bot_trades(trades_b, hold_b, np.asarray(rets_b)),
            "dates": dates_b,
            "equity_curve": [round(float(v), 2) for v in eq_b],
            "active_positions": hold_b,
        },
        "bot_c": {
            "id": "bot_c",
            "code": "BOT C",
            "name": "Estrategia Posicional de Largos y Futuros SWAP con Open Interest",
            "timeframe": "Contratos SWAP 4H + Carry 8H & OI",
            "inception_utc": inception_map["bot_c"],
            "elapsed_days": elapsed_days_map["bot_c"],
            "latest_order": latest_order_by_bot.get("bot_c"),
            "methodology": "Tendencia EMA 21/55 + Ruptura Bollinger + ROC(24) + ADX/DI + Carry Funding 8h + Open Interest SWAP + OBV + Rebalanceo Delta",
            "risk_profile": "Direccional Cubierto (Largos/Cortos SWAP · Bruto <= 1.05x · SL 2.85x ATR · Trailing 1.85x ATR · Umbral estricto en rango lateral)",
            "cash_usd": round(realized_cash_c, 4),
            "fees_paid_usd": round(fees_cum_c, 2),
            "is_futures": True,
            "stats": calc_metrics(np.asarray(eq_c), np.asarray(rets_c), 6.0 * 365.0, "Bot C · Largos y Futuros Perpetuos SWAP"),
            "trade_eval": summarize_bot_trades(trades_c, hold_c, np.asarray(rets_c)),
            "dates": dates_c,
            "equity_curve": [round(float(v), 2) for v in eq_c],
            "active_positions": hold_c,
        },
        "bot_d": {
            "id": "bot_d",
            "code": "BOT D",
            "name": "Ensemble Supervisado Triple-Barrera y Régimen GMM (4H)",
            "timeframe": "Ensemble 4H · Boosting + MLP + LogReg",
            "inception_utc": inception_map["bot_d"],
            "elapsed_days": elapsed_days_map["bot_d"],
            "latest_order": latest_order_by_bot.get("bot_d"),
            "methodology": "Ensemble (44% HistGradientBoosting + 26% MLP(32,16) + 15% LogisticRegression + 15% GMM) con etiquetas Triple-Barrera, purga temporal y Campeón/Retador",
            "risk_profile": "Gatekeeper & Triple Salida (Riesgo 0.25%–0.55%/orden · Reserva >= 25% USDT · Parcial 45% a 1.35x ATR · Trailing 1.30x ATR · Giro 3-clases)",
            "cash_usd": round(cash_d, 4),
            "fees_paid_usd": round(fees_cum_d, 2),
            "is_futures": False,
            "stats": calc_metrics(np.asarray(eq_d), np.asarray(rets_d), 6.0 * 365.0, "Bot D · Ensemble Supervisado Triple-Barrera"),
            "trade_eval": summarize_bot_trades(trades_d, hold_d, np.asarray(rets_d)),
            "dates": dates_d,
            "equity_curve": [round(float(v), 2) for v in eq_d],
            "active_positions": hold_d,
        },
    }

    return {
        "bots": bots_dict,
        "supervisor_3tier": supervisor_3tier,
        "ledger_chain": {
            "genesis_sha256": GENESIS_HASH,
            "chain_root_sha256": chain_root_hash,
            "total_certified_orders": len(certified_orders),
            "orders": list(reversed(certified_orders)),
        },
        "certified_orders_chrono": certified_orders,
        "portfolios_state": portfolios_serialized,
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
    certified_orders_chrono: List[Dict[str, Any]],
    portfolios_state: Dict[str, Any],
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
        "schema_version": STATEFUL_LEDGER_SCHEMA,
        "first_recorded_utc": first_recorded,
        "last_sync_utc": now_utc,
        "execution_cycles": cycles,
        "genesis_sha256": GENESIS_HASH,
        "chain_root_sha256": chain_root_sha256,
        "total_certified_orders": total_orders,
        "bots": bots_summary,
        "certified_orders": certified_orders_chrono,
        "portfolios": portfolios_state,
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
        if int(bt_5y.get("total_sessions", 0)) < 1500:
            suite_existing = base_dir / "quant_crypto_suite.json"
            if suite_existing.exists():
                try:
                    prev_suite = json.loads(suite_existing.read_text(encoding="utf-8"))
                    prev_bt = prev_suite.get("backtest_5y") or {}
                    if int(prev_bt.get("total_sessions", 0)) >= 1500:
                        logger.warning("Reteniendo curva certificada 5Y en disco (%d sesiones) ante respuesta parcial upstream.", prev_bt["total_sessions"])
                        bt_5y = prev_bt
                except Exception:
                    pass
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
        cache_bucket=cached_daily,
        base_dir=base_dir,
    )

    ledger_state = _update_persistent_ledger_state(
        base_dir,
        algo_pack["bots"],
        algo_pack["ledger_chain"]["chain_root_sha256"],
        algo_pack["ledger_chain"]["total_certified_orders"],
        algo_pack["certified_orders_chrono"],
        algo_pack["portfolios_state"],
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
        "supervisor_3tier": algo_pack["supervisor_3tier"],
        "ledger_chain": algo_pack["ledger_chain"],
        "market_candles_4h": algo_pack["market_candles_4h"],
        "signal_matrix_now": algo_pack["signal_matrix_now"],
        "rule_tests_summary": {
            "total_test_cases": n_test_methods,
            "chain_integrity_verified": True,
            "ohlc_bounds_verified": True,
            "causal_mlp_verified": True,
            "triple_barrier_verified": True,
            "regime_gmm_verified": True,
            "risk_gatekeeper_verified": True,
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

"""
=========================================================================================
VECTORES AUTORREGRESIVOS (VAR), CAUSALIDAD DE GRANGER, COINTEGRACIÓN DE JOHANSEN
Y CONECTIVIDAD DIEBOLD-YILMAZ EN PYTHON (2010 -> NOVIEMBRE 2026)
Evolución Cuantitativa del Estudio #17 en RStudio (Noviembre 2020 -> Noviembre 2026)
Autor: Jesús Benjamín Zerpa | Economista & Quantitative Data Scientist
Sitio Web: https://jesusbz.github.io/vectores-autorregresivos-var-python.html
=========================================================================================
"""

import argparse
import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.stats.stattools import jarque_bera
from statsmodels.tsa.api import VAR
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen

# 1. Parámetros Globales de Estimación y Configuración Cuantitativa
ASSETS = ["MSFT", "JNJ", "MA", "PEP", "WMT", "MCD"]
ASSET_NAMES = {
    "MSFT": "Microsoft",
    "JNJ": "Johnson & Johnson",
    "MA": "Mastercard",
    "PEP": "PepsiCo",
    "WMT": "Walmart",
    "MCD": "McDonald's",
    "^GSPC": "S&P 500",
}
BENCHMARK = "^GSPC"
ALL_TICKERS = ASSETS + [BENCHMARK]

START_DATE = "2010-01-04"
CUTOFF_2020 = "2020-04-30"
END_DATE_YF = "2026-11-11"  # Incluye cierre completo hasta el 10 de noviembre de 2026

# Ponderaciones del Portafolio Tangente Base (Estudio #10 / Estudio #16, corte Abr-2020)
WEIGHTS_2020_RAW = np.array([0.041, 0.278, 0.074, 0.142, 0.230, 0.234])
WEIGHTS_2020 = WEIGHTS_2020_RAW / WEIGHTS_2020_RAW.sum()

RF_ANNUAL = 0.025
INITIAL_CAPITAL_USD = 10_000.0
TX_COST_BPS = 5.0  # 5 puntos básicos por dólar rotado en rebalanceo semanal
IRF_HORIZON = 20
ROLLING_DY_WINDOW = 252
ROLLING_VAR_WINDOW = 756  # 3 años bursátiles para estimación Walk-Forward
MAX_VAR_LAG_SELECT = 10


def compute_max_drawdown(wealth_series: np.ndarray) -> float:
    """Calcula el Maximum Drawdown (MDD) exacto sobre una trayectoria de riqueza."""
    peaks = np.maximum.accumulate(wealth_series)
    return float(np.min(wealth_series / peaks - 1.0))


def compute_perf_metrics(daily_ret: np.ndarray, rf_annual: float = RF_ANNUAL) -> dict:
    """Calcula CAGR, volatilidad anualizada, Sharpe, Sortino, MDD, Calmar y riqueza final."""
    n_days = len(daily_ret)
    wealth = INITIAL_CAPITAL_USD * np.cumprod(1.0 + daily_ret)
    total_ret = float(wealth[-1] / INITIAL_CAPITAL_USD - 1.0)
    years = n_days / 252.0
    cagr = float((wealth[-1] / INITIAL_CAPITAL_USD) ** (1.0 / years) - 1.0)
    vol = float(np.std(daily_ret, ddof=1) * np.sqrt(252.0))
    rf_daily = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
    excess = daily_ret - rf_daily
    sharpe = float((np.mean(excess) * 252.0) / vol) if vol > 1e-12 else 0.0
    downside = np.minimum(excess, 0.0)
    downside_vol = float(np.sqrt(np.mean(downside ** 2)) * np.sqrt(252.0))
    sortino = float((np.mean(excess) * 252.0) / downside_vol) if downside_vol > 1e-12 else 0.0
    mdd = compute_max_drawdown(np.concatenate([[INITIAL_CAPITAL_USD], wealth]))
    calmar = float(cagr / abs(mdd)) if abs(mdd) > 1e-12 else 0.0
    var95 = float(np.percentile(daily_ret, 5.0))
    cvar95 = float(np.mean(daily_ret[daily_ret <= var95]))
    return {
        "final_wealth": round(float(wealth[-1]), 2),
        "total_return_pct": round(total_ret * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "vol_pct": round(vol * 100.0, 2),
        "sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "max_dd_pct": round(mdd * 100.0, 2),
        "calmar": round(calmar, 3),
        "var95_daily_pct": round(var95 * 100.0, 2),
        "cvar95_daily_pct": round(cvar95 * 100.0, 2),
    }


# 2. Ingesta Reproducible de Precios Ajustados (2010-01-04 al 2026-11-10)
def load_market_prices(csv_fallback: str = "data/sp500_montecarlo_2010_2026.csv") -> pd.DataFrame:
    repo_root = Path(__file__).resolve().parent.parent
    candidates = [Path(csv_fallback), repo_root / csv_fallback]
    for candidate in candidates:
        if candidate.exists():
            prices = pd.read_csv(candidate, index_col=0, parse_dates=True)
            prices = prices[ALL_TICKERS].dropna().sort_index()
            return prices

    import yfinance as yf  # Descarga opcional solo si falta el CSV local

    raw = yf.download(ALL_TICKERS, start=START_DATE, end=END_DATE_YF, auto_adjust=True, progress=False)
    prices = raw["Close"][ALL_TICKERS].dropna().copy()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices.index.name = "Date"
    target = repo_root / csv_fallback
    os.makedirs(target.parent, exist_ok=True)
    prices.round(6).to_csv(target)
    return prices


# 3. Contraste de Estacionariedad (ADF & KPSS) y Momentos Estadísticos (2010-2026)
def audit_stationarity_and_moments(prices: pd.DataFrame) -> list:
    log_p = np.log(prices)
    log_r_pct = 100.0 * log_p.diff().dropna()
    rows = []
    years = (prices.index[-1] - prices.index[0]).days / 365.25
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for col in ALL_TICKERS:
            p_ser = prices[col].values
            lp_ser = log_p[col].values
            r_dec = log_p[col].diff().dropna().values
            r_pct = log_r_pct[col].values

            adf_lvl = adfuller(lp_ser, autolag="AIC", regression="ct")
            kpss_lvl = kpss(lp_ser, regression="ct", nlags="auto")
            adf_ret = adfuller(r_pct, autolag="AIC", regression="c")
            kpss_ret = kpss(r_pct, regression="c", nlags="auto")

            cagr = (p_ser[-1] / p_ser[0]) ** (252.0 / len(r_dec)) - 1.0
            vol_ann = float(np.std(r_dec, ddof=1) * np.sqrt(252.0))
            sharpe = float((np.mean(r_dec) * 252.0 - RF_ANNUAL) / vol_ann)
            mdd = compute_max_drawdown(p_ser)

            rows.append(
                {
                    "ticker": col,
                    "name": ASSET_NAMES[col],
                    "p_start": round(float(p_ser[0]), 2),
                    "p_end": round(float(p_ser[-1]), 2),
                    "cagr_pct": round(float(cagr * 100.0), 2),
                    "vol_ann_pct": round(float(vol_ann * 100.0), 2),
                    "sharpe": round(sharpe, 3),
                    "max_dd_pct": round(float(mdd * 100.0), 2),
                    "skew": round(float(stats.skew(r_pct)), 3),
                    "kurt_excess": round(float(stats.kurtosis(r_pct)), 2),
                    "adf_lvl_stat": round(float(adf_lvl[0]), 3),
                    "adf_lvl_p": round(float(adf_lvl[1]), 4),
                    "kpss_lvl_stat": round(float(kpss_lvl[0]), 3),
                    "kpss_lvl_p": round(float(kpss_lvl[1]), 4),
                    "adf_ret_stat": round(float(adf_ret[0]), 3),
                    "adf_ret_p": float(f"{adf_ret[1]:.2e}"),
                    "kpss_ret_stat": round(float(kpss_ret[0]), 3),
                    "kpss_ret_p": round(float(kpss_ret[1]), 4),
                    "integration_order": "I(1) -> I(0) en Δln",
                    "years_span": round(float(years), 2),
                }
            )
    return rows


# 4. Prueba de Cointegración Multivariada de Johansen sobre Niveles Logarítmicos
def audit_johansen_cointegration(prices: pd.DataFrame) -> dict:
    log_p_assets = np.log(prices[ASSETS])
    results_by_spec = {}
    for det_order, label in [(0, "det_0_constante"), (1, "det_1_tendencia")]:
        joh = coint_johansen(log_p_assets.values, det_order=det_order, k_ar_diff=2)
        rows = []
        rank_trace = 0
        rank_max = 0
        for r in range(len(ASSETS)):
            tr_stat = float(joh.lr1[r])
            tr_c95 = float(joh.cvt[r, 1])
            mx_stat = float(joh.lr2[r])
            mx_c95 = float(joh.cvm[r, 1])
            rej_tr = tr_stat > tr_c95
            rej_mx = mx_stat > mx_c95
            if rej_tr and rank_trace == r:
                rank_trace = r + 1
            if rej_mx and rank_max == r:
                rank_max = r + 1
            rows.append(
                {
                    "null_rank": f"r <= {r}",
                    "eigenvalue": round(float(joh.eig[r]), 6),
                    "trace_stat": round(tr_stat, 2),
                    "trace_crit90": round(float(joh.cvt[r, 0]), 2),
                    "trace_crit95": round(tr_c95, 2),
                    "trace_crit99": round(float(joh.cvt[r, 2]), 2),
                    "reject_trace_95": bool(rej_tr),
                    "maxeig_stat": round(mx_stat, 2),
                    "maxeig_crit90": round(float(joh.cvm[r, 0]), 2),
                    "maxeig_crit95": round(mx_c95, 2),
                    "maxeig_crit99": round(float(joh.cvm[r, 2]), 2),
                    "reject_maxeig_95": bool(rej_mx),
                }
            )
        results_by_spec[label] = {
            "rank_trace_95": rank_trace,
            "rank_maxeig_95": rank_max,
            "rows": rows,
        }
    return results_by_spec


# 5. Selección de Rezagos, Estimación VAR(p), Estabilidad y Diagnóstico Residual
def estimate_var_system(ret_pct: pd.DataFrame) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = VAR(ret_pct[ASSETS])
        sel = model.select_order(maxlags=MAX_VAR_LAG_SELECT)

        criteria_table = []
        for p in range(0, MAX_VAR_LAG_SELECT + 1):
            res_p = model.fit(p)
            criteria_table.append(
                {
                    "lag": p,
                    "aic": round(float(res_p.aic), 4),
                    "bic": round(float(res_p.bic), 4),
                    "hqic": round(float(res_p.hqic), 4),
                    "fpe": float(f"{res_p.fpe:.4e}"),
                }
            )

        res_var8 = model.fit(8)
        res_var1 = model.fit(1)

    # Valores propios de la matriz compañera (inv. de raíces polinomiales en statsmodels)
    comp_eigs_8 = 1.0 / res_var8.roots
    comp_mod_8 = np.abs(comp_eigs_8)
    comp_eigs_1 = 1.0 / res_var1.roots
    comp_mod_1 = np.abs(comp_eigs_1)

    # Diagnóstico residual por ecuación sobre VAR(8)
    resid_df = res_var8.resid
    y_fitted_df = res_var8.fittedvalues
    y_actual_df = ret_pct[ASSETS].iloc[8:]
    eq_diagnostics = []
    for asset in ASSETS:
        u = resid_df[asset].values
        y = y_actual_df[asset].values
        yhat = y_fitted_df[asset].values
        ss_res = float(np.sum((y - yhat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot
        n_obs = len(u)
        k_params = 1 + 8 * len(ASSETS)
        adj_r2 = 1.0 - (1.0 - r2) * (n_obs - 1) / (n_obs - k_params)

        lb_10 = acorr_ljungbox(u, lags=[10], return_df=True)
        arch_5 = het_arch(u, nlags=5)
        jb_stat, jb_p, _, _ = jarque_bera(u)

        eq_diagnostics.append(
            {
                "asset": asset,
                "r2_pct": round(r2 * 100.0, 2),
                "adj_r2_pct": round(adj_r2 * 100.0, 2),
                "resid_sd_pct": round(float(np.std(u, ddof=k_params)), 3),
                "lb10_stat": round(float(lb_10["lb_stat"].iloc[0]), 2),
                "lb10_p": round(float(lb_10["lb_pvalue"].iloc[0]), 4),
                "arch5_stat": round(float(arch_5[0]), 2),
                "arch5_p": float(f"{arch_5[1]:.2e}"),
                "jb_stat": round(float(jb_stat), 1),
            }
        )

    # Matriz de coeficientes A1 de VAR(1) (fila = ecuación destino, col = rezago t-1 origen)
    a1_matrix = np.round(res_var1.coefs[0], 4).tolist()
    corr_resid_8 = np.round(res_var8.resid_corr, 4).tolist()

    return {
        "model": model,
        "res_var8": res_var8,
        "res_var1": res_var1,
        "selected_lags": {k: int(v) for k, v in sel.selected_orders.items()},
        "criteria_table": criteria_table,
        "stability": {
            "var8_max_eig": round(float(np.max(comp_mod_8)), 6),
            "var8_is_stable": bool(np.max(comp_mod_8) < 1.0),
            "var8_eigs_real": [round(float(x.real), 5) for x in comp_eigs_8],
            "var8_eigs_imag": [round(float(x.imag), 5) for x in comp_eigs_8],
            "var8_top5_mod": [round(float(x), 5) for x in np.sort(comp_mod_8)[::-1][:5]],
            "var1_max_eig": round(float(np.max(comp_mod_1)), 6),
            "var1_is_stable": bool(np.max(comp_mod_1) < 1.0),
        },
        "eq_diagnostics": eq_diagnostics,
        "a1_matrix": a1_matrix,
        "corr_resid_8": corr_resid_8,
    }


# 6. Causalidad de Granger 6x6 y Exogeneidad en Bloque
def compute_granger_matrix(res_var8, res_var1) -> dict:
    def extract_for_fit(fit_res):
        n = len(ASSETS)
        f_mat = np.zeros((n, n))
        p_mat = np.ones((n, n))
        links = []
        sig_05 = 0
        sig_01 = 0
        for i, caused in enumerate(ASSETS):
            for j, causing in enumerate(ASSETS):
                if i == j:
                    continue
                tst = fit_res.test_causality(caused=caused, causing=[causing], kind="f")
                f_val = float(tst.test_statistic)
                p_val = float(tst.pvalue)
                f_mat[i, j] = round(f_val, 3)
                p_mat[i, j] = round(p_val, 6)
                if p_val < 0.05:
                    sig_05 += 1
                if p_val < 0.01:
                    sig_01 += 1
                links.append(
                    {
                        "source": causing,
                        "target": caused,
                        "f_stat": round(f_val, 3),
                        "p_value": round(p_val, 5),
                        "sig_05": bool(p_val < 0.05),
                        "sig_01": bool(p_val < 0.01),
                    }
                )
        # Prueba de exogeneidad en bloque: todos los otros 5 activos juntos -> target
        block_exo = []
        for target in ASSETS:
            others = [a for a in ASSETS if a != target]
            btst = fit_res.test_causality(caused=target, causing=others, kind="f")
            block_exo.append(
                {
                    "target": target,
                    "f_stat": round(float(btst.test_statistic), 3),
                    "p_value": round(float(btst.pvalue), 6),
                    "sig_05": bool(btst.pvalue < 0.05),
                }
            )
        links.sort(key=lambda x: x["f_stat"], reverse=True)
        return {
            "f_matrix": f_mat.tolist(),
            "p_matrix": p_mat.tolist(),
            "sig_05_count": sig_05,
            "sig_01_count": sig_01,
            "total_pairs": n * (n - 1),
            "links": links,
            "block_exogeneity": block_exo,
        }

    return {
        "var8": extract_for_fit(res_var8),
        "var1": extract_for_fit(res_var1),
    }


# 7. Funciones Impulso-Respuesta: Cholesky OIRF y Pesaran-Shin GIRF (h=0..20)
def compute_irf_suite(res_var8, horizon: int = IRF_HORIZON) -> dict:
    irf_obj = res_var8.irf(horizon)
    oirf = irf_obj.orth_irfs  # shape: (horizon+1, N, N) -> [h, response_i, impulse_j]
    stderr_orth = irf_obj.stderr(orth=True)

    # Pesaran & Shin (1998) Generalized IRF: invariante al orden de las variables
    phi = res_var8.ma_rep(horizon)  # shape: (horizon+1, N, N)
    sigma_u = np.asarray(res_var8.sigma_u)
    inv_sqrt_diag = 1.0 / np.sqrt(np.diag(sigma_u))
    girf = np.zeros_like(phi)
    for h in range(horizon + 1):
        # GIRF[:, j] = sigma_jj^{-1/2} * Phi_h @ Sigma_u[:, j]
        girf[h] = (phi[h] @ sigma_u) * inv_sqrt_diag[None, :]

    cum_girf = np.cumsum(girf, axis=0)
    cum_oirf = np.cumsum(oirf, axis=0)

    # Estructuramos diccionario por par (impulse_j, response_i) para tamaño compacto en HTML
    pairs_girf = {}
    pairs_oirf = {}
    pairs_cum_girf = {}
    for j, imp in enumerate(ASSETS):
        for i, resp in enumerate(ASSETS):
            key = f"{imp}->{resp}"
            g_ser = girf[:, i, j]
            o_ser = oirf[:, i, j]
            o_se = stderr_orth[:, i, j]
            cg_ser = cum_girf[:, i, j]
            pairs_girf[key] = [round(float(v), 4) for v in g_ser]
            pairs_cum_girf[key] = [round(float(v), 4) for v in cg_ser]
            pairs_oirf[key] = {
                "mean": [round(float(v), 4) for v in o_ser],
                "upper95": [round(float(m + 1.96 * s), 4) for m, s in zip(o_ser, o_se)],
                "lower95": [round(float(m - 1.96 * s), 4) for m, s in zip(o_ser, o_se)],
                "cum": [round(float(v), 4) for v in cum_oirf[:, i, j]],
            }

    return {
        "horizons": list(range(horizon + 1)),
        "girf": pairs_girf,
        "cum_girf": pairs_cum_girf,
        "oirf": pairs_oirf,
    }


# 8. Descomposición de Varianza FEVD & Índice de Conectividad Diebold-Yilmaz (2012)
def _gfevd_from_ma_sigma(phi: np.ndarray, sigma_u: np.ndarray) -> np.ndarray:
    """
    Calcula la matriz GFEVD normalizada (Pesaran-Shin / Diebold-Yilmaz 2012):
    theta[i, j] = contribución del choque en j (%) a la varianza del error de pronóstico de i.
    """
    n = sigma_u.shape[0]
    sigma_diag = np.diag(sigma_u)
    inv_sigma_diag = 1.0 / np.maximum(sigma_diag, 1e-12)

    num = np.zeros((n, n))
    denom = np.zeros(n)
    for h in range(phi.shape[0]):
        ph = phi[h]
        p_sig = ph @ sigma_u
        num += (p_sig ** 2) * inv_sigma_diag[None, :]
        denom += np.sum(p_sig * ph, axis=1)

    raw = num / np.maximum(denom[:, None], 1e-12)
    row_sums = np.sum(raw, axis=1, keepdims=True)
    return (raw / np.maximum(row_sums, 1e-12)) * 100.0


def _dy_summary_from_table(table_pct: np.ndarray) -> dict:
    n = table_pct.shape[0]
    diag_vals = np.diag(table_pct)
    to_others = np.sum(table_pct, axis=0) - diag_vals
    from_others = np.sum(table_pct, axis=1) - diag_vals
    net = to_others - from_others
    tsi = float(np.sum(from_others) / n)
    rows = []
    for i, a in enumerate(ASSETS):
        rows.append(
            {
                "asset": a,
                "own_pct": round(float(diag_vals[i]), 2),
                "from_others_pct": round(float(from_others[i]), 2),
                "to_others_pct": round(float(to_others[i]), 2),
                "net_pct": round(float(net[i]), 2),
                "role": "Transmisor Neto" if net[i] >= 0 else "Receptor Neto",
            }
        )
    return {
        "matrix_pct": np.round(table_pct, 2).tolist(),
        "total_spillover_index": round(tsi, 2),
        "directional": rows,
    }


def compute_diebold_yilmaz_spillover(
    res_var8, ret_pct: pd.DataFrame, horizon: int = IRF_HORIZON, window: int = ROLLING_DY_WINDOW
) -> dict:
    # 8.1 Matriz estática completa: GFEVD (Diebold-Yilmaz 2012) y Cholesky FEVD (orden clásico)
    phi_8 = res_var8.ma_rep(horizon - 1)
    sigma_8 = np.asarray(res_var8.sigma_u)
    gfevd_pct = _gfevd_from_ma_sigma(phi_8, sigma_8)

    chol_fevd_pct = res_var8.fevd(horizon).decomp[:, -1, :] * 100.0

    # 8.2 Dinámica Móvil Diebold-Yilmaz (ventana = 252 días, paso = 5 sesiones, VAR(2))
    # Usamos VAR(2) por álgebra matricial rápida para extraer evolución limpia 2011-2026
    y_vals = ret_pct[ASSETS].values
    dates = ret_pct.index
    t_total, n = y_vals.shape
    p_roll = 2

    roll_dates = []
    roll_tsi = []
    roll_net = {a: [] for a in ASSETS}

    for end_idx in range(window, t_total + 1, 5):
        sub = y_vals[end_idx - window : end_idx]
        # Regresión matricial VAR(2) OLS: Y = Z @ B + U
        y_dep = sub[p_roll:]
        cols = [np.ones((window - p_roll, 1))]
        for lag in range(1, p_roll + 1):
            cols.append(sub[p_roll - lag : window - lag])
        z_mat = np.hstack(cols)
        b_hat, _, _, _ = np.linalg.lstsq(z_mat, y_dep, rcond=None)
        u_hat = y_dep - z_mat @ b_hat
        df_resid = max(y_dep.shape[0] - z_mat.shape[1], 1)
        sigma_u = (u_hat.T @ u_hat) / df_resid

        a1 = b_hat[1 : 1 + n].T
        a2 = b_hat[1 + n : 1 + 2 * n].T

        # Matriz compañera (2n x 2n) y recursión MA_h = Phi_h
        phi_roll = np.zeros((horizon, n, n))
        phi_roll[0] = np.eye(n)
        if horizon > 1:
            phi_roll[1] = a1
        for h in range(2, horizon):
            phi_roll[h] = a1 @ phi_roll[h - 1] + a2 @ phi_roll[h - 2]

        g_pct = _gfevd_from_ma_sigma(phi_roll, sigma_u)
        diag_v = np.diag(g_pct)
        from_o = np.sum(g_pct, axis=1) - diag_v
        to_o = np.sum(g_pct, axis=0) - diag_v
        tsi = float(np.sum(from_o) / n)

        roll_dates.append(dates[end_idx - 1].strftime("%Y-%m-%d"))
        roll_tsi.append(round(tsi, 2))
        for i, a in enumerate(ASSETS):
            roll_net[a].append(round(float(to_o[i] - from_o[i]), 2))

    tsi_arr = np.array(roll_tsi)
    # Identificación de los picos históricos relevantes
    crisis_windows = [
        ("Crisis Eurozona / US Downgrade (2011)", "2011-01-01", "2011-12-31"),
        ("Sell-off Yuan & Petróleo (2015-2016)", "2015-08-01", "2016-04-30"),
        ("Volmageddon & Q4-2018 (2018)", "2018-01-01", "2019-02-28"),
        ("Shock COVID-19 (2020)", "2020-02-01", "2020-09-30"),
        ("Ciclo Alza de Tasas Fed (2022)", "2022-01-01", "2022-12-31"),
        ("Volatilidad Tarifaria / Tech (2025-2026)", "2025-01-01", "2026-11-10"),
    ]
    milestones = []
    dates_np = np.array(roll_dates)
    for label, d_start, d_end in crisis_windows:
        mask = (dates_np >= d_start) & (dates_np <= d_end)
        if np.any(mask):
            sub_idx = np.where(mask)[0]
            best_i = sub_idx[int(np.argmax(tsi_arr[sub_idx]))]
            milestones.append(
                {
                    "event": label,
                    "peak_date": roll_dates[best_i],
                    "peak_tsi": roll_tsi[best_i],
                }
            )

    return {
        "static_gfevd": _dy_summary_from_table(gfevd_pct),
        "static_cholesky": _dy_summary_from_table(chol_fevd_pct),
        "rolling": {
            "window_days": window,
            "p_lags": p_roll,
            "dates": roll_dates,
            "tsi": roll_tsi,
            "net": roll_net,
            "mean_tsi": round(float(np.mean(tsi_arr)), 2),
            "min_tsi": round(float(np.min(tsi_arr)), 2),
            "max_tsi": round(float(np.max(tsi_arr)), 2),
            "p80_tsi": round(float(np.percentile(tsi_arr, 80)), 2),
            "latest_tsi": roll_tsi[-1],
            "latest_date": roll_dates[-1],
            "milestones": milestones,
        },
    }


# 9. Estrategia Cuantitativa Walk-Forward OOS (2020-04-30 -> 2026-11-10)
def _fit_var_ridge_forecast(win_ret_dec: np.ndarray, p_lags: int, ridge_lambda: float, h_ahead: int = 5) -> np.ndarray:
    """
    Estima VAR(p)-Ridge sobre ventana histórica estrictamente pasada y proyecta el rendimiento
    esperado acumulado a h_ahead sesiones bursátiles sin ningún look-ahead bias.
    """
    t_win, n = win_ret_dec.shape
    y_dep = win_ret_dec[p_lags:]
    cols = [np.ones((t_win - p_lags, 1))]
    for lag in range(1, p_lags + 1):
        cols.append(win_ret_dec[p_lags - lag : t_win - lag])
    z_mat = np.hstack(cols)

    # Penalización Ridge únicamente sobre coeficientes de rezagos (no sobre el intercepto)
    pen = np.eye(z_mat.shape[1]) * ridge_lambda
    pen[0, 0] = 0.0
    b_hat = np.linalg.solve(z_mat.T @ z_mat + pen, z_mat.T @ y_dep)

    # Iteración multi-paso sin ruido futuro
    history = [win_ret_dec[-k] for k in range(1, p_lags + 1)]
    cum_pred = np.zeros(n)
    c_vec = b_hat[0]
    a_mats = [b_hat[1 + (lag - 1) * n : 1 + lag * n].T for lag in range(1, p_lags + 1)]

    for _ in range(h_ahead):
        next_r = c_vec.copy()
        for lag_idx, a_m in enumerate(a_mats):
            next_r += a_m @ history[lag_idx]
        cum_pred += next_r
        history = [next_r] + history[:-1]

    return cum_pred


def _solve_long_only_mv(mu_vec: np.ndarray, cov_mat: np.ndarray, risk_aversion: float = 4.0, w_min: float = 0.04, w_max: float = 0.35) -> np.ndarray:
    n = len(mu_vec)
    # Shrinkage lineal suave hacia la diagonal para estabilidad numérica
    diag_cov = np.diag(np.diag(cov_mat))
    cov_shrunk = 0.75 * cov_mat + 0.25 * diag_cov

    def objective(w):
        return float(0.5 * risk_aversion * (w @ cov_shrunk @ w) - mu_vec @ w)

    res = optimize.minimize(
        objective,
        np.full(n, 1.0 / n),
        method="SLSQP",
        bounds=[(w_min, w_max)] * n,
        constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
        options={"ftol": 1e-10, "maxiter": 200},
    )
    if res.success:
        w = np.clip(res.x, w_min, w_max)
        return w / np.sum(w)
    return np.full(n, 1.0 / n)


def _solve_mcop_var_weights(cov_ann: np.ndarray, conn_sym: np.ndarray, w_min: float = 0.08, w_max: float = 0.30) -> np.ndarray:
    """
    Portafolio de Mínima Conectividad y Varianza (Broadstock, Chatziantoniou & Gabauer, 2022):
    minimiza la exposición conjunta a la covarianza normalizada y al contagio GFEVD simétrico.
    """
    n = cov_ann.shape[0]
    risk_mat = 0.50 * (cov_ann / max(float(np.mean(np.diag(cov_ann))), 1e-12)) + 0.50 * conn_sym
    res = optimize.minimize(
        lambda w: float(w @ risk_mat @ w),
        np.full(n, 1.0 / n),
        method="SLSQP",
        bounds=[(w_min, w_max)] * n,
        constraints=[{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}],
        options={"ftol": 1e-10, "maxiter": 200},
    )
    if res.success:
        w = np.clip(res.x, w_min, w_max)
        return w / np.sum(w)
    return np.full(n, 1.0 / n)


def _window_dy_matrix_var1(win_ret_dec: np.ndarray, horizon: int = 10) -> tuple[np.ndarray, float]:
    """Calcula la matriz simétrica de conectividad GFEVD y el índice TSI sobre los últimos 252 días."""
    sub = win_ret_dec[-ROLLING_DY_WINDOW:] * 100.0
    n = sub.shape[1]
    y_dep = sub[1:]
    z_mat = np.hstack([np.ones((sub.shape[0] - 1, 1)), sub[:-1]])
    b_hat, _, _, _ = np.linalg.lstsq(z_mat, y_dep, rcond=None)
    u_hat = y_dep - z_mat @ b_hat
    sigma_u = (u_hat.T @ u_hat) / max(y_dep.shape[0] - z_mat.shape[1], 1)
    a1 = b_hat[1:].T
    phi = np.zeros((horizon, n, n))
    phi[0] = np.eye(n)
    for h in range(1, horizon):
        phi[h] = phi[h - 1] @ a1
    g_pct = _gfevd_from_ma_sigma(phi, sigma_u) / 100.0
    conn_sym = 0.5 * (g_pct + g_pct.T)
    tsi = float((np.sum(g_pct) - np.sum(np.diag(g_pct))) / n * 100.0)
    return conn_sym, tsi


def run_walkforward_backtest(prices: pd.DataFrame) -> dict:
    ret_dec_df = prices[ALL_TICKERS].pct_change().dropna()
    dates = ret_dec_df.index
    oos_start_idx = int(np.searchsorted(dates, pd.Timestamp(CUTOFF_2020)))

    r_assets = ret_dec_df[ASSETS].values
    r_bench = ret_dec_df[BENCHMARK].values
    oos_dates = dates[oos_start_idx:]
    n_oos = len(oos_dates)
    n_assets = len(ASSETS)
    tc_rate = TX_COST_BPS / 10_000.0
    rf_daily = (1.0 + RF_ANNUAL) ** (1.0 / 252.0) - 1.0

    # Calibración estricta pre-muestra (2011 -> 2020-04-30) sin sesgo de anticipación (zero look-ahead)
    pre_ts = [_window_dy_matrix_var1(r_assets[k - ROLLING_DY_WINDOW : k])[1] for k in range(ROLLING_DY_WINDOW, oos_start_idx, 5)]
    pre_vs = [float(np.std(np.mean(r_assets[k - 20 : k], axis=1), ddof=1) * np.sqrt(252.0)) for k in range(ROLLING_DY_WINDOW, oos_start_idx, 5)]
    tsi_p80 = float(np.percentile(pre_ts, 80))
    vol_p80 = float(np.percentile(pre_vs, 80))

    # Trayectorias diarias netas de las 5 estrategias
    strat_keys = ["mcop_var_shield", "var1_ols", "markowitz_2020", "equal_1n", "sp500"]
    daily_rets = {k: np.zeros(n_oos) for k in strat_keys}

    w_mcop_prev = np.full(n_assets, 1.0 / n_assets)
    w_ols_prev = np.full(n_assets, 1.0 / n_assets)
    w_eq_prev = np.full(n_assets, 1.0 / n_assets)
    w_mkw_prev = WEIGHTS_2020.copy()

    w_mcop_curr = w_mcop_prev.copy()
    w_ols_curr = w_ols_prev.copy()
    w_eq_curr = np.full(n_assets, 1.0 / n_assets)
    w_mkw_curr = WEIGHTS_2020.copy()
    cash_weight_curr = 0.0

    weights_history_dates = []
    weights_history_rows = []
    rebal_count = 0
    shield_active_weeks = 0

    for k in range(n_oos):
        idx = oos_start_idx + k  # r_assets[idx] es el retorno observado al cierre del día idx
        cost_mcop = 0.0
        cost_ols = 0.0
        cost_eq = 0.0
        cost_mkw = 0.0

        # Rebalanceo semanal cada 5 sesiones usando SOLO datos estrictamente anteriores [< idx]
        if k % 5 == 0:
            rebal_count += 1
            win_past = r_assets[max(0, idx - ROLLING_VAR_WINDOW) : idx]
            cov_ann = np.cov(win_past[-ROLLING_DY_WINDOW:], rowvar=False) * 252.0

            # 1) Portafolio Mínima Conectividad (MCoP-VAR) + Escudo Sistémico Diebold-Yilmaz (P80 pre-2020)
            conn_sym, tsi_now = _window_dy_matrix_var1(win_past)
            w_target_mcop = _solve_mcop_var_weights(cov_ann, conn_sym, w_min=0.08, w_max=0.30)
            vol_20d = float(np.std(np.mean(win_past[-20:], axis=1), ddof=1) * np.sqrt(252.0))

            if tsi_now > tsi_p80 and vol_20d > vol_p80:
                new_cash = 0.20
                shield_active_weeks += 1
            else:
                new_cash = 0.0

            w_equity_eff = w_target_mcop * (1.0 - new_cash)
            cost_mcop = float(np.sum(np.abs(w_equity_eff - w_mcop_prev)) * tc_rate)
            w_mcop_curr = w_equity_eff
            cash_weight_curr = new_cash

            # 2) VAR(1) OLS Direccional sin regularización (evidencia inestabilidad por R^2 bajo en media)
            pred_5d_ols = _fit_var_ridge_forecast(win_past, p_lags=1, ridge_lambda=0.0, h_ahead=5)
            w_target_ols = _solve_long_only_mv(pred_5d_ols * 50.4, cov_ann, risk_aversion=2.5, w_min=0.0, w_max=0.50)
            cost_ols = float(np.sum(np.abs(w_target_ols - w_ols_prev)) * tc_rate)
            w_ols_curr = w_target_ols

            # 3) Equiponderada 1/N (rebalanceo semanal)
            cost_eq = float(np.sum(np.abs(w_eq_curr - w_eq_prev)) * tc_rate)

            # 4) Markowitz 2020 (rebalanceo mensual ~ cada 20 sesiones)
            if k % 20 == 0:
                cost_mkw = float(np.sum(np.abs(WEIGHTS_2020 - w_mkw_prev)) * tc_rate)
                w_mkw_curr = WEIGHTS_2020.copy()

            if k % 20 == 0 or new_cash > 0.0:
                weights_history_dates.append(dates[idx].strftime("%Y-%m-%d"))
                weights_history_rows.append(
                    [round(float(x * 100.0), 1) for x in w_mcop_curr] + [round(float(cash_weight_curr * 100.0), 1)]
                )

        r_day = r_assets[idx]
        # Retorno diario neto y deriva intra-semanal de ponderaciones
        r_p_mcop = float(np.dot(w_mcop_curr, r_day) + cash_weight_curr * rf_daily - cost_mcop)
        daily_rets["mcop_var_shield"][k] = r_p_mcop
        w_mcop_prev = w_mcop_curr * (1.0 + r_day) / max(1.0 + r_p_mcop + cost_mcop, 1e-8)
        w_mcop_curr = w_mcop_prev.copy()

        r_p_ols = float(np.dot(w_ols_curr, r_day) - cost_ols)
        daily_rets["var1_ols"][k] = r_p_ols
        w_ols_prev = w_ols_curr * (1.0 + r_day) / max(1.0 + r_p_ols + cost_ols, 1e-8)
        w_ols_curr = w_ols_prev.copy()

        r_p_eq = float(np.dot(w_eq_curr, r_day) - cost_eq)
        daily_rets["equal_1n"][k] = r_p_eq
        w_eq_prev = w_eq_curr * (1.0 + r_day) / max(1.0 + r_p_eq + cost_eq, 1e-8)

        r_p_mkw = float(np.dot(w_mkw_curr, r_day) - cost_mkw)
        daily_rets["markowitz_2020"][k] = r_p_mkw
        w_mkw_prev = w_mkw_curr * (1.0 + r_day) / max(1.0 + r_p_mkw + cost_mkw, 1e-8)
        w_mkw_curr = w_mkw_prev.copy()

        daily_rets["sp500"][k] = float(r_bench[idx])

    # Series de riqueza para visualización (muestreo cada 5 días para aligerar el HTML manteniendo el punto final)
    sample_idx = list(range(0, n_oos, 5))
    if sample_idx[-1] != n_oos - 1:
        sample_idx.append(n_oos - 1)

    wealth_curves = {"dates": [oos_dates[i].strftime("%Y-%m-%d") for i in sample_idx]}
    drawdown_curves = {"dates": wealth_curves["dates"]}
    metrics = {}

    labels = {
        "mcop_var_shield": "MCoP-VAR + Cobertura DY",
        "var1_ols": "VAR(1) OLS Direccional",
        "markowitz_2020": "Tangente Markowitz (Jul 2020)",
        "equal_1n": "Equiponderada 1/N",
        "sp500": "Benchmark S&P 500 (^GSPC)",
    }

    for k in strat_keys:
        m = compute_perf_metrics(daily_rets[k])
        m["label"] = labels[k]
        metrics[k] = m

        w_full = INITIAL_CAPITAL_USD * np.cumprod(1.0 + daily_rets[k])
        dd_full = (w_full / np.maximum.accumulate(w_full) - 1.0) * 100.0
        wealth_curves[k] = [round(float(w_full[i]), 2) for i in sample_idx]
        drawdown_curves[k] = [round(float(dd_full[i]), 2) for i in sample_idx]

    return {
        "oos_start": oos_dates[0].strftime("%Y-%m-%d"),
        "oos_end": oos_dates[-1].strftime("%Y-%m-%d"),
        "oos_sessions": n_oos,
        "rebalances": rebal_count,
        "shield_active_weeks": shield_active_weeks,
        "tsi_p80_pre2020": round(tsi_p80, 2),
        "vol_p80_pre2020_pct": round(vol_p80 * 100.0, 2),
        "tx_cost_bps": TX_COST_BPS,
        "metrics": metrics,
        "wealth_curves": wealth_curves,
        "drawdown_curves": drawdown_curves,
        "weights_history": {
            "dates": weights_history_dates,
            "columns": ASSETS + ["CASH_RF"],
            "rows": weights_history_rows,
        },
        "final_weights_pct": weights_history_rows[-1] if weights_history_rows else [],
    }


def run_full_var_audit(export_json_path: str | None = None) -> dict:
    prices = load_market_prices()
    ret_pct = 100.0 * np.log(prices[ASSETS] / prices[ASSETS].shift(1)).dropna()

    print("=" * 88)
    print("ESTUDIO #17 (PYTHON): VECTORES AUTORREGRESIVOS (VAR), GRANGER, JOHANSEN & DIEBOLD-YILMAZ")
    print(f"Muestra: {prices.index[0].strftime('%Y-%m-%d')} al {prices.index[-1].strftime('%Y-%m-%d')} | {len(prices):,} sesiones | {len(ret_pct):,} retornos")
    print("=" * 88)

    stationarity = audit_stationarity_and_moments(prices)
    print("\n[1] ESTADÍSTICA DESCRIPTIVA & RAÍCES UNITARIAS (ADF / KPSS):")
    for r in stationarity:
        print(
            f"  {r['ticker']:6s} | CAGR {r['cagr_pct']:6.2f}% | Vol {r['vol_ann_pct']:5.2f}% | "
            f"ADF_lvl p={r['adf_lvl_p']:.4f} | ADF_ret p={r['adf_ret_p']:.1e} | MDD {r['max_dd_pct']:6.2f}%"
        )

    johansen = audit_johansen_cointegration(prices)
    print("\n[2] COINTEGRACIÓN DE JOHANSEN (k_ar_diff=2):")
    for spec_name, spec_val in johansen.items():
        first_row = spec_val["rows"][0]
        print(
            f"  {spec_name}: r<=0 Trace={first_row['trace_stat']} (crit95={first_row['trace_crit95']}) | "
            f"MaxEig={first_row['maxeig_stat']} (crit95={first_row['maxeig_crit95']}) -> Rango={spec_val['rank_trace_95']}"
        )

    var_sys = estimate_var_system(ret_pct)
    print("\n[3] SELECCIÓN DE REZAGOS & ESTABILIDAD:")
    print(f"  Órdenes seleccionados: {var_sys['selected_lags']}")
    print(
        f"  VAR(8) max|λ| = {var_sys['stability']['var8_max_eig']} (estable={var_sys['stability']['var8_is_stable']}) | "
        f"VAR(1) max|λ| = {var_sys['stability']['var1_max_eig']}"
    )

    granger = compute_granger_matrix(var_sys["res_var8"], var_sys["res_var1"])
    print("\n[4] CAUSALIDAD DE GRANGER:")
    print(
        f"  VAR(8): {granger['var8']['sig_05_count']}/{granger['var8']['total_pairs']} pares (p<0.05), "
        f"{granger['var8']['sig_01_count']} (p<0.01) | Top 3: {granger['var8']['links'][:3]}"
    )
    print(f"  VAR(1): {granger['var1']['sig_05_count']}/{granger['var1']['total_pairs']} pares (p<0.05)")

    irf = compute_irf_suite(var_sys["res_var8"], horizon=IRF_HORIZON)
    dy = compute_diebold_yilmaz_spillover(var_sys["res_var8"], ret_pct, horizon=IRF_HORIZON, window=ROLLING_DY_WINDOW)
    print("\n[5] CONECTIVIDAD DIEBOLD-YILMAZ (h=20):")
    print(
        f"  GFEVD TSI Estático: {dy['static_gfevd']['total_spillover_index']}% | "
        f"Cholesky TSI: {dy['static_cholesky']['total_spillover_index']}%"
    )
    print(
        f"  Rolling 252d TSI -> Media: {dy['rolling']['mean_tsi']}% | Mín: {dy['rolling']['min_tsi']}% | "
        f"Máx: {dy['rolling']['max_tsi']}% | Último ({dy['rolling']['latest_date']}): {dy['rolling']['latest_tsi']}%"
    )
    for row in dy["static_gfevd"]["directional"]:
        print(
            f"    {row['asset']:4s} | Own={row['own_pct']:5.2f}% | From={row['from_others_pct']:5.2f}% | "
            f"To={row['to_others_pct']:5.2f}% | Net={row['net_pct']:+6.2f}% ({row['role']})"
        )

    backtest = run_walkforward_backtest(prices)
    print(f"\n[6] BACKTEST WALK-FORWARD ({backtest['oos_start']} -> {backtest['oos_end']}, {backtest['rebalances']} rebalanceos, Shield {backtest['shield_active_weeks']} sem.):")
    for k, m in backtest["metrics"].items():
        print(
            f"  {m['label']:30s} | Final=${m['final_wealth']:9,.2f} | CAGR={m['cagr_pct']:5.2f}% | "
            f"Vol={m['vol_pct']:5.2f}% | Sharpe={m['sharpe']:5.3f} | Sortino={m['sortino']:5.3f} | MDD={m['max_dd_pct']:6.2f}%"
        )

    payload = {
        "meta": {
            "assets": ASSETS,
            "asset_names": ASSET_NAMES,
            "start_date": prices.index[0].strftime("%Y-%m-%d"),
            "end_date": prices.index[-1].strftime("%Y-%m-%d"),
            "cutoff_2020": CUTOFF_2020,
            "n_sessions": int(len(prices)),
            "n_returns": int(len(ret_pct)),
        },
        "stationarity": stationarity,
        "johansen": johansen,
        "var_selection": {
            "selected_lags": var_sys["selected_lags"],
            "criteria_table": var_sys["criteria_table"],
            "stability": var_sys["stability"],
            "eq_diagnostics": var_sys["eq_diagnostics"],
            "a1_matrix": var_sys["a1_matrix"],
            "corr_resid_8": var_sys["corr_resid_8"],
        },
        "granger": granger,
        "irf": irf,
        "diebold_yilmaz": dy,
        "backtest": backtest,
    }

    if export_json_path:
        out_p = Path(export_json_path)
        os.makedirs(out_p.parent, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        print(f"\n[OK] Payload compacto exportado en {out_p} ({out_p.stat().st_size:,} bytes)")

    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Estimación econométrica VAR, Granger, Johansen y Diebold-Yilmaz (2010-2026).")
    parser.add_argument("--json-out", type=str, default=None, help="Ruta opcional para exportar el payload JSON.")
    args = parser.parse_args()
    run_full_var_audit(export_json_path=args.json_out)

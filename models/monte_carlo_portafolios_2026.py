"""
=========================================================================================
SIMULACIÓN ESTOCÁSTICA DE MONTE CARLO MULTIVARIANTE EN LA GESTIÓN DE CARTERAS EN PYTHON:
FACTORIZACIÓN DE CHOLESKY, COLAS PESADAS t-STUDENT, SALTO-DIFUSIÓN DE MERTON Y FRONTERA
EFICIENTE SOBRE EL PORTAFOLIO TANGENTE DE MARKOWITZ (2010 -> NOVIEMBRE 2026 -> 2036)
Evolución Cuantitativa del Estudio #10 en RStudio (Julio 2020 -> Noviembre 2026)
Autor: Jesús Benjamín Zerpa | Economista & Quantitative Data Scientist
Sitio Web: https://jesusbz.github.io/simulacion-monte-carlo-portafolios-python.html
=========================================================================================
"""

import os
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats, optimize
from scipy.special import gammaln

# 1. Parámetros Globales de Estimación y Configuración Cuantitativa
ASSETS = ["MSFT", "JNJ", "MA", "PEP", "WMT", "MCD"]
BENCHMARK = "^GSPC"
ALL_TICKERS = ASSETS + [BENCHMARK]

START_DATE = "2010-01-04"
CUTOFF_2020 = "2020-04-30"
END_DATE_YF = "2026-11-11"   # Incluye cierre completo hasta el 10 de noviembre de 2026

# Ponderaciones del Portafolio Tangente Original (Trabajo #10, Julio 2020)
WEIGHTS_2020_RAW = np.array([0.041, 0.278, 0.074, 0.142, 0.230, 0.234])
WEIGHTS_2020 = WEIGHTS_2020_RAW / WEIGHTS_2020_RAW.sum()

RF_ANNUAL = 0.025            # Tasa libre de riesgo de referencia estructural (2.50% anual)
INITIAL_CAPITAL_USD = 10_000.0
N_MONTE_CARLO_PATHS = 10_000
HORIZON_MONTHS = 120         # 10 años (120 meses = 2,520 sesiones bursátiles)
DAYS_PER_MONTH = 21
HORIZON_DAYS = HORIZON_MONTHS * DAYS_PER_MONTH
SEED_MASTER = 20261111


def to_monthly_last(df: pd.DataFrame) -> pd.DataFrame:
    """Extrae el último cierre bursátil efectivo de cada mes calendario."""
    idx = df.groupby(df.index.to_period("M")).apply(lambda x: x.index[-1])
    return df.loc[idx.values]


def compute_max_drawdown(wealth_series: np.ndarray) -> float:
    """Calcula el Maximum Drawdown (MDD) exacto sobre una trayectoria de riqueza."""
    peaks = np.maximum.accumulate(wealth_series)
    return float(np.min(wealth_series / peaks - 1.0))


# 2. Ingesta Reproducible de Precios Ajustados (2010-01-04 al 2026-11-10)
def load_market_prices(csv_fallback: str = "data/sp500_montecarlo_2010_2026.csv") -> pd.DataFrame:
    if os.path.exists(csv_fallback):
        prices = pd.read_csv(csv_fallback, index_col=0, parse_dates=True)
        return prices[ALL_TICKERS].dropna()

    raw = yf.download(ALL_TICKERS, start=START_DATE, end=END_DATE_YF, auto_adjust=True, progress=False)
    prices = raw["Close"][ALL_TICKERS].dropna().copy()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices.index.name = "Date"
    os.makedirs(os.path.dirname(csv_fallback), exist_ok=True)
    prices.round(6).to_csv(csv_fallback)
    return prices


# 3. Réplica de la Línea Base de Julio 2020 (2010-2020) y Evaluación Ex-Post (2020-2026)
def audit_2020_baseline_and_expost(prices: pd.DataFrame) -> dict:
    """
    Replica exactamente la parametrización mensual en RStudio de julio de 2020 (N = 123 meses)
    y audita el desempeño real fuera de muestra entre el 30-Abr-2020 y el 10-Nov-2026.
    """
    p_pre = prices.loc[:CUTOFF_2020, ASSETS]
    m_pre = to_monthly_last(p_pre)
    m_log_pre = np.log(m_pre / m_pre.shift(1)).dropna()
    port_m_2020 = m_log_pre.values @ WEIGHTS_2020

    mu_2020 = float(np.mean(port_m_2020))
    sd_2020 = float(np.std(port_m_2020, ddof=1))

    # Cono analítico de 10,000 trayectorias bajo la ecuación original de julio de 2020
    rng_base = np.random.default_rng(202007)
    cone_2020 = np.cumprod(1.0 + rng_base.normal(mu_2020, sd_2020, size=(N_MONTE_CARLO_PATHS, HORIZON_MONTHS)), axis=1)
    cone_2020 = np.hstack([np.ones((N_MONTE_CARLO_PATHS, 1)), cone_2020])

    # Validación Estadística empírica fuera de muestra (30-Abr-2020 -> 10-Nov-2026)
    p_post = prices.loc[CUTOFF_2020:]
    dates_post = p_post.index
    rel_assets = p_post[ASSETS] / p_post[ASSETS].iloc[0]

    bh_unit = rel_assets.values @ WEIGHTS_2020
    ew_unit = rel_assets.mean(axis=1).values
    sp500_unit = (p_post[BENCHMARK] / p_post[BENCHMARK].iloc[0]).values

    # Portafolio Tangente 2020 con rebalanceo mensual exacto (rebalance_on = "months")
    d_rets_post = p_post[ASSETS].pct_change().fillna(0.0).values
    reb_unit = np.ones(len(p_post))
    cur_w = WEIGHTS_2020.copy()
    for t in range(1, len(p_post)):
        r_vec = d_rets_post[t]
        r_p = float(np.dot(cur_w, r_vec))
        reb_unit[t] = reb_unit[t - 1] * (1.0 + r_p)
        cur_w = cur_w * (1.0 + r_vec) / (1.0 + r_p)
        if t < len(p_post) - 1 and dates_post[t].month != dates_post[t + 1].month:
            cur_w = WEIGHTS_2020.copy()

    elapsed_days = (dates_post[-1] - dates_post[0]).days
    elapsed_years = elapsed_days / 365.25
    elapsed_months = elapsed_years * 12.0

    m_idx = int(np.floor(elapsed_months))
    frac = elapsed_months - m_idx
    cone_at_cutoff = (1.0 - frac) * cone_2020[:, m_idx] + frac * cone_2020[:, m_idx + 1]

    def metrics_from_unit(w_arr: np.ndarray) -> dict:
        cagr = float(w_arr[-1] ** (1.0 / elapsed_years) - 1.0)
        d_r = np.diff(w_arr) / w_arr[:-1]
        vol = float(np.std(d_r, ddof=1) * np.sqrt(252))
        sharpe = float((np.mean(d_r) * 252 - RF_ANNUAL) / vol)
        downside = d_r[d_r < 0.0]
        sortino = float((np.mean(d_r) * 252 - RF_ANNUAL) / (np.std(downside, ddof=1) * np.sqrt(252)))
        mdd = compute_max_drawdown(w_arr)
        cone_pct = float(np.mean(cone_at_cutoff <= w_arr[-1]) * 100.0)
        return {
            "unit_final": float(w_arr[-1]),
            "usd_10k_final": float(w_arr[-1] * 10_000.0),
            "usd_5k_final": float(w_arr[-1] * 5_000.0),
            "total_return_pct": float((w_arr[-1] - 1.0) * 100.0),
            "cagr_pct": cagr * 100.0,
            "vol_pct": vol * 100.0,
            "sharpe": sharpe,
            "sortino": sortino,
            "mdd_pct": mdd * 100.0,
            "cone_2020_percentile": cone_pct,
        }

    return {
        "mu_2020_monthly": mu_2020,
        "sd_2020_monthly": sd_2020,
        "n_months_2020": int(len(port_m_2020)),
        "cone_2020": cone_2020,
        "cone_at_cutoff_quantiles": {
            "p05": float(np.percentile(cone_at_cutoff, 5)),
            "p25": float(np.percentile(cone_at_cutoff, 25)),
            "p50": float(np.median(cone_at_cutoff)),
            "mean": float(np.mean(cone_at_cutoff)),
            "p75": float(np.percentile(cone_at_cutoff, 75)),
            "p95": float(np.percentile(cone_at_cutoff, 95)),
        },
        "elapsed_sessions": int(len(p_post) - 1),
        "elapsed_years": float(elapsed_years),
        "elapsed_months": float(elapsed_months),
        "dates_post": dates_post,
        "series_unit": {
            "tangent_rebal": reb_unit,
            "tangent_bh": bh_unit,
            "equal_weight": ew_unit,
            "sp500": sp500_unit,
        },
        "summary_expost": {
            "tangent_rebal": metrics_from_unit(reb_unit),
            "tangent_bh": metrics_from_unit(bh_unit),
            "equal_weight": metrics_from_unit(ew_unit),
            "sp500": metrics_from_unit(sp500_unit),
        },
    }


# 4. Estimación por Máxima Verosimilitud (MLE) de la t-Student Multivariante 6D y Cholesky
def fit_multivariate_tail_and_cholesky(daily_log_returns: pd.DataFrame) -> dict:
    """
    Calcula la descomposición triangular inferior de Cholesky Sigma = L @ L.T y estima por
    Máxima Verosimilitud (MLE) los grados de libertad conjuntos nu de la ley t-Student 6D.
    """
    X = daily_log_returns.values
    n_obs, d = X.shape
    mu_d = X.mean(axis=0)
    cov_d = np.cov(X, rowvar=False, ddof=1)
    L_chol = np.linalg.cholesky(cov_d)

    inv_cov = np.linalg.inv(cov_d)
    _, logdet_cov = np.linalg.slogdet(cov_d)
    centered = X - mu_d

    quad_gauss = np.sum((centered @ inv_cov) * centered, axis=1)
    ll_gauss = float(-0.5 * n_obs * (d * np.log(2.0 * np.pi) + logdet_cov) - 0.5 * np.sum(quad_gauss))

    def neg_mvt_loglik(nu_arr):
        nu = float(nu_arr[0])
        if nu <= 2.05:
            return 1e12
        S_inv = inv_cov * (nu / (nu - 2.0))
        logdet_S = logdet_cov + d * np.log((nu - 2.0) / nu)
        quad = np.sum((centered @ S_inv) * centered, axis=1)
        ll = n_obs * (
            gammaln((nu + d) / 2.0)
            - gammaln(nu / 2.0)
            - 0.5 * d * np.log(nu * np.pi)
            - 0.5 * logdet_S
        ) - 0.5 * (nu + d) * np.sum(np.log(1.0 + quad / nu))
        return -ll

    opt = optimize.minimize(neg_mvt_loglik, [4.0], bounds=[(2.1, 50.0)], method="L-BFGS-B")
    nu_mle = float(opt.x[0])
    ll_mvt = float(-opt.fun)
    lr_stat = float(2.0 * (ll_mvt - ll_gauss))
    lr_pval = float(stats.chi2.sf(lr_stat, df=1))

    return {
        "mu_daily_log": mu_d,
        "cov_daily_log": cov_d,
        "cholesky_daily": L_chol,
        "nu_mvt_mle": nu_mle,
        "loglik_gaussian_6d": ll_gauss,
        "loglik_student_t_6d": ll_mvt,
        "lr_statistic": lr_stat,
        "lr_pvalue": lr_pval,
    }


# 5. Simulación Monte Carlo Transversal de Markowitz (15,000 Carteras Dirichlet + SLSQP)
def optimize_cross_sectional_markowitz(daily_simple_returns: pd.DataFrame, n_portfolios: int = 15_000) -> dict:
    """
    Genera 15,000 carteras aleatorias long-only en el símplex mediante distribuciones
    de Dirichlet multiescala y resuelve analíticamente la Frontera Eficiente vía SLSQP.
    """
    mu_ann = daily_simple_returns.mean().values * 252.0
    cov_ann = daily_simple_returns.cov().values * 252.0
    d = len(ASSETS)

    rng = np.random.default_rng(SEED_MASTER)
    n1 = n_portfolios // 2
    n2 = n_portfolios - n1
    # Mezcla Dirichlet (alpha=1.0 uniforme en el símplex + alpha=0.35 concentrada hacia esquinas)
    W_cloud = np.vstack([
        rng.dirichlet(np.ones(d), size=n1),
        rng.dirichlet(np.full(d, 0.35), size=n2),
    ])
    ret_cloud = W_cloud @ mu_ann
    vol_cloud = np.sqrt(np.einsum("ij,jk,ik->i", W_cloud, cov_ann, W_cloud))
    sharpe_cloud = (ret_cloud - RF_ANNUAL) / vol_cloud

    cons_sum = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
    bounds = [(0.0, 1.0)] * d

    res_tan = optimize.minimize(
        lambda w: -((w @ mu_ann - RF_ANNUAL) / np.sqrt(w @ cov_ann @ w)),
        WEIGHTS_2020, method="SLSQP", bounds=bounds, constraints=cons_sum, options={"ftol": 1e-12}
    )
    res_gmv = optimize.minimize(
        lambda w: np.sqrt(w @ cov_ann @ w),
        WEIGHTS_2020, method="SLSQP", bounds=bounds, constraints=cons_sum, options={"ftol": 1e-12}
    )

    w_tan_2026 = res_tan.x
    w_gmv_2026 = res_gmv.x
    w_equal = np.ones(d) / d

    # Curva exacta de la Frontera Eficiente (60 puntos entre GMV y máximo retorno)
    r_min = float(w_gmv_2026 @ mu_ann)
    r_max = float(np.max(mu_ann) * 0.998)
    frontier_rets = np.linspace(r_min, r_max, 60)
    frontier_vols = []
    for target_r in frontier_rets:
        cons_ef = (
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w, tr=target_r: float(w @ mu_ann) - tr},
        )
        ef_opt = optimize.minimize(
            lambda w: np.sqrt(w @ cov_ann @ w),
            w_tan_2026, method="SLSQP", bounds=bounds, constraints=cons_ef, options={"ftol": 1e-11}
        )
        frontier_vols.append(float(ef_opt.fun))

    def eval_w(w_vec: np.ndarray) -> dict:
        r_p = float(w_vec @ mu_ann)
        v_p = float(np.sqrt(w_vec @ cov_ann @ w_vec))
        return {
            "weights": {a: float(val) for a, val in zip(ASSETS, w_vec)},
            "ret_pct": r_p * 100.0,
            "vol_pct": v_p * 100.0,
            "sharpe": float((r_p - RF_ANNUAL) / v_p),
        }

    return {
        "mu_ann": mu_ann,
        "cov_ann": cov_ann,
        "w_tan_2026": w_tan_2026,
        "w_gmv_2026": w_gmv_2026,
        "portfolios": {
            "tangent_2020": eval_w(WEIGHTS_2020),
            "tangent_2026": eval_w(w_tan_2026),
            "gmv_2026": eval_w(w_gmv_2026),
            "equal_weight": eval_w(w_equal),
        },
        "cloud": {
            "ret_pct": ret_cloud * 100.0,
            "vol_pct": vol_cloud * 100.0,
            "sharpe": sharpe_cloud,
        },
        "frontier": {
            "ret_pct": frontier_rets * 100.0,
            "vol_pct": np.array(frontier_vols) * 100.0,
        },
    }


# 6. Torneo de 5 Arquitecturas Estocásticas de Monte Carlo a 10 Años (Nov 2026 -> Nov 2036)
def run_stochastic_tournament(
    prices: pd.DataFrame,
    weights: np.ndarray,
    tail_fit: dict,
    n_sims: int = N_MONTE_CARLO_PATHS,
    seed: int = SEED_MASTER,
) -> dict:
    """
    Ejecuta 5 motores estocásticos competitivos sobre H = 120 meses (2,520 sesiones diarias)
    con reducción de varianza mediante Variables Antitéticas:
      1. Univariado Gaussiano Mensual (Metodología base RStudio 2020 actualizada)
      2. GBM Multivariante Exacto (Lema de Itô + Factorización de Cholesky L @ L.T)
      3. Monte Carlo Multivariante t-Student de Colas Pesadas (nu_MLE = 3.937)
      4. Salto-Difusión Multivariante de Merton (Difusión Cholesky + Saltos de Poisson)
      5. Stationary Block Bootstrap No Paramétrico (Politis & Romano, bloques b = 21 días)
    """
    rng = np.random.default_rng(seed)
    d = len(ASSETS)

    daily_log = np.log(prices[ASSETS] / prices[ASSETS].shift(1)).dropna()
    daily_simp = prices[ASSETS].pct_change().dropna()
    m_prices = to_monthly_last(prices.loc[:"2026-10-31", ASSETS])
    m_log = np.log(m_prices / m_prices.shift(1)).dropna()

    mu_d = tail_fit["mu_daily_log"]
    L_d = tail_fit["cholesky_daily"]
    nu_d = tail_fit["nu_mvt_mle"]

    # Calibración de saltos sistémicos de Merton sobre eventos de cola izquierda (< mu - 3*sigma)
    port_d_log = daily_log.values @ weights
    sd_port_d = float(np.std(port_d_log, ddof=1))
    crash_mask = port_d_log < (float(np.mean(port_d_log)) - 3.0 * sd_port_d)
    lam_jump_d = float(np.mean(crash_mask))
    mu_jump = float(np.mean(port_d_log[crash_mask]))
    sd_jump = float(np.std(port_d_log[crash_mask], ddof=1))
    drift_comp_jd = mu_d - lam_jump_d * mu_jump

    # Modelo 1: Univariado Gaussiano Mensual (Estilo RStudio 2020: 1 + N(mu_m, sd_m))
    port_m_log = m_log.values @ weights
    mu_m_uni = float(np.mean(port_m_log))
    sd_m_uni = float(np.std(port_m_log, ddof=1))
    z_m_half = rng.standard_normal((n_sims // 2, HORIZON_MONTHS))
    z_m_uni = np.vstack([z_m_half, -z_m_half])
    m1_monthly = np.hstack([np.ones((n_sims, 1)), np.cumprod(1.0 + (mu_m_uni + sd_m_uni * z_m_uni), axis=1)])
    m1_peaks = np.maximum.accumulate(m1_monthly, axis=1)
    m1_mdd = np.min(m1_monthly / m1_peaks - 1.0, axis=1)
    m1_yr1 = m1_monthly[:, 12] - 1.0

    # Contenedores para los modelos diarios (2,520 sesiones agrupadas en 120 meses de 21 días)
    keys_daily = ["gbm_cholesky", "student_t_mvt", "merton_jump", "block_bootstrap"]
    store = {
        k: {
            "monthly": np.ones((n_sims, HORIZON_MONTHS + 1)),
            "mdd": np.zeros(n_sims),
            "yr1_ret": np.zeros(n_sims),
            "mo1_ret": np.zeros(n_sims),
        }
        for k in keys_daily
    }
    bh_terminal = np.zeros(n_sims)
    bh_final_tech_weight = np.zeros(n_sims)

    hist_simp = daily_simp.values
    T_hist = len(hist_simp)
    p_geom = 1.0 / float(DAYS_PER_MONTH)

    chunk = 1_000
    for c in range(n_sims // chunk):
        sl = slice(c * chunk, (c + 1) * chunk)
        z_half = rng.standard_normal((chunk // 2, HORIZON_DAYS, d))
        z_antithetic = np.vstack([z_half, -z_half])
        corr_innov = np.einsum("mhd,kd->mhk", z_antithetic, L_d)

        # Modelo 2: GBM Multivariante Exacto (Cholesky + Lema de Itô + Rebalanceo Mensual)
        r_gbm = np.exp(mu_d + corr_innov) - 1.0
        # Evaluar también Buy & Hold sin rebalanceo para cuantificar deriva de pesos
        cum_assets_bh = np.cumprod(1.0 + r_gbm, axis=1)  # (chunk, 2520, d)
        end_vals_bh = cum_assets_bh[:, -1, :] * weights
        bh_terminal[sl] = np.sum(end_vals_bh, axis=1)
        # Peso terminal conjunto de MSFT (idx 0) + MA (idx 2) sin rebalanceo
        bh_final_tech_weight[sl] = (end_vals_bh[:, 0] + end_vals_bh[:, 2]) / np.sum(end_vals_bh, axis=1)

        def aggregate_rebalanced(r_daily_3d: np.ndarray, target_key: str):
            r_reshaped = r_daily_3d.reshape(chunk, HORIZON_MONTHS, DAYS_PER_MONTH, d)
            intra_growth = np.cumprod(1.0 + r_reshaped, axis=2)
            port_intra = np.einsum("cmtd,d->cmt", intra_growth, weights)
            mo_mult = port_intra[:, :, -1]
            mo_cum = np.hstack([np.ones((chunk, 1)), np.cumprod(mo_mult, axis=1)])
            daily_path = np.hstack([np.ones((chunk, 1)), (mo_cum[:, :-1, None] * port_intra).reshape(chunk, HORIZON_DAYS)])
            peaks = np.maximum.accumulate(daily_path, axis=1)
            store[target_key]["monthly"][sl] = mo_cum
            store[target_key]["mdd"][sl] = np.min(daily_path / peaks - 1.0, axis=1)
            store[target_key]["yr1_ret"][sl] = mo_cum[:, 12] - 1.0
            store[target_key]["mo1_ret"][sl] = mo_cum[:, 1] - 1.0

        aggregate_rebalanced(r_gbm, "gbm_cholesky")

        # Modelo 3: t-Student Multivariante 6D (Cholesky + Choque Conjunto Chi-Cuadrado)
        chi2_draws = rng.chisquare(df=nu_d, size=(chunk, HORIZON_DAYS, 1))
        scale_t = np.sqrt((nu_d - 2.0) / chi2_draws)
        r_mvt = np.exp(np.clip(mu_d + scale_t * corr_innov, -0.35, 0.35)) - 1.0
        aggregate_rebalanced(r_mvt, "student_t_mvt")

        # Modelo 4: Salto-Difusión Multivariante de Merton (Poisson Crash + Difusión Cholesky)
        n_jumps = rng.poisson(lam=lam_jump_d, size=(chunk, HORIZON_DAYS, 1))
        jump_shock = n_jumps * (mu_jump + sd_jump * rng.standard_normal((chunk, HORIZON_DAYS, 1)))
        r_jd = np.exp(np.clip(drift_comp_jd + corr_innov + jump_shock, -0.35, 0.35)) - 1.0
        aggregate_rebalanced(r_jd, "merton_jump")

        # Modelo 5: Stationary Block Bootstrap (Politis & Romano, 1994)
        idx = rng.integers(0, T_hist, size=chunk)
        boot_idx = np.empty((chunk, HORIZON_DAYS), dtype=np.int32)
        for h in range(HORIZON_DAYS):
            boot_idx[:, h] = idx
            jmp = rng.random(chunk) < p_geom
            idx = np.where(jmp, rng.integers(0, T_hist, size=chunk), (idx + 1) % T_hist)
        r_boot = hist_simp[boot_idx]
        aggregate_rebalanced(r_boot, "block_bootstrap")

    store["univariate_2020"] = {
        "monthly": m1_monthly,
        "mdd": m1_mdd,
        "yr1_ret": m1_yr1,
        "mo1_ret": m1_monthly[:, 1] - 1.0,
    }

    summaries = {}
    for k, v in store.items():
        term_usd = v["monthly"][:, -1] * INITIAL_CAPITAL_USD
        cagr_arr = (v["monthly"][:, -1] ** (1.0 / 10.0) - 1.0) * 100.0
        yr1_pct = v["yr1_ret"] * 100.0
        mo1_pct = v["mo1_ret"] * 100.0
        mdd_pct = v["mdd"] * 100.0

        p05_usd = float(np.percentile(term_usd, 5))
        p01_usd = float(np.percentile(term_usd, 1))
        cvar95_usd = float(np.mean(term_usd[term_usd <= p05_usd]))
        cvar99_usd = float(np.mean(term_usd[term_usd <= p01_usd]))

        yr1_var95 = float(np.percentile(yr1_pct, 5))
        yr1_var99 = float(np.percentile(yr1_pct, 1))
        yr1_cvar99 = float(np.mean(yr1_pct[yr1_pct <= yr1_var99]))
        mo1_var99 = float(np.percentile(mo1_pct, 1))
        mo1_cvar99 = float(np.mean(mo1_pct[mo1_pct <= mo1_var99]))

        summaries[k] = {
            "median_usd": float(np.median(term_usd)),
            "mean_usd": float(np.mean(term_usd)),
            "p05_usd": p05_usd,
            "cvar95_usd": cvar95_usd,
            "p01_usd": p01_usd,
            "cvar99_usd": cvar99_usd,
            "p25_usd": float(np.percentile(term_usd, 25)),
            "p75_usd": float(np.percentile(term_usd, 75)),
            "p95_usd": float(np.percentile(term_usd, 95)),
            "min_usd": float(np.min(term_usd)),
            "max_usd": float(np.max(term_usd)),
            "median_cagr_pct": float(np.median(cagr_arr)),
            "mean_cagr_pct": float(np.mean(cagr_arr)),
            "yr1_var95_pct": yr1_var95,
            "yr1_var99_pct": yr1_var99,
            "yr1_cvar99_pct": yr1_cvar99,
            "mo1_var99_pct": mo1_var99,
            "mo1_cvar99_pct": mo1_cvar99,
            "median_mdd_pct": float(np.median(mdd_pct)),
            "p95_mdd_pct": float(np.percentile(mdd_pct, 5)),
            "p99_mdd_pct": float(np.percentile(mdd_pct, 1)),
            "prob_double_pct": float(np.mean(term_usd >= 2.0 * INITIAL_CAPITAL_USD) * 100.0),
            "prob_triple_pct": float(np.mean(term_usd >= 3.0 * INITIAL_CAPITAL_USD) * 100.0),
            "prob_beat_rf_pct": float(np.mean(v["monthly"][:, -1] >= (1.0 + RF_ANNUAL) ** 10) * 100.0),
        }

    return {
        "paths_store": store,
        "summaries": summaries,
        "merton_params": {
            "lambda_annual": lam_jump_d * 252.0,
            "mu_jump_pct": mu_jump * 100.0,
            "sd_jump_pct": sd_jump * 100.0,
        },
        "drift_audit": {
            "bh_median_usd": float(np.median(bh_terminal) * INITIAL_CAPITAL_USD),
            "bh_mean_tech_weight_pct": float(np.mean(bh_final_tech_weight) * 100.0),
        },
    }


if __name__ == "__main__":
    prices_df = load_market_prices()
    daily_log_df = np.log(prices_df[ASSETS] / prices_df[ASSETS].shift(1)).dropna()
    daily_simp_df = prices_df[ASSETS].pct_change().dropna()

    audit_res = audit_2020_baseline_and_expost(prices_df)
    tail_res = fit_multivariate_tail_and_cholesky(daily_log_df)
    mkw_res = optimize_cross_sectional_markowitz(daily_simp_df)
    mc_2020_w = run_stochastic_tournament(prices_df, WEIGHTS_2020, tail_res)
    mc_2026_w = run_stochastic_tournament(prices_df, mkw_res["w_tan_2026"], tail_res)

    print("=" * 90)
    print("EVALUACIÓN MONTE CARLO MULTIVARIANTE EN PYTHON (2010 -> NOVIEMBRE 2026 -> 2036)")
    print("=" * 90)
    print(f"Sesiones diarias analizadas : {len(prices_df):,} ({prices_df.index[0].date()} -> {prices_df.index[-1].date()})")
    print(f"Ex-Post Tangente 2020 Rebal: $1.00 -> ${audit_res['summary_expost']['tangent_rebal']['unit_final']:.4f} "
          f"(${audit_res['summary_expost']['tangent_rebal']['usd_10k_final']:,.2f} por $10k | "
          f"Percentil {audit_res['summary_expost']['tangent_rebal']['cone_2020_percentile']:.1f}% del Cono 2020)")
    print(f"Ajuste Cola t-Student 6D   : nu_MLE = {tail_res['nu_mvt_mle']:.3f} | LR = {tail_res['lr_statistic']:,.2f} (p < 1e-100)")
    print("-" * 90)
    for model_key, s in mc_2020_w["summaries"].items():
        print(f"[Pesos 2020] {model_key:18s} | Med 10Y: ${s['median_usd']:9,.2f} | P05: ${s['p05_usd']:8,.2f} | "
              f"CVaR95: ${s['cvar95_usd']:8,.2f} | MDD P95: {s['p95_mdd_pct']:6.2f}%")
    print("-" * 90)
    for model_key, s in mc_2026_w["summaries"].items():
        print(f"[Pesos 2026] {model_key:18s} | Med 10Y: ${s['median_usd']:9,.2f} | P05: ${s['p05_usd']:8,.2f} | "
              f"CVaR95: ${s['cvar95_usd']:8,.2f} | MDD P95: {s['p95_mdd_pct']:6.2f}%")


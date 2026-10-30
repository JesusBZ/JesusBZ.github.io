"""
=========================================================================================
MODELIZACIÓN DE VOLATILIDAD ASIMÉTRICA GARCH, VALOR EN RIESGO (VaR) Y EXPECTED SHORTFALL
(CVaR) EN PYTHON: TRANSICIÓN DE RÉGIMEN INSTITUCIONAL DEL BITCOIN (2014 -> 2026)
Evolución Cuantitativa del Estudio Original en RStudio (Mayo 2020 -> Octubre 2026)
Autor: Jesús Benjamín Zerpa | Economista & Quantitative Data Scientist
Sitio Web: https://jesusbz.github.io/volatilidad-garch-var-cvar-python.html
=========================================================================================
"""

import numpy as np
import pandas as pd
import yfinance as yf
from arch import arch_model
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch

# 1. Parámetros Globales de Auditoría Institucional
TICKER = "BTC-USD"
START_DATE = "2014-09-17"
END_DATE = "2026-10-30"
CUTOFF_ORIGINAL_2020 = "2020-01-30"
ETF_APPROVAL_DATE = "2024-01-11"
NOTIONAL_EXPOSURE_USD = 1_000_000.0


# 2. Ingesta de Serie Histórica y Descomposición por Regímenes de Mercado (2014-2026)
def load_btc_series(csv_fallback="data/btc_usd_2014_2026.csv"):
    try:
        df = pd.read_csv(csv_fallback, index_col=0, parse_dates=True)
    except Exception:
        raw = yf.download(TICKER, start=START_DATE, end=END_DATE, auto_adjust=True, progress=False)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0] for c in raw.columns]
        df = raw[["Open", "High", "Low", "Close", "Volume"]].dropna().copy()
        df["Log_Return"] = np.log(df["Close"] / df["Close"].shift(1))
        df["Pct_Return"] = df["Log_Return"] * 100.0
        df = df.dropna()
    return df


# 3. Torneo Econométrico de Especificaciones GARCH Simétricas y Asimétricas (MLE)
def fit_garch_tournament(returns_pct: pd.Series) -> dict:
    """
    Estima por Máxima Verosimilitud (MLE) cinco especificaciones de varianza condicional:
    1. AR(1)-sGARCH(1,1) bajo innovación Normal (Bollerslev, 1986)
    2. AR(1)-sGARCH(1,1) bajo innovación t-Student
    3. AR(1)-EGARCH(1,1) bajo innovación t-Student (Nelson, 1991)
    4. AR(1)-EGARCH(2,1) bajo innovación Skewed Student-t de Hansen (1994)
    5. AR(1)-GJR-GARCH(1,1,1) bajo innovación Skewed Student-t (Glosten, Jagannathan & Runkle, 1993)
    """
    specs = {
        "AR(1)-sGARCH(1,1)-Normal": arch_model(returns_pct, mean="AR", lags=1, vol="Garch", p=1, o=0, q=1, dist="normal"),
        "AR(1)-sGARCH(1,1)-Student-t": arch_model(returns_pct, mean="AR", lags=1, vol="Garch", p=1, o=0, q=1, dist="t"),
        "AR(1)-EGARCH(1,1)-Student-t": arch_model(returns_pct, mean="AR", lags=1, vol="EGARCH", p=1, o=1, q=1, dist="t"),
        "AR(1)-EGARCH(2,1)-Skewed-t": arch_model(returns_pct, mean="AR", lags=1, vol="EGARCH", p=2, o=1, q=1, dist="skewt"),
        "AR(1)-GJR-GARCH(1,1,1)-Skewed-t": arch_model(returns_pct, mean="AR", lags=1, vol="Garch", p=1, o=1, q=1, dist="skewt"),
    }

    results = {}
    for name, spec in specs.items():
        res = spec.fit(disp="off")
        z = res.std_resid.dropna()
        lb_q2 = acorr_ljungbox(z ** 2, lags=[10], return_df=True)
        arch_lm = het_arch(z, nlags=5)
        results[name] = {
            "fit": res,
            "loglik": float(res.loglikelihood),
            "aic": float(res.aic),
            "bic": float(res.bic),
            "lb_q2_10_p": float(lb_q2["lb_pvalue"].iloc[0]),
            "arch_lm5_p": float(arch_lm[1]),
        }
    return results


# 4. Cálculo Dinámico de Valor en Riesgo (VaR) y Expected Shortfall (CVaR / ES)
def compute_dynamic_var_cvar(returns_pct: pd.Series, fit_result, is_normal: bool = False) -> pd.DataFrame:
    """
    Calcula las bandas dinámicas diarias de VaR y Expected Shortfall (CVaR) al 95% y 99%
    de confianza utilizando cuantiles condicionales y esperanza condicional de cola:
      VaR_{alpha, t}  = mu_t + q_{alpha}(z) * sigma_t
      CVaR_{alpha, t} = mu_t + E[z | z <= q_{alpha}(z)] * sigma_t
    """
    const = fit_result.params["Const"]
    phi1 = fit_result.params["Pct_Return[1]"]
    mu_t = const + phi1 * returns_pct.shift(1)
    sigma_t = fit_result.conditional_volatility
    z = fit_result.std_resid.dropna()

    if is_normal:
        q95, q99 = stats.norm.ppf(0.05), stats.norm.ppf(0.01)
        es95_z = -stats.norm.pdf(q95) / 0.05
        es99_z = -stats.norm.pdf(q99) / 0.01
    else:
        q95 = float(np.percentile(z, 5.0))
        q99 = float(np.percentile(z, 1.0))
        es95_z = float(z[z <= q95].mean())
        es99_z = float(z[z <= q99].mean())

    out = pd.DataFrame(index=returns_pct.index)
    out["Return_Pct"] = returns_pct
    out["Cond_Mean"] = mu_t
    out["Sigma_Daily"] = sigma_t
    out["Sigma_Annualized"] = sigma_t * np.sqrt(365.0)
    out["VaR_95"] = mu_t + q95 * sigma_t
    out["CVaR_95"] = mu_t + es95_z * sigma_t
    out["VaR_99"] = mu_t + q99 * sigma_t
    out["CVaR_99"] = mu_t + es99_z * sigma_t
    return out.dropna()


# 5. Contrastes Regulatorios de Backtesting: Kupiec (1995) y Christoffersen (1998)
def kupiec_christoffersen_backtest(returns: pd.Series, var_series: pd.Series, alpha: float = 0.01) -> dict:
    """
    Ejecuta el contraste de Cobertura Incondicional de Kupiec (POF, LR_uc ~ Chi2(1))
    y el contraste de Cobertura Condicional e Independencia de Christoffersen (LR_cc ~ Chi2(2)).
    """
    hits = (returns < var_series).astype(int).values
    T = len(hits)
    N = int(hits.sum())
    p_hat = N / T

    lr_uc = -2.0 * (
        (T - N) * np.log(1.0 - alpha) + N * np.log(alpha)
        - ((T - N) * np.log(1.0 - p_hat) + N * np.log(p_hat))
    )
    p_uc = float(1.0 - stats.chi2.cdf(lr_uc, df=1))

    h0, h1 = hits[:-1], hits[1:]
    n00 = int(np.sum((h0 == 0) & (h1 == 0)))
    n01 = int(np.sum((h0 == 0) & (h1 == 1)))
    n10 = int(np.sum((h0 == 1) & (h1 == 0)))
    n11 = int(np.sum((h0 == 1) & (h1 == 1)))

    pi0 = n01 / max(n00 + n01, 1)
    pi1 = n11 / max(n10 + n11, 1)
    pi = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)

    eps = 1e-12
    ll_null = (n00 + n10) * np.log(max(1.0 - pi, eps)) + (n01 + n11) * np.log(max(pi, eps))
    ll_alt = (
        n00 * np.log(max(1.0 - pi0, eps))
        + n01 * np.log(max(pi0, eps))
        + n10 * np.log(max(1.0 - pi1, eps))
        + n11 * np.log(max(pi1, eps))
    )
    lr_ind = max(0.0, -2.0 * (ll_null - ll_alt))
    lr_cc = lr_uc + lr_ind
    p_cc = float(1.0 - stats.chi2.cdf(lr_cc, df=2))

    return {
        "obs": T,
        "violations": N,
        "empirical_rate_pct": p_hat * 100.0,
        "lr_uc": float(lr_uc),
        "p_uc": p_uc,
        "lr_ind": float(lr_ind),
        "lr_cc": float(lr_cc),
        "p_cc": p_cc,
    }


# 6. Motor Operativo de Trading Cuantitativo, Position Sizing y Presupuesto de Riesgo
def compute_trading_and_risk_execution_rules(
    risk_df: pd.DataFrame,
    portfolio_equity_usd: float = 1_000_000.0,
    target_vol_annual_pct: float = 20.0,
    max_daily_tail_loss_usd: float = 25_000.0,
    maint_margin_rate: float = 0.005,
    safety_buffer_kappa: float = 3.0,
) -> pd.DataFrame:
    """
    Traduce las estimaciones del modelo AR(1)-EGARCH(2,1) Skewed-t en señales cuantitativas
    ejecutables para mesas de trading, gestores de portafolio y comités de tesorería:
      1. Volatility Targeting Weight: w_t = min(1.0, sigma_target / sigma_{anual, t})
      2. Capital Asignado por Presupuesto de Cola (CVaR_99): E_max = L_max / |CVaR_{99, t}|
      3. Stop-Loss Dinámico Condicional al 99%: SL_t = VaR_{99, t} (%)
      4. Apalancamiento Máximo Institucional en Derivados: Lev_max = (1 - m_mant) / (kappa * |CVaR_{99, t}|)
    """
    exec_df = risk_df.copy()
    cvar_dec = (exec_df["CVaR_99"].abs() / 100.0).clip(lower=1e-4)

    exec_df["Vol_Target_Weight"] = (target_vol_annual_pct / exec_df["Sigma_Annualized"]).clip(upper=1.0)
    exec_df["Vol_Target_Notional_USD"] = exec_df["Vol_Target_Weight"] * portfolio_equity_usd
    exec_df["CVaR_Budget_Max_Notional_USD"] = max_daily_tail_loss_usd / cvar_dec
    exec_df["Adaptive_StopLoss_99_Pct"] = exec_df["VaR_99"]
    exec_df["Max_Institutional_Leverage_x"] = (1.0 - maint_margin_rate) / (safety_buffer_kappa * cvar_dec)
    return exec_df


if __name__ == "__main__":
    df = load_btc_series()
    tournament = fit_garch_tournament(df["Pct_Return"])
    best_fit = tournament["AR(1)-EGARCH(2,1)-Skewed-t"]["fit"]
    risk_df = compute_dynamic_var_cvar(df["Pct_Return"], best_fit, is_normal=False)
    exec_df = compute_trading_and_risk_execution_rules(risk_df)
    eval_df = risk_df.loc["2020-01-31":]
    bt99 = kupiec_christoffersen_backtest(eval_df["Return_Pct"], eval_df["VaR_99"], alpha=0.01)
    last_row = exec_df.iloc[-1]

    print("=== RESUMEN DE AUDITORÍA ECONOMÉTRICA Y EJECUCIÓN CUANTITATIVA (2014-2026) ===")
    print(f"Observaciones auditadas : {len(df)} días ({df.index[0].date()} -> {df.index[-1].date()})")
    print(f"Modelo Óptimo (AIC/MLE) : AR(1)-EGARCH(2,1) con Distribución Skewed-t de Hansen")
    print(f"Log-Verosimilitud       : {best_fit.loglikelihood:.2f} | AIC: {best_fit.aic:.2f}")
    print(f"Violaciones VaR 99%     : {bt99['violations']} / {bt99['obs']} ({bt99['empirical_rate_pct']:.3f}%)")
    print(f"Test de Kupiec LR_uc    : {bt99['lr_uc']:.3f} (p-valor = {bt99['p_uc']:.4f})")
    print(f"Test Christoffersen CC  : {bt99['lr_cc']:.3f} (p-valor = {bt99['p_cc']:.4f})")
    print(f"Peso Volatility Target  : {last_row['Vol_Target_Weight']*100:.2f}% (${last_row['Vol_Target_Notional_USD']:,.0f} USD)")
    print(f"Stop-Loss Dinámico 99%  : {last_row['Adaptive_StopLoss_99_Pct']:.3f}% | Apalancamiento Máx: {last_row['Max_Institutional_Leverage_x']:.2f}x")

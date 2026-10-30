"""
=========================================================================================
DEEP PORTFOLIO OPTIMIZATION CON REDES NEURONALES LSTM EN PYTHON (PyTorch & NumPy/SciPy)
Evolución Cuantitativa del Portafolio Tangente de Markowitz (2020 -> 2026)
Autor: Jesús Benjamín Zerpa | Economista & Quantitative Data Scientist
Sitio Web: https://jesusbz.github.io/deep-portfolio-lstm-python.html
=========================================================================================
"""

import numpy as np
import pandas as pd
import yfinance as yf
import torch
import torch.nn as nn
import torch.optim as optim

# 1. Configuración del Universo Bursátil (S&P 500 - Cartera Original 2020)
TICKERS = ["MSFT", "JNJ", "MA", "PEP", "WMT", "MCD"]
BENCHMARK = "^GSPC"
CAPITAL_INICIAL = 5000.0
RF_ANNUAL = 0.025

# Pesos originales publicados en Abril 2020 (proyecto4.html)
W_TANGENTE_2020 = np.array([0.041, 0.278, 0.074, 0.142, 0.230, 0.234])
W_TANGENTE_2020 /= W_TANGENTE_2020.sum()

W_MINVAR_2020 = np.array([0.000, 0.319, 0.000, 0.204, 0.256, 0.221])
W_MINVAR_2020 /= W_MINVAR_2020.sum()


# 2. Extracción de Series Temporales e Ingeniería de Características (Feature Engineering)
def build_market_features(start_date="2010-01-01", end_date="2026-10-30"):
    raw = yf.download(TICKERS + [BENCHMARK], start=start_date, end=end_date, auto_adjust=True)
    prices = raw["Close"][TICKERS + [BENCHMARK]].dropna()
    ret_simple = prices[TICKERS].pct_change().dropna()
    ret_log = np.log(prices[TICKERS] / prices[TICKERS].shift(1)).dropna()

    # Indicadores multi-horizonte de Momentum, Volatilidad Realizada, Sharpe Móvil y Tendencia SMA-200
    m21 = ret_log.rolling(21).sum()
    m63 = ret_log.rolling(63).sum()
    m126 = ret_log.rolling(126).sum()
    m252 = ret_log.rolling(252).sum()
    vol21 = ret_log.rolling(21).std() * np.sqrt(252)
    vol63 = ret_log.rolling(63).std() * np.sqrt(252)
    sh126 = (ret_log.rolling(126).mean() * 252 - RF_ANNUAL) / (vol63 + 1e-6)
    sh252 = (ret_log.rolling(252).mean() * 252 - RF_ANNUAL) / (ret_log.rolling(252).std() * np.sqrt(252) + 1e-6)
    sma200 = np.log(prices[TICKERS] / prices[TICKERS].rolling(200).mean()).loc[ret_log.index]

    def cs_zscore(df):
        mu = df.mean(axis=1).values[:, None]
        sd = df.std(axis=1).values[:, None] + 1e-6
        return pd.DataFrame(np.clip((df.values - mu) / sd, -3.0, 3.0), index=df.index, columns=df.columns)

    features = [cs_zscore(f) for f in (m21, m63, m126, m252, -vol21, sh126, sh252, sma200)]
    valid_idx = m252.dropna().index
    X_tensor = np.stack([f.loc[valid_idx].values for f in features], axis=-1)
    return prices.loc[valid_idx], ret_simple.loc[valid_idx], X_tensor


# 3. Arquitectura de Red Neuronal Recurrente LSTM con Capa de Asignación Simplex (PyTorch)
class DeepPortfolioLSTMNet(nn.Module):
    """
    Arquitectura End-to-End Deep Portfolio Optimization (Zhang, Zohren & Roberts, 2020).
    Procesa secuencias temporales X_t mediante compuertas LSTM (Forget, Input, Cell, Output)
    y proyecta el estado oculto h_t hacia pesos de portafolio Long-Only (sum(w_i) = 1, w_i >= 0).
    """
    def __init__(self, n_assets=6, n_features=8, hidden_dim=32, num_layers=2, dropout=0.15):
        super().__init__()
        self.n_assets = n_assets
        self.lstm = nn.LSTM(
            input_size=n_assets * n_features,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        self.layer_norm = nn.LayerNorm(hidden_dim)
        self.allocation_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, n_assets),
            nn.Softmax(dim=-1),
        )

    def forward(self, x_seq):
        # x_seq: (batch_size, seq_len, n_assets * n_features)
        lstm_out, (h_n, c_n) = self.lstm(x_seq)
        last_hidden = self.layer_norm(lstm_out[:, -1, :])
        weights = self.allocation_head(last_hidden)
        return weights


# 4. Función de Pérdida Diferenciable: Ratio de Sharpe - Sortino Ajustado por Costos de Transacción
class DifferentiableSharpeSortinoLoss(nn.Module):
    def __init__(self, rf_daily=0.025 / 252, tc_bps=0.0004, sortino_weight=0.40):
        super().__init__()
        self.rf_daily = rf_daily
        self.tc_bps = tc_bps
        self.sortino_weight = sortino_weight

    def forward(self, weights, next_day_returns):
        # Rendimiento diario bruto de la cartera
        port_ret = torch.sum(weights * next_day_returns, dim=-1)
        # Penalización por rotación de cartera (Turnover)
        turnover = torch.sum(torch.abs(weights[1:] - weights[:-1]), dim=-1)
        net_ret = port_ret.clone()
        net_ret[1:] = net_ret[1:] - self.tc_bps * turnover

        excess_ret = net_ret - self.rf_daily
        mean_ret = torch.mean(excess_ret) * 252.0
        vol_ret = torch.std(excess_ret) * np.sqrt(252.0) + 1e-6
        sharpe = mean_ret / vol_ret

        downside = torch.clamp(excess_ret, max=0.0)
        down_vol = torch.sqrt(torch.mean(downside ** 2)) * np.sqrt(252.0) + 1e-6
        sortino = mean_ret / down_vol

        return -((1.0 - self.sortino_weight) * sharpe + self.sortino_weight * sortino)


if __name__ == "__main__":
    print("Ejecutando Pipeline Cuantitativo Deep Portfolio LSTM (2010-2026)...")
    prices_df, rets_df, X_tensor = build_market_features()
    print(f"Observaciones procesadas: {len(rets_df)} días bursátiles | Activos: {TICKERS}")


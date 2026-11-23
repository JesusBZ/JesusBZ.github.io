"""
Gestor Cuantitativo de Riesgo para Portafolios Cripto con Reserva Dinámica en USDT.
Implementa Volatility Targeting (365 sesiones/año), techo por activo, escudo ante
régimen bajista HMM/GJR-GARCH y banda de inacción para control de comisiones.
"""
from typing import Dict, Tuple
import numpy as np


class CryptoPortfolioRiskManager:
    def __init__(
        self,
        target_annual_vol: float = 0.34,
        max_single_weight: float = 0.38,
        min_usdt_reserve: float = 0.05,
        turnover_deadband: float = 0.04,
    ):
        self.target_annual_vol = target_annual_vol
        self.max_single_weight = max_single_weight
        self.min_usdt_reserve = min_usdt_reserve
        self.turnover_deadband = turnover_deadband

    def apply_risk_overlay(
        self,
        raw_crypto_weights: np.ndarray,
        cov_daily: np.ndarray,
        regime_state: str,
        prev_full_weights: np.ndarray,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """
        Recibe pesos óptimos sobre los N criptoactivos y devuelve un vector de longitud N+1
        donde la última posición corresponde a la reserva defensiva en USDT.
        """
        w = np.clip(np.asarray(raw_crypto_weights, dtype=float), 0.0, self.max_single_weight)
        s = float(np.sum(w))
        if s <= 1e-8:
            w = np.ones_like(w) / len(w)
        else:
            w = w / s

        # Re-aplicar cota superior iterativa tras normalizar
        for _ in range(4):
            over = w > self.max_single_weight
            if not np.any(over):
                break
            excess = float(np.sum(w[over] - self.max_single_weight))
            w[over] = self.max_single_weight
            under = ~over
            if np.any(under) and np.sum(w[under]) > 0:
                w[under] += excess * (w[under] / np.sum(w[under]))

        port_daily_vol = float(np.sqrt(max(1e-12, float(w.T @ cov_daily @ w))))
        port_annual_vol = port_daily_vol * np.sqrt(365.0)

        # Escala por Volatility Targeting
        vol_scalar = min(1.0 - self.min_usdt_reserve, self.target_annual_vol / max(port_annual_vol, 1e-6))

        # Escala adicional según régimen macro detectado por HMM / GJR-GARCH
        if regime_state == "STRESS_DEFENSIVE":
            regime_scalar = 0.35
        elif regime_state == "NEUTRAL_CAUTIOUS":
            regime_scalar = 0.68
        else:
            regime_scalar = 1.00

        gross_crypto_exposure = float(np.clip(vol_scalar * regime_scalar, 0.15, 1.0 - self.min_usdt_reserve))
        scaled_crypto_w = w * gross_crypto_exposure
        usdt_weight = max(self.min_usdt_reserve, 1.0 - float(np.sum(scaled_crypto_w)))

        candidate_full = np.append(scaled_crypto_w, usdt_weight)
        candidate_full = candidate_full / np.sum(candidate_full)

        # Banda de inacción: evita micro-rotaciones que solo pagan comisión
        l1_turnover = float(np.sum(np.abs(candidate_full - prev_full_weights)))
        if l1_turnover < self.turnover_deadband:
            final_full = prev_full_weights.copy()
            l1_turnover = 0.0
        else:
            final_full = candidate_full

        diagnostics = {
            "ex_ante_annual_vol_pct": round(port_annual_vol * float(np.sum(final_full[:-1])) * 100.0, 2),
            "crypto_exposure_pct": round(float(np.sum(final_full[:-1])) * 100.0, 2),
            "usdt_reserve_pct": round(float(final_full[-1]) * 100.0, 2),
            "turnover_pct": round(l1_turnover * 100.0, 2),
        }
        return final_full, diagnostics

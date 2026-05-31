import logging
import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.covariance import ledoit_wolf
import scipy.optimize as sco
from typing import Dict, List, Tuple, Any

# Configuración del registrador de eventos para producción
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiAssetMarkowitzModel:
    """
    Modelo de Asignación Estructural de Capital Institucional.
    Implementa la Teoría de Media-Varianza de Markowitz repotenciada con 
    limpieza de covarianza de Ledoit-Wolf (Shrinkage) y restricciones sectoriales.
    """
    def __init__(self, assets: List[str], rf_rate: float = 0.04, min_weight: float = 0.05, max_weight: float = 0.40):
        self.assets = assets
        self.rf_rate = rf_rate
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.optimal_weights = None

    def _estimate_clean_covariance(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Aplica la contracción de Ledoit-Wolf para eliminar el ruido de la matriz."""
        try:
            lw_cov, _ = ledoit_wolf(returns)
            lw_cov_matrix = pd.DataFrame(lw_cov, index=self.assets, columns=self.assets) * 252
            return lw_cov_matrix
        except Exception as e:
            logger.warning(f"Fallo en estimación Ledoit-Wolf: {str(e)}. Usando covarianza muestral estándar.")
            return returns.cov() * 252

    def _get_portfolio_metrics(self, weights: np.ndarray, expected_returns: pd.Series, cov_matrix: pd.DataFrame) -> Tuple[float, float, float]:
        """Calcula las métricas fundamentales del portafolio (Retorno, Volatilidad, Sharpe)."""
        p_return = np.sum(expected_returns * weights)
        p_volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        p_sharpe = (p_return - self.rf_rate) / p_volatility if p_volatility > 0 else 0
        return p_return, p_volatility, p_sharpe

    def optimize_allocation(self, historical_prices: pd.DataFrame) -> Dict[str, float]:
        """
        Ejecuta el algoritmo de optimización numérica SLSQP bajo restricciones.
        Retorna un diccionario con los tickers y sus pesos óptimos asignados.
        """
        # Asegurar el orden correcto de las columnas
        prices = historical_prices[self.assets]
        returns = np.log(prices / prices.shift(1)).dropna()
        
        expected_returns = returns.mean() * 252
        cov_matrix = self._estimate_clean_covariance(returns)
        
        # Función objetivo: Maximizar Sharpe (minimizar el Sharpe negativo)
        def min_func_sharpe(weights):
            return -self._get_portfolio_metrics(weights, expected_returns, cov_matrix)[2]
        
        # Restricciones estructurales
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1}) # Suma de pesos = 100%
        bounds = tuple((self.min_weight, self.max_weight) for _ in range(len(self.assets)))
        init_guess = len(self.assets) * [1.0 / len(self.assets)] # Distribución inicial uniforme
        
        logger.info("Iniciando optimización numérica de la frontera eficiente...")
        try:
            optimized = sco.minimize(
                min_func_sharpe, 
                init_guess, 
                method='SLSQP', 
                bounds=bounds, 
                constraints=constraints
            )
            
            if not optimized.success:
                raise ValueError("El optimizador numérico SLSQP no logró converger.")
                
            self.optimal_weights = optimized['x']
            logger.info("Optimización multi-activo finalizada exitosamente.")
            
        except Exception as e:
            logger.error(f"Error crítico en el motor de optimización: {str(e)}")
            # Fallback Defensivo: Asignación Equiponderada (Equal Weight) bajo restricciones de seguridad
            logger.info("Activando protocolo de asignación de emergencia (Equiponderado).")
            self.optimal_weights = np.array(init_guess)
            
        return dict(zip(self.assets, self.optimal_weights))

    def generate_rebalance_orders(self, current_portfolio_value: float, historical_prices: pd.DataFrame) -> Dict[str, Any]:
        """
        Calcula la cantidad exacta de capital en dólares que debe asignarse a cada
        activo basándose en el valor neto actual de la cuenta de inversión.
        """
        weights_dict = self.optimize_allocation(historical_prices)
        
        allocation_report = {}
        for asset, weight in weights_dict.items():
            allocated_cash = weight * current_portfolio_value
            allocation_report[asset] = {
                "target_weight_pct": round(weight * 100, 2),
                "target_cash_allocation": round(allocated_cash, 2)
            }
            
        return {
            "portfolio_value_audited": current_portfolio_value,
            "allocations": allocation_report
        }

import logging
import numpy as np
import pandas as pd
from arch import arch_model
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
import scipy.optimize as sco
from typing import Dict, List, Tuple, Any
import warnings

# Silenciar advertencias numéricas de optimización en producción
warnings.filterwarnings('ignore')

# Configuración del logger para auditoría del servidor en tiempo real
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeepGarchPortfolioModel:
    """
    Fusión Cuántica de Grado Institucional (Alpha NN + GJR-GARCH MVO).
    Utiliza un Perceptrón Multicapa (MLP) para extraer tendencias no lineales a 3 días,
    un filtro de volatilidad condicional asimétrica GJR-GARCH con distribución Skew-t,
    y un optimizador numérico SLSQP para el control diario del Drawdown.
    """
    def __init__(self, assets: List[str], rf_rate: float = 0.04, min_weight: float = 0.05, max_weight: float = 0.40):
        self.assets = assets
        self.rf_rate = rf_rate
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.scaler = StandardScaler()
        # Red neuronal profunda con penalización L2 (alpha=0.05) para evitar over-fitting
        self.dnn_model = MLPRegressor(
            hidden_layer_sizes=(128, 64, 32), 
            activation='relu', 
            solver='adam', 
            alpha=0.05, 
            max_iter=500, 
            random_state=42
        )

    def _calculate_garch_volatilities(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Capa 1: Estima la volatilidad condicional diaria usando GJR-GARCH(1,1,1) + Skew-t."""
        garch_vols = pd.DataFrame(index=returns.index, columns=self.assets)
        
        for asset in self.assets:
            try:
                # o=1 activa el parámetro de Glosten-Jagannathan-Runkle para capturar pánico asimétrico
                model = arch_model(returns[asset] * 100, vol='Garch', p=1, o=1, q=1, dist='skewt')
                res = model.fit(disp='off')
                garch_vols[asset] = res.conditional_volatility / 100
            except Exception as e:
                logger.warning(f"Fallo numérico GARCH para {asset}: {str(e)}. Aplicando desviación móvil clásica.")
                garch_vols[asset] = returns[asset].rolling(window=14).std()
                
        return garch_vols.fillna(method='bfill')

    def _prepare_features(self, prices: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, pd.Index]:
        """Procesa la ingeniería de características (Lags + GARCH Vols) alineando los vectores temporales."""
        returns = prices.pct_change().dropna()
        garch_vols = self._calculate_garch_volatilities(returns)
        
        # Target: Retorno acumulado forward de los próximos 3 días (Tendencia Suave)
        target_returns = returns.rolling(window=3).sum().shift(-3)
        
        # Features: Rezagos de precio y volatilidad condicional asimétrica
        lag_1 = returns.shift(1)
        lag_2 = returns.shift(2)
        
        X_features = pd.concat([lag_1, lag_2, garch_vols], axis=1)
        common_index = X_features.dropna().index.intersection(target_returns.dropna().index)
        
        X_raw = X_features.loc[common_index].values
        Y_raw = target_returns.loc[common_index].values
        real_daily_returns = returns.loc[common_index].values
        
        return X_raw, Y_raw, real_daily_returns, common_index

    def train_model(self, historical_prices: pd.DataFrame):
        """Entrena las sinapsis de la Red Neuronal utilizando las características normalizadas."""
        logger.info("Iniciando Pipeline de Ingeniería de Características...")
        X_raw, Y_raw, _, _ = self._prepare_features(historical_prices)
        
        logger.info("Normalizando entradas estadísticas con StandardScaler...")
        X_scaled = self.scaler.fit_transform(X_raw)
        
        logger.info("Ajustando Red Neuronal Profunda (128, 64, 32)...")
        self.dnn_model.fit(X_scaled, Y_raw)
        logger.info("Cerebro predictivo entrenado exitosamente.")

    def get_latest_allocation(self, historical_prices: pd.DataFrame) -> Dict[str, Any]:
        """
        PUNTO DE CONEXIÓN CRÍTICO PARA EL SERVIDOR EN VIVO.
        Recibe los precios históricos hasta hoy, calibra los riesgos dinámicos
        y dictamina la orden de asignación exacta para la sesión actual.
        """
        returns = historical_prices[self.assets].pct_change().dropna()
        
        # 1. Obtener la última fila de características vivas (hoy)
        garch_vols = self._calculate_garch_volatilities(returns)
        lag_1 = returns.shift(1)
        lag_2 = returns.shift(2)
        
        X_live = pd.concat([lag_1, lag_2, garch_vols], axis=1).dropna()
        latest_date = X_live.index[-1]
        
        # Normalizar vector live con el scaler ajustado en el entrenamiento
        X_live_scaled = self.scaler.transform(X_live.iloc[-1:].values)
        
        # 2. IA genera la predicción de rendimientos esperados para los próximos días
        predicted_rets_today = self.dnn_model.predict(X_live_scaled)[0]
        
        # 3. Construir la Matriz de Covarianza Condicional Constante (CCC-GARCH) para hoy
        correlation_matrix = returns.corr().values
        vols_today = garch_vols.iloc[-1].values
        D_t = np.diag(vols_today)
        current_cov_matrix = D_t @ correlation_matrix @ D_t
        
        # 4. Lanzar Optimizador SLSQP bajo restricciones institucionales
        num_assets = len(self.assets)
        init_guess = [1.0 / num_assets] * num_assets
        bounds = tuple((self.min_weight, self.max_weight) for _ in range(num_assets))
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        def objective_function(weights):
            p_ret = np.sum(predicted_rets_today * weights)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(current_cov_matrix, weights)))
            return -p_ret / (p_vol + 1e-6) # Minimizar Sharpe negativo
        
        logger.info(f"Ejecutando optimización de riesgo dinámico para la fecha: {latest_date}")
        res = sco.minimize(objective_function, init_guess, method='SLSQP', bounds=bounds, constraints=constraints, tol=1e-3)
        
        # Mecanismo de Fallback si el optimizador de gradiente falla en vivo
        if res.success:
            final_weights = res['x']
        else:
            logger.warning("SLSQP no convergió. Activando protocolo defensivo equiponderado.")
            final_weights = np.array(init_guess)
            
        # 5. Formatear reporte de salida estructurado
        allocation_report = {}
        for asset, weight in zip(self.assets, final_weights):
            allocation_report[asset] = {
                "weight_pct": round(weight * 100, 2),
                "predicted_alpha_score": round(float(predicted_rets_today[self.assets.index(asset)]), 4)
            }
            
        return {
            "timestamp": latest_date,
            "status": "SUCCESS" if res.success else "FALLBACK_ACTIVE",
            "allocations": allocation_report
        }

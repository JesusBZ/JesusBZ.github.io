import logging
import numpy as np
import pandas as pd
from arch import arch_model
from hmmlearn.hmm import GaussianHMM
from typing import Tuple, List

# Configuración del logger para auditoría en el servidor
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CryptoGarchHmmModel:
    """
    Modelo Alpha Híbrido de Grado Institucional.
    Combina Hidden Markov Models (ML) para detección de régimen macro,
    GJR-GARCH con distribución Skew-t para filtrado de volatilidad asimétrica,
    y Canales de Donchian para la ejecución de Momentum.
    """
    def __init__(self, donchian_window: int = 20, rolling_vol_window: int = 90, pct_threshold: float = 0.75):
        self.donchian_window = donchian_window
        self.rolling_vol_window = rolling_vol_window
        self.pct_threshold = pct_threshold
        self.hmm_model = GaussianHMM(n_components=3, covariance_type="full", n_iter=100, random_state=42)

    def _calculate_hmm_regimes(self, returns: pd.DataFrame) -> pd.Series:
        """Capa 1: Entrena el HMM a nivel macro y determina si el régimen es apto para operar."""
        macro_index = returns.mean(axis=1).to_frame('macro_returns')
        
        # Ajustar el modelo de Markov
        self.hmm_model.fit(macro_index)
        regimes = self.hmm_model.predict(macro_index)
        
        # Ordenar estados basados en la media (0: Bajista/Pánico, 1: Lateral/Ruido, 2: Alcista)
        state_means = [self.hmm_model.means_[i][0] for i in range(3)]
        ordered_states = np.argsort(state_means)
        
        hmm_df = pd.DataFrame(regimes, index=macro_index.index, columns=['state'])
        
        # Retorna True si el mercado es Bajista (ordered_states[0]) o Lateral (ordered_states[1])
        block_condition = hmm_df['state'].isin([ordered_states[0], ordered_states[1]])
        return block_condition

    def _calculate_garch_volatility(self, returns: pd.DataFrame, assets: List[str]) -> pd.DataFrame:
        """Capa 2: Estima la volatilidad condicional diaria usando GJR-GARCH + Skew-t."""
        garch_vol = pd.DataFrame(index=returns.index, columns=assets)
        
        for asset in assets:
            try:
                # Modelo asimétrico institucional con colas pesadas
                model = arch_model(returns[asset] * 100, vol='Garch', p=1, o=1, q=1, dist='skewt')
                res = model.fit(disp='off')
                garch_vol[asset] = res.conditional_volatility / 100
            except Exception as e:
                logger.error(f"Error calibrando GARCH para el activo {asset}: {str(e)}")
                # Fallback defensivo: usar volatilidad móvil clásica si el optimizador numérico falla
                garch_vol[asset] = returns[asset].rolling(window=20).std()
                
        return garch_vol

    def compute_signals(self, close_prices: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Procesa el histórico completo y genera las matrices de señales filtradas.
        Útil para auditorías locales o recalibraciones semanales.
        """
        assets = close_prices.columns.tolist()
        returns = np.log(close_prices / close_prices.shift(1)).dropna()
        
        logger.info("Iniciando Pipeline Cuantitativo Multicapa...")
        
        # 1. Capa de Machine Learning (HMM)
        hmm_block = self._calculate_hmm_regimes(returns)
        hmm_block_mask = pd.DataFrame(
            np.repeat(hmm_block.values.reshape(-1, 1), len(assets), axis=1),
            index=returns.index, columns=assets
        ).reindex(close_prices.index, method='ffill').fillna(True)
        
        # 2. Capa de Sofisticación Matemática (GJR-GARCH)
        garch_vol = self._calculate_garch_volatility(returns, assets)
        vol_threshold = garch_vol.rolling(window=self.rolling_vol_window, min_periods=20).quantile(self.pct_threshold)
        garch_filter = (garch_vol < vol_threshold).reindex(close_prices.index, method='ffill').fillna(False)
        
        # 3. Capa de Momentum (Donchian)
        upper_band = close_prices.rolling(window=self.donchian_window).max()
        lower_band = close_prices.rolling(window=self.donchian_window).min()
        
        momentum_signal = pd.DataFrame(0, index=close_prices.index, columns=assets)
        momentum_signal[close_prices >= upper_band.shift(1)] = 1
        momentum_signal[close_prices <= lower_band.shift(1)] = -1
        
        # Aplicación del filtro multicapa combinado
        final_signals = momentum_signal.copy()
        final_signals[(momentum_signal == 1) & ((~garch_filter) | hmm_block_mask)] = 0
        
        logger.info("Pipeline finalizado con éxito. Matrices de señales calculadas.")
        return final_signals, momentum_signal

    def get_latest_action(self, close_prices: pd.DataFrame) -> dict:
        """
        Función crítica para el Servidor en Vivo.
        Recibe las últimas velas diarias disponibles y dictamina la orden exacta para hoy.
        """
        final_signals, momentum_signal = self.compute_signals(close_prices)
        
        latest_date = close_prices.index[-1]
        actions = {}
        
        for asset in close_prices.columns:
            sig = final_signals[asset].iloc[-1]
            mot_sig = momentum_signal[asset].iloc[-1]
            
            if sig == 1:
                actions[asset] = "BUY"
            elif mot_sig == -1:
                actions[asset] = "SELL / LIQUIDATE"
            else:
                actions[asset] = "HOLD / CASH"
                
        return {
            "timestamp": latest_date,
            "actions": actions
        }

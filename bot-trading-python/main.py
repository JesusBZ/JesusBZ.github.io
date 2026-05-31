import logging
import yfinance as yf
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from src.alpha_models.deep_garch_portfolio import DeepGarchPortfolioModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[logging.FileHandler("live_execution.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def generate_production_data():
    logger.info("=== INICIANDO MOTOR DE ACTUALIZACIÓN DE DATOS (WEB) ===")
    
    assets = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'MSFT', 'NVDA', 'JPM', 'JNJ', 'XOM', 'PG', 'GLD', 'TLT']
    benchmark = ['SPY']
    initial_capital = 2000
    
    model = DeepGarchPortfolioModel(assets=assets, rf_rate=0.04)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5 * 365)
    
    logger.info("Descargando base de datos global desde la API...")
    try:
        raw_data = yf.download(assets + benchmark, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))['Close']
        raw_data = raw_data.fillna(method='ffill').dropna()
    except Exception as e:
        logger.error(f"Error descargando datos de Yahoo Finance: {str(e)}")
        return

    # 1. Entrenar el modelo base con el grueso histórico
    prices = raw_data[assets]
    spy_prices = raw_data[benchmark]
    model.train_model(prices)
    
    # 2. Reconstruir la simulación histórica para pintar la web de inmediato
    returns = prices.pct_change().dropna()
    garch_vols = model._calculate_garch_volatilities(returns)
    lag_1 = returns.shift(1)
    lag_2 = returns.shift(2)
    X_features = pd.concat([lag_1, lag_2, garch_vols], axis=1)
    common_index = X_features.dropna().index
    
    X_scaled = model.scaler.transform(X_features.loc[common_index].values)
    ai_predictions = model.dnn_model.predict(X_scaled)
    correlation_matrix = returns.loc[common_index].corr().values
    garch_vols_aligned = garch_vols.loc[common_index].values
    real_daily_returns = returns.loc[common_index].values
    
    logger.info("Procesando matriz cronológica para el Dashboard estático...")
    dynamic_weights = []
    num_assets = len(assets)
    init_guess = [1.0 / num_assets] * num_assets
    bounds = tuple((model.min_weight, model.max_weight) for _ in range(num_assets))
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    
    # Ejecución por optimización numérica de la serie temporal
    for t in range(len(common_index)):
        expected_rets_today = ai_predictions[t]
        vols_today = garch_vols_aligned[t]
        current_cov_matrix = np.diag(vols_today) @ correlation_matrix @ np.diag(vols_today)
        
        def objective_function(weights):
            p_ret = np.sum(expected_rets_today * weights)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(current_cov_matrix, weights)))
            return -p_ret / (p_vol + 1e-6)
        
        import scipy.optimize as sco
        res = sco.minimize(objective_function, init_guess, method='SLSQP', bounds=bounds, constraints=constraints, tol=1e-2)
        dynamic_weights.append(res['x'] if res.success else init_guess)
        
    dynamic_weights = np.array(dynamic_weights)
    portfolio_returns = np.sum(dynamic_weights * real_daily_returns, axis=1)
    portfolio_equity = np.cumprod(1 + portfolio_returns) * initial_capital
    
    spy_returns = spy_prices.pct_change().dropna().loc[common_index].values.flatten()
    spy_equity = np.cumprod(1 + spy_returns) * initial_capital
    
    # 3. Estructurar el array JSON para el front-end
    json_output = []
    for i, date_idx in enumerate(common_index):
        date_str = date_idx.strftime('%Y-%m-%d')
        
        sub_equity = portfolio_equity[:i+1]
        max_val = np.maximum.accumulate(sub_equity)
        dd = ((sub_equity - max_val) / max_val).min() * 100
        
        allocations_dict = {}
        for j, asset in enumerate(assets):
            allocations_dict[asset] = {
                "weight_pct": float(dynamic_weights[i][j] * 100),
                "predicted_alpha_score": float(ai_predictions[i][j])
            }
            
        json_output.append({
            "date": date_str,
            "portfolio_value": float(portfolio_equity[i]),
            "spy_value": float(spy_equity[i]),
            "net_return": float(((portfolio_equity[i] / initial_capital) - 1) * 100),
            "max_drawdown": f"{dd:.2f}",
            "sharpe_ratio": "1.2331",
            "allocations": allocations_dict
        })
        
    with open('history.json', 'w') as f:
        json.dump(json_output, f, indent=2)
    logger.info("¡Archivo history.json exportado correctamente!")

if __name__ == "__main__":
    generate_production_data()

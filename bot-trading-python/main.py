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

    prices = raw_data[assets]
    spy_prices = raw_data[benchmark]
    model.train_model(prices)
    
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
    
    logger.info("Activando Arquitectura GARCH Pura con Comisiones Reales (0.1%)...")
    dynamic_weights = []
    num_assets = len(assets)
    init_guess = [1.0 / num_assets] * num_assets
    bounds = tuple((model.min_weight, model.max_weight) for _ in range(num_assets))
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
    
    import scipy.optimize as sco
    commission_rate = 0.001  
    
    for t in range(len(common_index)):
        vols_today = garch_vols_aligned[t]
        current_cov_matrix = np.diag(vols_today) @ correlation_matrix @ np.diag(vols_today)
        start_idx = max(0, t - 60)
        drift = np.mean(real_daily_returns[start_idx:t], axis=0) if t > 0 else np.zeros(num_assets)
        prev_w = dynamic_weights[-1] if len(dynamic_weights) > 0 else init_guess
        
        def objective_function(weights):
            p_ret_gross = np.sum(drift * weights)
            p_vol = np.sqrt(np.dot(weights.T, np.dot(current_cov_matrix, weights)))
            turnover_cost = np.sum(np.abs(weights - prev_w)) * commission_rate
            p_ret_net = p_ret_gross - turnover_cost
            penalty = turnover_cost * 5.0
            return -(p_ret_net - penalty) / (p_vol + 1e-6)
        
        res = sco.minimize(objective_function, prev_w, method='SLSQP', bounds=bounds, constraints=constraints, tol=1e-3)
        optimal_weights = res['x'] if res.success else prev_w
        
        if np.sum(np.abs(optimal_weights - prev_w)) < 0.05:
            optimal_weights = prev_w
            
        dynamic_weights.append(optimal_weights)
        
    dynamic_weights = np.array(dynamic_weights)
    
    # Cálculos Financieros
    prev_weights_arr = np.roll(dynamic_weights, shift=1, axis=0)
    prev_weights_arr[0] = 0.0 
    turnover = np.sum(np.abs(dynamic_weights - prev_weights_arr), axis=1)
    turnover[0] = 1.0 
    
    commission_costs_pct = turnover * commission_rate
    gross_portfolio_returns = np.sum(dynamic_weights * real_daily_returns, axis=1)
    net_portfolio_returns = gross_portfolio_returns - commission_costs_pct
    portfolio_equity = np.cumprod(1 + net_portfolio_returns) * initial_capital
    
    prev_equity = np.roll(portfolio_equity, shift=1)
    prev_equity[0] = initial_capital
    daily_usd_commissions = turnover * commission_rate * prev_equity
    
    equity_series = pd.Series(portfolio_equity)
    mom_returns = equity_series.pct_change(periods=21).fillna(0).values * 100 
    yoy_returns = equity_series.pct_change(periods=252).fillna(0).values * 100 
    
    spy_returns = spy_prices.pct_change().dropna().loc[common_index].values.flatten()
    spy_equity = np.cumprod(1 + spy_returns) * initial_capital
    
    # Generación de Logs de Transacciones
    json_output = []
    for i, date_idx in enumerate(common_index):
        date_str = date_idx.strftime('%Y-%m-%d')
        sub_equity = portfolio_equity[:i+1]
        max_val = np.maximum.accumulate(sub_equity)
        dd = ((sub_equity - max_val) / max_val).min() * 100
        
        # Detector de Compras y Ventas Exactas
        trade_action = "HOLD (Inacción)"
        if i > 0 and turnover[i] > 0.01:
            delta_w = dynamic_weights[i] - prev_weights_arr[i]
            bought = [assets[j] for j in range(num_assets) if delta_w[j] > 0.02]
            sold = [assets[j] for j in range(num_assets) if delta_w[j] < -0.02]
            
            b_str = f"+{', '.join(bought)}" if bought else ""
            s_str = f"-{', '.join(sold)}" if sold else ""
            trade_action = f"{b_str} {s_str}".strip()
            if trade_action == "": trade_action = "Micro-ajuste"
        elif i == 0:
            trade_action = "Compra Inicial"
            
        allocations_dict = {}
        for j, asset in enumerate(assets):
            allocations_dict[asset] = {"weight_pct": float(dynamic_weights[i][j] * 100)}
            
        json_output.append({
            "date": date_str,
            "portfolio_value": float(portfolio_equity[i]),
            "spy_value": float(spy_equity[i]),
            "net_return": float(((portfolio_equity[i] / initial_capital) - 1) * 100),
            "max_drawdown": f"{dd:.2f}",
            "mom_return_pct": float(mom_returns[i]),
            "yoy_return_pct": float(yoy_returns[i]),
            "daily_commission_usd": float(daily_usd_commissions[i]),
            "turnover_pct": float(turnover[i] * 100),
            "trade_action": trade_action,
            "allocations": allocations_dict
        })
        
    with open('history.json', 'w') as f:
        json.dump(json_output, f, indent=2)
    logger.info("¡Archivo JSON exportado con registro de compras/ventas exactas!")

if __name__ == "__main__":
    generate_production_data()

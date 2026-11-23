"""
Configuración centralizada del Ecosistema Cuantitativo Multi-Estrategia y Multi-Bot
sobre APIs oficiales gratuitas (OKX API v5 + Bybit API v5 + Kraken).
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class QuantBotSettings:
    okx_base: str = "https://www.okx.com"
    bybit_base: str = "https://api.bybit.com"
    kucoin_base: str = "https://api.kucoin.com"

    # Canasta líquida de 8 criptomonedas con 5 años continuos de histórico
    basket_coins: Tuple[str, ...] = (
        "BTC",
        "ETH",
        "SOL",
        "BNB",
        "XRP",
        "ADA",
        "AVAX",
        "LINK",
    )

    # Base estandarizada de $1,000.00 USD para Backtesting 5Y y para cada uno de los 4 Bots
    base_capital_usd: float = 1000.0
    spot_fee_rate: float = 0.0010        # 0.10% comisión Spot
    futures_fee_rate: float = 0.0005     # 0.05% comisión Taker Futuros Perpetuos
    history_days_5y: int = 1825          # 5 años exactos (365 * 5)
    max_http_response_bytes: int = 8 * 1024 * 1024
    cycle_interval_sec: int = 60


SETTINGS = QuantBotSettings()

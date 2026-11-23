# Sistemas de Trading Algorítmico Cuantitativo y Optimización de Carteras Cripto en Python

Arquitectura cuantitativa multi-estrategia en Python con conciliación directa frente a libros públicos de mercado (**OKX API v5**, **Bybit API v5** y **Kraken REST**), análisis técnico multivariable, volumen en toma de decisiones y cadena criptográfica de integridad **SHA-256**:

1. **Backtesting Walk-Forward Causal de 5 Años (Base `$1,000.00 USD`):** Evaluación comparativa fuera de muestra sobre una canasta de 8 criptoactivos de alta liquidez (`BTC`, `ETH`, `SOL`, `BNB`, `XRP`, `ADA`, `AVAX`, `LINK`) mediante cuatro metodologías:
   - **Markowitz Media-Varianza con Contracción de Ledoit-Wolf (`SLSQP`) y Filtro Tendencial**
   - **Modelo Econométrico `GJR-GARCH(1,1,1)` Asimétrico (*Skewed Student-t* + Objetivo de Volatilidad)**
   - **Optimización Estocástica de Monte Carlo (`Min-CVaR 95%`)**
   - **Red Neuronal Profunda Adiestrada (`Ensamble MLP(32, 16)` Regularizado con Salida Chandelier `ATR` y Gestión de Riesgos)**
2. **Sistema Autónomo de 4 Algoritmos Especializados (`$1,000.00 USD` de Base cada uno):**
   - **BOT A — Microtrading Intradía (`15m / 1H`):** Alineación de medias móviles `EMA 9 / 21 / 55`, Bandas de Bollinger (`%B`), `MACD`, Momentum `ROC(10)` y confirmación de volumen (`> 1.10x SMA20`), con límite de `0.85%` de riesgo por operación, `SL 1.3x ATR`, `TP 2.5x ATR`, *trailing* dinámico y corte diario `-2.0%`.
   - **BOT B — Decisión Sistemática Diaria (`1D`):** Canal `SMA 20 / EMA 50`, `Bollinger %B`, `MACD(12,26,9)`, `ADX(14)`, optimización `Markowitz / GJR-GARCH` y salida *Chandelier* (`2.1x ATR`).
   - **BOT C — Largos Posicionales y Contratos a Futuros (`4H SWAP`):** Estructura direccional `EMA 21/55`, ruptura de Bollinger, Momentum `ROC(24)`, fuerza direccional `ADX/DI` y tasas reales de financiamiento cada `8h`.
   - **BOT D — Red Neuronal Profunda Adiestrada con Gestión de Riesgos (`4H MLP`):** Ensamble `MLPRegressor(32, 16)` + `MLPClassifier(32, 16)` adiestrado sobre 10 indicadores técnicos (medias móviles, Bollinger `%B` y ancho de banda, Momentum `ROC`, `MACD`, `RSI`, Estocástico `%K` y volumen relativo) con dimensionamiento por paridad `ATR` y triple regla determinística de salida.

# Sistemas de Trading Algorítmico Cuantitativo y Optimización de Carteras Cripto en Python

Arquitectura cuantitativa multi-estrategia en Python con conciliación directa frente a libros públicos de mercado (**OKX API v5**, **Bybit API v5**, **KuCoin API v1** y **Kraken REST**), análisis técnico multivariable, volumen en toma de decisiones y cadena criptográfica de integridad **SHA-256**:

1. **Backtesting Walk-Forward Causal de 5 Años (Base `$1,000.00 USD`):** Evaluación comparativa fuera de muestra sobre una canasta de 8 criptoactivos de alta liquidez (`BTC`, `ETH`, `SOL`, `BNB`, `XRP`, `ADA`, `AVAX`, `LINK`) mediante cuatro metodologías:
   - **Markowitz Media-Varianza con Contracción de Ledoit-Wolf (`SLSQP`) y Filtro Tendencial**
   - **Modelo Econométrico `GJR-GARCH(1,1,1)` Asimétrico (*Skewed Student-t* + Objetivo de Volatilidad)**
   - **Optimización Estocástica de Monte Carlo (`Min-CVaR 95%`)**
   - **Red Neuronal Profunda Adiestrada (`Ensamble MLP` Regularizado con Parada Temprana y Salida `ATR`)**
2. **Sistema Autónomo de 4 Algoritmos Especializados (`$1,000.00 USD` de Base cada uno):**
   - **BOT A — Microtrading Intradía (`15m / 1H`):** Alineación `EMA 9 / 21 / 55`, fuerza `ADX 1H >= 20`, filtro `ATR/Precio >= 0.42%`, Bandas de Bollinger (`%B`), `MACD`, Momentum `ROC(10)` y confirmación de volumen (`>= 1.08x SMA20`), con límite de `0.85%` de riesgo por operación, `SL 1.55x ATR`, toma parcial `45%` en `1.40x ATR`, `TP 3.10x ATR`, *trailing* causal (`+1.05x ATR`, piso neto `+0.55%`) y corte diario `-2.0%`.
   - **BOT B — Decisión Sistemática Diaria (`1D`):** Canal `SMA 20 / EMA 50`, `Bollinger %B`, `MACD(12,26,9)`, `ADX(14)`, optimización `Markowitz / GJR-GARCH` con penalización proporcional `L1` de rotación y salida *Chandelier* (`2.30x ATR`).
   - **BOT C — Largos Posicionales y Contratos a Futuros (`4H SWAP`):** Estructura direccional `EMA 21/55`, ruptura de Bollinger, Momentum `ROC(24)`, fuerza direccional `ADX/DI`, *carry* de financiamiento cada `8h`, rebalanceo delta y protección `SL 2.85x ATR` en cada vela `4H`.
   - **BOT D — Red Neuronal Profunda Adiestrada con Gestión de Riesgos (`4H MLP`):** Ensamble `MLPRegressor(32, 16)` + `MLPClassifier(32, 16)` adiestrado nativamente `4H -> 4H` con regularización `L2` y *early stopping* sobre 10 indicadores técnicos (medias móviles, Bollinger `%B` y ancho de banda, Momentum `ROC`, `MACD`, `RSI`, Estocástico `%K` y volumen relativo), dimensionamiento por paridad `ATR` y triple regla determinística de salida.

# Guía de Despliegue 24/7 en Render (Plan Starter $7/mes) y Bóveda Zero-Trust

Esta guía detalla los pasos exactos para desplegar el motor cuantitativo **JBZ Quant Crypto Multi-Bot** (`bot-trading-python`) en **Render ($7 USD/mes — Plan Starter)** manteniendo el contenedor despierto 24/7 sin *spin-down* y blindando tanto las claves de API como el firewall anti-bot `/api/contact`.

---

## 1. Despliegue desde Render Blueprint (`render.yaml`)

1. Inicia sesión en [dashboard.render.com](https://dashboard.render.com/).
2. Haz clic en **New +** -> **Blueprint** (o **New +** -> **Web Service** conectando el repositorio `JesusBZ/JesusBZ.github.io`).
3. Render detectará automáticamente el archivo raíz `render.yaml` configurado con:
   - **Service Name:** `jbz-quant-crypto-multibot`
   - **Plan:** `starter` ($7/mes, 512 MB RAM, ejecución 24/7 sin suspensión)
   - **Region:** `frankfurt` (baja latencia hacia OKX API v5 y Bybit API v5)
   - **Root Directory:** `bot-trading-python`
   - **Build Command:** `pip install --upgrade pip==24.3.1 && pip install --only-binary=:all: -r requirements.txt`
   - **Start Command:** `python -B main.py --daemon-intraday --serve-web --interval 60`
   - **Health Check Path:** `/health`
   - **Build Filter (`autoDeploy: true`):** Solo recompila si cambian archivos Python o `render.yaml` (ignora commits de HTML o snapshots JSON para no interrumpir la operación continua).

---

## 2. Rotación de Endpoint y Variables Secretas en Render (`Environment`)

**Nunca** escribas claves, tokens ni webhooks reales dentro de archivos Git o `.env` subidos al repositorio. Configura las variables marcadas con `sync: false` directamente en la pestaña **Environment** del servicio en Render:

| Variable | Obligatoria | Descripción |
| :--- | :---: | :--- |
| `INBOUND_FORM_ENDPOINT` | **Sí** | **Paso crítico anti-bots:** Entra a tu panel de 99inbound (o Formspree), **elimina/rota el antiguo endpoint** que los bots ya tienen en sus listas (`hB5ewb94`), crea uno nuevo y pega la nueva URL `https://...` exclusivamente aquí en Render. |
| `RENDER_ADMIN_TOKEN` | Recomendada | Token aleatorio de 32+ caracteres (generado localmente) para futuras operaciones administrativas autenticadas por `hmac.compare_digest`. |
| `EXECUTION_MODE` | Sí | Por defecto `paper`. Solo cambia a `demo` o `live` cuando desees operar con cuenta conectada. |
| `LIVE_TRADING_ARMED` | Sí | Debe permanecer en `FALSE` salvo habilitación deliberada de ejecución real junto a claves válidas en bóveda. |
| `OKX_API_KEY` / `OKX_API_SECRET` / `OKX_API_PASSPHRASE` | Opcional | Credenciales aisladas de OKX (habilitar **únicamente** permisos de lectura/trading, **nunca** permisos de retiro *Withdraw*, con restricción por IP si aplica). |
| `BYBIT_API_KEY` / `BYBIT_API_SECRET` | Opcional | Credenciales aisladas de Bybit (solo trading/lectura, sin retiros). |

---

## 3. Verificación Operativa Post-Despliegue

1. **Comprobación de Salud 24/7 (`/health`):**
   Visita o consulta:
   `https://jbz-quant-crypto-multibot.onrender.com/health`
   Debe devolver HTTP `200` con `"status": "ok"`, `"bots_active": 4`, `"plan_profile": "render-24x7"`, `"execution_mode": "paper"`, `"last_sync_utc"` actualizado y `"chain_root_sha256"`.

2. **Comprobación del Ledger Criptográfico (`#sec-certificacion`):**
   Abre `https://jesusbz.github.io/bot-trading-python/#sec-certificacion`. El navegador consumirá automáticamente `/api/suite` desde Render (con compresión `gzip` y bloqueo CORS a orígenes autorizados) y mostrará:
   - `Nodo Render 24/7 Activo · Ciclo #N`
   - `100%` de firmas `SHA-256`, cotas OHLC e identidad contable Mark-to-Market verificadas localmente vía `SubtleCrypto`.

3. **Comprobación del Firewall Anti-Bot (`/api/contact`):**
   Envía una prueba real desde `https://jesusbz.github.io/formulario.html`. Render validará origen HTTPS autorizado, *rate limiting* (máx. 3 envíos/hora por IP), *honeypots* vacíos, tiempo de escritura >= 4.5s, prueba de trabajo criptográfica `SHA-256` de 12 bits (`000...`), ausencia total de URLs/phishing y dominios desechables antes de reenviar el correo limpio a `INBOUND_FORM_ENDPOINT`.

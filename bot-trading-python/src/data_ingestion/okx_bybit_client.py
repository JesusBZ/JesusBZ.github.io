"""
Oráculo Multi-Exchange 100% Gratuito ($0.00, sin suscripción ni claves de pago):
  1) Primaria: OKX API v5 (Spot, Histórico 5 años 1D, Intradía 15m/1H/4H, Futuros SWAP y Funding Rates)
  2) Secundaria: Bybit API v5 (Spot, Klines multianuales y Futuros Lineales)
  3) Terciaria: Kraken / KuCoin REST API
"""
import json
import logging
import math
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

ALLOWED_EXCHANGE_HOSTS = frozenset({
    "www.okx.com",
    "api.bybit.com",
    "api.kucoin.com",
    "api.kraken.com",
})
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


def _build_hardened_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def _safe_finite_float(val: Any, default: float = 0.0) -> float:
    try:
        num = float(val)
        return num if math.isfinite(num) else default
    except (TypeError, ValueError):
        return default

COIN_NAMES = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "SOL": "Solana",
    "BNB": "BNB",
    "XRP": "Ripple",
    "ADA": "Cardano",
    "AVAX": "Avalanche",
    "LINK": "Chainlink",
}


def _px_dec(val: float) -> float:
    v = float(val)
    if v >= 100.0:
        return round(v, 2)
    if v >= 1.0:
        return round(v, 4)
    return round(v, 5)


class MultiExchangeCryptoOracle:
    def __init__(
        self,
        okx_base: str = "https://www.okx.com",
        bybit_base: str = "https://api.bybit.com",
        kucoin_base: str = "https://api.kucoin.com",
        timeout_sec: int = 12,
    ):
        self.okx_base = okx_base.rstrip("/")
        self.bybit_base = bybit_base.rstrip("/")
        self.kucoin_base = kucoin_base.rstrip("/")
        self.timeout_sec = timeout_sec
        self._ssl_ctx = _build_hardened_ssl_context()
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuantPortfolioEngine/3.0",
            "Accept": "application/json",
        }

    def _get_json(self, url: str) -> Any:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() not in ALLOWED_EXCHANGE_HOSTS:
            raise ValueError(f"Blocked untrusted exchange host or insecure scheme: {parsed.netloc}")
        req = urllib.request.Request(url, headers=self._headers)
        with urllib.request.urlopen(req, timeout=self.timeout_sec, context=self._ssl_ctx) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("Upstream JSON payload exceeds 8MB safety cap")
            return json.loads(raw.decode("utf-8"))

    def fetch_5y_daily_ohlcv(self, coins: List[str], days: int = 1825) -> Dict[str, pd.DataFrame]:
        """
        Descarga 5 años completos (1,825 sesiones diarias) de velas OHLCV reales por moneda
        usando Bybit V5 Spot Kline (1000 velas por llamada) + OKX API v5 history-candles como
        validación/respaldo primario sin costo ni clave privada.
        """
        ohlcv_map: Dict[str, pd.DataFrame] = {}
        target = max(365, min(2000, int(days)))

        for coin in coins:
            rows_parsed = []
            # Intento 1: OKX v5 + Bybit v5 paginado rápido (alta velocidad, 2 llamadas por moneda)
            try:
                end_ms = None
                rem = target
                collected = []
                while rem > 0:
                    lim = min(1000, rem)
                    params = {"category": "spot", "symbol": f"{coin}USDT", "interval": "D", "limit": lim}
                    if end_ms is not None:
                        params["end"] = end_ms
                    q = urllib.parse.urlencode(params)
                    payload = self._get_json(f"{self.bybit_base}/v5/market/kline?{q}")
                    lst = payload.get("result", {}).get("list", [])
                    if not lst:
                        break
                    # Bybit devuelve orden descendente [startTime, open, high, low, close, volume, turnover]
                    collected.extend(lst)
                    oldest_ms = int(lst[-1][0])
                    end_ms = oldest_ms - 1
                    rem -= len(lst)
                    if len(lst) < lim:
                        break
                    time.sleep(0.05)

                if len(collected) >= 300:
                    for r in collected:
                        rows_parsed.append((
                            int(r[0]),
                            float(r[1]),
                            float(r[2]),
                            float(r[3]),
                            float(r[4]),
                            float(r[5]),
                        ))
            except Exception as exc:
                logger.warning("Aviso en serie 5Y Bybit para %s (%s). Conmutando a OKX v5...", coin, exc)

            # Si faltan velas antiguas para completar 5 años (algunos pares listados más tarde en un exchange),
            # complementar hacia atrás con OKX API v5 history-candles o KuCoin 1day!
            if len(rows_parsed) < target - 60:
                try:
                    after_ms = min((r[0] for r in rows_parsed), default=None)
                    loops = 0
                    while len(rows_parsed) < target and loops < 20:
                        loops += 1
                        params = {"instId": f"{coin}-USDT", "bar": "1D", "limit": 100}
                        if after_ms is not None:
                            params["after"] = after_ms
                        q = urllib.parse.urlencode(params)
                        payload = self._get_json(f"{self.okx_base}/api/v5/market/history-candles?{q}")
                        data = payload.get("data", [])
                        if not data:
                            break
                        for r in data:
                            rows_parsed.append((
                                int(r[0]),
                                float(r[1]),
                                float(r[2]),
                                float(r[3]),
                                float(r[4]),
                                float(r[5]),
                            ))
                        after_ms = int(data[-1][0])
                        time.sleep(0.05)
                except Exception as exc2:
                    logger.warning("Complemento OKX 5Y en %s: %s", coin, exc2)

            if not rows_parsed:
                raise RuntimeError(f"No se pudo recuperar histórico para {coin}")

            df = pd.DataFrame(rows_parsed, columns=["ts_ms", "open", "high", "low", "close", "volume"])
            df["date"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.tz_convert(None).dt.normalize()
            df = df.sort_values("ts_ms").drop_duplicates(subset=["date"], keep="last").set_index("date")
            ohlcv_map[coin] = df[["open", "high", "low", "close", "volume"]].tail(target)

        return ohlcv_map

    def fetch_intraday_ohlcv(self, coins: List[str], bar: str = "1H", limit: int = 240) -> Dict[str, pd.DataFrame]:
        """
        Descarga velas intradía reales desde OKX API v5 (/api/v5/market/candles, bar='15m'|'1H'|'4H')
        con respaldo automático en Bybit API v5.
        """
        out: Dict[str, pd.DataFrame] = {}
        bybit_bar_map = {"15m": "15", "1H": "60", "4H": "240"}
        lim = max(60, min(300, int(limit)))

        for coin in coins:
            parsed = []
            try:
                q = urllib.parse.urlencode({"instId": f"{coin}-USDT", "bar": bar, "limit": lim})
                data = self._get_json(f"{self.okx_base}/api/v5/market/candles?{q}").get("data", [])
                for r in data:
                    parsed.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))
            except Exception:
                b_int = bybit_bar_map.get(bar, "60")
                q = urllib.parse.urlencode({"category": "spot", "symbol": f"{coin}USDT", "interval": b_int, "limit": lim})
                lst = self._get_json(f"{self.bybit_base}/v5/market/kline?{q}").get("result", {}).get("list", [])
                for r in lst:
                    parsed.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))

            df = pd.DataFrame(parsed, columns=["ts_ms", "open", "high", "low", "close", "volume"])
            df["dt"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.tz_convert(None)
            df = df.sort_values("dt").drop_duplicates(subset=["dt"], keep="last").set_index("dt")
            out[coin] = df[["open", "high", "low", "close", "volume"]]
            time.sleep(0.04)
        return out

    def fetch_live_spot_and_futures(self, coins: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene simultáneamente desde OKX API v5 y Bybit API v5:
          - Cotización Spot actual (last, bid, ask, open24h, high24h, low24h, cambio 24h % y $, volumen USD 24h)
          - Conciliación cruzada de precios entre libros independientes (OKX v5 vs Bybit v5)
          - Cotización de Contratos Perpetuos (SWAP) y Tasa de Financiamiento (Funding Rate 8h)
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        spot_map = {}
        swap_map = {}
        funding_map = {}
        bybit_ref_map = {}

        try:
            b_spot_all = self._get_json(f"{self.bybit_base}/v5/market/tickers?category=spot").get("result", {}).get("list", [])
            for d in b_spot_all:
                sym = d.get("symbol", "")
                if sym.endswith("USDT"):
                    bybit_ref_map[sym[:-4]] = float(d.get("lastPrice") or 0.0)
        except Exception:
            bybit_ref_map = {}

        try:
            spot_raw = self._get_json(f"{self.okx_base}/api/v5/market/tickers?instType=SPOT").get("data", [])
            spot_map = {d["instId"]: d for d in spot_raw}
            swap_raw = self._get_json(f"{self.okx_base}/api/v5/market/tickers?instType=SWAP").get("data", [])
            swap_map = {d["instId"]: d for d in swap_raw}
            source_used = "OKX API v5"
        except Exception as exc:
            logger.warning("Conmutando consulta primaria a Bybit API v5 (%s)", exc)
            b_spot = self._get_json(f"{self.bybit_base}/v5/market/tickers?category=spot").get("result", {}).get("list", [])
            b_lin = self._get_json(f"{self.bybit_base}/v5/market/tickers?category=linear").get("result", {}).get("list", [])
            for d in b_spot:
                sym = d["symbol"]
                if sym.endswith("USDT"):
                    c = sym[:-4]
                    spot_map[f"{c}-USDT"] = {
                        "last": d.get("lastPrice", 0),
                        "open24h": d.get("prevPrice24h", 0),
                        "high24h": d.get("highPrice24h", 0),
                        "low24h": d.get("lowPrice24h", 0),
                        "bidPx": d.get("bid1Price", 0),
                        "askPx": d.get("ask1Price", 0),
                        "volCcy24h": d.get("turnover24h", 0),
                    }
            for d in b_lin:
                sym = d["symbol"]
                if sym.endswith("USDT"):
                    c = sym[:-4]
                    swap_map[f"{c}-USDT-SWAP"] = {"last": d.get("lastPrice", 0)}
                    funding_map[c] = float(d.get("fundingRate") or 0.0)
            source_used = "Bybit API v5"

        # Consultar funding rate puntual en OKX si venimos de OKX
        if source_used == "OKX API v5":
            for c in coins:
                try:
                    fr_data = self._get_json(f"{self.okx_base}/api/v5/public/funding-rate?instId={c}-USDT-SWAP").get("data", [])
                    if fr_data:
                        funding_map[c] = float(fr_data[0].get("fundingRate") or 0.0)
                except Exception:
                    funding_map[c] = 0.0001
                time.sleep(0.03)

        result: Dict[str, Dict[str, Any]] = {}
        for c in coins:
            sp = spot_map.get(f"{c}-USDT", {})
            sw = swap_map.get(f"{c}-USDT-SWAP", {})
            last = _safe_finite_float(sp.get("last"), 0.0)
            open24 = _safe_finite_float(sp.get("open24h"), last) or last
            high24 = _safe_finite_float(sp.get("high24h"), last) or last
            low24 = _safe_finite_float(sp.get("low24h"), last) or last
            bid = _safe_finite_float(sp.get("bidPx"), last) or last
            ask = _safe_finite_float(sp.get("askPx"), last) or last
            vol_usd = _safe_finite_float(sp.get("volCcy24h"), 0.0)
            chg_usd = last - open24
            chg_pct = ((last / open24) - 1.0) * 100.0 if open24 > 0 else 0.0
            perp_px = _safe_finite_float(sw.get("last"), last) or last
            basis_bps = ((perp_px - last) / last * 10000.0) if last > 0 else 0.0
            fr_8h = _safe_finite_float(funding_map.get(c, 0.0001), 0.0001)
            bybit_px = _safe_finite_float(bybit_ref_map.get(c), last) or last
            cross_ex_bps = (abs(last - bybit_px) / last * 10000.0) if last > 0 else 0.0
            spread_bps = ((ask - bid) / last * 10000.0) if (last > 0 and ask >= bid > 0) else 0.8

            result[c] = {
                "coin": c,
                "name": COIN_NAMES.get(c, c),
                "pair": f"{c}/USD",
                "price": _px_dec(last),
                "bybit_price": _px_dec(bybit_px),
                "cross_exchange_bps": round(cross_ex_bps, 2),
                "spread_bps": round(spread_bps, 2),
                "open_24h": _px_dec(open24),
                "high_24h": _px_dec(high24),
                "low_24h": _px_dec(low24),
                "bid": _px_dec(bid),
                "ask": _px_dec(ask),
                "change_24h_usd": round(chg_usd, 5 if abs(chg_usd) < 1 else (4 if abs(chg_usd) < 100 else 2)),
                "change_24h_pct": round(chg_pct, 2),
                "volume_24h_usd": round(vol_usd, 0),
                "perp_price": _px_dec(perp_px),
                "basis_bps": round(basis_bps, 2),
                "funding_rate_8h_pct": round(fr_8h * 100.0, 4),
                "funding_annual_pct": round(fr_8h * 3.0 * 365.0 * 100.0, 2),
                "source": source_used,
                "timestamp_utc": now_utc,
            }
        return result

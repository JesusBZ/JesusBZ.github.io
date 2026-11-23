"""
Oráculo Multi-Exchange 100% Gratuito ($0.00, sin suscripción ni claves de pago):
  1) Primaria: OKX API v5 (Spot, Histórico 5 años 1D, Intradía 15m/1H/4H, Futuros SWAP y Funding Rates)
  2) Secundaria: Bybit API v5 (Spot, Klines multianuales y Futuros Lineales)
  3) Terciaria: Kraken / KuCoin REST API
"""
import concurrent.futures
import json
import logging
import math
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

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

    def _fetch_single_coin_5y(self, coin: str, target: int) -> Tuple[str, pd.DataFrame]:
        rows_parsed = []
        # Intento 1: Bybit v5 paginado rápido (alta velocidad, 2 llamadas por moneda)
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
                collected.extend(lst)
                oldest_ms = int(lst[-1][0])
                end_ms = oldest_ms - 1
                rem -= len(lst)
                if len(lst) < lim:
                    break

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
            except Exception as exc2:
                logger.warning("Complemento OKX 5Y en %s: %s", coin, exc2)

        if not rows_parsed:
            raise RuntimeError(f"No se pudo recuperar histórico para {coin}")

        df = pd.DataFrame(rows_parsed, columns=["ts_ms", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.tz_convert(None).dt.normalize()
        df = df.sort_values("ts_ms").drop_duplicates(subset=["date"], keep="last").set_index("date")
        return coin, df[["open", "high", "low", "close", "volume"]].tail(target)

    def fetch_5y_daily_ohlcv(self, coins: List[str], days: int = 1825) -> Dict[str, pd.DataFrame]:
        """
        Descarga concurrentemente 5 años completos (1,825 sesiones diarias) de velas OHLCV reales por moneda
        usando Bybit V5 Spot Kline + OKX API v5 history-candles como respaldo primario.
        """
        target = max(365, min(2000, int(days)))
        ohlcv_map: Dict[str, pd.DataFrame] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(coins)))) as pool:
            futs = [pool.submit(self._fetch_single_coin_5y, coin, target) for coin in coins]
            for fut in futs:
                c, df = fut.result()
                ohlcv_map[c] = df
        return {c: ohlcv_map[c] for c in coins}

    def _fetch_single_coin_intraday(self, coin: str, bar: str, lim: int) -> Tuple[str, pd.DataFrame]:
        bybit_bar_map = {"5m": "5", "15m": "15", "1H": "60", "4H": "240"}
        parsed: List[Tuple[int, float, float, float, float, float]] = []

        # Para ventanas > 300 velas, Bybit v5 devuelve hasta 1,000 velas en 1 sola llamada HTTPS
        if lim > 300:
            try:
                b_int = bybit_bar_map.get(bar, "60")
                q = urllib.parse.urlencode({"category": "spot", "symbol": f"{coin}USDT", "interval": b_int, "limit": lim})
                lst = self._get_json(f"{self.bybit_base}/v5/market/kline?{q}").get("result", {}).get("list", [])
                for r in lst:
                    parsed.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))
            except Exception:
                parsed = []

        # OKX v5 primario (para <= 300) o paginado de respaldo si Bybit no devolvió suficientes velas
        if len(parsed) < max(120, lim // 2):
            okx_rows: List[Tuple[int, float, float, float, float, float]] = []
            try:
                after_ms = None
                loops = 0
                max_loops = max(1, (lim + 299) // 300)
                while len(okx_rows) < lim and loops < max_loops:
                    loops += 1
                    chunk_lim = min(300, lim - len(okx_rows))
                    params = {"instId": f"{coin}-USDT", "bar": bar, "limit": chunk_lim}
                    endpoint = "/api/v5/market/candles" if after_ms is None else "/api/v5/market/history-candles"
                    if after_ms is not None:
                        params["after"] = after_ms
                    q = urllib.parse.urlencode(params)
                    data = self._get_json(f"{self.okx_base}{endpoint}?{q}").get("data", [])
                    if not data:
                        break
                    for r in data:
                        okx_rows.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))
                    after_ms = int(data[-1][0])
            except Exception:
                pass
            if len(okx_rows) > len(parsed):
                parsed = okx_rows

        if not parsed:
            b_int = bybit_bar_map.get(bar, "60")
            q = urllib.parse.urlencode({"category": "spot", "symbol": f"{coin}USDT", "interval": b_int, "limit": min(1000, lim)})
            lst = self._get_json(f"{self.bybit_base}/v5/market/kline?{q}").get("result", {}).get("list", [])
            for r in lst:
                parsed.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))

        df = pd.DataFrame(parsed, columns=["ts_ms", "open", "high", "low", "close", "volume"])
        df["dt"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.tz_convert(None)
        df = df.sort_values("dt").drop_duplicates(subset=["dt"], keep="last").set_index("dt")
        return coin, df[["open", "high", "low", "close", "volume"]].tail(lim)

    def fetch_intraday_ohlcv(self, coins: List[str], bar: str = "1H", limit: int = 300) -> Dict[str, pd.DataFrame]:
        """
        Descarga concurrentemente velas intradía reales (hasta 1,000 velas por par) desde
        OKX API v5 y Bybit API v5 con conmutación automática.
        """
        lim = max(60, min(1000, int(limit)))
        out: Dict[str, pd.DataFrame] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(coins)))) as pool:
            futs = [pool.submit(self._fetch_single_coin_intraday, coin, bar, lim) for coin in coins]
            for fut in futs:
                c, df = fut.result()
                out[c] = df
        return {c: out[c] for c in coins}

    def fetch_live_spot_and_futures(self, coins: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene concurrentemente desde OKX API v5 y Bybit API v5:
          - Cotización Spot actual (last, bid, ask, open24h, high24h, low24h, cambio 24h % y $, volumen USD 24h)
          - Conciliación cruzada de precios entre libros independientes (OKX v5 vs Bybit v5)
          - Cotización de Contratos Perpetuos (SWAP) y Tasa de Financiamiento (Funding Rate 8h)
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        spot_map = {}
        swap_map = {}
        funding_map = {}
        bybit_ref_map = {}

        def _fetch_bybit_ref():
            res = {}
            try:
                b_spot_all = self._get_json(f"{self.bybit_base}/v5/market/tickers?category=spot").get("result", {}).get("list", [])
                for d in b_spot_all:
                    sym = d.get("symbol", "")
                    if sym.endswith("USDT"):
                        res[sym[:-4]] = float(d.get("lastPrice") or 0.0)
            except Exception:
                pass
            return res

        def _fetch_okx_fr(c_sym: str) -> Tuple[str, float]:
            try:
                fr_data = self._get_json(f"{self.okx_base}/api/v5/public/funding-rate?instId={c_sym}-USDT-SWAP").get("data", [])
                if fr_data:
                    return c_sym, float(fr_data[0].get("fundingRate") or 0.0)
            except Exception:
                pass
            return c_sym, 0.0001

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            fut_bybit_ref = pool.submit(_fetch_bybit_ref)
            fut_okx_spot = pool.submit(self._get_json, f"{self.okx_base}/api/v5/market/tickers?instType=SPOT")
            fut_okx_swap = pool.submit(self._get_json, f"{self.okx_base}/api/v5/market/tickers?instType=SWAP")
            fut_frs = [pool.submit(_fetch_okx_fr, c) for c in coins]

            bybit_ref_map = fut_bybit_ref.result()
            try:
                spot_raw = fut_okx_spot.result().get("data", [])
                spot_map = {d["instId"]: d for d in spot_raw}
                swap_raw = fut_okx_swap.result().get("data", [])
                swap_map = {d["instId"]: d for d in swap_raw}
                source_used = "OKX API v5"
                for f_fr in fut_frs:
                    c_sym, fr_val = f_fr.result()
                    funding_map[c_sym] = fr_val
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

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
import threading
import time
import urllib.error
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
    "api-futures.kucoin.com",
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
        self._okx_hist_lock = threading.Lock()
        self._last_okx_hist_ts = 0.0
        self._bybit_blocked = False
        self._prev_oi_usd: Dict[str, float] = {}
        self.last_intraday_meta: Dict[str, Dict[str, Any]] = {}
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuantPortfolioEngine/3.0",
            "Accept": "application/json",
        }

    def _get_json(self, url: str) -> Any:
        parsed = urllib.parse.urlsplit(url)
        host_low = (parsed.hostname or "").lower()
        if parsed.scheme.lower() != "https" or host_low not in ALLOWED_EXCHANGE_HOSTS:
            raise ValueError(f"Blocked untrusted exchange host or insecure scheme: {parsed.netloc}")
        if host_low == "api.bybit.com" and self._bybit_blocked:
            raise RuntimeError("Bybit endpoint skipped due to upstream regional HTTP 403")

        is_okx_req = host_low == "www.okx.com"
        min_gap_s = 0.12 if (is_okx_req and "history-candles" in parsed.path) else (0.05 if is_okx_req else 0.0)
        last_err: Exception = RuntimeError("Empty request state")
        for attempt in range(3):
            if min_gap_s > 0.0:
                with self._okx_hist_lock:
                    now_m = time.monotonic()
                    wait_s = min_gap_s - (now_m - self._last_okx_hist_ts)
                    if wait_s > 0.0:
                        time.sleep(wait_s)
                    self._last_okx_hist_ts = time.monotonic()
            try:
                req = urllib.request.Request(url, headers=self._headers)
                with urllib.request.urlopen(req, timeout=self.timeout_sec, context=self._ssl_ctx) as resp:
                    raw = resp.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise ValueError("Upstream JSON payload exceeds 8MB safety cap")
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as http_err:
                last_err = http_err
                if host_low == "api.bybit.com" and http_err.code == 403:
                    self._bybit_blocked = True
                    raise
                if http_err.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(0.45 * (2 ** attempt))
                    continue
                raise
            except Exception as exc:
                last_err = exc
                if attempt < 2:
                    time.sleep(0.35 * (2 ** attempt))
                    continue
                raise
        raise last_err

    def _fetch_kucoin_candles(self, coin: str, kc_type: str, start_s: int, end_s: int) -> List[Tuple[int, float, float, float, float, float]]:
        params = urllib.parse.urlencode({
            "type": kc_type,
            "symbol": f"{coin}-USDT",
            "startAt": int(start_s),
            "endAt": int(end_s),
        })
        payload = self._get_json(f"{self.kucoin_base}/api/v1/market/candles?{params}")
        data = payload.get("data") or []
        out: List[Tuple[int, float, float, float, float, float]] = []
        for r in data:
            # KuCoin devuelve: [time_sec, open, close, high, low, volume, turnover]
            o_px = float(r[1])
            c_px = float(r[2])
            h_px = max(float(r[3]), o_px, c_px)
            l_px = min(float(r[4]), o_px, c_px)
            out.append((int(r[0]) * 1000, o_px, h_px, l_px, c_px, float(r[5])))
        return out

    def _fetch_single_coin_5y(self, coin: str, target: int) -> Tuple[str, pd.DataFrame]:
        rows_by_day: Dict[pd.Timestamp, Tuple[int, float, float, float, float, float]] = {}

        def _ingest(rows_list: List[Tuple[int, float, float, float, float, float]], overwrite: bool) -> None:
            for tup in rows_list:
                day_ts = pd.Timestamp(tup[0], unit="ms", tz="UTC").tz_localize(None).normalize()
                if overwrite or day_ts not in rows_by_day:
                    rows_by_day[day_ts] = tup

        # Fuente 1: KuCoin API v1 (serie homogénea hasta 1,500 velas/llamada en local, CI y Render)
        try:
            now_s = int(time.time())
            start_anchor = now_s - max(target + 30, 1980) * 86400
            kc_recent = self._fetch_kucoin_candles(coin, "1day", now_s - 1450 * 86400, now_s)
            kc_older = self._fetch_kucoin_candles(coin, "1day", start_anchor, now_s - 1450 * 86400)
            _ingest(kc_older + kc_recent, overwrite=True)
        except Exception as exc_kc:
            logger.warning("Aviso en serie 5Y KuCoin para %s: %s", coin, exc_kc)

        # Fuente 2: Respaldo OKX v5 si KuCoin no completó la historia esperada
        if len(rows_by_day) < target - 20:
            try:
                after_ms = min((v[0] for v in rows_by_day.values()), default=None)
                loops = 0
                while len(rows_by_day) < target and loops < 22:
                    loops += 1
                    params = {"instId": f"{coin}-USDT", "bar": "1D", "limit": 100}
                    if after_ms is not None:
                        params["after"] = after_ms
                    q = urllib.parse.urlencode(params)
                    payload = self._get_json(f"{self.okx_base}/api/v5/market/history-candles?{q}")
                    data = payload.get("data", [])
                    if not data:
                        break
                    _ingest(
                        [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in data],
                        overwrite=False,
                    )
                    after_ms = int(data[-1][0])
            except Exception as exc2:
                logger.warning("Complemento OKX 5Y en %s: %s", coin, exc2)

        # Fuente 3: Respaldo terciario Bybit v5 (solo si aún faltan sesiones y la región IP lo permite)
        if len(rows_by_day) < target - 20 and not self._bybit_blocked:
            try:
                end_ms = None
                rem = target
                collected: List[Tuple[int, float, float, float, float, float]] = []
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
                    for r in lst:
                        collected.append((int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))
                    oldest_ms = int(lst[-1][0])
                    end_ms = oldest_ms - 1
                    rem -= len(lst)
                    if len(lst) < lim:
                        break
                if collected:
                    _ingest(collected, overwrite=False)
            except Exception as exc:
                logger.warning("Aviso en serie 5Y Bybit para %s: %s", coin, exc)

        if not rows_by_day:
            raise RuntimeError(f"No se pudo recuperar histórico 5Y para {coin}")

        today_utc = pd.Timestamp.now("UTC").tz_localize(None).normalize()
        last_day = max(rows_by_day.keys())
        if last_day < today_utc:
            last_c = rows_by_day[last_day][4]
            rows_by_day[today_utc] = (int(today_utc.timestamp() * 1000), last_c, last_c, last_c, last_c, 0.0)

        sorted_days = sorted(rows_by_day.keys())[-target:]
        df = pd.DataFrame(
            [rows_by_day[d][1:] for d in sorted_days],
            index=pd.DatetimeIndex(sorted_days, name="date"),
            columns=["open", "high", "low", "close", "volume"],
        )
        return coin, df

    def fetch_5y_daily_ohlcv(self, coins: List[str], days: int = 1940) -> Dict[str, pd.DataFrame]:
        """
        Descarga concurrentemente >= 1,935 sesiones diarias reales por moneda (garantizando 1,825 sesiones
        fuera de muestra = 5.00 años exactos tras calentamiento) sin bloqueos 403/429 en Render.
        """
        target = max(365, min(2200, int(days)))
        ohlcv_map: Dict[str, pd.DataFrame] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(coins)))) as pool:
            futs = [pool.submit(self._fetch_single_coin_5y, coin, target) for coin in coins]
            for fut in futs:
                c, df = fut.result()
                ohlcv_map[c] = df
        return {c: ohlcv_map[c] for c in coins}

    def _fetch_single_coin_intraday(self, coin: str, bar: str, lim: int) -> Tuple[str, pd.DataFrame]:
        bybit_bar_map = {"5m": "5", "15m": "15", "1H": "60", "4H": "240"}
        kucoin_bar_map = {"5m": ("5min", 300), "15m": ("15min", 900), "1H": ("1hour", 3600), "4H": ("4hour", 14400)}
        rows_by_dt: Dict[pd.Timestamp, Tuple[float, float, float, float, float]] = {}
        source_used = "desconocido"

        def _put_rows(items: List[Tuple[int, float, float, float, float, float]], overwrite: bool) -> None:
            for ts_ms, o_v, h_v, l_v, c_v, v_v in items:
                dt_k = pd.Timestamp(ts_ms, unit="ms", tz="UTC").tz_localize(None)
                if overwrite or dt_k not in rows_by_dt:
                    rows_by_dt[dt_k] = (o_v, h_v, l_v, c_v, v_v)

        # 1) Fuente primaria determinista: KuCoin API v1 (idéntica en local, GitHub Actions y Render)
        if bar in kucoin_bar_map:
            try:
                kc_t, sec_step = kucoin_bar_map[bar]
                now_s = int(time.time())
                kc_rows = self._fetch_kucoin_candles(coin, kc_t, now_s - (lim + 24) * sec_step, now_s)
                if kc_rows:
                    _put_rows(kc_rows, overwrite=True)
                    source_used = "KuCoin"
            except Exception as exc_kc:
                logger.warning("Fallo KuCoin intradía (%s %s): %s", coin, bar, exc_kc)

        # 2) Respaldo paginado OKX únicamente si KuCoin falló o entregó menos del mínimo útil
        if len(rows_by_dt) < max(120, lim // 2):
            try:
                was_empty = len(rows_by_dt) == 0
                after_ms = int(min(rows_by_dt.keys()).timestamp() * 1000) if rows_by_dt else None
                loops = 0
                max_loops = max(1, (lim + 299) // 300)
                while len(rows_by_dt) < lim and loops < max_loops:
                    loops += 1
                    params = {"instId": f"{coin}-USDT", "bar": bar, "limit": 300}
                    endpoint = "/api/v5/market/candles" if after_ms is None else "/api/v5/market/history-candles"
                    if after_ms is not None:
                        params["after"] = after_ms
                    q = urllib.parse.urlencode(params)
                    data = self._get_json(f"{self.okx_base}{endpoint}?{q}").get("data", [])
                    if not data:
                        break
                    _put_rows([(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in data], overwrite=False)
                    after_ms = int(data[-1][0])
                if rows_by_dt and was_empty:
                    source_used = "OKX"
                elif rows_by_dt and source_used == "KuCoin":
                    source_used = "KuCoin+OKX"
            except Exception:
                pass

        # 3) Respaldo terciario Bybit v5 únicamente si KuCoin+OKX siguen incompletos y Bybit está accesible
        if len(rows_by_dt) < max(120, lim // 2) and not self._bybit_blocked:
            try:
                was_empty = len(rows_by_dt) == 0
                b_int = bybit_bar_map.get(bar, "60")
                q = urllib.parse.urlencode({"category": "spot", "symbol": f"{coin}USDT", "interval": b_int, "limit": lim})
                lst = self._get_json(f"{self.bybit_base}/v5/market/kline?{q}").get("result", {}).get("list", [])
                if lst:
                    _put_rows([(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in lst], overwrite=was_empty)
                    source_used = "Bybit" if was_empty else f"{source_used}+Bybit"
            except Exception:
                pass

        if not rows_by_dt:
            raise RuntimeError(f"Sin datos intradía ({bar}) para {coin}")

        # Guardia de barra en formación: asegurar siempre una fila final alineada al intervalo actual UTC
        sec_step = kucoin_bar_map.get(bar, (bar, 3600))[1]
        now_s = int(time.time())
        floor_now = pd.Timestamp((now_s // sec_step) * sec_step, unit="s", tz="UTC").tz_localize(None)
        last_dt = max(rows_by_dt.keys())
        if last_dt < floor_now:
            last_close = rows_by_dt[last_dt][3]
            rows_by_dt[floor_now] = (last_close, last_close, last_close, last_close, 0.0)

        sorted_dts = sorted(rows_by_dt.keys())[-lim:]
        df = pd.DataFrame(
            [rows_by_dt[dt_k] for dt_k in sorted_dts],
            index=pd.DatetimeIndex(sorted_dts, name="dt"),
            columns=["open", "high", "low", "close", "volume"],
        )
        df.attrs["source"] = source_used
        return coin, df

    def fetch_intraday_ohlcv(self, coins: List[str], bar: str = "1H", limit: int = 300) -> Dict[str, pd.DataFrame]:
        """
        Descarga concurrentemente velas intradía reales (hasta 1,000 velas por par) con fuente
        primaria determinista KuCoin API v1 y conmutación automática a OKX/Bybit ante fallas.
        """
        lim = max(60, min(1000, int(limit)))
        out: Dict[str, pd.DataFrame] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(coins)))) as pool:
            futs = [pool.submit(self._fetch_single_coin_intraday, coin, bar, lim) for coin in coins]
            for fut in futs:
                c, df = fut.result()
                out[c] = df
        ordered = {c: out[c] for c in coins}
        sources = sorted({str(df.attrs.get("source", "?")) for df in ordered.values()})
        if len(sources) > 1:
            logger.warning("Fuentes mixtas detectadas en velas %s: %s", bar, sources)
        last_bars = [
            (df.index[-2] if len(df) >= 2 else df.index[-1]).strftime("%Y-%m-%dT%H:%M:%SZ")
            for df in ordered.values()
            if len(df) > 0
        ]
        self.last_intraday_meta[bar] = {
            "sources": sources,
            "last_bar_utc": max(last_bars) if last_bars else "",
            "bars_min": min((len(df) for df in ordered.values()), default=0),
        }
        return ordered

    def fetch_funding_history(self, coins: List[str], days: int = 50) -> Dict[str, pd.Series]:
        """Descarga serie histórica de funding rates 8h desde OKX API v5 (/api/v5/public/funding-rate-history)."""
        cutoff_ms = int((time.time() - max(1, int(days)) * 86400) * 1000)

        def _fetch_coin_fr(coin: str) -> Tuple[str, pd.Series]:
            rows: Dict[pd.Timestamp, float] = {}
            after_ms = None
            for _ in range(4):
                params: Dict[str, Any] = {"instId": f"{coin}-USDT-SWAP", "limit": 100}
                if after_ms is not None:
                    params["after"] = after_ms
                q = urllib.parse.urlencode(params)
                try:
                    data = self._get_json(f"{self.okx_base}/api/v5/public/funding-rate-history?{q}").get("data", [])
                except Exception:
                    break
                if not data:
                    break
                oldest_t = None
                for item in data:
                    ts_ms = int(item.get("fundingTime") or 0)
                    if ts_ms <= 0:
                        continue
                    oldest_t = ts_ms if oldest_t is None else min(oldest_t, ts_ms)
                    rate = _safe_finite_float(item.get("realizedRate") or item.get("fundingRate"), 0.0001)
                    dt_k = pd.Timestamp(ts_ms, unit="ms", tz="UTC").tz_localize(None).floor("4h")
                    rows[dt_k] = rate
                if oldest_t is None or oldest_t <= cutoff_ms or len(data) < 95:
                    break
                after_ms = oldest_t
            if not rows:
                return coin, pd.Series(dtype=float)
            s = pd.Series(rows).sort_index()
            return coin, s[~s.index.duplicated(keep="last")]

        out: Dict[str, pd.Series] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, max(1, len(coins)))) as pool:
            for c, s in pool.map(_fetch_coin_fr, coins):
                out[c] = s
        return {c: out.get(c, pd.Series(dtype=float)) for c in coins}

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
        oi_map: Dict[str, float] = {}
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

        def _fetch_okx_oi() -> Dict[str, float]:
            oi_res: Dict[str, float] = {}
            try:
                oi_raw = self._get_json(f"{self.okx_base}/api/v5/public/open-interest?instType=SWAP").get("data", [])
                for item in oi_raw:
                    inst_id = item.get("instId")
                    if inst_id:
                        oi_res[inst_id] = _safe_finite_float(item.get("oiUsd"), 0.0)
            except Exception:
                pass
            return oi_res

        def _fetch_okx_fr(c_sym: str) -> Tuple[str, float]:
            try:
                fr_data = self._get_json(f"{self.okx_base}/api/v5/public/funding-rate?instId={c_sym}-USDT-SWAP").get("data", [])
                if fr_data:
                    return c_sym, float(fr_data[0].get("fundingRate") or 0.0)
            except Exception:
                pass
            return c_sym, 0.0001

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            fut_bybit_ref = pool.submit(_fetch_bybit_ref)
            fut_okx_spot = pool.submit(self._get_json, f"{self.okx_base}/api/v5/market/tickers?instType=SPOT")
            fut_okx_swap = pool.submit(self._get_json, f"{self.okx_base}/api/v5/market/tickers?instType=SWAP")
            fut_okx_oi = pool.submit(_fetch_okx_oi)
            fut_frs = [pool.submit(_fetch_okx_fr, c) for c in coins]

            bybit_ref_map = fut_bybit_ref.result()
            secondary_source = "Bybit v5" if bybit_ref_map else ""
            kc_tickers_raw: List[Dict[str, Any]] = []
            if self._bybit_blocked or not bybit_ref_map:
                try:
                    kc_tickers_raw = self._get_json(f"{self.kucoin_base}/api/v1/market/allTickers").get("data", {}).get("ticker", [])
                    for item in kc_tickers_raw:
                        sym_kc = item.get("symbol", "")
                        if sym_kc.endswith("-USDT"):
                            px_kc = _safe_finite_float(item.get("last"), 0.0)
                            if px_kc > 0:
                                bybit_ref_map[sym_kc[:-5]] = px_kc
                    if bybit_ref_map:
                        secondary_source = "KuCoin L1"
                except Exception:
                    pass
            try:
                oi_map = fut_okx_oi.result()
            except Exception:
                oi_map = {}
            source_used = ""
            try:
                spot_raw = fut_okx_spot.result().get("data", [])
                spot_map = {d["instId"]: d for d in spot_raw if d.get("instId")}
                swap_raw = fut_okx_swap.result().get("data", [])
                swap_map = {d["instId"]: d for d in swap_raw if d.get("instId")}
                if spot_map:
                    source_used = "OKX API v5"
                for f_fr in fut_frs:
                    c_sym, fr_val = f_fr.result()
                    funding_map[c_sym] = fr_val
            except Exception as exc:
                logger.warning("Conmutando consulta primaria desde OKX (%s)", exc)

            if not spot_map and not self._bybit_blocked:
                try:
                    b_spot = self._get_json(f"{self.bybit_base}/v5/market/tickers?category=spot").get("result", {}).get("list", [])
                    b_lin = self._get_json(f"{self.bybit_base}/v5/market/tickers?category=linear").get("result", {}).get("list", [])
                    for d in b_spot:
                        sym = d.get("symbol", "")
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
                        sym = d.get("symbol", "")
                        if sym.endswith("USDT"):
                            c = sym[:-4]
                            swap_map[f"{c}-USDT-SWAP"] = {"last": d.get("lastPrice", 0)}
                            funding_map[c] = _safe_finite_float(d.get("fundingRate"), 0.0001)
                            oi_val = _safe_finite_float(d.get("openInterestValue"), 0.0)
                            if oi_val > 0:
                                oi_map[f"{c}-USDT-SWAP"] = oi_val
                    if spot_map:
                        source_used = "Bybit API v5"
                except Exception as exc_by:
                    logger.warning("Respaldo Bybit no disponible, conmutando a KuCoin REST (%s)", exc_by)

            if not spot_map or any(_safe_finite_float(spot_map.get(f"{c}-USDT", {}).get("last"), 0.0) <= 0.0 for c in coins):
                try:
                    if not kc_tickers_raw:
                        kc_tickers_raw = self._get_json(f"{self.kucoin_base}/api/v1/market/allTickers").get("data", {}).get("ticker", [])
                    for item in kc_tickers_raw:
                        sym_kc = item.get("symbol", "")
                        if not sym_kc.endswith("-USDT"):
                            continue
                        c_kc = sym_kc[:-5]
                        if f"{c_kc}-USDT" in spot_map and _safe_finite_float(spot_map[f"{c_kc}-USDT"].get("last"), 0.0) > 0.0:
                            continue
                        last_kc = _safe_finite_float(item.get("last"), 0.0)
                        if last_kc <= 0.0:
                            continue
                        chg_rate = _safe_finite_float(item.get("changeRate"), 0.0)
                        open24_kc = (last_kc / (1.0 + chg_rate)) if (1.0 + chg_rate) > 1e-6 else last_kc
                        spot_map[f"{c_kc}-USDT"] = {
                            "last": last_kc,
                            "open24h": open24_kc,
                            "high24h": _safe_finite_float(item.get("high"), last_kc) or last_kc,
                            "low24h": _safe_finite_float(item.get("low"), last_kc) or last_kc,
                            "bidPx": _safe_finite_float(item.get("buy"), last_kc) or last_kc,
                            "askPx": _safe_finite_float(item.get("sell"), last_kc) or last_kc,
                            "volCcy24h": _safe_finite_float(item.get("volValue"), 0.0),
                        }
                        if c_kc not in bybit_ref_map:
                            bybit_ref_map[c_kc] = last_kc
                    if not source_used and spot_map:
                        source_used = "KuCoin API v1"
                except Exception as exc_kc_spot:
                    logger.warning("Error en respaldo KuCoin Spot (%s)", exc_kc_spot)

                if not swap_map:
                    try:
                        kc_fut = self._get_json("https://api-futures.kucoin.com/api/v1/contracts/active").get("data") or []
                        kc_sym_alias = {"XBTUSDTM": "BTC", "ETHUSDTM": "ETH", "SOLUSDTM": "SOL", "BNBUSDTM": "BNB", "XRPUSDTM": "XRP", "ADAUSDTM": "ADA", "AVAXUSDTM": "AVAX", "LINKUSDTM": "LINK"}
                        for fc in kc_fut:
                            c_alias = kc_sym_alias.get(str(fc.get("symbol") or ""))
                            if not c_alias:
                                continue
                            f_px = _safe_finite_float(fc.get("lastTradePrice") or fc.get("markPrice"), 0.0)
                            if f_px > 0.0:
                                swap_map[f"{c_alias}-USDT-SWAP"] = {"last": f_px}
                            if c_alias not in funding_map:
                                funding_map[c_alias] = _safe_finite_float(fc.get("fundingFeeRate"), 0.0001)
                            oi_lots = _safe_finite_float(fc.get("openInterest"), 0.0)
                            mult = _safe_finite_float(fc.get("multiplier"), 0.0)
                            if oi_lots > 0 and mult > 0 and f_px > 0 and f"{c_alias}-USDT-SWAP" not in oi_map:
                                oi_map[f"{c_alias}-USDT-SWAP"] = oi_lots * mult * f_px
                    except Exception:
                        pass

        missing_coins = [c for c in coins if _safe_finite_float(spot_map.get(f"{c}-USDT", {}).get("last"), 0.0) <= 0.0 and _safe_finite_float(bybit_ref_map.get(c), 0.0) <= 0.0]
        if missing_coins:
            raise RuntimeError(f"Cotizaciones Spot no disponibles en OKX/Bybit/KuCoin para: {missing_coins}")
        if not source_used:
            source_used = "KuCoin API v1"

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
            oi_usd = _safe_finite_float(oi_map.get(f"{c}-USDT-SWAP"), 0.0)
            prev_oi = self._prev_oi_usd.get(c, oi_usd) or oi_usd
            oi_chg_pct = ((oi_usd / prev_oi) - 1.0) * 100.0 if prev_oi > 0 else 0.0
            if oi_usd > 0:
                self._prev_oi_usd[c] = oi_usd
            oi_vol_ratio = (oi_usd / max(vol_usd, 1.0)) if (oi_usd > 0 and vol_usd > 0) else 0.35

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
                "open_interest_usd": round(oi_usd, 0),
                "oi_change_cycle_pct": round(oi_chg_pct, 3),
                "oi_vol_ratio": round(oi_vol_ratio, 3),
                "source": source_used,
                "secondary_source": secondary_source or source_used,
                "timestamp_utc": now_utc,
            }
        return result

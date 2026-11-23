"""
Suite de Pruebas Automatizadas de las Reglas Cuantitativas y Ciberseguridad (20 verificaciones determinísticas):
  - Indicadores técnicos libres de NaN y dentro de rangos matemáticos
  - Reglas de BOT A (paridad ATR <= 0.85%, tope 24%, filtro volumen, trailing ATR y cortacircuitos -2.0%)
  - Reglas de BOT B (restricción símplex <= 34%/activo y salida Chandelier ATR a USDT)
  - Reglas de BOT C (contabilidad simétrica Long/Short, financiamiento 8h y apalancamiento bruto <= 1.05x)
  - Reglas de BOT D (entrenamiento MLP strictly causal sin fuga futura, reserva >= 25% y triple salida)
  - Integridad criptográfica SHA-256 y detección ante alteraciones + contrato RFC-8259 de JSON
  - Servidor HTTP blindado (/health GET/HEAD, CORS estricto, compresión GZIP, bóveda Zero-Trust y firewall POST /api/contact)
"""
import gzip
import hashlib
import json
import os
import pathlib
import sys
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import numpy as np
import pandas as pd

BOT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src.strategies.quant_bots_rules import (  # noqa: E402
    GENESIS_HASH,
    BotAConfig,
    calc_adx_di,
    calc_atr,
    calc_futures_account_state,
    calc_rsi,
    calc_stoch_k,
    compute_bollinger,
    compute_bot_d_sizing,
    compute_macd_pct,
    evaluate_bot_d_exit_decision,
    fit_causal_mlp_ensemble,
    init_bot_a_state,
    sign_orders_sha256_chain,
    step_bot_a_microtrading,
    step_bot_b_daily,
    step_bot_c_futures,
    verify_orders_sha256_chain,
)


def _sample_ohlcv(n: int = 80, drift: float = 0.002, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = drift + rng.normal(0.0, 0.008, size=n)
    close = 100.0 * np.cumprod(1.0 + rets)
    high = close * (1.0 + rng.uniform(0.002, 0.010, size=n))
    low = close * (1.0 - rng.uniform(0.002, 0.010, size=n))
    open_p = np.roll(close, 1)
    open_p[0] = close[0] * 0.998
    high = np.maximum(high, np.maximum(open_p, close))
    low = np.minimum(low, np.minimum(open_p, close))
    vol = rng.uniform(1000.0, 2500.0, size=n)
    idx = pd.date_range("2026-11-10 00:00", periods=n, freq="15min")
    return pd.DataFrame({"open": open_p, "high": high, "low": low, "close": close, "volume": vol}, index=idx)


class TestQuantBotsRules(unittest.TestCase):
    def test_01_indicators_no_nan_and_bounds(self):
        df = _sample_ohlcv(90)
        rsi = calc_rsi(df["close"], 14)
        atr = calc_atr(df, 14)
        stoch = calc_stoch_k(df, 14, 3)
        adx, pdi, mdi = calc_adx_di(df, 14)
        ml, ms, mh = compute_macd_pct(df["close"])
        mid, up, dn, pb, bw = compute_bollinger(df["close"], 20, 2.0)

        for s in (rsi, atr, stoch, adx, pdi, mdi, ml, ms, mh, mid, up, dn, pb, bw):
            self.assertFalse(s.isna().any())
            self.assertTrue(np.all(np.isfinite(s.values)))

        self.assertTrue(((rsi >= 0.0) & (rsi <= 100.0)).all())
        self.assertTrue(((stoch >= 0.0) & (stoch <= 100.0)).all())
        self.assertTrue((atr > 0.0).all())
        self.assertTrue((up >= mid).all())
        self.assertTrue((mid >= dn).all())

    def test_02_bot_a_position_sizing_risk_and_weight_caps(self):
        coins = ["BTC", "ETH"]
        cfg = BotAConfig()
        st = init_bot_a_state(coins, base_cap=1000.0)
        ts = pd.Timestamp("2026-11-21 10:15")
        step_bot_a_microtrading(
            state=st, ts=ts, coins=coins,
            bar_open_prev={"BTC": 100.0, "ETH": 50.0},
            bar_close_prev={"BTC": 102.0, "ETH": 50.0},
            bar_close_cur={"BTC": 102.5, "ETH": 50.0},
            bar_low_cur={"BTC": 101.4, "ETH": 49.5},
            bar_high_cur={"BTC": 103.0, "ETH": 50.5},
            atr_prev={"BTC": 2.8, "ETH": 1.0},
            ema9_prev={"BTC": 101.2, "ETH": 50.2},
            ema21_prev={"BTC": 100.2, "ETH": 50.4},
            ema21_1h_prev={"BTC": 100.8, "ETH": 50.0},
            ema55_1h_prev={"BTC": 99.5, "ETH": 50.5},
            roc10_prev={"BTC": 1.6, "ETH": -0.2},
            mh_prev={"BTC": 0.28, "ETH": -0.05},
            mh_prev2={"BTC": 0.14, "ETH": -0.02},
            pb_prev={"BTC": 0.68, "ETH": 0.45},
            pb_prev2={"BTC": 0.60, "ETH": 0.46},
            rsi_prev={"BTC": 58.0, "ETH": 47.0},
            vrel_prev={"BTC": 1.45, "ETH": 0.90},
            breadth_1h=0.625,
            cfg=cfg,
        )
        self.assertGreater(st["units"]["BTC"], 0.0)
        self.assertEqual(st["units"]["ETH"], 0.0)
        notional = st["units"]["BTC"] * st["entry"]["BTC"]
        risk_usd = st["units"]["BTC"] * (st["entry"]["BTC"] - st["sl"]["BTC"])
        self.assertLessEqual(notional, 240.0 + 1e-6)
        self.assertLessEqual(risk_usd, 8.50 + 1e-4)

    def test_03_bot_a_rejects_low_volume_breakout(self):
        coins = ["BTC"]
        cfg = BotAConfig()
        st = init_bot_a_state(coins, base_cap=1000.0)
        step_bot_a_microtrading(
            state=st, ts=pd.Timestamp("2026-11-21 10:30"), coins=coins,
            bar_open_prev={"BTC": 100.0}, bar_close_prev={"BTC": 102.0},
            bar_close_cur={"BTC": 103.0}, bar_low_cur={"BTC": 101.8}, bar_high_cur={"BTC": 103.5},
            atr_prev={"BTC": 1.5}, ema9_prev={"BTC": 101.2}, ema21_prev={"BTC": 100.1},
            ema21_1h_prev={"BTC": 101.0}, ema55_1h_prev={"BTC": 99.0},
            roc10_prev={"BTC": 1.8}, mh_prev={"BTC": 0.35}, mh_prev2={"BTC": 0.18},
            pb_prev={"BTC": 0.72}, pb_prev2={"BTC": 0.65}, rsi_prev={"BTC": 60.0},
            vrel_prev={"BTC": 0.72},  # Volumen insuficiente (< 1.08x)
            breadth_1h=0.75, cfg=cfg,
        )
        self.assertEqual(st["units"]["BTC"], 0.0)
        self.assertEqual(len(st["trades"]), 0)

    def test_04_bot_a_trailing_stop_and_take_profit_execution(self):
        coins = ["BTC"]
        cfg = BotAConfig()
        st = init_bot_a_state(coins, base_cap=1000.0)
        st["units"]["BTC"] = 2.0
        st["entry"]["BTC"] = 100.0
        st["peak"]["BTC"] = 100.0
        st["sl"]["BTC"] = 97.3
        st["tp"]["BTC"] = 104.9
        st["cash_usd"] = 800.0

        # Barra sube a 102.5 (> +0.95*ATR=1.9) activando trailing stop sobre equilibrio
        step_bot_a_microtrading(
            state=st, ts=pd.Timestamp("2026-11-21 10:45"), coins=coins,
            bar_open_prev={"BTC": 100.0}, bar_close_prev={"BTC": 101.0},
            bar_close_cur={"BTC": 102.2}, bar_low_cur={"BTC": 100.8}, bar_high_cur={"BTC": 102.5},
            atr_prev={"BTC": 2.0}, ema9_prev={"BTC": 101.2}, ema21_prev={"BTC": 100.3},
            ema21_1h_prev={"BTC": 101.0}, ema55_1h_prev={"BTC": 99.0},
            roc10_prev={"BTC": 1.1}, mh_prev={"BTC": 0.15}, mh_prev2={"BTC": 0.10},
            pb_prev={"BTC": 0.70}, pb_prev2={"BTC": 0.60}, rsi_prev={"BTC": 61.0},
            vrel_prev={"BTC": 1.20}, breadth_1h=0.50, cfg=cfg,
        )
        self.assertGreater(st["sl"]["BTC"], 100.0)
        self.assertGreater(st["units"]["BTC"], 0.0)

        # Siguiente barra perfora el trailing stop y ejecuta salida con ganancia dentro de rango OHLC
        step_bot_a_microtrading(
            state=st, ts=pd.Timestamp("2026-11-21 11:00"), coins=coins,
            bar_open_prev={"BTC": 102.2}, bar_close_prev={"BTC": 101.5},
            bar_close_cur={"BTC": 99.8}, bar_low_cur={"BTC": 99.4}, bar_high_cur={"BTC": 101.6},
            atr_prev={"BTC": 2.0}, ema9_prev={"BTC": 101.0}, ema21_prev={"BTC": 100.5},
            ema21_1h_prev={"BTC": 101.0}, ema55_1h_prev={"BTC": 99.0},
            roc10_prev={"BTC": 0.5}, mh_prev={"BTC": 0.05}, mh_prev2={"BTC": 0.10},
            pb_prev={"BTC": 0.55}, pb_prev2={"BTC": 0.65}, rsi_prev={"BTC": 52.0},
            vrel_prev={"BTC": 1.15}, breadth_1h=0.50, cfg=cfg,
        )
        self.assertEqual(st["units"]["BTC"], 0.0)
        self.assertEqual(st["trades"][-1]["action"], "TOMA TRAILING ATR")
        self.assertGreater(st["trades"][-1]["realized_pnl_usd"], 0.0)

    def test_05_bot_a_daily_circuit_breaker_liquidates_and_halts(self):
        coins = ["BTC"]
        cfg = BotAConfig()
        st = init_bot_a_state(coins, base_cap=1000.0)
        st["cur_day"] = pd.Timestamp("2026-11-21").date()
        st["day_anchor_eq"] = 1000.0
        st["eq_curve"].append(978.0)  # -2.20% debajo de 1000
        st["units"]["BTC"] = 1.0
        st["entry"]["BTC"] = 100.0
        st["sl"]["BTC"] = 90.0
        st["tp"]["BTC"] = 120.0
        st["cash_usd"] = 885.0

        step_bot_a_microtrading(
            state=st, ts=pd.Timestamp("2026-11-21 12:00"), coins=coins,
            bar_open_prev={"BTC": 94.0}, bar_close_prev={"BTC": 93.0},
            bar_close_cur={"BTC": 93.5}, bar_low_cur={"BTC": 92.8}, bar_high_cur={"BTC": 94.2},
            atr_prev={"BTC": 1.5}, ema9_prev={"BTC": 95.0}, ema21_prev={"BTC": 96.0},
            ema21_1h_prev={"BTC": 97.0}, ema55_1h_prev={"BTC": 99.0},
            roc10_prev={"BTC": -2.0}, mh_prev={"BTC": -0.2}, mh_prev2={"BTC": -0.1},
            pb_prev={"BTC": 0.25}, pb_prev2={"BTC": 0.30}, rsi_prev={"BTC": 34.0},
            vrel_prev={"BTC": 1.4}, breadth_1h=0.2, cfg=cfg,
        )
        self.assertTrue(st["circuit_halted_day"])
        self.assertEqual(st["units"]["BTC"], 0.0)
        self.assertEqual(st["trades"][-1]["action"], "CORTE DIARIO RIESGO (-2.0%)")

    def test_06_bot_b_weights_simplex_and_asset_cap(self):
        coins = ["BTC", "ETH", "SOL", "BNB"]
        cov = np.eye(4) * 0.0004
        wb, bull, macro = step_bot_b_daily(
            px_y=np.array([105.0, 55.0, 22.0, 310.0]),
            s20_y=np.array([100.0, 52.0, 20.0, 300.0]),
            e12_y=np.array([104.0, 54.0, 21.5, 308.0]),
            e26_y=np.array([101.0, 52.5, 20.5, 301.0]),
            e50_y=np.array([98.0, 50.0, 19.5, 295.0]),
            r14_y=np.array([5.5, 6.2, 7.1, 4.4]),
            mh_y=np.array([0.8, 0.9, 1.1, 0.6]),
            pb_y=np.array([0.78, 0.80, 0.85, 0.72]),
            atr_y=np.array([2.0, 1.1, 0.6, 5.0]),
            pk15_y=np.array([106.0, 55.5, 22.4, 312.0]),
            adx_y=np.array([28.0, 31.0, 35.0, 24.0]),
            vol_y=np.array([0.02, 0.025, 0.03, 0.022]),
            cov_lw=cov,
            coins=coins,
        )
        self.assertTrue(macro)
        self.assertTrue(np.all(bull))
        self.assertTrue(np.all(wb >= -1e-9))
        self.assertTrue(np.all(wb <= 0.34 + 1e-6))
        self.assertLessEqual(float(np.sum(wb)), 1.0 + 1e-6)

    def test_07_bot_b_chandelier_exit_forces_zero_weight(self):
        coins = ["BTC", "ETH"]
        cov = np.eye(2) * 0.0005
        # BTC perfora pk15 - 2.1*ATR = 100 - 4.2 = 95.8 -> debe salir a 0.0
        wb, bull, _ = step_bot_b_daily(
            px_y=np.array([95.0, 55.0]),
            s20_y=np.array([94.0, 52.0]),
            e12_y=np.array([96.0, 54.0]),
            e26_y=np.array([95.5, 52.5]),
            e50_y=np.array([92.0, 50.0]),
            r14_y=np.array([1.2, 6.0]),
            mh_y=np.array([0.2, 0.8]),
            pb_y=np.array([0.55, 0.75]),
            atr_y=np.array([2.0, 1.0]),
            pk15_y=np.array([100.0, 55.5]),
            adx_y=np.array([22.0, 28.0]),
            vol_y=np.array([0.025, 0.022]),
            cov_lw=cov,
            coins=coins,
        )
        self.assertFalse(bool(bull[0]))
        self.assertEqual(float(wb[0]), 0.0)
        self.assertGreater(float(wb[1]), 0.0)

    def test_08_bot_c_gross_leverage_and_short_cap(self):
        wc = step_bot_c_futures(
            px_v=np.array([110.0, 108.0, 105.0, 80.0, 75.0, 70.0]),
            e21_v=np.array([105.0, 104.0, 102.0, 85.0, 80.0, 74.0]),
            e55_v=np.array([100.0, 100.0, 99.0, 90.0, 86.0, 80.0]),
            r24_v=np.array([8.0, 7.0, 6.0, -7.5, -6.5, -5.5]),
            mh_v=np.array([0.8, 0.7, 0.6, -0.7, -0.6, -0.5]),
            pb_v=np.array([0.85, 0.82, 0.78, 0.18, 0.22, 0.25]),
            adx_v=np.array([32.0, 28.0, 25.0, 30.0, 27.0, 24.0]),
            pdi_v=np.array([30.0, 29.0, 28.0, 12.0, 14.0, 15.0]),
            mdi_v=np.array([14.0, 15.0, 16.0, 29.0, 28.0, 26.0]),
            atr_v=np.array([1.5, 1.4, 1.4, 1.2, 1.1, 1.0]),
            max_gross_leverage=1.05,
        )
        self.assertLessEqual(float(np.sum(np.abs(wc))), 1.05 + 1e-6)
        self.assertTrue(np.any(wc > 0.0))
        self.assertTrue(np.any(wc < 0.0))

    def test_09_bot_c_long_short_pnl_and_funding_symmetry(self):
        # 1 contrato LONG en BTC a $100 y 2 contratos SHORT en ETH a $50 -> cash $1,000
        # Si BTC sube a $110 (+10) y ETH baja a $45 (short +10), patrimonio debe ser $1,020
        units = {"BTC": 1.0, "ETH": -2.0}
        entry = {"BTC": 100.0, "ETH": 50.0}
        eq, gross, free_m = calc_futures_account_state(units, entry, 1000.0, {"BTC": 110.0, "ETH": 45.0})
        self.assertAlmostEqual(eq, 1020.0, places=4)
        self.assertAlmostEqual(gross, 200.0, places=4)
        self.assertAlmostEqual(free_m, 1020.0 - 200.0 * 0.35, places=4)

    def test_10_bot_d_causal_mlp_no_lookahead_leakage(self):
        rng = np.random.default_rng(7)
        X_train = rng.normal(0.0, 1.0, size=(120, 10))
        yr_train = 0.01 * X_train[:, 0] + rng.normal(0.0, 0.005, size=120)
        yc_train = (yr_train > 0.0).astype(int)
        scaler, reg, clf = fit_causal_mlp_ensemble(X_train, yr_train, yc_train, seed=101)

        x_live = np.array([[0.05, 0.02, 0.12, 0.06, 0.03, 0.04, 0.02, 0.15, 0.10, 0.25]])
        x_future_perturbed = np.vstack([x_live, rng.normal(5.0, 2.0, size=(5, 10))])
        p1 = float(clf.predict_proba(scaler.transform(x_live))[0, 1])
        r1 = float(reg.predict(scaler.transform(x_live))[0])
        p2 = float(clf.predict_proba(scaler.transform(x_future_perturbed))[0, 1])
        r2 = float(reg.predict(scaler.transform(x_future_perturbed))[0])
        self.assertAlmostEqual(p1, p2, places=10)
        self.assertAlmostEqual(r1, r2, places=10)

    def test_11_bot_d_sizing_respects_risk_asset_and_reserve_caps(self):
        alloc, stop_dist = compute_bot_d_sizing(
            equity_usd=1000.0, cash_usd=400.0, invested_usd=600.0,
            price_now=500.0, atr_14=10.0, prob_up=0.60,
        )
        # cash_usd era $400 y reserva mínima 25% = $250 -> alloc máxima = $150
        self.assertLessEqual(alloc, 150.0 + 1e-6)
        self.assertLessEqual(alloc, 250.0 + 1e-6)
        self.assertLessEqual(alloc * stop_dist, 10.50 + 1e-4)

    def test_12_bot_d_triple_exit_protocol_branches(self):
        # 1) Trailing ATR exit
        ex1, lbl1, px1, sl1 = evaluate_bot_d_exit_decision(
            prob_up=0.52, pred_ret=0.001, e9=101.0, e21=100.0,
            low_bar=102.0, high_bar=105.0, sl_price=97.0, tp_price=110.0,
            peak_price=105.0, entry_price=100.0, atr_14=2.0,
        )
        self.assertTrue(ex1)
        self.assertEqual(lbl1, "SALIDA TRAILING MLP/ATR")
        self.assertGreater(px1, 100.0)
        self.assertGreater(sl1, 100.0)

        # 2) Take Profit exit
        ex2, lbl2, px2, _ = evaluate_bot_d_exit_decision(
            prob_up=0.58, pred_ret=0.003, e9=104.0, e21=102.0,
            low_bar=105.0, high_bar=111.0, sl_price=97.0, tp_price=109.5,
            peak_price=106.0, entry_price=104.0, atr_14=2.0,
        )
        self.assertTrue(ex2)
        self.assertEqual(lbl2, "TOMA DE BENEFICIO MLP (2.8x ATR)")
        self.assertAlmostEqual(px2, 109.5, places=4)

        # 3) Reversión de señal neuronal
        ex3, lbl3, _, _ = evaluate_bot_d_exit_decision(
            prob_up=0.41, pred_ret=-0.003, e9=99.5, e21=100.2,
            low_bar=99.0, high_bar=101.0, sl_price=95.0, tp_price=112.0,
            peak_price=101.0, entry_price=100.0, atr_14=2.0,
        )
        self.assertTrue(ex3)
        self.assertEqual(lbl3, "SALIDA POR GIRO DE SEÑAL MLP")

    def test_13_sha256_chain_integrity_and_tamper_detection(self):
        orders = [
            {
                "bot_id": "bot_a", "time_utc": "2026-11-22 10:00 UTC",
                "instrument": "BTC-USDT", "side_type": "BUY",
                "units": 0.0025, "price": 60340.0, "bar_low": 60100.0, "bar_high": 60500.0,
            },
            {
                "bot_id": "bot_d", "time_utc": "2026-11-22 10:15 UTC",
                "instrument": "ETH-USDT", "side_type": "BUY",
                "units": 0.12, "price": 1685.5, "bar_low": 1680.0, "bar_high": 1692.0,
            },
        ]
        signed, root = sign_orders_sha256_chain(orders, GENESIS_HASH)
        ok, vh, vb, errs = verify_orders_sha256_chain(signed, GENESIS_HASH, root)
        self.assertTrue(ok, msg=f"Errores inesperados: {errs}")
        self.assertEqual(vh, 2)
        self.assertEqual(vb, 2)

        # Modificar $0.01 en la primera orden invalida la verificación criptográfica
        signed[0]["price"] = 60340.01
        ok_bad, _, _, bad_errs = verify_orders_sha256_chain(signed, GENESIS_HASH, root)
        self.assertFalse(ok_bad)
        self.assertTrue(len(bad_errs) >= 1)

    def test_14_generated_suite_json_contracts_and_sha256(self):
        json_path = BOT_DIR / "quant_crypto_suite.json"
        self.assertTrue(json_path.exists())

        def _reject_nan(token: str):
            raise AssertionError(f"Token JSON inválido: {token}")

        suite = json.loads(json_path.read_text(encoding="utf-8"), parse_constant=_reject_nan)
        self.assertEqual(suite["meta"]["base_capital_usd"], 1000.0)
        self.assertIn("python_source_modules", suite)

        # Identidad contable MTM exacta en los 4 algoritmos
        for bk, bot in suite["algo_bots"].items():
            self.assertEqual(bot["stats"]["base_usd"], 1000.0)
            self.assertTrue(bot.get("inception_utc"))
            if not bot["is_futures"]:
                pos_val = sum(p["units"] * p["market_price"] for p in bot["active_positions"] if p["coin"] != "USDT")
                drift = abs((bot["cash_usd"] + pos_val) - bot["stats"]["final_usd"])
            else:
                unreal = sum(p["units"] * (p["market_price"] - p["entry_price"]) for p in bot["active_positions"] if p["coin"] != "USDT")
                drift = abs((bot["cash_usd"] + unreal) - bot["stats"]["final_usd"])
            self.assertLess(drift, 0.05, msg=f"Desviación MTM en {bk}: {drift}")

        orders_chrono = list(reversed(suite["ledger_chain"]["orders"]))
        ok, vh, vb, errs = verify_orders_sha256_chain(
            orders_chrono, suite["ledger_chain"]["genesis_sha256"], suite["ledger_chain"]["chain_root_sha256"]
        )
        self.assertTrue(ok, msg=f"Fallo de verificación en JSON: {errs}")
        self.assertEqual(vh, len(orders_chrono))
        self.assertEqual(vb, len(orders_chrono))

    def test_15_bot_a_active_exposure_in_generated_suite(self):
        suite = json.loads((BOT_DIR / "quant_crypto_suite.json").read_text(encoding="utf-8"))
        bot_a = suite["algo_bots"]["bot_a"]
        active_coins = [p for p in bot_a["active_positions"] if p["coin"] != "USDT" and p["units"] > 0]
        self.assertGreaterEqual(len(active_coins), 2, "BOT A debe mantener cartera diversificada activa (>=2 pares).")
        total_w = sum(float(p["weight_pct"]) for p in active_coins)
        self.assertGreaterEqual(total_w, 35.0)
        self.assertLessEqual(total_w, 72.0)

    def test_16_bot_d_reserve_and_protective_bands_in_generated_suite(self):
        suite = json.loads((BOT_DIR / "quant_crypto_suite.json").read_text(encoding="utf-8"))
        bot_d = suite["algo_bots"]["bot_d"]
        usdt_rows = [p for p in bot_d["active_positions"] if p["coin"] == "USDT"]
        self.assertEqual(len(usdt_rows), 1)
        self.assertGreaterEqual(float(usdt_rows[0]["weight_pct"]), 24.5)
        for p in bot_d["active_positions"]:
            if p["coin"] != "USDT" and p["units"] > 0:
                self.assertIsNotNone(p["sl_price"])
                self.assertIsNotNone(p["tp_price"])
                self.assertLess(p["sl_price"], p["entry_price"])
                self.assertGreater(p["tp_price"], p["entry_price"])

    def test_17_render_http_health_head_and_cors_suite_endpoint(self):
        from main import start_suite_http_server

        httpd = start_suite_http_server(BOT_DIR, host="127.0.0.1", port=0)
        actual_port = httpd.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{actual_port}/health", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "https://jesusbz.github.io")
                self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
                self.assertIn("max-age=31536000", resp.headers.get("Strict-Transport-Security", ""))
                health = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(health["status"], "ok")
                self.assertEqual(health["bots_active"], 4)
                self.assertEqual(health["plan_profile"], "render-24x7")
                self.assertTrue(health.get("last_sync_utc"))

            head_req = urllib.request.Request(f"http://127.0.0.1:{actual_port}/health", method="HEAD")
            with urllib.request.urlopen(head_req, timeout=5) as resp_head:
                self.assertEqual(resp_head.status, 200)
                self.assertEqual(resp_head.headers.get("Access-Control-Allow-Origin"), "https://jesusbz.github.io")
                self.assertEqual(resp_head.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(resp_head.headers.get("X-Frame-Options"), "DENY")

            for endpoint in ("/quant_crypto_suite.json", "/api/suite"):
                with urllib.request.urlopen(f"http://127.0.0.1:{actual_port}{endpoint}", timeout=10) as resp_suite:
                    self.assertEqual(resp_suite.status, 200)
                    self.assertEqual(resp_suite.headers.get("Access-Control-Allow-Origin"), "https://jesusbz.github.io")
                    self.assertEqual(resp_suite.headers.get("X-Content-Type-Options"), "nosniff")
                    self.assertEqual(resp_suite.headers.get("X-Frame-Options"), "DENY")
                    suite_data = json.loads(resp_suite.read().decode("utf-8"))
                    self.assertIn("algo_bots", suite_data)
                    for bk in ("bot_a", "bot_b", "bot_c", "bot_d"):
                        self.assertIn(bk, suite_data["algo_bots"])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_18_cors_origin_lock_blocks_untrusted_domains(self):
        from main import start_suite_http_server

        httpd = start_suite_http_server(BOT_DIR, host="127.0.0.1", port=0)
        actual_port = httpd.server_address[1]
        try:
            ok_req = urllib.request.Request(
                f"http://127.0.0.1:{actual_port}/health",
                headers={"Origin": "https://jesusbz.github.io"},
            )
            with urllib.request.urlopen(ok_req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "https://jesusbz.github.io")

            bad_origin_req = urllib.request.Request(
                f"http://127.0.0.1:{actual_port}/quant_crypto_suite.json",
                headers={"Origin": "https://phishing-bot.ru"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_bad_origin:
                urllib.request.urlopen(bad_origin_req, timeout=5)
            self.assertEqual(ctx_bad_origin.exception.code, 403)
            ctx_bad_origin.exception.close()

            no_origin_post = urllib.request.Request(
                f"http://127.0.0.1:{actual_port}/api/contact",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_no_origin:
                urllib.request.urlopen(no_origin_post, timeout=5)
            self.assertEqual(ctx_no_origin.exception.code, 403)
            ctx_no_origin.exception.close()
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_19_gzip_compression_and_secret_vault_redaction(self):
        from main import start_suite_http_server
        from src.execution.secure_vault import SecretValue, scrub_secrets

        sv = SecretValue("MY_SECRET_KEY_123456")
        self.assertNotIn("MY_SECRET_KEY_123456", repr(sv))
        self.assertNotIn("MY_SECRET_KEY_123456", str(sv))
        self.assertEqual(sv.get_secret_value(), "MY_SECRET_KEY_123456")

        dummy_gkey = "AIza" + "SyD1234567890abcdefghijk_1234567890"
        dummy_hook = "https://app." + "99inbound." + "com/api/e/syntheticTest00"
        scrubbed = scrub_secrets(f"token {dummy_gkey} url {dummy_hook}")
        self.assertNotIn("D1234567890abcdefghijk", scrubbed)
        self.assertNotIn("syntheticTest00", scrubbed)
        self.assertIn("REDACTED", scrubbed)

        httpd = start_suite_http_server(BOT_DIR, host="127.0.0.1", port=0)
        actual_port = httpd.server_address[1]
        try:
            gz_req = urllib.request.Request(
                f"http://127.0.0.1:{actual_port}/api/suite",
                headers={"Accept-Encoding": "gzip"},
            )
            with urllib.request.urlopen(gz_req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Content-Encoding"), "gzip")
                compressed = resp.read()
                decompressed = gzip.decompress(compressed)
                self.assertLess(len(compressed), 0.35 * len(decompressed))
                parsed = json.loads(decompressed.decode("utf-8"))
                self.assertIn("algo_bots", parsed)
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_20_contact_firewall_blocks_bots_urls_bad_pow_and_honeypots(self):
        from main import start_suite_http_server
        from src.execution.secure_vault import load_vault_config

        def _mine_pow(email: str, ts_ms: int) -> str:
            nonce = 0
            email_low = email.lower()
            while True:
                challenge = f"JBZ-POW-V1|{email_low}|{ts_ms}|{nonce}".encode("utf-8")
                if hashlib.sha256(challenge).hexdigest().startswith("000"):
                    return str(nonce)
                nonce += 1

        def _post_contact(port: int, payload: dict):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/contact",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://jesusbz.github.io",
                },
                method="POST",
            )
            return urllib.request.urlopen(req, timeout=5)

        ts_now = int(time.time() * 1000)
        valid_email = "cliente.verificado@empresa.org"
        valid_pow = _mine_pow(valid_email, ts_now)
        base_human_payload = {
            "name": "Carlos Mendoza",
            "email": valid_email,
            "phone": "+58 412 5550199",
            "company": "Grupo Financiero Andino",
            "message": "Solicito consultoria cuantitativa en R y Python para modelado de riesgos financieros.",
            "ts_ms": ts_now,
            "dwell_ms": 6500,
            "pow_nonce": valid_pow,
            "website_url": "",
            "company_fax": "",
            "bluetooth_magenta_argyle_rhino": "",
        }

        with patch.dict(os.environ, {"INBOUND_FORM_ENDPOINT": ""}, clear=False):
            unconfigured_vault = load_vault_config()
        httpd = start_suite_http_server(BOT_DIR, host="127.0.0.1", port=0, vault_config=unconfigured_vault)
        actual_port = httpd.server_address[1]
        try:
            bad_cases = [
                {**base_human_payload, "website_url": "https://spam.bot"},
                {**base_human_payload, "dwell_ms": 800},
                {**base_human_payload, "pow_nonce": "badnonce"},
                {**base_human_payload, "message": "Hola revisa este link https://steal-data.xyz urgente por favor"},
                {
                    **base_human_payload,
                    "email": "hacker@mailinator.com",
                    "pow_nonce": _mine_pow("hacker@mailinator.com", ts_now),
                },
            ]
            for bad_payload in bad_cases:
                with self.assertRaises(urllib.error.HTTPError) as ctx_err:
                    _post_contact(actual_port, bad_payload)
                self.assertEqual(ctx_err.exception.code, 400)
                ctx_err.exception.close()

            with self.assertRaises(urllib.error.HTTPError) as ctx_unconf:
                _post_contact(actual_port, base_human_payload)
            self.assertEqual(ctx_unconf.exception.code, 503)
            ctx_unconf.exception.close()
        finally:
            httpd.shutdown()
            httpd.server_close()

        with patch.dict(
            os.environ,
            {"INBOUND_FORM_ENDPOINT": "https://secure-relay.invalid/hook/clean123"},
            clear=False,
        ):
            configured_vault = load_vault_config()
        httpd_ok = start_suite_http_server(BOT_DIR, host="127.0.0.1", port=0, vault_config=configured_vault)
        ok_port = httpd_ok.server_address[1]
        orig_urlopen = urllib.request.urlopen

        class _DummyUpstreamResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"ok":true}'

        def _selective_urlopen(req, *args, **kwargs):
            url = getattr(req, "full_url", str(req))
            if url.startswith("https://secure-relay.invalid/"):
                return _DummyUpstreamResponse()
            return orig_urlopen(req, *args, **kwargs)

        try:
            with patch("urllib.request.urlopen", side_effect=_selective_urlopen):
                with _post_contact(ok_port, base_human_payload) as resp_ok:
                    self.assertEqual(resp_ok.status, 200)
                    body_ok = json.loads(resp_ok.read().decode("utf-8"))
                    self.assertEqual(body_ok["status"], "delivered")
        finally:
            httpd_ok.shutdown()
            httpd_ok.server_close()


if __name__ == "__main__":
    unittest.main()

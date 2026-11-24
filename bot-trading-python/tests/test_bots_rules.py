"""
Suite de Pruebas Automatizadas de las Reglas Cuantitativas y Ciberseguridad (30 verificaciones determinísticas):
  - Indicadores técnicos libres de NaN y dentro de rangos matemáticos (incluyendo OBV Slope y métricas BTC)
  - Reglas de BOT A (paridad ATR modulado por régimen, tope 24%, filtro volumen, trailing ATR y límite máximo de pérdida diaria -2.0%)
  - Reglas de BOT B (restricción símplex <= 34%/activo, tope GMM y salida Chandelier ATR a USDT)
  - Reglas de BOT C (contabilidad simétrica Long/Short, financiamiento 8h, Open Interest y desapalancamiento progresivo)
  - Reglas de BOT D y Gobernanza Econométrica (Triple-Barrera causal, GMM 4 Regímenes, Ensemble 3-Clases con purga, reestimación OOS y Control Pre-Ejecución de Riesgo)
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
    RiskGatekeeperConfig,
    append_orders_sha256_chain,
    calc_adx_di,
    calc_atr,
    calc_futures_account_state,
    calc_obv_slope,
    calc_rsi,
    calc_stoch_k,
    calc_structure_and_btc_metrics,
    compute_bollinger,
    compute_bot_d_sizing,
    compute_macd_pct,
    compute_triple_barrier_labels,
    detect_market_regimes_gmm,
    evaluate_bot_d_exit_decision,
    evaluate_risk_gatekeeper,
    extract_ta_features_row,
    fit_causal_mlp_ensemble,
    fit_supervised_3class_ensemble,
    govern_champion_challenger,
    init_bot_a_state,
    predict_supervised_3class_ensemble,
    sign_orders_sha256_chain,
    step_bot_a_microtrading,
    step_bot_b_daily,
    step_bot_c_futures,
    step_realtime_futures_protections,
    step_realtime_spot_protections,
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
        usdt_rows = [p for p in bot_a["active_positions"] if p["coin"] == "USDT"]
        self.assertEqual(len(usdt_rows), 1)
        self.assertLessEqual(len(active_coins), 3)
        total_w = sum(float(p["weight_pct"]) for p in active_coins)
        self.assertLessEqual(total_w, 72.0)
        self.assertGreaterEqual(float(usdt_rows[0]["weight_pct"]), 28.0)
        for p in active_coins:
            self.assertIsNotNone(p["sl_price"])
            self.assertIsNotNone(p["tp_price"])
            self.assertLess(float(p["sl_price"]), float(p["tp_price"]))

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
                self.assertLess(p["sl_price"], max(p["entry_price"], p["market_price"]) * 1.0001)
                self.assertLess(p["sl_price"], p["tp_price"])
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

    def test_21_bot_a_no_same_bar_stop_partial_tp_and_vol_adx_gates(self):
        coins = ["BTC"]
        cfg = BotAConfig()
        st = init_bot_a_state(coins, base_cap=1000.0)
        st["units"]["BTC"] = 2.0
        st["entry"]["BTC"] = 100.0
        st["entry_fee"]["BTC"] = 200.0 * cfg.fee_rate
        st["peak"]["BTC"] = 100.0
        st["sl"]["BTC"] = 96.9
        st["tp"]["BTC"] = 106.2
        st["cash_usd"] = 800.0 - st["entry_fee"]["BTC"]

        # Barra volátil que toca +1.30x ATR (102.6) pero también baja a 100.1 (> SL pre-barra 96.9):
        # NO debe disparar falso stop intra-barra sobre el trailing recién activado.
        step_bot_a_microtrading(
            state=st, ts=pd.Timestamp("2026-11-22 10:15"), coins=coins,
            bar_open_prev={"BTC": 100.0}, bar_close_prev={"BTC": 101.0},
            bar_close_cur={"BTC": 101.8}, bar_low_cur={"BTC": 100.1}, bar_high_cur={"BTC": 102.6},
            atr_prev={"BTC": 2.0}, ema9_prev={"BTC": 101.0}, ema21_prev={"BTC": 100.3},
            ema21_1h_prev={"BTC": 101.0}, ema55_1h_prev={"BTC": 99.0},
            roc10_prev={"BTC": 1.1}, mh_prev={"BTC": 0.15}, mh_prev2={"BTC": 0.10},
            pb_prev={"BTC": 0.70}, pb_prev2={"BTC": 0.62}, rsi_prev={"BTC": 60.0},
            vrel_prev={"BTC": 1.30}, breadth_1h=0.625, cfg=cfg, adx_1h_prev={"BTC": 24.0},
        )
        self.assertEqual(st["units"]["BTC"], 2.0)
        self.assertGreaterEqual(st["sl"]["BTC"], 100.55 - 1e-6)

        # Siguiente barra alcanza +1.65x ATR (103.3): ejecuta TOMA PARCIAL 45% dejando 55% abierto
        step_bot_a_microtrading(
            state=st, ts=pd.Timestamp("2026-11-22 10:30"), coins=coins,
            bar_open_prev={"BTC": 101.0}, bar_close_prev={"BTC": 101.8},
            bar_close_cur={"BTC": 103.4}, bar_low_cur={"BTC": 101.5}, bar_high_cur={"BTC": 103.6},
            atr_prev={"BTC": 2.0}, ema9_prev={"BTC": 101.4}, ema21_prev={"BTC": 100.5},
            ema21_1h_prev={"BTC": 101.0}, ema55_1h_prev={"BTC": 99.0},
            roc10_prev={"BTC": 1.6}, mh_prev={"BTC": 0.22}, mh_prev2={"BTC": 0.15},
            pb_prev={"BTC": 0.78}, pb_prev2={"BTC": 0.70}, rsi_prev={"BTC": 63.0},
            vrel_prev={"BTC": 1.40}, breadth_1h=0.625, cfg=cfg, adx_1h_prev={"BTC": 25.0},
        )
        self.assertAlmostEqual(st["units"]["BTC"], 1.10, places=5)
        self.assertTrue(st["partial_taken"]["BTC"])
        self.assertIn("TOMA PARCIAL 45%", st["trades"][-1]["action"])
        self.assertGreater(st["trades"][-1]["realized_pnl_usd"], 0.0)

        # Filtro de rango muerto ATR (< 0.38%) y ADX 1H débil (< 18) bloquea entrada en ruido
        st_flat = init_bot_a_state(coins, base_cap=1000.0)
        step_bot_a_microtrading(
            state=st_flat, ts=pd.Timestamp("2026-11-22 10:45"), coins=coins,
            bar_open_prev={"BTC": 100.0}, bar_close_prev={"BTC": 100.5},
            bar_close_cur={"BTC": 100.8}, bar_low_cur={"BTC": 100.2}, bar_high_cur={"BTC": 101.0},
            atr_prev={"BTC": 0.20},  # 0.20% < 0.38% min_atr_pct
            ema9_prev={"BTC": 100.3}, ema21_prev={"BTC": 100.1},
            ema21_1h_prev={"BTC": 100.2}, ema55_1h_prev={"BTC": 99.5},
            roc10_prev={"BTC": 0.9}, mh_prev={"BTC": 0.12}, mh_prev2={"BTC": 0.06},
            pb_prev={"BTC": 0.70}, pb_prev2={"BTC": 0.60}, rsi_prev={"BTC": 58.0},
            vrel_prev={"BTC": 1.60}, breadth_1h=0.75, cfg=cfg, adx_1h_prev={"BTC": 26.0},
        )
        self.assertEqual(st_flat["units"]["BTC"], 0.0)

    def test_22_bot_b_l1_turnover_penalty_and_bot_c_funding_carry(self):
        coins = ["BTC", "ETH", "SOL", "BNB"]
        cov = np.eye(4) * 0.0004
        prev_w = np.array([0.30, 0.25, 0.15, 0.10])
        common_b = dict(
            px_y=np.array([105.0, 55.0, 22.0, 310.0]),
            s20_y=np.array([100.0, 52.0, 20.0, 300.0]),
            e12_y=np.array([104.0, 54.0, 21.5, 308.0]),
            e26_y=np.array([101.0, 52.5, 20.5, 301.0]),
            e50_y=np.array([98.0, 50.0, 19.5, 295.0]),
            r14_y=np.array([3.5, 5.2, 8.8, 7.4]),
            mh_y=np.array([0.4, 0.6, 1.3, 1.0]),
            pb_y=np.array([0.70, 0.75, 0.88, 0.82]),
            atr_y=np.array([2.0, 1.1, 0.6, 5.0]),
            pk15_y=np.array([106.0, 55.5, 22.4, 312.0]),
            adx_y=np.array([24.0, 27.0, 35.0, 31.0]),
            vol_y=np.array([0.02, 0.024, 0.028, 0.022]),
            cov_lw=cov,
            coins=coins,
            chandelier_mult=2.30,
        )
        wb_free, _, _ = step_bot_b_daily(**common_b, prev_w=None, turnover_penalty=0.0)
        wb_pen, _, _ = step_bot_b_daily(**common_b, prev_w=prev_w, turnover_penalty=0.15)
        self.assertLessEqual(float(np.sum(np.abs(wb_pen - prev_w))), float(np.sum(np.abs(wb_free - prev_w))) + 1e-4)
        self.assertTrue(np.all(wb_pen <= 0.34 + 1e-6))

        # Bot C respeta carry de funding 8h manteniendo apalancamiento bruto <= 1.05x
        wc_carry = step_bot_c_futures(
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
            funding_8h=np.array([-0.0004, 0.0002, 0.0001, 0.0005, 0.0003, -0.0002]),
        )
        self.assertLessEqual(float(np.sum(np.abs(wc_carry))), 1.05 + 1e-6)
        self.assertTrue(np.any(wc_carry > 0.0))
        self.assertTrue(np.any(wc_carry < 0.0))

    def test_23_bot_d_mlp_early_stopping_zero_convergence_warnings(self):
        import warnings
        from sklearn.exceptions import ConvergenceWarning

        rng = np.random.default_rng(19)
        X_train = rng.normal(0.0, 1.0, size=(320, 10))
        yr_train = 0.008 * X_train[:, 0] - 0.004 * X_train[:, 2] + rng.normal(0.0, 0.006, size=320)
        yc_train = (yr_train > 0.002).astype(int)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            scaler, reg, clf = fit_causal_mlp_ensemble(X_train, yr_train, yc_train, seed=101)
        conv_warns = [w for w in caught if issubclass(w.category, ConvergenceWarning)]
        self.assertEqual(len(conv_warns), 0, msg=f"ConvergenceWarning inesperado: {conv_warns}")
        self.assertTrue(clf.early_stopping)
        self.assertTrue(reg.early_stopping)
        p = float(clf.predict_proba(scaler.transform(X_train[:1]))[0, 1])
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_24_append_only_sha256_ledger_preserves_prior_orders(self):
        initial = [
            {
                "bot_id": "bot_a", "time_utc": "2026-11-24 03:30 UTC",
                "instrument": "AVAX-USDT", "side_type": "BUY",
                "units": 30.0, "price": 6.753, "bar_low": 6.72, "bar_high": 6.79,
            },
            {
                "bot_id": "bot_c", "time_utc": "2026-11-24 04:00 UTC",
                "instrument": "BTC-USDT-SWAP", "side_type": "LONG",
                "units": 0.004, "price": 61200.0, "bar_low": 61050.0, "bar_high": 61400.0,
            },
        ]
        signed_init, root_init = sign_orders_sha256_chain(initial, GENESIS_HASH)
        snap_ids = [o["tx_id"] for o in signed_init]
        snap_hashes = [o["sha256"] for o in signed_init]

        close_trade = [
            {
                "bot_id": "bot_a", "time_utc": "2026-11-24 04:32 UTC",
                "instrument": "AVAX-USDT", "side_type": "SELL",
                "units": 30.0, "price": 6.89, "bar_low": 6.75, "bar_high": 6.91,
                "realized_pnl_usd": 3.95, "realized_pnl_pct": 1.95,
            }
        ]
        extended, root_ext = append_orders_sha256_chain(signed_init, close_trade, GENESIS_HASH)
        self.assertEqual(len(extended), 3)
        self.assertEqual([o["tx_id"] for o in extended[:2]], snap_ids)
        self.assertEqual([o["sha256"] for o in extended[:2]], snap_hashes)
        self.assertEqual(extended[2]["tx_id"], "JBZ-A-0003")
        self.assertEqual(extended[2]["prev_hash"], root_init)
        ok, vh, vb, errs = verify_orders_sha256_chain(extended, GENESIS_HASH, root_ext)
        self.assertTrue(ok, msg=f"Errores cadena aditiva: {errs}")
        self.assertEqual(vh, 3)
        self.assertEqual(vb, 3)

    def test_25_realtime_spot_and_futures_protections_record_closes(self):
        coins = ["BTC", "ETH"]
        pf_spot = init_bot_a_state(coins, base_cap=1000.0)
        pf_spot["cash_usd"] = 800.0
        pf_spot["units"]["BTC"] = 2.0
        pf_spot["entry"]["BTC"] = 100.0
        pf_spot["entry_fee"]["BTC"] = 0.08
        pf_spot["sl"]["BTC"] = 96.9
        pf_spot["tp"]["BTC"] = 106.2

        # 1) Toma parcial 45% en tiempo real al alcanzar +1.40x ATR (102.8)
        em1 = step_realtime_spot_protections(
            pf_spot, "bot_a", "BOT A", coins,
            live_prices={"BTC": 103.0, "ETH": 50.0},
            forming_lows={"BTC": 100.2, "ETH": 49.8},
            forming_highs={"BTC": 103.1, "ETH": 50.2},
            atr_map={"BTC": 2.0, "ETH": 1.0},
            vrel_map={"BTC": 1.35, "ETH": 1.0},
            now_time_utc="2026-11-24 06:12 UTC", now_ts_iso="2026-11-24 06:12",
            fee_rate=0.0004, trail_activate_atr=1.05, trail_dist_atr=1.10,
            partial_tp_atr=1.40, partial_tp_frac=0.45,
        )
        self.assertEqual(len(em1), 1)
        self.assertIn("TOMA PARCIAL 45%", em1[0]["action"])
        self.assertGreater(em1[0]["realized_pnl_usd"], 0.0)
        self.assertAlmostEqual(pf_spot["units"]["BTC"], 1.10, places=5)
        self.assertGreater(pf_spot["sl"]["BTC"], 100.0)

        # 2) Cierre total restante al alcanzar TP (106.5 >= 106.2)
        em2 = step_realtime_spot_protections(
            pf_spot, "bot_a", "BOT A", coins,
            live_prices={"BTC": 106.5, "ETH": 50.0},
            forming_lows={"BTC": 102.5, "ETH": 49.8},
            forming_highs={"BTC": 106.6, "ETH": 50.2},
            atr_map={"BTC": 2.0, "ETH": 1.0},
            vrel_map={"BTC": 1.50, "ETH": 1.0},
            now_time_utc="2026-11-24 06:18 UTC", now_ts_iso="2026-11-24 06:18",
            fee_rate=0.0004, trail_activate_atr=1.05, trail_dist_atr=1.10,
            partial_tp_atr=1.40, partial_tp_frac=0.45,
        )
        self.assertEqual(len(em2), 1)
        self.assertEqual(em2[0]["action"], "TOMA DE BENEFICIO ATR")
        self.assertEqual(pf_spot["units"]["BTC"], 0.0)
        self.assertGreater(pf_spot["cash_usd"], 1008.0)

        # 3) Cierre en tiempo real de cobertura SHORT perpetua SWAP al alcanzar TP inferior
        pf_fut = {
            "realized_cash_c": 1000.0, "fees_cum": 0.0,
            "units": {"BTC": 0.0, "ETH": -4.0},
            "entry": {"BTC": 0.0, "ETH": 50.0},
            "entry_fee": {"BTC": 0.0, "ETH": 0.10},
            "sl": {"BTC": 0.0, "ETH": 52.5},
            "tp": {"BTC": 0.0, "ETH": 47.0},
            "peak": {"BTC": 0.0, "ETH": 50.0},
            "trades": [],
        }
        em_fut = step_realtime_futures_protections(
            pf_fut, coins,
            perp_prices={"BTC": 100.0, "ETH": 46.8},
            forming_lows={"BTC": 99.5, "ETH": 46.7},
            forming_highs={"BTC": 100.5, "ETH": 50.1},
            atr_map={"BTC": 2.0, "ETH": 1.0},
            vrel_map={"BTC": 1.1, "ETH": 1.4},
            now_time_utc="2026-11-24 06:21 UTC", now_ts_iso="2026-11-24 06:21",
            fee_rate=0.0005,
        )
        self.assertEqual(len(em_fut), 1)
        self.assertEqual(em_fut[0]["action"], "TOMA BENEFICIO SHORT SWAP")
        self.assertEqual(pf_fut["units"]["ETH"], 0.0)
        self.assertGreater(em_fut[0]["realized_pnl_usd"], 12.0)

    def test_26_triple_barrier_labeling_and_no_future_leakage(self) -> None:
        df_b = _sample_ohlcv(70, drift=0.004, seed=7)
        df_e = _sample_ohlcv(70, drift=-0.002, seed=9)
        close_df = pd.DataFrame({"BTC": df_b["close"], "ETH": df_e["close"]})
        high_df = pd.DataFrame({"BTC": df_b["high"], "ETH": df_e["high"]})
        low_df = pd.DataFrame({"BTC": df_b["low"], "ETH": df_e["low"]})
        atr_df = pd.DataFrame({
            "BTC": calc_atr(df_b, 14),
            "ETH": calc_atr(df_e, 14),
        })
        horizon = 4
        lbl1, ret1 = compute_triple_barrier_labels(
            close_df, high_df, low_df, atr_df,
            horizon=horizon, tp_atr_mult=1.80, sl_atr_mult=1.40, roundtrip_fee=0.0020,
        )
        self.assertTrue(lbl1.iloc[-horizon:].isna().all().all())
        valid_lbls = set(lbl1.iloc[:-horizon].stack().unique().tolist())
        self.assertTrue(valid_lbls.issubset({0.0, 1.0, 2.0}))
        self.assertFalse(ret1.iloc[:-horizon].isna().any().any())

        close_mod = close_df.copy()
        high_mod = high_df.copy()
        low_mod = low_df.copy()
        close_mod.iloc[50:] *= 1.35
        high_mod.iloc[50:] *= 1.40
        low_mod.iloc[50:] *= 0.85
        lbl2, ret2 = compute_triple_barrier_labels(
            close_mod, high_mod, low_mod, atr_df,
            horizon=horizon, tp_atr_mult=1.80, sl_atr_mult=1.40, roundtrip_fee=0.0020,
        )
        pd.testing.assert_frame_equal(lbl1.iloc[:44], lbl2.iloc[:44])
        pd.testing.assert_frame_equal(ret1.iloc[:44], ret2.iloc[:44])

    def test_27_gmm_four_market_regimes_classification(self) -> None:
        rng = np.random.default_rng(123)
        r_bull = np.full(60, 0.008) + rng.normal(0.0, 0.004, 60)
        r_flat = rng.normal(0.0, 0.002, 60)
        r_bear = np.full(60, -0.007) + rng.normal(0.0, 0.004, 60)
        r_hv = rng.normal(0.0, 0.055, 60)
        rets_btc = np.concatenate([r_bull, r_flat, r_bear, r_hv])
        idx = pd.date_range("2026-01-01", periods=len(rets_btc), freq="4h")
        c_btc = 100.0 * np.cumprod(1.0 + rets_btc)
        c_eth = 50.0 * np.cumprod(1.0 + 0.9 * rets_btc + rng.normal(0.0, 0.005, len(rets_btc)))
        c_sol = 20.0 * np.cumprod(1.0 + 1.1 * rets_btc + rng.normal(0.0, 0.006, len(rets_btc)))
        close_df = pd.DataFrame({"BTC": c_btc, "ETH": c_eth, "SOL": c_sol}, index=idx)
        adx_dict = {}
        for col in close_df.columns:
            s = close_df[col]
            oh = pd.DataFrame({"high": s * 1.006, "low": s * 0.994, "close": s}, index=idx)
            adx_dict[col] = calc_adx_di(oh, 14)[0]
        adx_df = pd.DataFrame(adx_dict, index=idx).bfill()

        res = detect_market_regimes_gmm(close_df, adx_df, btc_col="BTC", seed=42)
        cur = res["current_regime"]
        valid_codes = {"TENDENCIA_ALCISTA", "MERCADO_LATERAL", "TENDENCIA_BAJISTA", "ALTA_VOLATILIDAD"}
        self.assertIn(cur["code"], valid_codes)
        self.assertAlmostEqual(sum(cur["probabilities"].values()), 1.0, places=3)
        self.assertEqual(cur["code"], "ALTA_VOLATILIDAD")
        self.assertLessEqual(cur["risk_multiplier"], 0.55)
        self.assertGreaterEqual(cur["sl_atr_buffer"], 1.15)

    def test_28_supervised_3class_ensemble_purged_split_and_champion_challenger(self) -> None:
        import warnings
        from sklearn.exceptions import ConvergenceWarning

        n_bars = 260
        df_b = _sample_ohlcv(n_bars, drift=0.0025, seed=31)
        df_e = _sample_ohlcv(n_bars, drift=-0.001, seed=37)
        close_df = pd.DataFrame({"BTC": df_b["close"], "ETH": df_e["close"]})
        high_df = pd.DataFrame({"BTC": df_b["high"], "ETH": df_e["high"]})
        low_df = pd.DataFrame({"BTC": df_b["low"], "ETH": df_e["low"]})
        vol_df = pd.DataFrame({"BTC": df_b["volume"], "ETH": df_e["volume"]})
        vrel_df = vol_df / (vol_df.rolling(20, min_periods=5).mean() + 1e-9)
        atr_df = pd.DataFrame({"BTC": calc_atr(df_b, 14), "ETH": calc_atr(df_e, 14)})
        rsi_df = pd.DataFrame({c: calc_rsi(close_df[c], 14) for c in close_df.columns}).bfill()
        stoch_df = pd.DataFrame({"BTC": calc_stoch_k(df_b, 14, 3), "ETH": calc_stoch_k(df_e, 14, 3)}).bfill()
        ema9 = close_df.ewm(span=9, adjust=False).mean()
        ema21 = close_df.ewm(span=21, adjust=False).mean()
        ema55 = close_df.ewm(span=55, adjust=False).mean()
        roc12 = (close_df.pct_change(12) * 100.0).fillna(0.0)
        roc24 = (close_df.pct_change(24) * 100.0).fillna(0.0)
        macd_h = pd.DataFrame({c: compute_macd_pct(close_df[c])[2] for c in close_df.columns})
        bb_pb = pd.DataFrame({c: compute_bollinger(close_df[c], 20, 2.0)[3] for c in close_df.columns})
        bb_bw = pd.DataFrame({c: compute_bollinger(close_df[c], 20, 2.0)[4] for c in close_df.columns})
        obv_df = pd.DataFrame({c: calc_obv_slope(close_df[c], vol_df[c], 14) for c in close_df.columns})
        st = calc_structure_and_btc_metrics(close_df, high_df, low_df, "BTC", 20)
        lbl_df, ret_df = compute_triple_barrier_labels(close_df, high_df, low_df, atr_df, horizon=4)

        X_rows, yc_rows, yr_rows = [], [], []
        for ii in range(30, n_bars - 5):
            for c in ("BTC", "ETH"):
                if not np.isnan(lbl_df.iloc[ii][c]):
                    row = extract_ta_features_row(
                        ii, c, ema9, ema21, ema55, bb_pb, bb_bw, roc12, roc24, macd_h,
                        rsi_df, stoch_df, vrel_df,
                        obv_slope_df=obv_df, ema200_dist_df=st["ema200_dist"],
                        range_pos_df=st["range_pos"], btc_rel_df=st["btc_rel"], rsi_accel_df=st["rsi_accel"],
                    )
                    self.assertEqual(len(row), 15)
                    self.assertTrue(np.all(np.isfinite(row)))
                    X_rows.append(row)
                    yc_rows.append(int(lbl_df.iloc[ii][c]))
                    yr_rows.append(float(ret_df.iloc[ii][c]))

        with warnings.catch_warnings(record=True) as rec_w:
            warnings.simplefilter("always", ConvergenceWarning)
            bundle = fit_supervised_3class_ensemble(np.asarray(X_rows), np.asarray(yc_rows), np.asarray(yr_rows), purge_samples=32, seed=101)
            conv_w = [w for w in rec_w if issubclass(w.category, ConvergenceWarning)]
            self.assertEqual(len(conv_w), 0)

        self.assertGreater(bundle["purged_gap"], 0)
        pred = predict_supervised_3class_ensemble(
            bundle, np.asarray(X_rows[-6:]),
            regime_probs={"TENDENCIA_ALCISTA": 0.55, "MERCADO_LATERAL": 0.25, "TENDENCIA_BAJISTA": 0.10, "ALTA_VOLATILIDAD": 0.10},
        )
        p_sums = pred["prob_bear"] + pred["prob_flat"] + pred["prob_bull"]
        for s_val in p_sums:
            self.assertAlmostEqual(float(s_val), 1.0, places=5)

        champ1, dec1 = govern_champion_challenger(None, bundle, "2026-11-24 04:00")
        self.assertTrue(dec1["promoted"])
        self.assertEqual(dec1["active_version"], 1)

        better = dict(champ1)
        better["oos_brier_score"] = max(0.01, float(champ1["oos_brier_score"]) - 0.02)
        better["oos_expectancy_pct"] = float(champ1["oos_expectancy_pct"]) + 0.10
        champ2, dec2 = govern_champion_challenger(champ1, better, "2026-11-24 08:00")
        self.assertTrue(dec2["promoted"])
        self.assertEqual(dec2["active_version"], 2)

        worse = dict(champ2)
        worse["oos_brier_score"] = 0.95
        worse["oos_expectancy_pct"] = -5.0
        champ3, dec3 = govern_champion_challenger(champ2, worse, "2026-11-24 12:00")
        self.assertFalse(dec3["promoted"])
        self.assertEqual(dec3["active_version"], 2)
        self.assertEqual(champ3["version"], 2)

    def test_29_independent_risk_gatekeeper_veto_authority_and_kill_switch(self) -> None:
        cfg = RiskGatekeeperConfig()
        ok = evaluate_risk_gatekeeper(
            [1000.0, 1005.0], 1000.0, 0.20, 0.70,
            spread_bps=2.5, cross_exchange_bps=4.0,
            regime_info={"risk_multiplier": 0.80, "sl_atr_buffer": 1.05},
            rr_ratio=2.10, cfg=cfg,
        )
        self.assertTrue(ok["approved"])
        self.assertIsNone(ok["veto_code"])
        self.assertGreaterEqual(ok["effective_risk_pct"], 0.0025)
        self.assertLessEqual(ok["effective_risk_pct"], 0.0055)

        v_ks = evaluate_risk_gatekeeper([1000.0, 910.0], 920.0, 0.10, 0.70, cfg=cfg)
        self.assertFalse(v_ks["approved"])
        self.assertEqual(v_ks["veto_code"], "KILL_SWITCH_DRAWDOWN")

        v_day = evaluate_risk_gatekeeper([1000.0, 978.0], 1000.0, 0.10, 0.70, cfg=cfg)
        self.assertFalse(v_day["approved"])
        self.assertEqual(v_day["veto_code"], "DAILY_LOSS_LIMIT")

        v_sp = evaluate_risk_gatekeeper([1000.0, 1002.0], 1000.0, 0.10, 0.70, spread_bps=15.0, cfg=cfg)
        self.assertEqual(v_sp["veto_code"], "LIQUIDITY_SPREAD_HIGH")

        v_cx = evaluate_risk_gatekeeper([1000.0, 1002.0], 1000.0, 0.10, 0.70, cross_exchange_bps=52.0, cfg=cfg)
        self.assertEqual(v_cx["veto_code"], "ORACLE_DIVERGENCE")

        v_cap = evaluate_risk_gatekeeper([1000.0, 1002.0], 1000.0, 0.70, 0.68, cfg=cfg)
        self.assertEqual(v_cap["veto_code"], "EXPOSURE_CAP_REACHED")

        v_rr = evaluate_risk_gatekeeper([1000.0, 1002.0], 1000.0, 0.10, 0.70, rr_ratio=1.20, cfg=cfg)
        self.assertEqual(v_rr["veto_code"], "RR_BELOW_MINIMUM")

    def test_30_stress_scenarios_flash_crash_and_sideways_capital_preservation(self) -> None:
        coins = ["BTC", "ETH"]
        cfg_a = BotAConfig()
        gk_cfg = RiskGatekeeperConfig()

        # Escenario A: Desplome abrupto (-28%) con spread amplio y OBV negativo
        st_crash = init_bot_a_state(coins, 1000.0)
        px = 100.0
        for step_i in range(8):
            ts_c = pd.Timestamp("2026-11-20 00:00") + pd.Timedelta(minutes=15 * step_i)
            nxt = px * 0.96
            step_bot_a_microtrading(
                st_crash, ts_c, coins,
                bar_open_prev={"BTC": px * 1.01, "ETH": px * 0.505},
                bar_close_prev={"BTC": px, "ETH": px * 0.5},
                bar_close_cur={"BTC": nxt, "ETH": nxt * 0.5},
                bar_low_cur={"BTC": nxt * 0.985, "ETH": nxt * 0.49},
                bar_high_cur={"BTC": px, "ETH": px * 0.5},
                atr_prev={"BTC": px * 0.03, "ETH": px * 0.015},
                ema9_prev={"BTC": px * 1.02, "ETH": px * 0.51},
                ema21_prev={"BTC": px * 1.05, "ETH": px * 0.53},
                ema21_1h_prev={"BTC": px * 1.06, "ETH": px * 0.54},
                ema55_1h_prev={"BTC": px * 1.08, "ETH": px * 0.55},
                roc10_prev={"BTC": -4.0, "ETH": -4.5},
                mh_prev={"BTC": -0.5, "ETH": -0.6},
                mh_prev2={"BTC": -0.3, "ETH": -0.4},
                pb_prev={"BTC": 0.12, "ETH": 0.10},
                pb_prev2={"BTC": 0.20, "ETH": 0.18},
                rsi_prev={"BTC": 24.0, "ETH": 22.0},
                vrel_prev={"BTC": 2.4, "ETH": 2.5},
                breadth_1h=0.0,
                cfg=cfg_a,
                adx_1h_prev={"BTC": 34.0, "ETH": 35.0},
                obv_prev={"BTC": -0.65, "ETH": -0.70},
                ema200_dist_prev={"BTC": -0.18, "ETH": -0.20},
                regime_code="ALTA_VOLATILIDAD",
                spread_bps_map={"BTC": 18.0, "ETH": 22.0},
                risk_mult=0.50,
            )
            px = nxt

        self.assertGreaterEqual(st_crash["eq_curve"][-1], 995.0)
        self.assertEqual(len(st_crash["trades"]), 0)
        gk_crash = evaluate_risk_gatekeeper([1000.0, 912.0], 950.0, 0.0, 0.74, spread_bps=2.0, cfg=gk_cfg)
        self.assertFalse(gk_crash["approved"])
        self.assertEqual(gk_crash["veto_code"], "KILL_SWITCH_DRAWDOWN")

        # Escenario B: Rango lateral estrecho (+/- 0.15%) sin sobreoperación ni erosión de capital
        st_flat = init_bot_a_state(coins, 1000.0)
        for step_j in range(16):
            ts_f = pd.Timestamp("2026-11-21 00:00") + pd.Timedelta(minutes=15 * step_j)
            p_cur = 100.0 + (0.12 if step_j % 2 == 0 else -0.12)
            step_bot_a_microtrading(
                st_flat, ts_f, coins,
                bar_open_prev={"BTC": 100.0, "ETH": 50.0},
                bar_close_prev={"BTC": p_cur, "ETH": p_cur * 0.5},
                bar_close_cur={"BTC": 100.0, "ETH": 50.0},
                bar_low_cur={"BTC": 99.85, "ETH": 49.92},
                bar_high_cur={"BTC": 100.15, "ETH": 50.08},
                atr_prev={"BTC": 0.18, "ETH": 0.09},
                ema9_prev={"BTC": 100.0, "ETH": 50.0},
                ema21_prev={"BTC": 100.0, "ETH": 50.0},
                ema21_1h_prev={"BTC": 100.0, "ETH": 50.0},
                ema55_1h_prev={"BTC": 100.0, "ETH": 50.0},
                roc10_prev={"BTC": 0.05, "ETH": 0.04},
                mh_prev={"BTC": 0.0, "ETH": 0.0},
                mh_prev2={"BTC": 0.0, "ETH": 0.0},
                pb_prev={"BTC": 0.50, "ETH": 0.50},
                pb_prev2={"BTC": 0.49, "ETH": 0.49},
                rsi_prev={"BTC": 50.0, "ETH": 50.0},
                vrel_prev={"BTC": 0.80, "ETH": 0.85},
                breadth_1h=0.50,
                cfg=cfg_a,
                adx_1h_prev={"BTC": 14.0, "ETH": 13.5},
                obv_prev={"BTC": 0.01, "ETH": 0.0},
                ema200_dist_prev={"BTC": 0.0, "ETH": 0.0},
                regime_code="MERCADO_LATERAL",
                spread_bps_map={"BTC": 1.2, "ETH": 1.4},
                risk_mult=0.75,
            )
        self.assertGreaterEqual(st_flat["cash_usd"], 995.0)
        self.assertTrue(np.isfinite(st_flat["eq_curve"][-1]))
        al_d, _ = compute_bot_d_sizing(1000.0, 1000.0, 0.0, 100.0, 1.5, 0.62, max_risk_pct=0.0050 * 0.75)
        self.assertGreater(al_d, 0.0)
        self.assertLessEqual(al_d, 250.0)


if __name__ == "__main__":
    unittest.main()

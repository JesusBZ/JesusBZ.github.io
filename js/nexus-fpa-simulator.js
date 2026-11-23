/* ═══════════════════════════════════════════════════════════════════════
   NEXUS QUANT FP&A — MOTOR PREDICTIVO BAYESIANO, SIMULADOR Q×T Y MODALES
   100% Cliente · Nowcast P10–P90 · HBW-Nowcast Sub-Líneas · Z-MAD · Drawer
   ═══════════════════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';

  const SIM_COLORS = {
    cyan: '#0B1B33',
    cobalt: '#1D4ED8',
    violet: '#B8955A',
    emerald: '#059669',
    amber: '#B45309',
    rose: '#BE123C',
    slate: '#64748B',
    grid: 'rgba(11, 27, 51, 0.08)'
  };

  const MODAL_CHARTS = {};
  const AUDIT_CAT_LABELS = {
    HISTORICAL_OUTLIER: 'Anomalía Histórica Z-MAD',
    SUBLINE_MISMATCH: 'Conciliación Sub-Líneas',
    CLOSE_DRIFT: 'Desvío S4 → Cierre Contable'
  };

  const cmState = {
    type: null,
    focusKey: 'CLOUD_SAAS',
    tab: 'predictive',
    simMode: 'qt',
    simSubHorizon: 'S4',
    qtEditedS: 'qt',
    qtEditedS4: 'qt',
    s4Touched: false,
    predOverrides: {},
    predData: null,
    audSevFilter: 'ALL',
    audCatFilter: 'ALL'
  };

  const BASE_WEEK_WEIGHTS = { 1: 0.42, 2: 0.62, 3: 0.80, 4: 0.96 };
  const REM_UNCERTAINTY = { 1: 0.92, 2: 0.68, 3: 0.42, 4: 0.14 };

  const _ico = (n, s) => typeof global.ico === 'function' ? global.ico(n, s) : '';
  const _esc = s => typeof global.escHtml === 'function' ? global.escHtml(s) : String(s || '');
  const f$ = v => typeof global.f$ === 'function' ? global.f$(v) : `$${Math.round(v || 0)}`;
  const fN = v => typeof global.fN === 'function' ? global.fN(v) : Math.round(v || 0).toLocaleString('en-US');
  const fS = v => typeof global.fS === 'function' ? global.fS(v) : `$${Math.round(v || 0)}`;
  const fC = p => typeof global.fC === 'function' ? global.fC(p) : `${Number(p || 0).toFixed(1)}%`;

  function _cut() {
    return typeof global.getCut === 'function'
      ? global.getCut()
      : { A: 2026, M: 'NOVIEMBRE', S: 3 };
  }

  function _ymOrd(yr, mo) {
    const idx = global.MO.indexOf(String(mo).toUpperCase());
    return (parseInt(yr, 10) || 0) * 100 + (idx >= 0 ? idx + 1 : 0);
  }

  function _median(arr) {
    const a = (arr || []).filter(v => v !== null && v !== undefined && !isNaN(v)).map(Number).sort((x, y) => x - y);
    if (!a.length) return 0;
    const mid = Math.floor(a.length / 2);
    return a.length % 2 ? a[mid] : (a[mid - 1] + a[mid]) / 2;
  }

  function _mad(arr) {
    if (!arr || arr.length < 2) return 0;
    const m = _median(arr);
    return _median(arr.map(x => Math.abs(x - m)));
  }

  function _robustZ(val, hist) {
    const clean = (hist || []).filter(v => v > 0 && isFinite(v));
    if (!clean.length || !isFinite(val)) return { z: 0, med: 0, mad: 0 };
    const med = _median(clean);
    const mad = _mad(clean);
    const scale = Math.max(1.4826 * mad, Math.abs(med) * 0.045, 1.0);
    return { z: (val - med) / scale, med, mad };
  }

  function _robustZRel(val, hist) {
    const clean = (hist || []).filter(v => v > 0 && isFinite(v));
    if (!clean.length || !isFinite(val)) return { z: 0, med: 0, mad: 0 };
    const med = _median(clean);
    const mad = _mad(clean);
    const scale = Math.max(1.4826 * mad, Math.abs(med) * 0.05, 1e-6);
    return { z: (val - med) / scale, med, mad };
  }

  function _parseNumLoose(raw) {
    if (raw === null || raw === undefined || raw === '') return null;
    if (typeof raw === 'number') return isFinite(raw) ? raw : null;
    let s = String(raw).trim().replace(/[$€%\s]/g, '');
    if (!s) return null;
    if (s.includes(',') && s.includes('.')) {
      if (s.lastIndexOf(',') > s.lastIndexOf('.')) s = s.replace(/\./g, '').replace(',', '.');
      else s = s.replace(/,/g, '');
    } else if (s.includes(',')) {
      const parts = s.split(',');
      if (parts.length === 2 && parts[1].length <= 2) s = s.replace(',', '.');
      else s = s.replace(/,/g, '');
    }
    const n = parseFloat(s);
    return isFinite(n) ? n : null;
  }

  function _fmtNumInput(v, dec = 2) {
    if (v === null || v === undefined || !isFinite(v)) return '';
    return Number(Number(v).toFixed(dec));
  }

  function _fmtTariff(t) {
    return typeof global.fTariff === 'function' ? global.fTariff(t) : `$${Number(t || 0).toFixed(2)}`;
  }

  function _fmtSigned$(v) {
    const n = Number(v || 0);
    return `${n >= 0 ? '+' : ''}${f$(n)}`;
  }

  function _fmtPct(v, dec = 1) {
    const n = Number(v || 0);
    return `${n >= 0 ? '+' : ''}${n.toFixed(dec)}%`;
  }

  function _subCountsForMacroQ(line, subCode) {
    const meta = global.SUBLINE_META?.[`${line}::${subCode}`];
    if (meta) return Boolean(meta.countsMacroQ);
    return true;
  }

  function _extractSublinesRaw(yr, mo, s, line) {
    const obj = global.SUBLINEAS?.[String(yr)]?.[String(mo).toUpperCase()]?.[String(s)]?.[line] || {};
    const lc = (global.LINES_CONFIG || []).find(x => x.code === line);
    const keys = lc ? lc.sublines.map(x => x.code) : Object.keys(obj);
    return keys.map(sc => {
      const e = obj[sc] || {};
      const meta = global.SUBLINE_META?.[`${line}::${sc}`] || {};
      const dReal = Number(e.DOLARES?.REAL || 0);
      const dPpto = Number(e.DOLARES?.PRESUPUESTO || 0);
      const qReal = Number(e.CANTIDADES?.REAL || 0);
      const qPpto = Number(e.CANTIDADES?.PRESUPUESTO || 0);
      return {
        sub: sc,
        label: meta.label || global.SUB_LABELS?.[sc] || sc,
        hasQty: Boolean(meta.hasQty),
        dReal,
        dPpto,
        qReal,
        qPpto,
        tarifaReal: (meta.hasQty && qReal > 0) ? (dReal / qReal) : null,
        tarifaPpto: (meta.hasQty && qPpto > 0) ? (dPpto / qPpto) : null
      };
    });
  }

  function _destroyCharts() {
    Object.keys(MODAL_CHARTS).forEach(k => {
      try { MODAL_CHARTS[k].destroy(); } catch (_e) {}
      delete MODAL_CHARTS[k];
    });
  }

  function _regChart(canvasId, cfg) {
    if (MODAL_CHARTS[canvasId]) {
      try { MODAL_CHARTS[canvasId].destroy(); } catch (_e) {}
      delete MODAL_CHARTS[canvasId];
    }
    const canvas = document.getElementById(canvasId);
    if (!canvas || typeof global.Chart === 'undefined') return null;
    MODAL_CHARTS[canvasId] = new global.Chart(canvas.getContext('2d'), cfg);
    return MODAL_CHARTS[canvasId];
  }

  /* ═══════════════════════════════════════════════════════════════
     1. MOTOR PREDICTIVO BAYESIANO P10–P50–P90 + DETECTOR Z-MAD
     ═══════════════════════════════════════════════════════════════ */
  function computeClientPredictiveReport(targetA, targetM, targetS, overrides = {}) {
    const ovMap = overrides || {};
    const targetMoUp = String(targetM || 'NOVIEMBRE').toUpperCase();
    const targetYm = _ymOrd(targetA, targetMoUp);
    const april2026Ym = 202604;

    const allMonths = [];
    Object.keys(global.RAW || {}).forEach(yr => {
      Object.keys(global.RAW[yr] || {}).forEach(mo => {
        const up = String(mo).toUpperCase();
        if (global.MO.includes(up)) allMonths.push({ yr: String(yr), mo: up, ym: _ymOrd(yr, up) });
      });
    });
    allMonths.sort((a, b) => a.ym - b.ym);

    const priorMonths = allMonths.filter(m => m.ym < targetYm);
    const postAprMonths = priorMonths.filter(m => m.ym >= april2026Ym);
    const intraMonths = (targetYm >= april2026Ym && postAprMonths.length >= 2) ? postAprMonths : priorMonths;

    const linesOut = {};
    const outOfHistoryLines = [];
    let totEst = 0, totMeta = 0, totEvalClose = 0, totModel = 0, totP10 = 0, totP90 = 0;

    global.LN.forEach(line => {
      const sheetEst = global.sum(targetA, targetMoUp, targetS, line, 'DOLARES', 'REAL');
      const pptoSem = global.sum(targetA, targetMoUp, targetS, line, 'DOLARES', 'PRESUPUESTO');
      const sheetMeta = global.sum(targetA, targetMoUp, 4, line, 'DOLARES', 'PRESUPUESTO');
      const sheetQty = global.sum(targetA, targetMoUp, targetS, line, 'CANTIDADES', 'REAL');
      const pptoQtySem = global.sum(targetA, targetMoUp, targetS, line, 'CANTIDADES', 'PRESUPUESTO');
      const sheetMetaQty = global.sum(targetA, targetMoUp, 4, line, 'CANTIDADES', 'PRESUPUESTO');

      const baseSubs = _extractSublinesRaw(targetA, targetMoUp, targetS, line);
      const baseSubsS4 = _extractSublinesRaw(targetA, targetMoUp, 4, line);
      const subsS4Map = {};
      baseSubsS4.forEach(sr => { subsS4Map[sr.sub] = sr; });

      let fixedSheetS = 0;
      baseSubs.forEach(sr => {
        if (!sr.hasQty || !_subCountsForMacroQ(line, sr.sub)) fixedSheetS += sr.dReal;
      });
      const tariffVarSheetS = sheetQty > 0 ? Math.max(0, sheetEst - fixedSheetS) / sheetQty : 0;

      const histWeekVals = [], histQtyWeekVals = [], histTariffEffWeekVals = [];
      priorMonths.forEach(m => {
        const rs = global.sum(m.yr, m.mo, targetS, line, 'DOLARES', 'REAL');
        const qs = global.sum(m.yr, m.mo, targetS, line, 'CANTIDADES', 'REAL');
        if (rs > 0) histWeekVals.push(rs);
        if (qs > 0) histQtyWeekVals.push(qs);
        if (rs > 0 && qs > 0) histTariffEffWeekVals.push(rs / qs);
      });

      const histQtyS4Vals = [], histTariffEffS4Vals = [], qtyPacingRatios = [];
      const pushClose = list => {
        list.forEach(m => {
          const qs = global.sum(m.yr, m.mo, targetS, line, 'CANTIDADES', 'REAL');
          const q4 = global.sum(m.yr, m.mo, 4, line, 'CANTIDADES', 'REAL');
          const ci = global.getCi(m.yr, m.mo, line);
          const s4 = global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL');
          const eff = ci > 0 ? ci : s4;
          if (q4 > 0) {
            histQtyS4Vals.push(q4);
            if (eff > 0) histTariffEffS4Vals.push(eff / q4);
          }
          if (qs > 0 && q4 > 0) qtyPacingRatios.push(q4 / qs);
        });
      };
      pushClose(intraMonths);
      if (!histQtyS4Vals.length) pushClose(priorMonths);

      const medQtyRatio = qtyPacingRatios.length ? _median(qtyPacingRatios) : (4 / targetS);
      const histMetaVals = priorMonths.map(m => global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'PRESUPUESTO')).filter(v => v > 0);

      const ratios = [];
      intraMonths.forEach(m => {
        const rw = global.sum(m.yr, m.mo, targetS, line, 'DOLARES', 'REAL');
        const ci = global.getCi(m.yr, m.mo, line);
        const s4 = global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL');
        const denom = ci > 0 ? ci : s4;
        if (rw > 0 && denom > 0) ratios.push(denom / rw);
      });
      if (!ratios.length) {
        priorMonths.forEach(m => {
          const rw = global.sum(m.yr, m.mo, targetS, line, 'DOLARES', 'REAL');
          const s4 = global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL');
          if (rw > 0 && s4 > 0) ratios.push(s4 / rw);
        });
      }
      const medRatio = ratios.length ? _median(ratios) : (4 / targetS);

      const { z: zSheet, med: histMedWeek, mad: histMadWeek } = _robustZ(sheetEst, histWeekVals);
      const pacingHistBase = sheetEst > 0 ? sheetEst * medRatio : 0;

      // EWMA + YoY
      const lookupEff = {}, closedSeries = [];
      allMonths.forEach(m => {
        const ci = global.getCi(m.yr, m.mo, line);
        const s4 = global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL');
        const eff = ci > 0 ? ci : s4;
        if (eff > 0) lookupEff[`${m.yr}_${m.mo}`] = eff;
        if (m.ym < targetYm && eff > 0) closedSeries.push({ ...m, val: eff });
      });

      let trendEwma = sheetMeta;
      if (closedSeries.length) {
        let ewma = closedSeries[0].val;
        for (let i = 1; i < closedSeries.length; i++) ewma = 0.35 * closedSeries[i].val + 0.65 * ewma;
        const prevY = String((parseInt(targetA, 10) || 2026) - 1);
        const prevSame = lookupEff[`${prevY}_${targetMoUp}`] || 0;
        const yoyRatios = [];
        closedSeries.slice(-6).forEach(it => {
          const py = String((parseInt(it.yr, 10) || 2026) - 1);
          const pv = lookupEff[`${py}_${it.mo}`] || 0;
          if (pv > 0 && it.val > 0) yoyRatios.push(it.val / pv);
        });
        if (prevSame > 0 && yoyRatios.length) {
          const medYoy = Math.max(0.75, Math.min(1.45, _median(yoyRatios.slice(-3))));
          trendEwma = 0.65 * ewma + 0.35 * (prevSame * medYoy);
        } else {
          trendEwma = ewma;
        }
      }
      if (trendEwma <= 0) trendEwma = sheetMeta || pacingHistBase;

      const baseW = BASE_WEEK_WEIGHTS[targetS] || 0.6;
      const atten = 1 / (1 + 0.35 * Math.max(0, Math.abs(zSheet) - 1.5));
      const wEff = baseW * atten;
      const p50 = (pacingHistBase > 0 && trendEwma > 0)
        ? (wEff * pacingHistBase + (1 - wEff) * trendEwma)
        : (pacingHistBase || trendEwma);

      const recentCloses = priorMonths.map(m => global.getCi(m.yr, m.mo, line) || global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL')).filter(v => v > 0).slice(-8);
      const sigmaClose = 1.4826 * _mad(recentCloses);
      const sigmaRatio = ratios.length >= 2 && sheetEst > 0 ? 1.4826 * _mad(ratios) * sheetEst : 0;
      const remFac = REM_UNCERTAINTY[targetS] || 0.42;
      const sigmaComb = Math.sqrt(Math.pow(wEff * sigmaRatio, 2) + Math.pow((1 - wEff) * sigmaClose, 2));
      const sigmaEns = Math.max(sigmaComb * (0.65 + 0.35 * remFac), p50 * 0.04 * (1 + (4 - targetS) * 0.2), 1);
      const p10 = Math.max(0, p50 - 1.2815 * sigmaEns);
      const p90 = p50 + 1.2815 * sigmaEns;

      const shares = [];
      for (let w = 1; w <= 4; w++) {
        if (w === 4) { shares.push(1.0); continue; }
        const wRat = [];
        intraMonths.forEach(m => {
          const rw = global.sum(m.yr, m.mo, w, line, 'DOLARES', 'REAL');
          const denom = global.getCi(m.yr, m.mo, line) || global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL');
          if (rw > 0 && denom > 0) wRat.push(Math.min(1, rw / denom));
        });
        let sh = wRat.length ? _median(wRat) : (w / 4);
        if (shares.length && sh < shares[shares.length - 1]) sh = shares[shares.length - 1];
        shares.push(Math.max(0.05, Math.min(1, sh)));
      }

      const weeklyCurveModel = [], weeklyCurveP10 = [], weeklyCurveP90 = [];
      const halfLo = Math.max(0, p50 - p10), halfHi = Math.max(0, p90 - p50);
      shares.forEach((sh, idx) => {
        const wNum = idx + 1;
        const mPt = p50 * sh;
        const sf = wNum < 4 ? (0.45 + 0.55 * (wNum / 4)) : 1.0;
        weeklyCurveModel.push(Math.round(mPt * 100) / 100);
        weeklyCurveP10.push(Math.round((wNum < 4 ? Math.max(0, mPt - halfLo * sh * sf) : p10) * 100) / 100);
        weeklyCurveP90.push(Math.round((wNum < 4 ? (mPt + halfHi * sh * sf) : p90) * 100) / 100);
      });

      // Aplicar overrides de simulación
      const ov = ovMap[line] || {};
      const ovCurve = Array.isArray(ov.weeklyCurve) ? ov.weeklyCurve.slice(0, 4) : null;
      const hasOvCurve = ovCurve && ovCurve.some(v => v !== null && v !== undefined && !isNaN(v));
      const ovSubs = (ov.sublines && typeof ov.sublines === 'object') ? ov.sublines : {};
      const subHorizon = String(ov.sublinesHorizon || 'S4').toUpperCase() === 'S' ? 'S' : 'S4';

      let subTotalUsd = 0, subTotalQ = 0, subTotalFixed = 0, subMaxZ = 0;
      const subMismatchNotes = [];
      const sublinesDetail = [];

      baseSubs.forEach(r => {
        const sCode = r.sub;
        const hQS = [], hTS = [], hDS = [], hQS4 = [], hTS4 = [], hDS4 = [];
        intraMonths.forEach(m => {
          _extractSublinesRaw(m.yr, m.mo, targetS, line).forEach(sr => {
            if (sr.sub === sCode) {
              if (sr.dReal > 0) hDS.push(sr.dReal);
              if (sr.qReal > 0) hQS.push(sr.qReal);
              if (sr.tarifaReal > 0) hTS.push(sr.tarifaReal);
            }
          });
          _extractSublinesRaw(m.yr, m.mo, 4, line).forEach(sr => {
            if (sr.sub === sCode) {
              if (sr.dReal > 0) hDS4.push(sr.dReal);
              if (sr.qReal > 0) hQS4.push(sr.qReal);
              if (sr.tarifaReal > 0) hTS4.push(sr.tarifaReal);
            }
          });
        });

        const s4r = subsS4Map[sCode] || {};
        const medQS = _median(hQS), medTS = _median(hTS), medDS = _median(hDS);
        const medQS4 = _median(hQS4) || s4r.qPpto || 0;
        const medTS4 = _median(hTS4) || r.tarifaReal || r.tarifaPpto || 0;
        const medDS4 = _median(hDS4) || s4r.dPpto || 0;

        const sov = ovSubs[sCode];
        let simQ = null, simT = null, simD = null;
        if (sov) {
          const qIn = sov.qty != null && !isNaN(sov.qty) ? Number(sov.qty) : null;
          const tIn = sov.tariff != null && !isNaN(sov.tariff) ? Number(sov.tariff) : null;
          const aIn = sov.amount != null && !isNaN(sov.amount) ? Number(sov.amount) : null;
          if (qIn !== null && tIn !== null && r.hasQty) {
            simQ = qIn; simT = tIn; simD = simQ * simT;
          } else if (aIn !== null) {
            simD = aIn;
            if (qIn !== null && qIn > 0) { simQ = qIn; simT = simD / simQ; }
            else simQ = 0;
          } else if (qIn !== null && r.hasQty) {
            simQ = qIn; simT = r.tarifaReal || medTS4 || 0; simD = simQ * simT;
          }
          if (simD !== null) {
            subTotalUsd += simD;
            if (_subCountsForMacroQ(line, sCode) && simQ > 0) subTotalQ += simQ;
            else if (!r.hasQty || !_subCountsForMacroQ(line, sCode)) subTotalFixed += simD;
            const qb = subHorizon === 'S' ? hQS : hQS4;
            const tb = subHorizon === 'S' ? hTS : hTS4;
            if (simQ > 0 && qb.length) {
              const { z: zsq, med: mq } = _robustZRel(simQ, qb);
              subMaxZ = Math.max(subMaxZ, Math.abs(zsq));
              if (Math.abs(zsq) > 2.5) subMismatchNotes.push(`${r.label}: Q (${fN(simQ)}) atípico en ${subHorizon} (Z-MAD=${zsq.toFixed(2)} vs med ${fN(mq)}).`);
            }
            if (simT > 0 && tb.length) {
              const { z: zst, med: mt } = _robustZRel(simT, tb);
              subMaxZ = Math.max(subMaxZ, Math.abs(zst));
              if (Math.abs(zst) > 2.5) subMismatchNotes.push(`${r.label}: Tarifa (${_fmtTariff(simT)}) atípica en ${subHorizon} (Z-MAD=${zst.toFixed(2)} vs med ${_fmtTariff(mt)}).`);
            }
          }
        }

        sublinesDetail.push({
          sub: sCode,
          label: r.label,
          hasQty: r.hasQty,
          countsForMacroQ: Boolean(r.hasQty) && _subCountsForMacroQ(line, sCode),
          qReal: r.qReal, qPpto: r.qPpto, dReal: r.dReal, dPpto: r.dPpto,
          tarifaReal: r.tarifaReal, tarifaPpto: r.tarifaPpto,
          qPptoS4: s4r.qPpto || 0, dPptoS4: s4r.dPpto || 0, tarifaPptoS4: s4r.tarifaPpto ?? null,
          histMedianQ: medQS, histMedianTariff: medTS || null, histMedianD: medDS,
          histMedianQS4: medQS4, histMedianTariffS4: medTS4 || null, histMedianDS4: medDS4,
          simQty: simQ, simTariff: simT, simAmount: simD
        });
      });

      const hasSubAtS = Object.keys(ovSubs).length > 0 && subHorizon === 'S';
      const hasSubAtS4 = Object.keys(ovSubs).length > 0 && subHorizon === 'S4';

      let qtyActual = sheetQty, fixedActual = fixedSheetS, tariffVarActual = tariffVarSheetS, estActual = sheetEst, hasCutOv = false;
      if (hasSubAtS) {
        hasCutOv = true; estActual = subTotalUsd;
        qtyActual = subTotalQ > 0 ? subTotalQ : sheetQty; fixedActual = subTotalFixed;
        tariffVarActual = qtyActual > 0 ? Math.max(0, estActual - fixedActual) / qtyActual : 0;
      } else if (ov.calcFromQT || ov.qtyActual != null || ov.tariffActual != null || ov.fixedActual != null) {
        hasCutOv = true;
        qtyActual = ov.qtyActual != null ? Number(ov.qtyActual) : sheetQty;
        tariffVarActual = ov.tariffActual != null ? Number(ov.tariffActual) : tariffVarSheetS;
        fixedActual = ov.fixedActual != null ? Number(ov.fixedActual) : fixedSheetS;
        estActual = (ov.estActual != null && !ov.calcFromQT) ? Number(ov.estActual) : (qtyActual > 0 ? qtyActual * tariffVarActual + fixedActual : fixedActual);
      } else if (ov.estActual != null) {
        hasCutOv = true; estActual = Number(ov.estActual);
        if (qtyActual > 0) tariffVarActual = Math.max(0, estActual - fixedActual) / qtyActual;
      } else if (ovCurve && ovCurve[targetS - 1] != null) {
        hasCutOv = true; estActual = Number(ovCurve[targetS - 1]);
        if (qtyActual > 0) tariffVarActual = Math.max(0, estActual - fixedActual) / qtyActual;
      }

      const tariffEffActual = qtyActual > 0 ? estActual / qtyActual : 0;
      const weeklyActual = [];
      for (let w = 1; w <= 4; w++) {
        const ovW = ovCurve ? ovCurve[w - 1] : null;
        if (ovW !== null && ovW !== undefined && !isNaN(ovW)) weeklyActual.push(Math.round(Number(ovW) * 100) / 100);
        else if (w === targetS && hasCutOv) weeklyActual.push(Math.round(estActual * 100) / 100);
        else if (w === 4 && hasSubAtS4) weeklyActual.push(Math.round(subTotalUsd * 100) / 100);
        else if (w <= targetS) {
          const vw = global.sum(targetA, targetMoUp, w, line, 'DOLARES', 'REAL');
          weeklyActual.push(vw > 0 ? Math.round(vw * 100) / 100 : null);
        } else weeklyActual.push(null);
      }

      const metaMes = ov.metaMes != null ? Number(ov.metaMes) : sheetMeta;
      const pacingModel = estActual > 0 ? estActual * medRatio : 0;

      const biases = [], accs = [];
      priorMonths.forEach(m => {
        const ci = global.getCi(m.yr, m.mo, line);
        const s4 = global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL');
        if (ci > 0 && s4 > 0) {
          biases.push(((ci - s4) / s4) * 100);
          accs.push(Math.max(0, (1 - Math.abs(s4 - ci) / ci) * 100));
        }
      });
      const histCloseBias = biases.length ? _median(biases) : 0;
      const histAccuracyAvg = accs.length ? accs.reduce((a, b) => a + b, 0) / accs.length : 97.5;

      const hasCloseQtOv = ov.qtyClose != null || ov.tariffClose != null || ov.fixedClose != null;
      const qtyCloseDef = qtyActual > 0 ? qtyActual * medQtyRatio : 0;
      const fixedCloseDef = (fixedActual > 0 && qtyActual > 0) ? fixedActual * medRatio : fixedActual;
      let qtyCloseEval = qtyCloseDef, fixedCloseEval = fixedCloseDef, tariffVarClose = tariffVarActual, evalClose = 0, evalSource = '';

      if (hasSubAtS4) {
        evalClose = subTotalUsd;
        qtyCloseEval = subTotalQ > 0 ? subTotalQ : qtyCloseDef;
        fixedCloseEval = subTotalFixed;
        tariffVarClose = qtyCloseEval > 0 ? Math.max(0, evalClose - fixedCloseEval) / qtyCloseEval : 0;
        evalSource = 'Simulación Granular Sub-Líneas (S4)';
      } else if (hasCloseQtOv || ov.projClose != null) {
        qtyCloseEval = ov.qtyClose != null ? Number(ov.qtyClose) : qtyCloseDef;
        tariffVarClose = ov.tariffClose != null ? Number(ov.tariffClose) : tariffVarActual;
        fixedCloseEval = ov.fixedClose != null ? Number(ov.fixedClose) : fixedCloseDef;
        if (ov.projClose != null && (!hasCloseQtOv || !ov.calcFromQT)) {
          evalClose = Number(ov.projClose);
          if (qtyCloseEval > 0 && ov.tariffClose == null) tariffVarClose = Math.max(0, evalClose - fixedCloseEval) / qtyCloseEval;
          evalSource = 'Proyección Simulada Usuario (Cierre S4)';
        } else {
          evalClose = qtyCloseEval > 0 ? (qtyCloseEval * tariffVarClose + fixedCloseEval) : fixedCloseEval;
          evalSource = 'Simulador Interactivo (Q × Tarifa + Fijo)';
        }
      } else if (ovCurve && ovCurve[3] != null) {
        evalClose = Number(ovCurve[3]); evalSource = 'Curva Semanal Usuario (S4)';
      } else if (hasOvCurve) {
        let lastW = targetS;
        ovCurve.forEach((v, idx) => { if (v != null) lastW = idx + 1; });
        evalClose = Number(ovCurve[lastW - 1] ?? estActual) / Math.max(shares[lastW - 1], 0.15);
        evalSource = `Pacing desde S${lastW} Cargado`;
      } else if (hasCutOv) {
        evalClose = pacingModel; evalSource = `Pacing desde S${targetS} Simulado`;
      } else {
        evalClose = targetS < 4 ? (pptoSem > 0 ? metaMes * (estActual / pptoSem) : pacingModel) : estActual;
        evalSource = targetS < 4 ? 'Proyección Inercial Presupuesto' : 'Cierre Real S4';
      }

      const tariffEffClose = qtyCloseEval > 0 ? evalClose / qtyCloseEval : 0;
      const adjustedClose = evalClose * (1 + histCloseBias / 100);

      let probReach = p50 > 0 ? 100 : 0;
      if (metaMes > 0) {
        const zProb = Math.max(-20, Math.min(20, (evalClose - metaMes) / sigmaEns));
        probReach = 100 / (1 + Math.exp(-1.702 * zProb));
      }

      const { z: zEst } = _robustZ(estActual, histWeekVals);
      const metaRes = metaMes > 0 ? _robustZ(metaMes, histMetaVals) : { z: 0, med: _median(histMetaVals), mad: _mad(histMetaVals) };
      const qResS = (qtyActual > 0 && histQtyWeekVals.length) ? _robustZRel(qtyActual, histQtyWeekVals) : { z: 0, med: _median(histQtyWeekVals) };
      const tResS = (tariffEffActual > 0 && histTariffEffWeekVals.length) ? _robustZRel(tariffEffActual, histTariffEffWeekVals) : { z: 0, med: _median(histTariffEffWeekVals) };
      const qRes4 = (qtyCloseEval > 0 && histQtyS4Vals.length) ? _robustZRel(qtyCloseEval, histQtyS4Vals) : { z: 0, med: _median(histQtyS4Vals) };
      const tRes4 = (tariffEffClose > 0 && histTariffEffS4Vals.length) ? _robustZRel(tariffEffClose, histTariffEffS4Vals) : { z: 0, med: _median(histTariffEffS4Vals) };
      const zCloseModel = (p50 > 0 && evalClose > 0) ? (evalClose - p50) / sigmaEns : 0;

      const mismatchReasons = [];
      let opMaxZ = Math.max(Math.abs(zEst), Math.abs(qResS.z), Math.abs(tResS.z), Math.abs(qRes4.z), Math.abs(tRes4.z), Math.abs(zCloseModel), subMaxZ);

      if (histWeekVals.length && Math.abs(zEst) > 2.0) {
        mismatchReasons.push(`Ingreso S${targetS} (${f$(estActual)}) fuera de rango histórico (Z-MAD = ${zEst >= 0 ? '+' : ''}${zEst.toFixed(2)} vs mediana ${f$(histMedWeek)}).`);
      }
      if (histQtyWeekVals.length && qtyActual > 0 && Math.abs(qResS.z) > 2.2) {
        mismatchReasons.push(`Volumen Q en S${targetS} (${fN(qtyActual)}) se desvía del patrón (Z-MAD Q = ${qResS.z >= 0 ? '+' : ''}${qResS.z.toFixed(2)} vs mediana ${fN(qResS.med)}).`);
      }
      if (histTariffEffWeekVals.length && tariffEffActual > 0 && Math.abs(tResS.z) > 2.2) {
        mismatchReasons.push(`Tarifa efectiva (${_fmtTariff(tariffEffActual)}/Q) difiere de su histórico (Z-MAD Tarifa = ${tResS.z >= 0 ? '+' : ''}${tResS.z.toFixed(2)} vs med ${_fmtTariff(tResS.med)}/Q).`);
      }
      if (p50 > 0 && evalClose > 0) {
        const rIn = evalClose / p50;
        if (rIn < 0.72 || rIn > 1.38 || Math.abs(zCloseModel) > 1.85) {
          mismatchReasons.push(`Cierre simulado (${f$(evalClose)}) representa ${rIn.toFixed(2)}x el Nowcast Bayesiano P50 (${f$(p50)}; banda ${f$(p10)}–${f$(p90)}).`);
        }
      }
      if (subMismatchNotes.length) mismatchReasons.push(...subMismatchNotes.slice(0, 3));

      const penalty = Math.max(0, Math.abs(zCloseModel) - 0.75) * 14
        + Math.max(0, Math.abs(zEst) - 1.2) * 7
        + Math.max(0, Math.max(Math.abs(tResS.z), Math.abs(tRes4.z)) - 1.2) * 8.5
        + Math.max(0, Math.max(Math.abs(qResS.z), Math.abs(qRes4.z)) - 1.5) * 6.5
        + Math.max(0, subMaxZ - 2.0) * 6;
      const plausibilityScore = Math.max(5, Math.min(99, 100 - penalty));
      const verdictStatus = plausibilityScore >= 75 ? 'ok' : (plausibilityScore >= 45 ? 'warn' : 'critical');
      const verdictLabel = plausibilityScore >= 75 ? 'Proyección Consistente' : (plausibilityScore >= 45 ? 'Revisar Supuestos (Q / Tarifa)' : 'Fuera de Corredor Histórico');

      const isOutOfHistory = mismatchReasons.length > 0;
      const severity = (opMaxZ > 3.2 || plausibilityScore < 45) ? 'critical' : ((opMaxZ > 2.0 || isOutOfHistory) ? 'warning' : 'normal');
      if (isOutOfHistory) outOfHistoryLines.push(line);

      const monthlyHistory = allMonths.filter(m => m.ym <= targetYm).slice(-10).map(m => {
        const rs = global.sum(m.yr, m.mo, targetS, line, 'DOLARES', 'REAL');
        const qs = global.sum(m.yr, m.mo, targetS, line, 'CANTIDADES', 'REAL');
        return {
          month: `${m.mo.slice(0, 3)} ${String(m.yr).slice(-2)}`,
          realS: rs,
          realQtyS: qs,
          tariffEffS: (rs > 0 && qs > 0) ? (rs / qs) : 0,
          s4: global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'REAL'),
          meta: global.sum(m.yr, m.mo, 4, line, 'DOLARES', 'PRESUPUESTO'),
          cierre: global.getCi(m.yr, m.mo, line)
        };
      });

      totEst += estActual; totMeta += metaMes; totEvalClose += evalClose; totModel += p50; totP10 += p10; totP90 += p90;

      linesOut[line] = {
        line,
        lineName: global.DISP_MAP[line] || line,
        estActual, sheetEst, pptoSem, pptoQtySem, metaMes, metaQtyMes: sheetMetaQty,
        qtyActual, sheetQty, tariffVarActual, tariffEffActual, fixedActual,
        qtyCloseEval, tariffVarClose, tariffEffClose, fixedClose: fixedCloseEval,
        evalClose, evalSource, adjustedClose,
        modelExpected: p50, pacingModel, trendEwma, p10, p50, p90,
        histMedianWeek: histMedWeek, histMadWeek,
        histMedianMeta: metaRes.med, histMedianQtyWeek: qResS.med || 0,
        histMedianTariffWeek: tResS.med || 0, histMedianQtyS4: qRes4.med || 0, histMedianTariffS4: tRes4.med || 0,
        zScoreEst: zEst, zScoreMeta: metaRes.z, zScoreQty: qResS.z, zScoreTariff: tResS.z,
        zScoreQtyClose: qRes4.z, zScoreTariffClose: tRes4.z, zScoreCloseModel: zCloseModel,
        plausibilityScore, verdictStatus, verdictLabel,
        isOutOfHistory, severity, mismatchReasons,
        probReachMeta: probReach, histCloseBias, histAccuracyAvg,
        weeklyCurveActual: weeklyActual, weeklyCurveModel, weeklyCurveP10, weeklyCurveP90,
        sublinesDetail, monthlyHistory
      };
    });

    return {
      modelVersion: 2,
      anio: targetA,
      mes: targetMoUp,
      semana: targetS,
      source: 'client',
      summary: {
        totalEst: totEst, totalMeta: totMeta, totalEvalClose: totEvalClose,
        totalModelExpected: totModel, totalP10: totP10, totalP90: totP90,
        outOfHistoryCount: outOfHistoryLines.length, outOfHistoryLines
      },
      lines: linesOut
    };
  }

  /* ═══════════════════════════════════════════════════════════════
     2. APERTURA DE MODALES ANALÍTICOS & SIMULADOR INTERACTIVO
     ═══════════════════════════════════════════════════════════════ */
  function openChartModal(type, focusKey = 'CLOUD_SAAS', defaultTab = null) {
    cmState.type = type;
    cmState.focusKey = focusKey || 'CLOUD_SAAS';
    cmState.tab = defaultTab || (type === 'comp' ? 'predictive' : (type === 'waterfall' ? 'drivers' : (type === 'mix' ? 'mix' : 'hist')));
    cmState.qtEditedS = 'qt';
    cmState.qtEditedS4 = 'qt';
    cmState.s4Touched = false;

    document.getElementById('modal-backdrop')?.classList.add('open');
    document.getElementById('chart-modal')?.classList.add('open');
    renderActiveChartModal();
  }

  function closeChartModal() {
    document.getElementById('chart-modal')?.classList.remove('open');
    if (!document.getElementById('audit-modal')?.classList.contains('open') &&
        !document.getElementById('preload-modal')?.classList.contains('open') &&
        !document.getElementById('line-drawer')?.classList.contains('open')) {
      document.getElementById('modal-backdrop')?.classList.remove('open');
    }
    _destroyCharts();
  }

  function _setModalHdr(titleHtml, subText) {
    const t = document.getElementById('cm-title');
    const s = document.getElementById('cm-sub');
    if (t) t.innerHTML = titleHtml;
    if (s) s.textContent = subText;
  }

  function renderActiveChartModal() {
    _destroyCharts();
    const { A, M, S } = _cut();

    if (cmState.type === 'comp' || cmState.tab === 'predictive') {
      const rep = computeClientPredictiveReport(A, M, S, cmState.predOverrides);
      cmState.predData = rep;
      global.PREDICTIVE_DATA = rep;
      renderModalPredictive(rep, A, M, S);
    } else if (cmState.type === 'lines') {
      renderModalLines(A, M, S);
    } else if (cmState.type === 'gauges') {
      renderModalGauges(A, M, S);
    } else if (cmState.type === 'waterfall' || cmState.type === 'mix') {
      renderModalWaterfallMix(A, M, S);
    }
    if (typeof global.hydrateIcons === 'function') global.hydrateIcons(document.getElementById('chart-modal'));
  }

  function renderModalPredictive(rep, A, M, S) {
    const selLine = (cmState.focusKey && global.LN.includes(cmState.focusKey)) ? cmState.focusKey : global.LN[0];
    cmState.focusKey = selLine;
    const ld = rep.lines[selLine];
    const hasOv = Boolean(cmState.predOverrides[selLine] && Object.keys(cmState.predOverrides[selLine]).length);
    const simMode = cmState.simMode || 'qt';
    const subHorizon = cmState.simSubHorizon === 'S' ? 'S' : 'S4';

    _setModalHdr(
      `${_ico('sliders', 17)} <span>Simulador Interactivo Q × Tarifa &amp; Nowcast Bayesiano P10–P90</span>`,
      `${ld.lineName} · Corte ${M} ${A} (Semana ${S}) · ${ld.evalSource}`
    );

    const tabsEl = document.getElementById('cm-tabs');
    if (tabsEl) {
      tabsEl.innerHTML = global.LN.map((l, idx) => {
        const lineData = rep.lines[l];
        const flag = lineData.isOutOfHistory ? ' ⚡' : '';
        const ovMark = cmState.predOverrides[l] ? ' ●' : '';
        return `<button type="button" class="cm-tab ${l === selLine ? 'active' : ''}" onclick="window.__cmSetFocus('${l}')">
          <span class="line-dot" style="color:${global.LINE_COLORS[idx]};background:${global.LINE_COLORS[idx]};margin-right:3px;"></span>
          <span>${_esc(global.LL[idx])}${flag}${ovMark}</span>
        </button>`;
      }).join('');
    }

    const p50 = ld.p50;
    const evalClose = ld.evalClose;
    const prob = ld.probReachMeta;
    const score = ld.plausibilityScore;
    const scoreCol = score >= 75 ? SIM_COLORS.emerald : (score >= 45 ? SIM_COLORS.amber : SIM_COLORS.rose);

    const kpisEl = document.getElementById('cm-kpis');
    if (kpisEl) {
      kpisEl.innerHTML = `
        <div class="cm-kpi-card">
          <div class="cm-kpi-lbl">Real / Simulado Corte S${S}</div>
          <div class="cm-kpi-val" style="color:#0B1B33;">${f$(ld.estActual)}</div>
          <div class="cm-kpi-sub">Ppto S${S}: ${f$(ld.pptoSem)} (${ld.pptoSem > 0 ? ((ld.estActual / ld.pptoSem) * 100).toFixed(1) + '%' : '—'})</div>
        </div>
        <div class="cm-kpi-card">
          <div class="cm-kpi-lbl">Cierre S4 Evaluado</div>
          <div class="cm-kpi-val" style="color:#9A7438;">${f$(evalClose)}</div>
          <div class="cm-kpi-sub">Meta S4: ${f$(ld.metaMes)} · Prob. Logro: <strong>${prob.toFixed(0)}%</strong></div>
        </div>
        <div class="cm-kpi-card">
          <div class="cm-kpi-lbl">Nowcast Bayesiano P50</div>
          <div class="cm-kpi-val" style="color:#1D4ED8;">${f$(p50)}</div>
          <div class="cm-kpi-sub">Banda P10–P90: ${fS(ld.p10)} a ${fS(ld.p90)}</div>
        </div>
        <div class="cm-kpi-card">
          <div class="cm-kpi-lbl">Viabilidad &amp; Señal Z-MAD</div>
          <div class="cm-kpi-val" style="color:${scoreCol};">${score.toFixed(0)} / 100</div>
          <div class="cm-kpi-sub">${_esc(ld.verdictLabel)}</div>
        </div>
      `;
    }

    const subRows = ld.sublinesDetail || [];
    let simInputsHtml = '';

    if (simMode === 'qt') {
      simInputsHtml = `
        <div class="sim-stage-grid">
          <div class="sim-stage-card">
            <div class="sim-stage-hdr">
              <span>ETAPA 1 · CORTE SEMANA S${S}</span>
              <span class="sev-badge ${Math.abs(ld.zScoreQty) > 2 || Math.abs(ld.zScoreTariff) > 2 ? 'sev-warning' : 'sev-ok'}">Z(Q): ${ld.zScoreQty >= 0 ? '+' : ''}${ld.zScoreQty.toFixed(2)} · Z(P): ${ld.zScoreTariff >= 0 ? '+' : ''}${ld.zScoreTariff.toFixed(2)}</span>
            </div>
            <div class="sim-field-grid">
              <div class="sim-field">
                <label for="pred-qt-q-s">Cantidad S${S} (Q)</label>
                <input id="pred-qt-q-s" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.qtyActual, 0)}" oninput="window.__cmSyncQt('s','qt')" />
              </div>
              <div class="sim-field">
                <label for="pred-qt-t-s">Tarifa Variable ($/Q)</label>
                <input id="pred-qt-t-s" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.tariffVarActual, 4)}" oninput="window.__cmSyncQt('s','qt')" />
              </div>
              <div class="sim-field">
                <label for="pred-qt-fixed-s">Ingresos Fijos S${S} ($)</label>
                <input id="pred-qt-fixed-s" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.fixedActual, 2)}" oninput="window.__cmSyncQt('s','qt')" />
              </div>
              <div class="sim-field">
                <label for="pred-qt-est-s">Total Ingreso S${S} ($)</label>
                <input id="pred-qt-est-s" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.estActual, 2)}" oninput="window.__cmSyncQt('s','est')" />
              </div>
            </div>
            <div id="pred-qt-formula-s" class="sim-formula-hint">
              Q × Tarifa + Fijo = <strong>${f$(ld.estActual)}</strong> · Tarifa efectiva: <strong>${_fmtTariff(ld.tariffEffActual)}/Q</strong>
            </div>
          </div>

          <div class="sim-stage-card">
            <div class="sim-stage-hdr">
              <span>ETAPA 2 · PROYECCIÓN CIERRE S4 Y META</span>
              <span class="sev-badge ${Math.abs(ld.zScoreCloseModel) > 1.8 ? 'sev-warning' : 'sev-ok'}">Z(Cierre vs P50): ${ld.zScoreCloseModel >= 0 ? '+' : ''}${ld.zScoreCloseModel.toFixed(2)}</span>
            </div>
            <div class="sim-field-grid">
              <div class="sim-field">
                <label for="pred-qt-q-4">Cantidad Proy. S4 (Q)</label>
                <input id="pred-qt-q-4" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.qtyCloseEval, 0)}" oninput="window.__cmSyncQt('s4','qt')" />
              </div>
              <div class="sim-field">
                <label for="pred-qt-t-4">Tarifa Proy. S4 ($/Q)</label>
                <input id="pred-qt-t-4" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.tariffVarClose, 4)}" oninput="window.__cmSyncQt('s4','qt')" />
              </div>
              <div class="sim-field">
                <label for="pred-qt-fixed-4">Ingresos Fijos S4 ($)</label>
                <input id="pred-qt-fixed-4" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.fixedClose, 2)}" oninput="window.__cmSyncQt('s4','qt')" />
              </div>
              <div class="sim-field">
                <label for="pred-qt-close-4">Cierre Proyectado S4 ($)</label>
                <input id="pred-qt-close-4" class="sim-input" type="number" step="any" value="${_fmtNumInput(evalClose, 2)}" oninput="window.__cmSyncQt('s4','close')" />
              </div>
            </div>
            <div style="display:flex;gap:8px;align-items:flex-end;margin-top:8px;flex-wrap:wrap;">
              <div class="sim-field" style="flex:1;min-width:140px;">
                <label for="pred-sim-meta">Meta del Mes S4 ($)</label>
                <input id="pred-sim-meta" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.metaMes, 2)}" />
              </div>
              <div id="pred-qt-formula-4" class="sim-formula-hint" style="flex:2;margin-top:0;">
                Brecha vs Bayesiano P50: <strong class="${evalClose - p50 >= 0 ? 'pos' : 'neg'}">${_fmtSigned$(evalClose - p50)}</strong>
              </div>
            </div>
          </div>
        </div>
      `;
    } else if (simMode === 'sublines') {
      const subRowsHtml = subRows.map(sr => {
        const hasSim = sr.simAmount != null;
        const baseQ = subHorizon === 'S' ? sr.qReal : (sr.qPptoS4 || sr.histMedianQS4 || sr.qReal);
        const baseD = subHorizon === 'S' ? sr.dReal : (sr.dPptoS4 || sr.histMedianDS4 || sr.dReal);
        const baseT = sr.hasQty ? (subHorizon === 'S' ? (sr.tarifaReal || 0) : (sr.tarifaPptoS4 || (baseQ > 0 ? baseD / baseQ : 0))) : 0;
        const curQ = hasSim ? (sr.simQty || 0) : baseQ;
        const curT = hasSim ? (sr.simTariff || 0) : baseT;
        const curD = hasSim ? (sr.simAmount || 0) : baseD;
        return `<tr data-sub="${_esc(sr.sub)}" data-has-qty="${sr.hasQty ? '1' : '0'}" data-counts-q="${sr.countsForMacroQ ? '1' : '0'}" data-edited="qt">
          <td style="text-align:left;">
            <div style="font-weight:700;">${_esc(sr.label)}</div>
            <span class="kpi-badge ${sr.hasQty ? 'badge-blue' : 'badge-violet'}" style="font-size:9.5px;margin-top:3px;">${sr.hasQty ? (sr.countsForMacroQ ? 'Driver Q×T' : 'Auxiliar Q×T') : 'Recurrente Fijo'}</span>
          </td>
          <td>${sr.hasQty ? `${fN(baseQ)} · ${f$(baseD)}` : f$(baseD)}</td>
          <td>${sr.hasQty ? `<input class="sim-input" style="max-width:110px;" data-sub-q type="number" step="any" value="${_fmtNumInput(curQ, 0)}" oninput="window.__cmSyncSubRow('${_esc(sr.sub)}','qt')" />` : '<span class="neu">Fijo</span>'}</td>
          <td>${sr.hasQty ? `<input class="sim-input" style="max-width:105px;" data-sub-t type="number" step="any" value="${_fmtNumInput(curT, 4)}" oninput="window.__cmSyncSubRow('${_esc(sr.sub)}','qt')" />` : '<span class="neu">—</span>'}</td>
          <td><input class="sim-input" style="max-width:125px;" data-sub-d type="number" step="any" value="${_fmtNumInput(curD, 2)}" oninput="window.__cmSyncSubRow('${_esc(sr.sub)}','d')" /></td>
        </tr>`;
      }).join('');

      simInputsHtml = `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin:8px 0;flex-wrap:wrap;">
          <div class="pill-group">
            <button type="button" class="pill-btn ${subHorizon === 'S' ? 'active' : ''}" onclick="window.__cmSetSubHorizon('S')">Simular Corte S${S}</button>
            <button type="button" class="pill-btn ${subHorizon === 'S4' ? 'active' : ''}" onclick="window.__cmSetSubHorizon('S4')">Simular Cierre S4</button>
          </div>
          <div class="sim-field" style="min-width:180px;">
            <label for="pred-sim-meta">Meta del Mes S4 ($)</label>
            <input id="pred-sim-meta" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.metaMes, 2)}" />
          </div>
        </div>
        <div class="tbl-scroll">
          <table>
            <thead>
              <tr>
                <th>Sub-Línea</th>
                <th>Base ${subHorizon}</th>
                <th>Cantidad (Q)</th>
                <th>Tarifa ($/Q)</th>
                <th>Monto Simulado ($)</th>
              </tr>
            </thead>
            <tbody id="pred-sub-tbody">${subRowsHtml}</tbody>
          </table>
        </div>
      `;
    } else {
      const ovCur = cmState.predOverrides[selLine]?.weeklyCurve || ld.weeklyCurveActual || [null, null, null, null];
      const csvDef = ovCur.map(v => v == null ? '' : Math.round(v)).join(',');
      simInputsHtml = `
        <div class="sim-field-grid" style="grid-template-columns:repeat(4,minmax(0,1fr));margin-top:8px;">
          ${[1, 2, 3, 4].map(w => `
            <div class="sim-field">
              <label for="pred-wk-${w}">Semana ${w} ($)</label>
              <input id="pred-wk-${w}" class="sim-input" type="number" step="any" value="${ovCur[w - 1] != null ? _fmtNumInput(ovCur[w - 1], 2) : ''}" oninput="window.__cmSyncWeekly()" />
            </div>`).join('')}
        </div>
        <div class="sim-field-grid" style="margin-top:8px;">
          <div class="sim-field">
            <label for="pred-sim-meta">Meta Mensual S4 ($)</label>
            <input id="pred-sim-meta" class="sim-input" type="number" step="any" value="${_fmtNumInput(ld.metaMes, 2)}" />
          </div>
          <div class="sim-field">
            <label for="pred-sim-csv">Serie Rápida CSV (S1,S2,S3,S4)</label>
            <input id="pred-sim-csv" class="sim-input" type="text" value="${_esc(csvDef)}" />
          </div>
        </div>
      `;
    }

    const diagBanner = ld.mismatchReasons.length
      ? `<div class="verdict-banner ${ld.severity === 'critical' ? 'critical' : 'warn'}">
          <div>
            <div style="font-size:11px;font-weight:800;text-transform:uppercase;color:${ld.severity === 'critical' ? '#BE123C' : '#B45309'};margin-bottom:4px;">
              ${_ico('alert-triangle', 14)} Diagnóstico Robusto Z-MAD (${_esc(ld.lineName)})
            </div>
            <ul style="padding-left:18px;font-size:11.5px;color:#334155;line-height:1.45;">
              ${ld.mismatchReasons.map(r => `<li>${_esc(r)}</li>`).join('')}
            </ul>
          </div>
          <span class="sev-badge ${ld.severity === 'critical' ? 'sev-critical' : 'sev-warning'}">Score Viabilidad: ${score.toFixed(0)}/100</span>
        </div>`
      : `<div class="verdict-banner">
          <div style="font-size:12px;color:#065F46;display:flex;align-items:center;gap:8px;">
            ${_ico('check-circle', 15)} <span><strong>Supuestos Validados:</strong> Los parámetros de volumen Q, tarifa efectiva y trayectoria se mantienen dentro del corredor histórico Bayesiano P10–P90.</span>
          </div>
          <span class="sev-badge sev-ok">Score Viabilidad: ${score.toFixed(0)}/100</span>
        </div>`;

    const bodyEl = document.getElementById('cm-body');
    if (!bodyEl) return;
    bodyEl.innerHTML = `
      ${diagBanner}

      <div class="sim-box">
        <div class="cm-sec-title" style="color:#0B1B33;">
          <span style="display:inline-flex;align-items:center;gap:7px;">${_ico('zap', 15)} PANEL INTERACTIVO DE SIMULACIÓN &amp; SENSIBILIDAD (${_esc(ld.lineName)})</span>
          <div class="pill-group">
            <button type="button" class="pill-btn ${simMode === 'qt' ? 'active' : ''}" onclick="window.__cmSetSimMode('qt')">${_ico('sliders', 12)} Cantidades × Tarifas</button>
            <button type="button" class="pill-btn ${simMode === 'sublines' ? 'active' : ''}" onclick="window.__cmSetSimMode('sublines')">${_ico('layers', 12)} Por Sub-Línea (${subRows.length})</button>
            <button type="button" class="pill-btn ${simMode === 'weekly' ? 'active' : ''}" onclick="window.__cmSetSimMode('weekly')">${_ico('trending-up', 12)} Curva S1–S4 / CSV</button>
          </div>
        </div>

        ${simInputsHtml}

        <div class="sim-btn-row">
          <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap;">
            <button type="button" id="pred-eval-btn" class="btn-neon-primary" onclick="window.__cmEvalPredict('${selLine}')">
              ${_ico('activity', 14)} <span>Evaluar Simulación</span>
            </button>
            <button type="button" class="btn-ghost-sm" onclick="window.__cmQuickStress('${selLine}', 0.9)">-10% Estrés</button>
            <button type="button" class="btn-ghost-sm" onclick="window.__cmQuickStress('${selLine}', 1.0, true)">Alinear a Bayesiano P50</button>
            <button type="button" class="btn-ghost-sm" onclick="window.__cmQuickStress('${selLine}', 1.15)">+15% Expansión</button>
            <label class="btn-ghost-sm" style="cursor:pointer;">
              ${_ico('upload', 12)} <span>Cargar .csv</span>
              <input type="file" accept=".csv,.txt" style="display:none;" onchange="window.__cmHandleCsvUpload(this, '${selLine}')" />
            </label>
            ${hasOv ? `<button type="button" id="pred-reset-btn" class="btn-ghost-sm" style="border-color:rgba(190,18,60,0.45);color:#BE123C;" onclick="window.__cmResetPredict('${selLine}')">${_ico('rotate-ccw', 12)} <span>Restaurar Original</span></button>` : ''}
          </div>
          <div style="font-size:11px;color:#64748B;">
            Pacing: <strong style="color:#0B1B33;">${f$(ld.pacingModel)}</strong> · EWMA-YoY: <strong style="color:#0B1B33;">${f$(ld.trendEwma)}</strong>
          </div>
        </div>
      </div>

      <div class="cm-panel">
        <div class="cm-sec-title">
          <span>Fan Chart Bayesiano S1 → S4 (Corredor P10–P90 vs Simulación Usuario)</span>
          <span style="font-size:11px;color:#64748B;font-weight:600;">Precisión histórica media: ${ld.histAccuracyAvg.toFixed(1)}%</span>
        </div>
        <div style="position:relative;height:255px;"><canvas id="cm-pred-fan"></canvas></div>
      </div>

      <div class="cm-panel">
        <div class="cm-sec-title"><span>Histórico Reciente de Referencia — ${_esc(ld.lineName)} (Corte S${S})</span></div>
        <div class="tbl-scroll">
          <table>
            <thead>
              <tr>
                <th>Mes</th>
                <th>Real S${S} ($)</th>
                <th>Volumen S${S} (Q)</th>
                <th>Tarifa S${S}</th>
                <th>Real S4</th>
                <th>Meta S4</th>
                <th>Cierre Contable</th>
                <th>Cumpl. vs Meta</th>
              </tr>
            </thead>
            <tbody>
              ${ld.monthlyHistory.map(h => {
                const eff = h.cierre > 0 ? h.cierre : h.s4;
                const pct = (h.meta > 0 && eff > 0) ? (eff / h.meta) * 100 : null;
                return `<tr>
                  <td>${_esc(h.month)}</td>
                  <td>${h.realS > 0 ? f$(h.realS) : '—'}</td>
                  <td>${h.realQtyS > 0 ? fN(h.realQtyS) : '—'}</td>
                  <td>${h.tariffEffS > 0 ? _fmtTariff(h.tariffEffS) : '—'}</td>
                  <td>${h.s4 > 0 ? f$(h.s4) : '—'}</td>
                  <td>${h.meta > 0 ? f$(h.meta) : '—'}</td>
                  <td style="color:#1D4ED8;font-weight:700;">${h.cierre > 0 ? f$(h.cierre) : '—'}</td>
                  <td>${pct !== null ? fC(pct) : '—'}</td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;

    // Gráfico Fan Chart
    const actualArr = ld.weeklyCurveActual || [null, null, null, null];
    const userProj = [0, 1, 2, 3].map(idx => {
      if (actualArr[idx] != null) return actualArr[idx];
      if (idx === 3) return evalClose;
      const baseKnown = actualArr[S - 1] != null ? actualArr[S - 1] : ld.estActual;
      const frac = (idx + 1 - S) / Math.max(1, 4 - S);
      return Math.round(baseKnown + (evalClose - baseKnown) * frac);
    });

    _regChart('cm-pred-fan', {
      type: 'line',
      data: {
        labels: ['Semana 1', 'Semana 2', 'Semana 3', 'Semana 4'],
        datasets: [
          { label: 'Banda P90 (Techo)', data: ld.weeklyCurveP90, borderColor: 'rgba(184, 149, 90, 0.72)', borderWidth: 1, borderDash: [4, 4], pointRadius: 0, fill: false, tension: 0.25, datalabels: { display: false } },
          { label: 'Corredor Bayesiano P10–P90', data: ld.weeklyCurveP10, borderColor: 'rgba(184, 149, 90, 0.72)', borderWidth: 1, borderDash: [4, 4], backgroundColor: 'rgba(184, 149, 90, 0.22)', pointRadius: 0, fill: '-1', tension: 0.25, datalabels: { display: false } },
          { label: 'Modelo Esperado P50', data: ld.weeklyCurveModel, borderColor: '#1D4ED8', borderWidth: 2.6, pointRadius: 4, fill: false, tension: 0.25, datalabels: { display: false } },
          { label: 'Proyección Simulada (Q × Tarifa)', data: userProj, borderColor: '#B45309', borderWidth: 2.6, borderDash: [6, 4], pointRadius: 4, fill: false, tension: 0.25, datalabels: { display: false } },
          { label: 'Ejecución Observada', data: actualArr, borderColor: '#0B1B33', backgroundColor: '#FFFFFF', borderWidth: 3, pointRadius: 5, pointBorderColor: '#0B1B33', pointBorderWidth: 2.2, spanGaps: false, fill: false, tension: 0.25, datalabels: { display: false } },
          { label: 'Meta del Mes (S4)', data: [ld.metaMes, ld.metaMes, ld.metaMes, ld.metaMes], borderColor: '#059669', borderWidth: 1.8, borderDash: [3, 3], pointRadius: 0, fill: false, datalabels: { display: false } }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, color: '#334155', font: { size: 10.5, weight: '700' } } },
          tooltip: { enabled: false, external: global.extTooltip, mode: 'index', intersect: false }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155', font: { size: 11, weight: '700' } } },
          y: { beginAtZero: true, grid: { color: SIM_COLORS.grid }, ticks: { color: '#64748B', callback: v => fS(v) } }
        }
      }
    });
  }

  function renderModalLines(A, M, S) {
    _setModalHdr(
      `${_ico('bar-chart', 16)} <span>Ranking de Líneas y Descomposición Precio-Volumen (ΔQ vs ΔP)</span>`,
      `Corte ${M} ${A} · Semana ${S} · Consolidado 6 Unidades de Negocio`
    );
    document.getElementById('cm-tabs').innerHTML = '';
    const rows = global.LN.map((l, idx) => {
      const r = global.sum(A, M, S, l, 'DOLARES', 'REAL');
      const p = global.sum(A, M, S, l, 'DOLARES', 'PRESUPUESTO');
      const pv = global.computePriceVolume(A, M, S, l);
      return { l, name: global.DISP_MAP[l], short: global.LL[idx], color: global.LINE_COLORS[idx], r, p, gap: r - p, pv };
    });
    const totR = rows.reduce((a, x) => a + x.r, 0);
    const totP = rows.reduce((a, x) => a + x.p, 0);
    const totQ = rows.reduce((a, x) => a + x.pv.volEffect, 0);
    const totPr = rows.reduce((a, x) => a + x.pv.priceEffect, 0);

    document.getElementById('cm-kpis').innerHTML = `
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Real Consolidado S${S}</div><div class="cm-kpi-val">${f$(totR)}</div><div class="cm-kpi-sub">Meta S${S}: ${f$(totP)}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Brecha Neta Total</div><div class="cm-kpi-val ${totR - totP >= 0 ? 'pos' : 'neg'}">${_fmtSigned$(totR - totP)}</div><div class="cm-kpi-sub">${((totR / (totP || 1)) * 100).toFixed(1)}% cumplimiento</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Efecto Volumen Total (ΔQ)</div><div class="cm-kpi-val ${totQ >= 0 ? 'pos' : 'neg'}">${_fmtSigned$(totQ)}</div><div class="cm-kpi-sub">Impacto variación en Q</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Efecto Tarifa Total (ΔP)</div><div class="cm-kpi-val ${totPr >= 0 ? 'pos' : 'neg'}">${_fmtSigned$(totPr)}</div><div class="cm-kpi-sub">Impacto mix y precio unitario</div></div>
    `;
    document.getElementById('cm-body').innerHTML = `
      <div class="cm-panel">
        <div class="cm-sec-title"><span>Descomposición de Brecha por Línea: Efecto Volumen vs Efecto Tarifa ($)</span></div>
        <div style="position:relative;height:285px;"><canvas id="cm-lines-pv"></canvas></div>
      </div>
    `;
    _regChart('cm-lines-pv', {
      type: 'bar',
      data: {
        labels: rows.map(x => x.short),
        datasets: [
          { label: 'Efecto Volumen (ΔQ)', data: rows.map(x => Math.round(x.pv.volEffect)), backgroundColor: '#0B1B33', borderRadius: 5 },
          { label: 'Efecto Tarifa / Mix (ΔP)', data: rows.map(x => Math.round(x.pv.priceEffect)), backgroundColor: '#B8955A', borderRadius: 5 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', labels: { color: '#334155', font: { size: 11, weight: '700' } } },
          datalabels: { display: false },
          tooltip: { enabled: false, external: global.extTooltip, mode: 'index', intersect: false }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155', font: { weight: '700' } } },
          y: { grid: { color: SIM_COLORS.grid }, ticks: { color: '#64748B', callback: v => fS(v) } }
        }
      }
    });
  }

  function renderModalGauges(A, M, S) {
    _setModalHdr(
      `${_ico('gauge', 16)} <span>Estacionalidad Intra-Mensual S1–S4 · Cambio de Régimen</span>`,
      `Comparativa Patrón Ene–Mar vs Abr+ 2026 · Corte ${M} ${A} (S${S})`
    );
    document.getElementById('cm-tabs').innerHTML = '';

    const calcProfile = filterFn => [1, 2, 3, 4].map(w => {
      const vals = [];
      Object.keys(global.RAW || {}).forEach(yr => {
        Object.keys(global.RAW[yr] || {}).forEach(mo => {
          const ym = _ymOrd(yr, mo);
          if (!filterFn(parseInt(yr, 10), mo, ym)) return;
          const denom = global.getCi(yr, mo, null) || global.sum(yr, mo, 4, null, 'DOLARES', 'REAL');
          const rw = global.sum(yr, mo, w, null, 'DOLARES', 'REAL');
          if (denom > 0 && rw > 0) vals.push((rw / denom) * 100);
        });
      });
      return vals.length ? _median(vals) : w * 25;
    });

    const wPre = calcProfile((yr, _m, ym) => yr === 2026 && ym < 202604);
    const wPost = calcProfile((_y, _m, ym) => ym >= 202604);
    const curMeta = global.sum(A, M, 4, null, 'DOLARES', 'PRESUPUESTO');
    const wCur = [1, 2, 3, 4].map(w => {
      const rw = global.sum(A, M, w, null, 'DOLARES', 'REAL');
      return curMeta > 0 && rw > 0 ? (rw / curMeta) * 100 : null;
    });

    document.getElementById('cm-kpis').innerHTML = `
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Avance Corte S${S}</div><div class="cm-kpi-val">${(wCur[S - 1] || 0).toFixed(1)}%</div><div class="cm-kpi-sub">Sobre Meta Mensual ${fS(curMeta)}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Patrón Abr 2026+ (S${S})</div><div class="cm-kpi-val" style="color:#0B1B33;">${wPost[S - 1].toFixed(1)}%</div><div class="cm-kpi-sub">Regimen Ene–Mar: ${wPre[S - 1].toFixed(1)}%</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Diferencia Ritmo</div><div class="cm-kpi-val ${(wCur[S - 1] || 0) >= wPost[S - 1] ? 'pos' : 'neg'}">${((wCur[S - 1] || 0) - wPost[S - 1]).toFixed(1)} p.p.</div><div class="cm-kpi-sub">vs mediana histórica Abr+</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Cierre Implícito S4</div><div class="cm-kpi-val" style="color:#1D4ED8;">${f$(wPost[S - 1] > 0 ? (global.sum(A, M, S, null, 'DOLARES', 'REAL') / (wPost[S - 1] / 100)) : 0)}</div><div class="cm-kpi-sub">Por estacionalidad pura</div></div>
    `;

    document.getElementById('cm-body').innerHTML = `
      <div class="cm-panel">
        <div class="cm-sec-title"><span>% Acumulado de Facturación Semanal (S1 a S4): Ene–Mar vs Abr 2026+ vs Actual</span></div>
        <div style="position:relative;height:285px;"><canvas id="cm-gauges-ch"></canvas></div>
      </div>
    `;

    _regChart('cm-gauges-ch', {
      type: 'bar',
      data: {
        labels: ['Semana 1', 'Semana 2', 'Semana 3', 'Semana 4'],
        datasets: [
          { label: 'Régimen Ene–Mar 2026 (%)', data: wPre.map(v => +v.toFixed(1)), backgroundColor: 'rgba(100,116,139,0.45)', borderRadius: 5 },
          { label: 'Régimen Abr 2026+ (%)', data: wPost.map(v => +v.toFixed(1)), backgroundColor: '#B8955A', borderRadius: 5 },
          { label: `Corte ${M.slice(0, 3)} ${A}`, data: wCur.map(v => v != null ? +v.toFixed(1) : null), backgroundColor: '#0B1B33', borderRadius: 5 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', labels: { color: '#334155', font: { size: 11, weight: '700' } } },
          datalabels: { display: false },
          tooltip: { enabled: false, external: global.extTooltip, mode: 'index', intersect: false }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155', font: { weight: '700' } } },
          y: { beginAtZero: true, suggestedMax: 105, grid: { color: SIM_COLORS.grid }, ticks: { color: '#64748B', callback: v => v + '%' } }
        }
      }
    });
  }

  function renderModalWaterfallMix(A, M, S) {
    _setModalHdr(
      `${_ico('git-branch', 16)} <span>Curva Pareto 80/20 de las 24 Sub-Líneas &amp; Mix Estructural</span>`,
      `Corte ${M} ${A} (S${S}) · Contribución Granular al Ingreso Consolidado`
    );
    document.getElementById('cm-tabs').innerHTML = '';

    const subs = (typeof global.collectSublinesForCut === 'function')
      ? global.collectSublinesForCut(A, M, S, 'ALL').sort((a, b) => b.real - a.real)
      : [];
    const totR = subs.reduce((a, x) => a + x.real, 0) || 1;
    let cum = 0, p80 = 0;
    const pareto = subs.map(s => {
      const sh = (s.real / totR) * 100;
      cum += sh;
      if (cum <= 80.5 || p80 === 0) p80++;
      return { ...s, share: sh, cumPct: Math.min(100, cum) };
    });

    document.getElementById('cm-kpis').innerHTML = `
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Ingreso Total 24 Sub-Líneas</div><div class="cm-kpi-val">${f$(totR)}</div><div class="cm-kpi-sub">${M} ${A} · S${S}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Concentración Pareto 80/20</div><div class="cm-kpi-val" style="color:#0B1B33;">${p80} / ${pareto.length}</div><div class="cm-kpi-sub">sub-líneas aportan 80%</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Sub-Línea Líder</div><div class="cm-kpi-val" style="font-size:15px;">${_esc(pareto[0]?.label || '—')}</div><div class="cm-kpi-sub">${pareto[0] ? pareto[0].share.toFixed(1) + '% del total' : ''}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Ticket Promedio Sub-Línea</div><div class="cm-kpi-val">${f$(totR / (pareto.length || 1))}</div><div class="cm-kpi-sub">Media entre ${pareto.length} unidades</div></div>
    `;

    document.getElementById('cm-body').innerHTML = `
      <div class="cm-panel">
        <div class="cm-sec-title"><span>Distribución Pareto 80/20 — Top Sub-Líneas</span></div>
        <div style="position:relative;height:285px;"><canvas id="cm-pareto-ch"></canvas></div>
      </div>
    `;

    const top = pareto.slice(0, 16);
    _regChart('cm-pareto-ch', {
      type: 'bar',
      data: {
        labels: top.map(s => s.label.length > 16 ? s.label.slice(0, 15) + '…' : s.label),
        datasets: [
          { label: 'Ingreso S' + S + ' ($)', data: top.map(s => s.real), backgroundColor: top.map(s => s.cumPct <= 80.5 ? '#0B1B33' : 'rgba(100,116,139,0.35)'), borderRadius: 4, datalabels: { display: false } },
          { type: 'line', label: '% Acumulado', data: top.map(s => +s.cumPct.toFixed(1)), yAxisID: 'y1', borderColor: '#B8955A', borderWidth: 2.4, pointRadius: 3, fill: false, datalabels: { display: false } }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { color: '#334155' } }, tooltip: { enabled: false, external: global.extTooltip, mode: 'index', intersect: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155', font: { size: 9.5 } } },
          y: { beginAtZero: true, grid: { color: SIM_COLORS.grid }, ticks: { color: '#64748B', callback: v => fS(v) } },
          y1: { position: 'right', min: 0, max: 105, grid: { display: false }, ticks: { color: '#9A7438', callback: v => v + '%' } }
        }
      }
    });
  }

  /* ═══════════════════════════════════════════════════════════════
     3. PRE-CARGA HBW-NOWCAST POR SUB-LÍNEAS & SEMÁFORO MODAL
     ═══════════════════════════════════════════════════════════════ */
  function _holtDampedPredict(vals) {
    if (!vals || !vals.length) return 0;
    if (vals.length === 1) return vals[0];
    let level = vals[0];
    let trend = vals[1] - vals[0];
    const alpha = 0.45, beta = 0.25, phi = 0.82;
    for (let i = 1; i < vals.length; i++) {
      const prevLevel = level;
      level = alpha * vals[i] + (1 - alpha) * (level + phi * trend);
      trend = beta * (level - prevLevel) + (1 - beta) * phi * trend;
    }
    return Math.max(0, level + phi * trend);
  }

  function openPreloadModal() {
    const { A, M, S } = _cut();
    const bd = document.getElementById('modal-backdrop');
    const md = document.getElementById('preload-modal');
    if (!bd || !md) return;

    const subEl = document.getElementById('pl-subtitle');
    if (subEl) subEl.textContent = `Motor Holt Amortiguado + Winsorización (HBW-Nowcast) · Horizonte Cierre S4 ${M} ${A}`;

    const rows = [];
    global.LN.forEach(line => {
      const subsCur = _extractSublinesRaw(A, M, 4, line);
      subsCur.forEach(sr => {
        const histS4 = [];
        global.MO.forEach(mo => {
          [2025, 2026].forEach(yr => {
            if (yr === 2026 && global.MO.indexOf(mo) >= global.MO.indexOf(M)) return;
            const entry = global.SUBLINEAS?.[String(yr)]?.[mo]?.['4']?.[line]?.[sr.sub];
            if (entry?.DOLARES?.REAL > 0) histS4.push(Number(entry.DOLARES.REAL));
          });
        });
        const p50 = _holtDampedPredict(histS4.slice(-8)) || sr.dPpto;
        rows.push({
          line,
          lineName: global.DISP_MAP[line],
          sub: sr.sub,
          label: sr.label,
          hasQty: sr.hasQty,
          pptoS4: sr.dPpto,
          nowcast: p50
        });
      });
    });

    const body = document.getElementById('pl-body');
    if (body) {
      body.innerHTML = `
        <div class="tbl-scroll" style="max-height:55vh;">
          <table>
            <thead>
              <tr>
                <th>Línea</th>
                <th>Sub-Línea</th>
                <th>Ppto S4 ($)</th>
                <th>HBW-Nowcast P50 ($)</th>
                <th>Desvío vs Ppto</th>
              </tr>
            </thead>
            <tbody id="pl-tbody">
              ${rows.map(r => {
                const diff = r.pptoS4 > 0 ? ((r.nowcast - r.pptoS4) / r.pptoS4) * 100 : 0;
                return `<tr data-line="${_esc(r.line)}" data-sub="${_esc(r.sub)}">
                  <td><span class="kpi-badge badge-blue" style="font-size:10px;">${_esc(r.lineName)}</span></td>
                  <td>${_esc(r.label)}</td>
                  <td>${f$(r.pptoS4)}</td>
                  <td><input class="sim-input pl-val-inp" style="max-width:130px;" type="number" step="any" value="${_fmtNumInput(r.nowcast, 2)}" /></td>
                  <td class="${diff >= 0 ? 'pos' : 'neg'}" style="font-weight:700;">${_fmtPct(diff)}</td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    bd.classList.add('open');
    md.classList.add('open');
    if (typeof global.hydrateIcons === 'function') global.hydrateIcons(md);
  }

  function applyPreloadToSimulator() {
    document.querySelectorAll('#pl-tbody tr[data-line]').forEach(tr => {
      const line = tr.dataset.line;
      const sub = tr.dataset.sub;
      const val = _parseNumLoose(tr.querySelector('.pl-val-inp')?.value);
      if (val !== null) {
        if (!cmState.predOverrides[line]) cmState.predOverrides[line] = { sublinesHorizon: 'S4', sublines: {} };
        if (!cmState.predOverrides[line].sublines) cmState.predOverrides[line].sublines = {};
        cmState.predOverrides[line].sublinesHorizon = 'S4';
        cmState.predOverrides[line].sublines[sub] = { amount: val };
      }
    });
    closePreloadModal();
    cmState.simMode = 'sublines';
    cmState.simSubHorizon = 'S4';
    if (typeof global.renderCurrentView === 'function') global.renderCurrentView();
    if (typeof global.showToast === 'function') global.showToast('Pre-Carga HBW-Nowcast aplicada al Simulador de Sub-Líneas');
    openChartModal('comp', global.LN[0], 'predictive');
  }

  function closePreloadModal() {
    document.getElementById('preload-modal')?.classList.remove('open');
    document.getElementById('modal-backdrop')?.classList.remove('open');
  }

  function openSemaforoModal(metricName) {
    const { A, M, S } = _cut();
    cmState.type = 'semaforo';
    document.getElementById('modal-backdrop')?.classList.add('open');
    document.getElementById('chart-modal')?.classList.add('open');
    _destroyCharts();
    _setModalHdr(`${_ico('target', 16)} <span>Serie Histórica Semáforo: ${_esc(metricName)}</span>`, `Evolución mensual real vs meta · Año ${A} (S${S})`);
    document.getElementById('cm-tabs').innerHTML = '';

    const labels = [], reals = [], metas = [];
    global.MO.forEach(mo => {
      const raw = global.SEMAFORO_RAW || [];
      let rVal = null, mVal = null;
      for (let i = 1; i < raw.length; i++) {
        const row = raw[i];
        if (Number(row[0]) === Number(A) && String(row[1]).toUpperCase() === mo && parseInt(row[2], 10) === S && String(row[7]) === metricName) {
          if (String(row[3]).toUpperCase() === 'REAL') rVal = Number(row[9]);
          else if (String(row[3]).toUpperCase().includes('PRESUPUESTO')) mVal = Number(row[9]);
        }
      }
      if (rVal !== null || mVal !== null) {
        labels.push(mo.slice(0, 3));
        reals.push(rVal);
        metas.push(mVal);
      }
    });

    const latestR = reals.filter(x => x !== null).slice(-1)[0] || 0;
    const latestM = metas.filter(x => x !== null).slice(-1)[0] || 1;
    document.getElementById('cm-kpis').innerHTML = `
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Valor Corte Actual</div><div class="cm-kpi-val" style="color:#0B1B33;">${fN(latestR)}</div><div class="cm-kpi-sub">${M} ${A} S${S}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Meta Presupuestada</div><div class="cm-kpi-val">${fN(latestM)}</div><div class="cm-kpi-sub">Referencia S${S}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Cumplimiento</div><div class="cm-kpi-val">${((latestR / (latestM || 1)) * 100).toFixed(1)}%</div><div class="cm-kpi-sub">Desviación: ${fN(latestR - latestM)}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Meses Analizados</div><div class="cm-kpi-val">${labels.length}</div><div class="cm-kpi-sub">Serie ${A}</div></div>
    `;
    document.getElementById('cm-body').innerHTML = `
      <div class="cm-panel">
        <div class="cm-sec-title"><span>Evolución Mensual Ejecución Real vs Meta</span></div>
        <div style="position:relative;height:285px;"><canvas id="cm-sf-hist"></canvas></div>
      </div>
    `;
    _regChart('cm-sf-hist', {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Real Ejecutado', data: reals, borderColor: '#0B1B33', backgroundColor: 'rgba(11,27,51,0.10)', borderWidth: 2.8, fill: true, tension: 0.3, datalabels: { display: false } },
          { label: 'Meta', data: metas, borderColor: '#B8955A', borderWidth: 2.2, borderDash: [5, 4], fill: false, tension: 0.2, datalabels: { display: false } }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top', labels: { color: '#334155' } }, tooltip: { enabled: false, external: global.extTooltip, mode: 'index', intersect: false } },
        scales: { x: { grid: { display: false }, ticks: { color: '#334155' } }, y: { grid: { color: SIM_COLORS.grid }, ticks: { color: '#64748B' } } }
      }
    });
  }

  /* ═══════════════════════════════════════════════════════════════
     4. SLIDE-OVER DRAWER DE LÍNEA DE NEGOCIO & CONTROL ESTADÍSTICO Z-MAD
     ═══════════════════════════════════════════════════════════════ */
  function openDrawer(lineCode) {
    if (!global.LN.includes(lineCode)) return;
    const { A, M, S } = _cut();
    const drawer = document.getElementById('line-drawer');
    const bd = document.getElementById('modal-backdrop');
    if (!drawer || !bd) return;

    const r = global.sum(A, M, S, lineCode, 'DOLARES', 'REAL');
    const p = global.sum(A, M, S, lineCode, 'DOLARES', 'PRESUPUESTO');
    const q = global.sum(A, M, S, lineCode, 'CANTIDADES', 'REAL');
    const pv = global.computePriceVolume(A, M, S, lineCode);
    const subs = _extractSublinesRaw(A, M, S, lineCode);

    document.getElementById('dr-title').textContent = global.DISP_MAP[lineCode];
    document.getElementById('dr-sub').textContent = `Detalle Operativo · ${M} ${A} (S${S})`;

    document.getElementById('dr-body').innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;">
        <div class="cm-kpi-card"><div class="cm-kpi-lbl">Real Corte S${S}</div><div class="cm-kpi-val" style="color:#0B1B33;">${f$(r)}</div><div class="cm-kpi-sub">Ppto: ${f$(p)} (${fC(p > 0 ? (r / p) * 100 : null)})</div></div>
        <div class="cm-kpi-card"><div class="cm-kpi-lbl">Volumen Q &amp; Tarifa Eff.</div><div class="cm-kpi-val">${fN(q)}</div><div class="cm-kpi-sub">Tarifa media: ${_fmtTariff(pv.effTariffR)}/Q</div></div>
        <div class="cm-kpi-card"><div class="cm-kpi-lbl">Efecto Volumen (ΔQ)</div><div class="cm-kpi-val ${pv.volEffect >= 0 ? 'pos' : 'neg'}">${_fmtSigned$(pv.volEffect)}</div></div>
        <div class="cm-kpi-card"><div class="cm-kpi-lbl">Efecto Tarifa (ΔP)</div><div class="cm-kpi-val ${pv.priceEffect >= 0 ? 'pos' : 'neg'}">${_fmtSigned$(pv.priceEffect)}</div></div>
      </div>
      <div class="cm-panel">
        <div class="cm-sec-title"><span>Desglose de 4 Sub-Líneas (Corte S${S})</span></div>
        <div class="tbl-scroll">
          <table>
            <thead><tr><th>Sub-Línea</th><th>Q</th><th>Real ($)</th><th>Cumpl.</th></tr></thead>
            <tbody>
              ${subs.map(sr => `<tr>
                <td>${_esc(sr.label)}</td>
                <td>${sr.hasQty ? fN(sr.qReal) : 'Fijo'}</td>
                <td style="font-weight:800;">${f$(sr.dReal)}</td>
                <td>${fC(sr.dPpto > 0 ? (sr.dReal / sr.dPpto) * 100 : null)}</td>
              </tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>
      <button type="button" class="btn-neon-primary" style="justify-content:center;" onclick="window.closeDrawer(); window.openChartModal('comp','${lineCode}','predictive');">
        ${_ico('sliders', 15)} <span>Abrir Simulador Q × Tarifa para ${_esc(global.DISP_MAP[lineCode])}</span>
      </button>
    `;

    bd.classList.add('open');
    drawer.classList.add('open');
  }

  function closeDrawer() {
    document.getElementById('line-drawer')?.classList.remove('open');
    if (!document.getElementById('chart-modal')?.classList.contains('open') &&
        !document.getElementById('audit-modal')?.classList.contains('open') &&
        !document.getElementById('preload-modal')?.classList.contains('open')) {
      document.getElementById('modal-backdrop')?.classList.remove('open');
    }
  }

  function updateDbHealthBadge() {
    const el = document.getElementById('db-health-badge');
    if (!el) return;
    const sum = global.AUDIT_SUMMARY || global.AUDIT_DATA?.summary || {};
    const tot = Number(sum.total || 0);
    const crit = Number(sum.critical || 0);
    el.className = `db-health-pill ${crit > 0 ? 'crit' : (tot === 0 ? 'healthy' : '')}`;
    el.innerHTML = `${_ico(crit > 0 ? 'alert-octagon' : (tot > 0 ? 'alert-triangle' : 'shield-check'), 13)} <span>Validación BD: ${tot} hallazgos</span>`;
  }

  function openAuditModal() {
    document.getElementById('modal-backdrop')?.classList.add('open');
    document.getElementById('audit-modal')?.classList.add('open');
    const sum = global.AUDIT_DATA?.summary || {};
    const sub = document.getElementById('aud-sub');
    if (sub) sub.textContent = `${fN(sum.checkedCells || 0)} celdas evaluadas · Motor robusto Z-MAD + Conciliación Contable`;
    document.getElementById('aud-kpis').innerHTML = `
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Total Hallazgos</div><div class="cm-kpi-val">${sum.total || 0}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Críticos</div><div class="cm-kpi-val neg">${sum.critical || 0}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Anomalías Z-MAD</div><div class="cm-kpi-val" style="color:#1D4ED8;">${sum.anomaly || 0}</div></div>
      <div class="cm-kpi-card"><div class="cm-kpi-lbl">Advertencias</div><div class="cm-kpi-val" style="color:#B45309;">${sum.warning || 0}</div></div>
    `;
    renderAuditTable();
    if (typeof global.hydrateIcons === 'function') global.hydrateIcons(document.getElementById('audit-modal'));
  }

  function closeAuditModal() {
    document.getElementById('audit-modal')?.classList.remove('open');
    if (!document.getElementById('chart-modal')?.classList.contains('open')) {
      document.getElementById('modal-backdrop')?.classList.remove('open');
    }
  }

  function setAuditFilter(sev) {
    cmState.audSevFilter = sev || 'ALL';
    document.querySelectorAll('#aud-filters .pill-btn').forEach(b => {
      b.classList.toggle('active', b.getAttribute('data-sev') === cmState.audSevFilter);
    });
    renderAuditTable();
  }

  function renderAuditTable() {
    const tb = document.getElementById('aud-tb');
    if (!tb) return;
    const q = (document.getElementById('aud-search')?.value || '').trim().toUpperCase();
    const rows = (global.AUDIT_DATA?.issues || []).filter(it => {
      if (cmState.audSevFilter !== 'ALL' && it.severity !== cmState.audSevFilter) return false;
      if (q && !`${it.category} ${it.line} ${it.message} ${it.period}`.toUpperCase().includes(q)) return false;
      return true;
    });
    if (!rows.length) {
      tb.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#059669;padding:18px;">Sin hallazgos para el filtro seleccionado.</td></tr>';
      return;
    }
    tb.innerHTML = rows.map(it => {
      const cls = it.severity === 'critical' ? 'sev-critical' : (it.severity === 'anomaly' ? 'sev-anomaly' : 'sev-warning');
      return `<tr>
        <td><span class="sev-badge ${cls}">${_esc(it.severity.toUpperCase())}</span></td>
        <td>${_esc(AUDIT_CAT_LABELS[it.category] || it.category)}</td>
        <td><code class="aud-cell-code">${_esc(it.sheet)}!${_esc(it.cell)}</code></td>
        <td>${_esc(it.period)} · ${_esc(global.DISP_MAP[it.line] || it.line)}</td>
        <td style="white-space:normal;min-width:240px;">${_esc(it.message)}
          ${global.LN.includes(it.line) ? `<div style="margin-top:4px;"><button type="button" class="row-sim-btn" onclick="window.closeAuditModal(); window.openChartModal('comp','${it.line}','predictive');">Simular en Modelo</button></div>` : ''}
        </td>
        <td><strong>${_esc(it.formulaOrValue)}</strong><div style="font-size:10px;color:#64748B;">${_esc(it.expectedHint)}</div></td>
      </tr>`;
    }).join('');
  }

  function exportAuditCSV() {
    const rows = global.AUDIT_DATA?.issues || [];
    const lines = [['SEVERIDAD', 'CATEGORIA', 'CELDA', 'PERIODO', 'LINEA', 'DESCRIPCION', 'VALOR', 'REFERENCIA'].join(',')];
    rows.forEach(it => lines.push([it.severity, it.category, `${it.sheet}!${it.cell}`, it.period, it.line, it.message, it.formulaOrValue, it.expectedHint].map(v => `"${String(v || '').replace(/"/g, '""')}"`).join(',')));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' }));
    a.download = 'Nexus_FPA_Control_Estadistico_Z_MAD.csv';
    a.click();
  }

  /* ═══════════════════════════════════════════════════════════════
     5. HANDLERS INTERACTIVOS DEL SIMULADOR
     ═══════════════════════════════════════════════════════════════ */
  global.__cmSetFocus = function (key) {
    cmState.focusKey = key;
    cmState.qtEditedS = 'qt';
    cmState.qtEditedS4 = 'qt';
    cmState.s4Touched = false;
    renderActiveChartModal();
  };

  global.__cmSetSimMode = function (mode) {
    cmState.simMode = mode || 'qt';
    renderActiveChartModal();
  };

  global.__cmSetSubHorizon = function (h) {
    cmState.simSubHorizon = h === 'S' ? 'S' : 'S4';
    renderActiveChartModal();
  };

  global.__cmSyncQt = function (stage, source) {
    const isS = stage === 's';
    if (!isS) cmState.s4Touched = true;
    const qEl = document.getElementById(isS ? 'pred-qt-q-s' : 'pred-qt-q-4');
    const tEl = document.getElementById(isS ? 'pred-qt-t-s' : 'pred-qt-t-4');
    const fEl = document.getElementById(isS ? 'pred-qt-fixed-s' : 'pred-qt-fixed-4');
    const totEl = document.getElementById(isS ? 'pred-qt-est-s' : 'pred-qt-close-4');
    const hintEl = document.getElementById(isS ? 'pred-qt-formula-s' : 'pred-qt-formula-4');

    const q = _parseNumLoose(qEl?.value) || 0;
    const f = _parseNumLoose(fEl?.value) || 0;
    let t = _parseNumLoose(tEl?.value) || 0;
    let tot = _parseNumLoose(totEl?.value) || 0;

    if (source === 'qt') {
      if (isS) cmState.qtEditedS = 'qt'; else cmState.qtEditedS4 = 'qt';
      tot = q > 0 ? (q * t + f) : f;
      if (totEl) totEl.value = _fmtNumInput(tot, 2);
    } else {
      if (isS) cmState.qtEditedS = 'est'; else cmState.qtEditedS4 = 'close';
      if (q > 0 && tEl) {
        t = Math.max(0, tot - f) / q;
        tEl.value = _fmtNumInput(t, 4);
      }
    }

    const ld = cmState.predData?.lines?.[cmState.focusKey] || {};
    const effT = q > 0 ? tot / q : 0;
    if (hintEl) {
      hintEl.innerHTML = isS
        ? `Q × Tarifa + Fijo = <strong>${f$(tot)}</strong> · Tarifa efectiva: <strong>${_fmtTariff(effT)}/Q</strong>`
        : `Brecha vs Bayesiano P50 (${f$(ld.p50 || 0)}): <strong>${_fmtSigned$(tot - (ld.p50 || 0))}</strong>`;
    }

    if (isS && !cmState.s4Touched) {
      const q4El = document.getElementById('pred-qt-q-4');
      const t4El = document.getElementById('pred-qt-t-4');
      const f4El = document.getElementById('pred-qt-fixed-4');
      const c4El = document.getElementById('pred-qt-close-4');
      const fh4El = document.getElementById('pred-qt-formula-4');
      const qRatio = (ld.qtyActual > 0 && ld.qtyCloseEval > 0) ? (ld.qtyCloseEval / ld.qtyActual) : 1.33;
      const fRatio = (ld.fixedActual > 0 && ld.fixedClose > 0) ? (ld.fixedClose / ld.fixedActual) : 1.25;
      const q4 = Math.round(q * qRatio);
      const t4 = t;
      const f4 = f * fRatio;
      const tot4 = q4 > 0 ? (q4 * t4 + f4) : f4;
      if (q4El) q4El.value = _fmtNumInput(q4, 0);
      if (t4El) t4El.value = _fmtNumInput(t4, 4);
      if (f4El) f4El.value = _fmtNumInput(f4, 2);
      if (c4El) c4El.value = _fmtNumInput(tot4, 2);
      if (fh4El) fh4El.innerHTML = `Brecha vs Bayesiano P50 (${f$(ld.p50 || 0)}): <strong>${_fmtSigned$(tot4 - (ld.p50 || 0))}</strong>`;
    }
  };

  global.__cmSyncSubRow = function (subCode, source) {
    const tr = document.querySelector(`#pred-sub-tbody tr[data-sub="${subCode}"]`);
    if (!tr) return;
    tr.dataset.edited = source === 'd' ? 'd' : 'qt';
    const hasQty = tr.dataset.hasQty === '1';
    const qEl = tr.querySelector('[data-sub-q]');
    const tEl = tr.querySelector('[data-sub-t]');
    const dEl = tr.querySelector('[data-sub-d]');
    let q = _parseNumLoose(qEl?.value) || 0;
    let t = _parseNumLoose(tEl?.value) || 0;
    let d = _parseNumLoose(dEl?.value) || 0;
    if (hasQty) {
      if (source === 'qt') {
        d = q * t;
        if (dEl) dEl.value = _fmtNumInput(d, 2);
      } else if (q > 0 && tEl) {
        t = d / q;
        tEl.value = _fmtNumInput(t, 4);
      }
    }
  };

  global.__cmSyncWeekly = function () {
    const vals = [1, 2, 3, 4].map(w => {
      const v = _parseNumLoose(document.getElementById(`pred-wk-${w}`)?.value);
      return v == null ? '' : Math.round(v);
    });
    const csvEl = document.getElementById('pred-sim-csv');
    if (csvEl) csvEl.value = vals.join(',');
  };

  global.__cmQuickStress = function (lineCode, factor, alignToP50 = false) {
    const ld = cmState.predData?.lines?.[lineCode];
    if (!ld) return;
    cmState.simMode = 'qt';
    if (alignToP50) {
      const ratio = ld.evalClose > 0 ? (ld.p50 / ld.evalClose) : 1;
      cmState.predOverrides[lineCode] = {
        qtyClose: Math.round(ld.qtyCloseEval * ratio),
        tariffClose: ld.tariffVarClose,
        fixedClose: ld.fixedClose,
        calcFromQT: true
      };
    } else {
      cmState.predOverrides[lineCode] = {
        qtyActual: Math.round(ld.qtyActual * factor),
        tariffActual: ld.tariffVarActual,
        fixedActual: ld.fixedActual,
        qtyClose: Math.round(ld.qtyCloseEval * factor),
        tariffClose: ld.tariffVarClose,
        fixedClose: ld.fixedClose * factor,
        calcFromQT: true
      };
    }
    renderActiveChartModal();
    if (typeof global.renderCurrentView === 'function') global.renderCurrentView();
    if (typeof global.showToast === 'function') global.showToast(alignToP50 ? 'Escenario alineado al Nowcast Bayesiano P50' : `Escenario de sensibilidad (${factor > 1 ? '+' : ''}${Math.round((factor - 1) * 100)}%) aplicado`);
  };

  global.__cmEvalPredict = function (lineCode) {
    const mode = cmState.simMode || 'qt';
    const metaVal = _parseNumLoose(document.getElementById('pred-sim-meta')?.value);
    const ov = {};
    if (metaVal !== null) ov.metaMes = metaVal;

    if (mode === 'qt') {
      const qS = _parseNumLoose(document.getElementById('pred-qt-q-s')?.value);
      const tS = _parseNumLoose(document.getElementById('pred-qt-t-s')?.value);
      const fS = _parseNumLoose(document.getElementById('pred-qt-fixed-s')?.value);
      const estS = _parseNumLoose(document.getElementById('pred-qt-est-s')?.value);
      const q4 = _parseNumLoose(document.getElementById('pred-qt-q-4')?.value);
      const t4 = _parseNumLoose(document.getElementById('pred-qt-t-4')?.value);
      const f4 = _parseNumLoose(document.getElementById('pred-qt-fixed-4')?.value);
      const c4 = _parseNumLoose(document.getElementById('pred-qt-close-4')?.value);
      ov.calcFromQT = cmState.qtEditedS !== 'est' && cmState.qtEditedS4 !== 'close';
      if (qS !== null) ov.qtyActual = qS;
      if (tS !== null) ov.tariffActual = tS;
      if (fS !== null) ov.fixedActual = fS;
      if (cmState.qtEditedS === 'est' && estS !== null) ov.estActual = estS;
      if (q4 !== null) ov.qtyClose = q4;
      if (t4 !== null) ov.tariffClose = t4;
      if (f4 !== null) ov.fixedClose = f4;
      if (cmState.qtEditedS4 === 'close' && c4 !== null) ov.projClose = c4;
    } else if (mode === 'sublines') {
      ov.sublinesHorizon = cmState.simSubHorizon === 'S' ? 'S' : 'S4';
      ov.sublines = {};
      document.querySelectorAll('#pred-sub-tbody tr[data-sub]').forEach(tr => {
        const sc = tr.dataset.sub;
        const hasQty = tr.dataset.hasQty === '1';
        const qV = _parseNumLoose(tr.querySelector('[data-sub-q]')?.value);
        const tV = _parseNumLoose(tr.querySelector('[data-sub-t]')?.value);
        const dV = _parseNumLoose(tr.querySelector('[data-sub-d]')?.value);
        if (!hasQty && dV !== null) ov.sublines[sc] = { amount: dV };
        else if (tr.dataset.edited === 'd' && dV !== null) ov.sublines[sc] = qV !== null ? { qty: qV, amount: dV } : { amount: dV };
        else if (qV !== null || tV !== null) ov.sublines[sc] = { qty: qV, tariff: tV };
      });
    } else {
      const wkVals = [1, 2, 3, 4].map(w => _parseNumLoose(document.getElementById(`pred-wk-${w}`)?.value));
      ov.weeklyCurve = wkVals;
    }

    cmState.predOverrides[lineCode] = ov;
    renderActiveChartModal();
    if (typeof global.renderCurrentView === 'function') global.renderCurrentView();
    if (typeof global.showToast === 'function') global.showToast('Simulación recalculada con éxito');
  };

  global.__cmResetPredict = function (lineCode) {
    delete cmState.predOverrides[lineCode];
    cmState.qtEditedS = 'qt';
    cmState.qtEditedS4 = 'qt';
    cmState.s4Touched = false;
    renderActiveChartModal();
    if (typeof global.renderCurrentView === 'function') global.renderCurrentView();
  };

  global.__cmResetAllOverrides = function () {
    cmState.predOverrides = {};
  };

  global.__cmHandleCsvUpload = function (inputEl, lineCode) {
    const file = inputEl?.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { if (typeof global.showToast === 'function') global.showToast('El archivo supera el límite de seguridad de 2 MB'); return; }
    const reader = new FileReader();
    reader.onload = ev => {
      const text = String(ev.target?.result || '').trim();
      const nums = text.split(/[;,\s\r\n]+/).map(_parseNumLoose).filter(v => v !== null);
      if (!nums.length) return;
      cmState.simMode = 'weekly';
      cmState.predOverrides[lineCode] = { weeklyCurve: [nums[0] ?? null, nums[1] ?? null, nums[2] ?? null, nums[3] ?? null] };
      renderActiveChartModal();
      if (typeof global.showToast === 'function') global.showToast('Serie CSV cargada al Simulador');
    };
    reader.readAsText(file);
  };

  global.getActiveSimOverrides = () => cmState.predOverrides;

  global.document?.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (typeof global.closeWelcomeModal === 'function') global.closeWelcomeModal();
      closeChartModal();
      closeAuditModal();
      closePreloadModal();
      closeDrawer();
    }
  });

  global.computeClientPredictiveReport = computeClientPredictiveReport;
  global.openChartModal = openChartModal;
  global.closeChartModal = closeChartModal;
  global.renderActiveChartModal = renderActiveChartModal;
  global.openPreloadModal = openPreloadModal;
  global.closePreloadModal = closePreloadModal;
  global.applyPreloadToSimulator = applyPreloadToSimulator;
  global.openSemaforoModal = openSemaforoModal;
  global.openDrawer = openDrawer;
  global.closeDrawer = closeDrawer;
  global.openAuditModal = openAuditModal;
  global.closeAuditModal = closeAuditModal;
  global.setAuditFilter = setAuditFilter;
  global.renderAuditTable = renderAuditTable;
  global.exportAuditCSV = exportAuditCSV;
  global.updateDbHealthBadge = updateDbHealthBadge;
})(typeof window !== 'undefined' ? window : globalThis);

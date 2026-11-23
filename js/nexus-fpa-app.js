/* ═══════════════════════════════════════════════════════════════════════
   NEXUS QUANT FP&A — CONTROLADOR PRINCIPAL DEL DASHBOARD EJECUTIVO
   Vistas: 1. Ingresos y Ejecución | 2. Analítica & Sub-Líneas | 3. Semáforo
   100% Cliente · Datos Estocásticos · Acceso Directo · Paleta Ejecutiva PDF CV
   ═══════════════════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';

  global.RAW = {};
  global.SUBLINEAS = {};
  global.CIERRE = {};
  global.SEMAFORO_RAW = [];
  global.AUDIT_DATA = null;
  global.AUDIT_SUMMARY = null;
  global.PREDICTIVE_DATA = null;
  global.__PREDICTIVE_CACHE__ = {};

  let chartInstances = {};
  let activeView = 'view-ingresos';
  let activeSfStatusFilter = 'ALL';
  let activeAnaLineFilter = 'ALL';
  let currentEcosystem = null;

  /* ─── FORMATEADORES TABULARES ─── */
  function escHtml(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function f$(v) {
    const n = Number(v || 0);
    const abs = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    return `${sign}$${Math.round(abs).toLocaleString('en-US')}`;
  }

  function fN(v) {
    const n = Number(v || 0);
    return Math.round(n).toLocaleString('en-US');
  }

  function fS(v) {
    const n = Number(v || 0);
    const abs = Math.abs(n);
    const sign = n < 0 ? '-' : '';
    if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
    return `${sign}$${Math.round(abs)}`;
  }

  function fTariff(v) {
    const n = Number(v || 0);
    if (!n || !isFinite(n)) return '—';
    if (Math.abs(n) < 1) return `$${n.toFixed(3)}`;
    if (Math.abs(n) < 20) return `$${n.toFixed(2)}`;
    return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  function cp(real, ppto) {
    const r = Number(real || 0), p = Number(ppto || 0);
    if (p <= 0) return null;
    return (r / p) * 100;
  }

  function vp(cur, prev) {
    const c = Number(cur || 0), p = Number(prev || 0);
    if (p <= 0) return null;
    return ((c - p) / p) * 100;
  }

  function fC(pct) {
    if (pct === null || pct === undefined || isNaN(pct)) return '<span class="kpi-badge" style="background:rgba(100,116,139,0.12);color:#64748B;">—</span>';
    const cls = pct >= 105 ? 'badge-blue' : (pct >= 98 ? 'badge-ok' : (pct >= 90 ? 'badge-warn' : 'badge-bad'));
    return `<span class="kpi-badge ${cls}">${pct.toFixed(1)}%</span>`;
  }

  function fP(pct) {
    if (pct === null || pct === undefined || isNaN(pct)) return '<span class="neu">—</span>';
    const sign = pct > 0 ? '+' : '';
    const cls = pct > 0 ? 'pos' : (pct < 0 ? 'neg' : 'neu');
    return `<span class="${cls}" style="font-weight:700;">${sign}${pct.toFixed(1)}%</span>`;
  }

  function sum(yr, mo, w, l, m, e) {
    const yObj = global.RAW[String(yr)] || global.RAW[yr];
    if (!yObj) return 0;
    const mObj = yObj[String(mo).toUpperCase()];
    if (!mObj) return 0;
    const wObj = mObj[String(w)] || mObj[w];
    if (!wObj) return 0;
    if (l) {
      return Number(wObj[l]?.[m]?.[e] || 0);
    }
    let acc = 0;
    global.LN.forEach(lc => { acc += Number(wObj[lc]?.[m]?.[e] || 0); });
    return acc;
  }

  function getCi(yr, mo, l) {
    const yObj = global.CIERRE[String(yr)] || global.CIERRE[yr];
    if (!yObj) return 0;
    const mObj = yObj[String(mo).toUpperCase()];
    if (!mObj) return 0;
    if (l) return Number(mObj[l]?.DOLARES || 0);
    let acc = 0;
    global.LN.forEach(lc => { acc += Number(mObj[lc]?.DOLARES || 0); });
    return acc;
  }

  function showToast(msg) {
    const el = document.getElementById('nx-toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => el.classList.remove('show'), 3200);
  }

  /* ─── TOOLTIP EXTERNO EJECUTIVO ─── */
  function extTooltip(context) {
    const tip = document.getElementById('nx-chart-tooltip');
    if (!tip) return;
    const { chart, tooltip } = context;
    if (!tooltip || tooltip.opacity === 0) {
      tip.style.opacity = '0';
      return;
    }
    const title = (tooltip.title || []).join(' ');
    const lines = (tooltip.dataPoints || []).map(dp => {
      const col = dp.dataset.borderColor || dp.dataset.backgroundColor || '#D9C29A';
      const lbl = dp.dataset.label ? `${dp.dataset.label}: ` : '';
      const valText = typeof dp.formattedValue === 'string' && dp.formattedValue.includes('$')
        ? dp.formattedValue
        : (dp.raw != null && typeof dp.raw === 'number'
          ? (dp.dataset.yAxisID === 'y1' || (dp.dataset.label || '').includes('%') ? `${dp.raw.toFixed(1)}%` : f$(dp.raw))
          : dp.formattedValue);
      return `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:3px;">
        <span style="display:inline-flex;align-items:center;gap:6px;color:#E2E8F0;">
          <span style="width:8px;height:8px;border-radius:50%;background:${Array.isArray(col) ? col[dp.dataIndex] : col};display:inline-block;border:1px solid rgba(255,255,255,0.35);"></span>
          ${escHtml(lbl)}
        </span>
        <strong style="color:#FFFFFF;font-family:'JetBrains Mono',monospace;">${escHtml(valText)}</strong>
      </div>`;
    }).join('');
    tip.innerHTML = `<div style="font-weight:800;color:#D9C29A;margin-bottom:4px;font-size:11px;">${escHtml(title)}</div>${lines}`;
    const rect = chart.canvas.getBoundingClientRect();
    let x = rect.left + tooltip.caretX + 14;
    let y = rect.top + tooltip.caretY - 12;
    if (x + 240 > window.innerWidth) x = rect.left + tooltip.caretX - 235;
    if (y + 160 > window.innerHeight) y = window.innerHeight - 170;
    tip.style.left = `${Math.max(8, x)}px`;
    tip.style.top = `${Math.max(8, y)}px`;
    tip.style.opacity = '1';
  }

  function destroyChart(id) {
    if (chartInstances[id]) {
      try { chartInstances[id].destroy(); } catch (_e) {}
      delete chartInstances[id];
    }
  }

  function makeChart(id, cfg) {
    destroyChart(id);
    const canvas = document.getElementById(id);
    if (!canvas || typeof global.Chart === 'undefined') return null;
    chartInstances[id] = new global.Chart(canvas.getContext('2d'), cfg);
    return chartInstances[id];
  }

  /* ─── INICIALIZACIÓN Y REGENERACIÓN ESTOCÁSTICA ─── */
  function initChartDefaults() {
    if (typeof global.Chart === 'undefined') return;
    if (typeof global.ChartDataLabels !== 'undefined' && !initChartDefaults._dlRegistered) {
      global.Chart.register(global.ChartDataLabels);
      initChartDefaults._dlRegistered = true;
    }
    global.Chart.defaults.color = '#334155';
    global.Chart.defaults.borderColor = 'rgba(11, 27, 51, 0.08)';
    global.Chart.defaults.font.family = "'Plus Jakarta Sans', 'Inter', -apple-system, sans-serif";
  }

  function boot(d, preserveFilters = false) {
    currentEcosystem = d;
    const prevA = preserveFilters ? document.getElementById('selAnio')?.value : null;
    const prevM = preserveFilters ? document.getElementById('selMes')?.value : null;
    const prevS = preserveFilters ? document.getElementById('selSemana')?.value : null;

    global.RAW = d.datos || {};
    global.SUBLINEAS = d.sublineas || {};
    global.CIERRE = d.cierre || {};
    global.SEMAFORO_RAW = d.semaforo || [];
    global.AUDIT_DATA = d.audit || null;
    global.AUDIT_SUMMARY = d.auditSummary || d.audit?.summary || null;
    global.PREDICTIVE_DATA = null;
    global.__PREDICTIVE_CACHE__ = {};

    const syncTxt = document.getElementById('sync-status-txt');
    if (syncTxt) {
      syncTxt.textContent = `Motor Sintético · ${d.scenarioLabel || 'LIVE'}`;
    }
    const scBadge = document.getElementById('scenario-badge');
    if (scBadge) {
      scBadge.innerHTML = `${global.ico('cpu', 13)} <span>Universo ${escHtml(d.scenarioLabel || 'LIVE')} · 6 Líneas · 24 Sub-Líneas</span>`;
    }

    initChartDefaults();
    pop(prevA, prevM, prevS);

    if (typeof global.updateDbHealthBadge === 'function') {
      global.updateDbHealthBadge();
    }

    renderCurrentView();
    if (typeof global.hydrateIcons === 'function') global.hydrateIcons(document);
  }

  function regenerateRandomScenario() {
    const newData = global.NexusSyntheticEngine.generateDataset();
    boot(newData, true);
    if (typeof global.__cmResetAllOverrides === 'function') {
      global.__cmResetAllOverrides();
    }
    if (document.getElementById('chart-modal')?.classList.contains('open') && typeof global.renderActiveChartModal === 'function') {
      global.renderActiveChartModal();
    }
    if (document.getElementById('audit-modal')?.classList.contains('open') && typeof global.openAuditModal === 'function') {
      global.openAuditModal();
    }
    showToast(`Nuevo escenario estocástico generado: ${newData.scenarioLabel}`);
  }

  function pop(prevA = null, prevM = null, prevS = null) {
    const sA = document.getElementById('selAnio');
    const sM = document.getElementById('selMes');
    const sS = document.getElementById('selSemana');
    if (!sA || !sM || !sS) return;

    const years = Object.keys(global.RAW).sort((a, b) => Number(b) - Number(a));
    sA.innerHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');
    const pickedA = (prevA && years.includes(String(prevA))) ? String(prevA) : (years[0] || '2026');
    sA.value = pickedA;

    const monthsForYear = Object.keys(global.RAW[pickedA] || {}).sort((a, b) => global.MO.indexOf(a) - global.MO.indexOf(b));
    sM.innerHTML = monthsForYear.map(m => `<option value="${m}">${m.charAt(0) + m.slice(1).toLowerCase()}</option>`).join('');
    const pickedM = (prevM && monthsForYear.includes(String(prevM).toUpperCase()))
      ? String(prevM).toUpperCase()
      : (monthsForYear[monthsForYear.length - 1] || 'NOVIEMBRE');
    sM.value = pickedM;

    // Detectar semanas con datos reales (> 0)
    const availWeeks = [1, 2, 3, 4].filter(w => sum(pickedA, pickedM, w, null, 'DOLARES', 'REAL') > 0);
    const weekList = availWeeks.length ? availWeeks : [1, 2, 3, 4];
    sS.innerHTML = weekList.map(w => `<option value="${w}">Semana ${w} (S${w})</option>`).join('');
    const pickedS = (prevS && weekList.includes(Number(prevS))) ? String(prevS) : String(weekList[weekList.length - 1]);
    sS.value = pickedS;
  }

  function onYearOrMonthChange(changedField) {
    const sA = document.getElementById('selAnio');
    const sM = document.getElementById('selMes');
    const sS = document.getElementById('selSemana');
    if (!sA || !sM || !sS) return;
    if (changedField === 'anio') {
      pop(sA.value, sM.value, sS.value);
    } else if (changedField === 'mes') {
      pop(sA.value, sM.value, sS.value);
    }
    renderCurrentView();
    if (document.getElementById('chart-modal')?.classList.contains('open') && typeof global.renderActiveChartModal === 'function') {
      global.renderActiveChartModal();
    }
  }

  function switchView(viewId) {
    activeView = viewId;
    document.querySelectorAll('.tb-tab').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-view') === viewId);
    });
    ['view-ingresos', 'view-analitica', 'view-semaforo'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = (id === viewId) ? 'flex' : 'none';
    });
    renderCurrentView();
  }

  function renderCurrentView() {
    if (activeView === 'view-analitica') renderAnalitica();
    else if (activeView === 'view-semaforo') renderSemaforo();
    else renderIngresos();
  }

  function getCut() {
    return {
      A: parseInt(document.getElementById('selAnio')?.value || '2026', 10),
      M: (document.getElementById('selMes')?.value || 'NOVIEMBRE').toUpperCase(),
      S: parseInt(document.getElementById('selSemana')?.value || '3', 10),
      cmp: document.getElementById('selCmp')?.value || 'PRESUPUESTO'
    };
  }

  /* ═══════════════════════════════════════════════════════════════
     DESCOMPOSICIÓN PRECIO-VOLUMEN (ELASTICIDAD Q × TARIFA)
     ═══════════════════════════════════════════════════════════════ */
  function computePriceVolume(A, M, S, lineCode) {
    const r = sum(A, M, S, lineCode, 'DOLARES', 'REAL');
    const p = sum(A, M, S, lineCode, 'DOLARES', 'PRESUPUESTO');
    const qR = sum(A, M, S, lineCode, 'CANTIDADES', 'REAL');
    const qP = sum(A, M, S, lineCode, 'CANTIDADES', 'PRESUPUESTO');
    if (qR <= 0 || qP <= 0) {
      return { volEffect: 0, priceEffect: r - p, effTariffR: 0, effTariffP: 0 };
    }
    const tarR = r / qR;
    const tarP = p / qP;
    const volEffect = (qR - qP) * tarP;
    const priceEffect = (tarR - tarP) * qR;
    return { volEffect, priceEffect, effTariffR: tarR, effTariffP: tarP };
  }

  /* ═══════════════════════════════════════════════════════════════
     VISTA 1: INGRESOS Y EJECUCIÓN EJECUTIVA
     ═══════════════════════════════════════════════════════════════ */
  function renderIngresos() {
    const { A, M, S, cmp } = getCut();

    let totReal = 0, totPpto = 0, totMetaMes = 0, totPrevY = 0, totPrevM = 0;
    const mIdx = global.MO.indexOf(M);
    const prevMes = mIdx > 0 ? global.MO[mIdx - 1] : 'DICIEMBRE';
    const prevMesYr = mIdx > 0 ? A : A - 1;

    let sumVolEffect = 0, sumPriceEffect = 0;

    global.LN.forEach(l => {
      totReal += sum(A, M, S, l, 'DOLARES', 'REAL');
      totPpto += sum(A, M, S, l, 'DOLARES', 'PRESUPUESTO');
      totMetaMes += sum(A, M, 4, l, 'DOLARES', 'PRESUPUESTO');
      totPrevY += sum(A - 1, M, S, l, 'DOLARES', 'REAL');
      totPrevM += sum(prevMesYr, prevMes, S, l, 'DOLARES', 'REAL');
      const pv = computePriceVolume(A, M, S, l);
      sumVolEffect += pv.volEffect;
      sumPriceEffect += pv.priceEffect;
    });

    const pctCumpl = cp(totReal, totPpto);
    const pctYoY = vp(totReal, totPrevY);
    const pctMoM = vp(totReal, totPrevM);
    const netGap = totReal - totPpto;

    // Calcular reporte predictivo bayesiano cliente
    let predRep = null;
    if (typeof global.computeClientPredictiveReport === 'function') {
      const ovs = (typeof global.getActiveSimOverrides === 'function') ? global.getActiveSimOverrides() : {};
      predRep = global.computeClientPredictiveReport(A, M, S, ovs);
      global.PREDICTIVE_DATA = predRep;
    }

    const p50Tot = Number(predRep?.summary?.totalModelExpected || totMetaMes);
    const p10Tot = Number(predRep?.summary?.totalP10 || p50Tot * 0.94);
    const p90Tot = Number(predRep?.summary?.totalP90 || p50Tot * 1.06);
    const outCnt = Number(predRep?.summary?.outOfHistoryCount || 0);
    const predCumpl = cp(p50Tot, totMetaMes);

    // Cinta ejecutiva
    const rib = document.getElementById('v1-ribbon');
    if (rib) {
      const gapTxt = netGap >= 0 ? `<strong class="pos">+${f$(netGap)} superávit</strong>` : `<strong class="neg">${f$(netGap)} déficit</strong>`;
      const alertTxt = outCnt > 0
        ? `<span class="sev-badge sev-warning">${global.ico('alert-triangle', 12)} ${outCnt} línea(s) con señal Z-MAD</span>`
        : `<span class="sev-badge sev-ok">${global.ico('check-circle', 12)} Todas las líneas en corredor histórico</span>`;
      rib.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
          <span>${global.ico('activity', 15)} <strong>Corte ${M} ${A} · Semana ${S}:</strong> Facturación acumulada <strong>${f$(totReal)}</strong> (${pctCumpl != null ? pctCumpl.toFixed(1) + '%' : '—'} vs Presupuesto) con ${gapTxt}.</span>
          <span>Descomposición Brecha: Volumen <strong class="${sumVolEffect >= 0 ? 'pos' : 'neg'}">${sumVolEffect >= 0 ? '+' : ''}${f$(sumVolEffect)}</strong> · Tarifa <strong class="${sumPriceEffect >= 0 ? 'pos' : 'neg'}">${sumPriceEffect >= 0 ? '+' : ''}${f$(sumPriceEffect)}</strong>.</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          ${alertTxt}
          <button type="button" class="ch-expand-btn ch-expand-accent" onclick="window.openChartModal('comp','CLOUD_SAAS','predictive')">
            ${global.ico('sliders', 12)} <span>Simular Cierre S4</span>
          </button>
        </div>
      `;
    }

    // KPIs
    document.getElementById('kpi-v1-real').textContent = f$(totReal);
    document.getElementById('kpi-v1-real-sub').innerHTML = `<span>Avance vs Meta Mensual S4 (${fS(totMetaMes)})</span><strong style="color:#0B1B33;">${totMetaMes > 0 ? ((totReal / totMetaMes) * 100).toFixed(1) + '%' : '—'}</strong>`;

    document.getElementById('kpi-v1-ppto').innerHTML = `${pctCumpl != null ? pctCumpl.toFixed(1) + '%' : '—'}`;
    document.getElementById('kpi-v1-ppto-sub').innerHTML = `<span>Ppto S${S}: ${fS(totPpto)}</span><span class="${netGap >= 0 ? 'pos' : 'neg'}" style="font-weight:800;">${netGap >= 0 ? '+' : ''}${fS(netGap)}</span>`;

    document.getElementById('kpi-v1-pred').textContent = f$(p50Tot);
    document.getElementById('kpi-v1-pred-sub').innerHTML = `<span>Banda P10–P90: ${fS(p10Tot)} a ${fS(p90Tot)}</span>${fC(predCumpl)}`;

    const cmpLabel = cmp === 'ANIO_ANT' ? 'Crecimiento Interanual (YoY)' : (cmp === 'MES_ANT' ? 'Variación Intermensual (MoM)' : 'Mix Efecto Volumen / Tarifa');
    const cmpMainVal = cmp === 'MES_ANT'
      ? (pctMoM != null ? `${pctMoM >= 0 ? '+' : ''}${pctMoM.toFixed(1)}%` : '—')
      : (pctYoY != null ? `${pctYoY >= 0 ? '+' : ''}${pctYoY.toFixed(1)}%` : '—');
    document.getElementById('kpi-v1-var-lbl').textContent = cmpLabel;
    document.getElementById('kpi-v1-var').innerHTML = `<span class="${(cmp === 'MES_ANT' ? pctMoM : pctYoY) >= 0 ? 'pos' : 'neg'}">${cmpMainVal}</span>`;
    document.getElementById('kpi-v1-var-sub').innerHTML = `<span>ΔQ: <strong class="${sumVolEffect >= 0 ? 'pos' : 'neg'}">${fS(sumVolEffect)}</strong></span><span>ΔP: <strong class="${sumPriceEffect >= 0 ? 'pos' : 'neg'}">${fS(sumPriceEffect)}</strong></span>`;

    // Gráfico Evolución Histórica Anual (12 meses del año A)
    const monthsShort = global.MO.map(m => m.slice(0, 3));
    const histReal = global.MO.map(m => {
      const ci = getCi(A, m, null);
      if (ci > 0) return ci;
      const s4 = sum(A, m, 4, null, 'DOLARES', 'REAL');
      if (s4 > 0) return s4;
      if (m === M) return totReal;
      return null;
    });
    const histPpto = global.MO.map(m => {
      const p4 = sum(A, m, 4, null, 'DOLARES', 'PRESUPUESTO');
      return p4 > 0 ? p4 : null;
    });
    const histPrevY = global.MO.map(m => {
      const ciPrev = getCi(A - 1, m, null);
      const s4Prev = sum(A - 1, m, 4, null, 'DOLARES', 'REAL');
      return (ciPrev > 0 ? ciPrev : s4Prev) || null;
    });

    makeChart('cHist', {
      type: 'line',
      data: {
        labels: monthsShort,
        datasets: [
          {
            label: `Real / Cierre ${A}`,
            data: histReal,
            borderColor: '#0B1B33',
            backgroundColor: 'rgba(11, 27, 51, 0.10)',
            borderWidth: 2.8,
            pointRadius: 4,
            pointBackgroundColor: '#FFFFFF',
            pointBorderColor: '#0B1B33',
            pointBorderWidth: 2.2,
            fill: true,
            tension: 0.3,
            datalabels: { display: false }
          },
          {
            label: `Presupuesto ${A}`,
            data: histPpto,
            borderColor: '#B8955A',
            borderWidth: 2.2,
            borderDash: [5, 5],
            pointRadius: 2.5,
            fill: false,
            tension: 0.25,
            datalabels: { display: false }
          },
          {
            label: `Real ${A - 1}`,
            data: histPrevY,
            borderColor: '#94A3B8',
            borderWidth: 1.7,
            pointRadius: 0,
            fill: false,
            tension: 0.25,
            datalabels: { display: false }
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, color: '#334155', font: { size: 11, weight: '700' } } },
          tooltip: { enabled: false, external: extTooltip, mode: 'index', intersect: false }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#475569', font: { size: 10.5, weight: '700' } } },
          y: {
            beginAtZero: false,
            grid: { color: 'rgba(11, 27, 51, 0.08)' },
            ticks: { color: '#64748B', callback: v => fS(v), font: { size: 10.5 } }
          }
        }
      }
    });

    // Gráfico Real vs Ppto por Línea
    const lLabels = global.LL;
    const lReal = global.LN.map(l => sum(A, M, S, l, 'DOLARES', 'REAL'));
    const lPpto = global.LN.map(l => sum(A, M, S, l, 'DOLARES', 'PRESUPUESTO'));
    makeChart('cLines', {
      type: 'bar',
      data: {
        labels: lLabels,
        datasets: [
          {
            label: `Real S${S}`,
            data: lReal,
            backgroundColor: global.LINE_COLORS,
            borderRadius: 6
          },
          {
            label: `Ppto S${S}`,
            data: lPpto,
            backgroundColor: 'rgba(100, 116, 139, 0.22)',
            borderColor: 'rgba(100, 116, 139, 0.55)',
            borderWidth: 1,
            borderRadius: 6
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        onClick: (_ev, els) => {
          if (els && els.length) {
            const idx = els[0].index;
            if (global.LN[idx] && typeof global.openDrawer === 'function') global.openDrawer(global.LN[idx]);
          }
        },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, color: '#334155', font: { size: 11, weight: '700' } } },
          datalabels: { display: false },
          tooltip: { enabled: false, external: extTooltip, mode: 'index', intersect: false }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155', font: { size: 10.5, weight: '700' } } },
          y: { beginAtZero: true, grid: { color: 'rgba(11, 27, 51, 0.08)' }, ticks: { color: '#64748B', callback: v => fS(v) } }
        }
      }
    });

    // Gauges Intra-Mensuales S1..S4
    [1, 2, 3, 4].forEach(w => {
      const rw = sum(A, M, w, null, 'DOLARES', 'REAL');
      const pctMeta = totMetaMes > 0 && rw > 0 ? (rw / totMetaMes) * 100 : 0;
      const pctEl = document.getElementById(`g${w}-pct`);
      const subEl = document.getElementById(`g${w}-sub`);
      const cardEl = document.getElementById(`g${w}-card`);
      if (cardEl) cardEl.classList.toggle('active-week', w === S);
      if (pctEl) pctEl.textContent = rw > 0 ? `${pctMeta.toFixed(1)}%` : 'Proy.';
      if (subEl) subEl.textContent = rw > 0 ? `${fS(rw)} / ${fS(totMetaMes)}` : `Ppto: ${fS(sum(A, M, w, null, 'DOLARES', 'PRESUPUESTO'))}`;

      const col = rw <= 0 ? 'rgba(184, 149, 90, 0.42)' : (w === S ? '#0B1B33' : '#B8955A');
      const fillVal = Math.min(100, pctMeta);
      makeChart(`g${w}`, {
        type: 'doughnut',
        data: {
          datasets: [{
            data: [fillVal, Math.max(0, 100 - fillVal)],
            backgroundColor: [col, 'rgba(11, 27, 51, 0.08)'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          rotation: -90,
          circumference: 180,
          cutout: '76%',
          plugins: { legend: { display: false }, tooltip: { enabled: false }, datalabels: { display: false } }
        }
      });
    });

    // Tabla Matriz Ejecutiva por Línea
    const tb = document.getElementById('tb-exec');
    const tf = document.getElementById('tf-exec');
    if (tb) {
      tb.innerHTML = global.LN.map((l, idx) => {
        const real = sum(A, M, S, l, 'DOLARES', 'REAL');
        const ppto = sum(A, M, S, l, 'DOLARES', 'PRESUPUESTO');
        const qReal = sum(A, M, S, l, 'CANTIDADES', 'REAL');
        const prevY = sum(A - 1, M, S, l, 'DOLARES', 'REAL');
        const brecha = real - ppto;
        const pct = cp(real, ppto);
        const yoy = vp(real, prevY);
        const pv = computePriceVolume(A, M, S, l);
        const predLine = predRep?.lines?.[l];
        const p50Line = Number(predLine?.p50 || sum(A, M, 4, l, 'DOLARES', 'PRESUPUESTO'));
        const isOut = Boolean(predLine?.isOutOfHistory);
        const weight = totReal > 0 ? (real / totReal) * 100 : 0;

        return `<tr class="clickable-row" onclick="window.openDrawer('${l}')">
          <td>
            <div style="display:flex;align-items:center;gap:6px;">
              <span class="line-dot" style="color:${global.LINE_COLORS[idx]};background:${global.LINE_COLORS[idx]};"></span>
              <span>${escHtml(global.DISP_MAP[l])}</span>
              ${isOut ? `<span class="sev-badge sev-warning" title="Anomalía Z-MAD detectada">${global.ico('alert-triangle', 10)} Z-MAD</span>` : ''}
            </div>
          </td>
          <td>${qReal > 0 ? fN(qReal) : 'Fijo'}</td>
          <td>${pv.effTariffR > 0 ? fTariff(pv.effTariffR) : '—'}</td>
          <td style="font-weight:800;color:#0B1B33;">${f$(real)}</td>
          <td>${f$(ppto)}</td>
          <td class="${brecha >= 0 ? 'pos' : 'neg'}" style="font-weight:800;">${brecha >= 0 ? '+' : ''}${f$(brecha)}</td>
          <td>${fC(pct)}</td>
          <td class="${pv.volEffect >= 0 ? 'pos' : 'neg'}">${pv.volEffect >= 0 ? '+' : ''}${fS(pv.volEffect)}</td>
          <td class="${pv.priceEffect >= 0 ? 'pos' : 'neg'}">${pv.priceEffect >= 0 ? '+' : ''}${fS(pv.priceEffect)}</td>
          <td>${fP(yoy)}</td>
          <td style="color:#1D4ED8;font-weight:700;">${fS(p50Line)}</td>
          <td>${weight.toFixed(1)}%</td>
          <td onclick="event.stopPropagation()">
            <button type="button" class="row-sim-btn" onclick="window.openChartModal('comp','${l}','predictive')">
              ${global.ico('sliders', 11)} <span>Simular</span>
            </button>
          </td>
        </tr>`;
      }).join('');
    }
    if (tf) {
      tf.innerHTML = `<tr>
        <td>CONSOLIDADO CORPORATIVO (6 LÍNEAS)</td>
        <td>—</td>
        <td>Mix Ponderado</td>
        <td>${f$(totReal)}</td>
        <td>${f$(totPpto)}</td>
        <td class="${netGap >= 0 ? 'pos' : 'neg'}">${netGap >= 0 ? '+' : ''}${f$(netGap)}</td>
        <td>${fC(pctCumpl)}</td>
        <td class="${sumVolEffect >= 0 ? 'pos' : 'neg'}">${sumVolEffect >= 0 ? '+' : ''}${fS(sumVolEffect)}</td>
        <td class="${sumPriceEffect >= 0 ? 'pos' : 'neg'}">${sumPriceEffect >= 0 ? '+' : ''}${fS(sumPriceEffect)}</td>
        <td>${fP(pctYoY)}</td>
        <td style="color:#1D4ED8;">${fS(p50Tot)}</td>
        <td>100.0%</td>
        <td>—</td>
      </tr>`;
    }
  }

  /* ═══════════════════════════════════════════════════════════════
     VISTA 2: ANALÍTICA ESTRUCTURAL, SUB-LÍNEAS & HEATMAP ANUAL
     ═══════════════════════════════════════════════════════════════ */
  function collectSublinesForCut(A, M, S, lineFilter = 'ALL') {
    const out = [];
    const lines = (lineFilter === 'ALL' || !global.LN.includes(lineFilter)) ? global.LN : [lineFilter];
    lines.forEach(l => {
      const sObj = global.SUBLINEAS?.[String(A)]?.[M]?.[String(S)]?.[l] || {};
      const lc = global.LINES_CONFIG.find(x => x.code === l);
      const subOrder = lc ? lc.sublines.map(x => x.code) : Object.keys(sObj);
      subOrder.forEach(sc => {
        const entry = sObj[sc];
        if (!entry) return;
        const meta = global.SUBLINE_META[`${l}::${sc}`] || {};
        const dReal = Number(entry.DOLARES?.REAL || 0);
        const dPpto = Number(entry.DOLARES?.PRESUPUESTO || 0);
        const qReal = Number(entry.CANTIDADES?.REAL || 0);
        const qPpto = Number(entry.CANTIDADES?.PRESUPUESTO || 0);
        out.push({
          line: l,
          lineName: global.DISP_MAP[l] || l,
          sub: sc,
          label: meta.label || global.SUB_LABELS[sc] || sc,
          hasQty: Boolean(meta.hasQty),
          real: dReal,
          ppto: dPpto,
          brecha: dReal - dPpto,
          cumpl: cp(dReal, dPpto),
          qReal,
          qPpto,
          tarReal: qReal > 0 ? dReal / qReal : 0,
          tarPpto: qPpto > 0 ? dPpto / qPpto : 0
        });
      });
    });
    return out;
  }

  function renderAnalitica() {
    const { A, M, S } = getCut();
    const lVals = global.LN.map(l => sum(A, M, S, l, 'DOLARES', 'REAL'));
    const lPptos = global.LN.map(l => sum(A, M, S, l, 'DOLARES', 'PRESUPUESTO'));
    const totReal = lVals.reduce((a, b) => a + b, 0) || 1;
    const totPpto = lPptos.reduce((a, b) => a + b, 0);

    // HHI Líneas
    const hhi = global.LN.reduce((acc, _l, idx) => acc + Math.pow((lVals[idx] / totReal) * 100, 2), 0);
    const effN = hhi > 0 ? 10000 / hhi : 0;

    // Pareto 24 sub-líneas
    const allSubs = collectSublinesForCut(A, M, S, 'ALL');
    const sortedSubs = [...allSubs].sort((a, b) => b.real - a.real);
    let cum = 0, p80 = 0;
    sortedSubs.forEach(s => {
      const sh = (s.real / totReal) * 100;
      cum += sh;
      if (cum <= 80.5 || p80 === 0) p80++;
    });

    const byGapDesc = [...allSubs].sort((a, b) => b.brecha - a.brecha);
    const topPos = byGapDesc[0];
    const topNeg = byGapDesc[byGapDesc.length - 1];

    document.getElementById('ana-hhi-val').textContent = Math.round(hhi).toLocaleString('en-US');
    document.getElementById('ana-hhi-sub').innerHTML = `<span>${hhi < 2000 ? 'Portafolio Diversificado' : 'Concentración Moderada'}</span><strong>N eff = ${effN.toFixed(1)} líneas</strong>`;
    document.getElementById('ana-pareto-val').textContent = `${p80} / ${allSubs.length}`;
    document.getElementById('ana-pareto-sub').innerHTML = `<span>Sub-líneas generan el 80% del ingreso</span><strong>S${S} ${M.slice(0, 3)}</strong>`;
    document.getElementById('ana-top-pos-val').textContent = topPos ? topPos.label : '—';
    document.getElementById('ana-top-pos-sub').innerHTML = `<span class="pos" style="font-weight:800;">+${f$(topPos?.brecha || 0)}</span><span>${topPos?.cumpl?.toFixed(1) || '—'}% cumpl.</span>`;
    document.getElementById('ana-top-neg-val').textContent = topNeg ? topNeg.label : '—';
    document.getElementById('ana-top-neg-sub').innerHTML = `<span class="neg" style="font-weight:800;">${f$(topNeg?.brecha || 0)}</span><span>${topNeg?.cumpl?.toFixed(1) || '—'}% cumpl.</span>`;

    // Puente Waterfall Ppto -> Brechas por Línea -> Real
    const wfLabels = [`Ppto S${S}`, ...global.LL, `Real S${S}`];
    const wfFloat = [[0, totPpto]];
    const wfCols = ['rgba(100, 116, 139, 0.55)'];
    const wfRaw = [totPpto];
    let run = totPpto;
    global.LN.forEach((_l, idx) => {
      const gap = lVals[idx] - lPptos[idx];
      const nxt = run + gap;
      wfFloat.push([Math.min(run, nxt), Math.max(run, nxt)]);
      wfCols.push(gap >= 0 ? '#059669' : '#BE123C');
      wfRaw.push(gap);
      run = nxt;
    });
    wfFloat.push([0, totReal]);
    wfCols.push('#0B1B33');
    wfRaw.push(totReal);

    makeChart('cWf', {
      type: 'bar',
      data: { labels: wfLabels, datasets: [{ label: 'Puente ($)', data: wfFloat, backgroundColor: wfCols, borderRadius: 6 }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 20 } },
        plugins: {
          legend: { display: false },
          datalabels: {
            display: true,
            anchor: 'end',
            align: 'top',
            font: { size: 10, weight: '800' },
            color: ctx => wfCols[ctx.dataIndex] === 'rgba(100, 116, 139, 0.55)' ? '#475569' : wfCols[ctx.dataIndex],
            formatter: (_v, ctx) => {
              const val = wfRaw[ctx.dataIndex];
              if (ctx.dataIndex === 0 || ctx.dataIndex === wfLabels.length - 1) return fS(val);
              return (val >= 0 ? '+' : '') + fS(val);
            }
          },
          tooltip: {
            enabled: false,
            external: extTooltip,
            callbacks: {
              label: ctx => {
                const v = wfRaw[ctx.dataIndex];
                return (ctx.dataIndex === 0 || ctx.dataIndex === wfLabels.length - 1) ? f$(v) : `${v >= 0 ? '+' : ''}${f$(v)}`;
              }
            }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#334155', font: { size: 10.5, weight: '700' } } },
          y: { beginAtZero: true, grid: { color: 'rgba(11, 27, 51, 0.08)' }, ticks: { color: '#64748B', callback: v => fS(v) } }
        }
      }
    });

    // Mix Doughnut
    makeChart('cMix', {
      type: 'doughnut',
      data: {
        labels: global.LL,
        datasets: [{
          data: lVals,
          backgroundColor: global.LINE_COLORS,
          borderColor: '#FFFFFF',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        plugins: {
          legend: { position: 'right', labels: { color: '#334155', boxWidth: 12, font: { size: 11, weight: '700' } } },
          datalabels: {
            display: true,
            color: '#FFFFFF',
            font: { size: 10, weight: '900' },
            formatter: v => `${((v / totReal) * 100).toFixed(1)}%`
          },
          tooltip: { enabled: false, external: extTooltip }
        }
      }
    });

    // Píldoras de filtro de línea para sub-líneas
    const pillBox = document.getElementById('ana-line-pills');
    if (pillBox) {
      pillBox.innerHTML = `<button type="button" class="pill-btn ${activeAnaLineFilter === 'ALL' ? 'active' : ''}" onclick="window.filterAnaSublines('ALL')">Todas (24)</button>` +
        global.LN.map((l, idx) => `<button type="button" class="pill-btn ${activeAnaLineFilter === l ? 'active' : ''}" onclick="window.filterAnaSublines('${l}')">${escHtml(global.LL[idx])}</button>`).join('');
    }
    renderAnaSublinesTable();

    // Heatmap Anual (Año A)
    const hmTb = document.getElementById('tb-heatmap');
    if (hmTb) {
      const monthsHdr = global.MO.map((m, idx) => {
        const s4R = sum(A, m, 4, null, 'DOLARES', 'REAL');
        const ci = getCi(A, m, null);
        const eff = ci > 0 ? ci : (s4R > 0 ? s4R : sum(A, m, S, null, 'DOLARES', 'REAL'));
        const p4 = sum(A, m, 4, null, 'DOLARES', 'PRESUPUESTO');
        const pct = (eff > 0 && p4 > 0 && (s4R > 0 || ci > 0 || m === M)) ? (eff / (m === M && s4R <= 0 ? sum(A, m, S, null, 'DOLARES', 'PRESUPUESTO') : p4)) * 100 : null;
        return { m, pct, idx };
      });
      const renderHmCell = pct => {
        if (pct === null || isNaN(pct)) return '<span class="hm-empty">—</span>';
        const cls = pct >= 105 ? 'hm-great' : (pct >= 98 ? 'hm-ok' : (pct >= 90 ? 'hm-warn' : 'hm-bad'));
        return `<span class="hm-cell ${cls}">${pct.toFixed(1)}%</span>`;
      };

      const rowsHm = global.LN.map((l, idx) => {
        const cells = global.MO.map(m => {
          const ci = getCi(A, m, l);
          const s4R = sum(A, m, 4, l, 'DOLARES', 'REAL');
          const curR = sum(A, m, S, l, 'DOLARES', 'REAL');
          let pct = null;
          if (ci > 0 || s4R > 0) {
            const val = ci > 0 ? ci : s4R;
            const ppto = sum(A, m, 4, l, 'DOLARES', 'PRESUPUESTO');
            pct = ppto > 0 ? (val / ppto) * 100 : null;
          } else if (m === M && curR > 0) {
            const curP = sum(A, m, S, l, 'DOLARES', 'PRESUPUESTO');
            pct = curP > 0 ? (curR / curP) * 100 : null;
          }
          return `<td>${renderHmCell(pct)}</td>`;
        }).join('');
        return `<tr class="clickable-row" onclick="window.openDrawer('${l}')">
          <td><span class="line-dot" style="color:${global.LINE_COLORS[idx]};background:${global.LINE_COLORS[idx]};"></span>${escHtml(global.LL[idx])}</td>
          ${cells}
        </tr>`;
      }).join('');

      const totRow = `<tr style="background:rgba(184,149,90,0.16);font-weight:800;">
        <td style="color:#0B1B33;">TOTAL PORTAFOLIO</td>
        ${monthsHdr.map(x => `<td>${renderHmCell(x.pct)}</td>`).join('')}
      </tr>`;

      hmTb.innerHTML = rowsHm + totRow;
    }
  }

  function filterAnaSublines(lineCode) {
    activeAnaLineFilter = lineCode || 'ALL';
    document.querySelectorAll('#ana-line-pills .pill-btn').forEach(btn => {
      const txt = btn.getAttribute('onclick') || '';
      btn.classList.toggle('active', txt.includes(`'${activeAnaLineFilter}'`));
    });
    renderAnaSublinesTable();
  }

  function renderAnaSublinesTable() {
    const { A, M, S } = getCut();
    const tb = document.getElementById('tb-ana-sublines');
    if (!tb) return;
    const q = (document.getElementById('ana-sub-search')?.value || '').trim().toUpperCase();
    const all = collectSublinesForCut(A, M, S, activeAnaLineFilter);
    const grandTotal = all.reduce((a, x) => a + x.real, 0) || 1;
    const filtered = all.filter(item => !q || item.label.toUpperCase().includes(q) || item.lineName.toUpperCase().includes(q));

    if (!filtered.length) {
      tb.innerHTML = '<tr><td colspan="9" style="text-align:center;color:#94a3b8;padding:18px;">Sin sub-líneas para el filtro actual.</td></tr>';
      return;
    }

    tb.innerHTML = filtered.map(it => `<tr class="clickable-row" onclick="window.openChartModal('comp','${it.line}','predictive')">
      <td>${escHtml(it.label)}<div style="font-size:10px;color:#64748b;font-weight:600;">${escHtml(it.lineName)}</div></td>
      <td><span class="kpi-badge ${it.hasQty ? 'badge-blue' : 'badge-violet'}">${it.hasQty ? 'Q × Tarifa' : 'Recurrente Fijo'}</span></td>
      <td>${it.hasQty ? fN(it.qReal) : '—'}</td>
      <td>${it.hasQty && it.tarReal > 0 ? fTariff(it.tarReal) : '—'}</td>
      <td style="font-weight:800;color:#0B1B33;">${f$(it.real)}</td>
      <td>${f$(it.ppto)}</td>
      <td class="${it.brecha >= 0 ? 'pos' : 'neg'}" style="font-weight:700;">${it.brecha >= 0 ? '+' : ''}${f$(it.brecha)}</td>
      <td>${fC(it.cumpl)}</td>
      <td>${((it.real / grandTotal) * 100).toFixed(1)}%</td>
    </tr>`).join('');
  }

  /* ═══════════════════════════════════════════════════════════════
     VISTA 3: SEMÁFORO COMERCIAL & OKRS ESTRATÉGICOS
     ═══════════════════════════════════════════════════════════════ */
  function sfColor(p) {
    return p > 105 ? '#1D4ED8' : (p >= 95 ? '#059669' : (p >= 90 ? '#B45309' : '#BE123C'));
  }

  function sfClass(p) {
    return p > 105 ? 'azul' : (p >= 95 ? 'verde' : (p >= 90 ? 'amarillo' : 'rojo'));
  }

  function sfFmt(v, tipo) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    if (tipo === '%') return `${Math.round(v)}%`;
    if (tipo === '$') return f$(v);
    if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
    return fN(v);
  }

  function extractSemaforoData(A, M, S) {
    const raw = global.SEMAFORO_RAW || [];
    const dict = {};
    for (let r = 1; r < raw.length; r++) {
      const row = raw[r];
      if (!row || row.length < 10) continue;
      const rowA = row[0], rowM = String(row[1]).toUpperCase(), rowS = parseInt(row[2], 10);
      if (Number(rowA) !== Number(A) || rowM !== String(M).toUpperCase()) continue;
      const esc = String(row[3]).toUpperCase();
      const tipoCat = String(row[5]).toUpperCase();
      const ind = String(row[7]);
      const uni = String(row[8]).toUpperCase();
      const val = Number(row[9] || 0);
      if (!dict[ind]) dict[ind] = { nombre: ind, tipoCat, uni, metaMes: 0, metaSem: 0, ejec: 0 };
      if (esc.includes('PRESUPUESTO')) {
        if (rowS === 4) dict[ind].metaMes += val;
        if (rowS === parseInt(S, 10)) dict[ind].metaSem += val;
      } else if (esc === 'REAL' && rowS === parseInt(S, 10)) {
        dict[ind].ejec += val;
      }
    }

    const res = { productos: [], kpis: [], proyectos: [] };
    Object.values(dict).forEach(it => {
      const tipo = it.uni.startsWith('DOLAR') ? '$' : (it.uni === 'PORCENTAJE' ? '%' : 'NUM');
      const metaSem = it.metaSem || it.metaMes || 1;
      const cumpl = metaSem > 0 ? Math.round((it.ejec / metaSem) * 100) : 100;
      const item = { nombre: it.nombre, metaMes: it.metaMes, metaSem, ejec: it.ejec, cumpl, tipo };
      if (it.tipoCat.includes('PRODUCTO')) res.productos.push(item);
      else if (it.tipoCat.includes('KPI')) res.kpis.push(item);
      else res.proyectos.push(item);
    });
    return res;
  }

  function setSfFilter(status) {
    activeSfStatusFilter = status || 'ALL';
    document.querySelectorAll('.sf-filter-card').forEach(c => {
      c.classList.toggle('sf-filter-active', c.getAttribute('data-sf-filter') === activeSfStatusFilter);
    });
    renderSemaforo();
  }

  function renderSemaforo() {
    const { A, M, S } = getCut();
    const ds = extractSemaforoData(A, M, S);
    const mIdx = global.MO.indexOf(M);
    const prevMes = mIdx > 0 ? global.MO[mIdx - 1] : 'DICIEMBRE';
    const prevYr = mIdx > 0 ? A : A - 1;
    const dsPrev = extractSemaforoData(prevYr, prevMes, S);

    const allItems = [
      ...ds.productos.map(x => ({ ...x, cat: 'Producto', catColor: '#0B1B33' })),
      ...ds.kpis.map(x => ({ ...x, cat: 'KPI', catColor: '#B8955A' })),
      ...ds.proyectos.map(x => ({ ...x, cat: 'Proyecto', catColor: '#1D4ED8' }))
    ];

    const cnt = { azul: 0, verde: 0, amarillo: 0, rojo: 0 };
    const lists = { azul: [], verde: [], amarillo: [], rojo: [] };
    let sumCumpl = 0;

    allItems.forEach(it => {
      sumCumpl += Math.min(it.cumpl, 125);
      const cls = sfClass(it.cumpl);
      cnt[cls]++;
      lists[cls].push(it);
    });

    const tot = allItems.length || 1;
    const promGlobal = Math.round(sumCumpl / tot);
    const gVal = document.getElementById('sf-salud-val');
    if (gVal) {
      gVal.textContent = `${promGlobal}%`;
      gVal.style.color = sfColor(promGlobal);
    }

    makeChart('gSalud', {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [Math.min(100, promGlobal), Math.max(0, 100 - Math.min(100, promGlobal))],
          backgroundColor: [sfColor(promGlobal), 'rgba(11, 27, 51, 0.09)'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        rotation: -90,
        circumference: 180,
        cutout: '78%',
        plugins: { legend: { display: false }, tooltip: { enabled: false }, datalabels: { display: false } }
      }
    });

    const descEl = document.getElementById('sf-salud-desc');
    if (descEl) {
      descEl.innerHTML = `
        <div style="font-size:11.5px;color:#334155;line-height:1.45;">
          Evaluando <strong>${tot} métricas OKR/KPI</strong> · <strong style="color:#1D4ED8;">${cnt.azul}</strong> sobresalientes y <strong style="color:#BE123C;">${cnt.rojo}</strong> en alerta crítica.
        </div>
        <div style="height:36px;margin-top:8px;"><canvas id="spark-salud"></canvas></div>
      `;
      const sparkVals = [0, 1, 2, 3, 4, 5].map(offset => {
        let mi = mIdx - (5 - offset);
        let yy = A;
        if (mi < 0) { mi += 12; yy -= 1; }
        const dH = extractSemaforoData(yy, global.MO[mi], S);
        const hAll = [...dH.productos, ...dH.kpis, ...dH.proyectos];
        if (!hAll.length) return promGlobal;
        return Math.round(hAll.reduce((a, x) => a + Math.min(x.cumpl, 125), 0) / hAll.length);
      });
      makeChart('spark-salud', {
        type: 'line',
        data: {
          labels: ['-5M', '-4M', '-3M', '-2M', '-1M', 'Act'],
          datasets: [{ data: sparkVals, borderColor: '#B8955A', borderWidth: 2.2, pointRadius: 2.5, fill: false, tension: 0.3, datalabels: { display: false } }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: false }, datalabels: { display: false } },
          scales: { x: { display: false }, y: { display: false } }
        }
      });
    }

    const mapNames = { azul: 'azul', verde: 'verde', amarillo: 'alerta', rojo: 'rojo' };
    Object.keys(mapNames).forEach(k => {
      const ui = mapNames[k];
      const ce = document.getElementById(`sf-cnt-${ui}`);
      const pe = document.getElementById(`sf-pct-${ui}`);
      const le = document.getElementById(`sf-list-${ui}`);
      if (ce) ce.textContent = cnt[k];
      if (pe) pe.innerHTML = `<b>${Math.round((cnt[k] / tot) * 100)}% portafolio</b>`;
      if (le) {
        le.innerHTML = lists[k].slice(0, 2).map(it => `
          <div style="font-size:10px;border-left:2.5px solid ${it.catColor};padding-left:6px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#334155;">
            ${escHtml(it.nombre)} (${it.cumpl}%)
          </div>`).join('');
      }
    });

    // 6 Driver Cards Corporativos
    const findMet = (dataset, q) =>
      dataset.productos.find(x => x.nombre.toUpperCase().includes(q)) ||
      dataset.kpis.find(x => x.nombre.toUpperCase().includes(q)) ||
      dataset.proyectos.find(x => x.nombre.toUpperCase().includes(q));

    global.DRIVER_CARDS_META.forEach(dm => {
      const card = document.getElementById(dm.id);
      const tEl = document.getElementById(`${dm.id}-title`);
      const vEl = document.getElementById(`${dm.id}-val`);
      const varEl = document.getElementById(`${dm.id}-var`);
      const cur = findMet(ds, dm.query) || { nombre: dm.title, ejec: 0, metaSem: 0, cumpl: 0, tipo: 'NUM' };
      const prv = findMet(dsPrev, dm.query) || { ejec: 0, tipo: 'NUM' };
      if (tEl) tEl.textContent = dm.title;
      if (vEl) vEl.textContent = sfFmt(cur.ejec, cur.tipo);
      const pPct = cur.cumpl - 100;
      const mPct = prv.ejec > 0 ? Math.round(((cur.ejec - prv.ejec) / prv.ejec) * 100) : 0;
      if (varEl) {
        varEl.innerHTML = `
          <span style="color:${pPct >= 0 ? '#059669' : '#BE123C'};font-weight:700;">${pPct >= 0 ? '▲ +' : '▼ '}${pPct}% Meta</span>
          <span style="color:${mPct >= 0 ? '#1D4ED8' : '#B45309'};font-weight:700;">${mPct >= 0 ? '+' : ''}${mPct}% MA</span>
        `;
      }
      if (card) {
        card.onclick = () => {
          if (typeof global.openSemaforoModal === 'function') global.openSemaforoModal(cur.nombre);
        };
      }
    });

    // Tablas Semáforo
    const q = (document.getElementById('sf-search')?.value || '').trim().toUpperCase();
    const fillTbl = (id, items, prevItems) => {
      const tb = document.getElementById(id);
      if (!tb) return;
      const filtered = items.filter(it => {
        if (q && !it.nombre.toUpperCase().includes(q)) return false;
        if (activeSfStatusFilter !== 'ALL' && sfClass(it.cumpl) !== activeSfStatusFilter) return false;
        return true;
      });
      if (!filtered.length) {
        tb.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#64748b;padding:12px;">Sin métricas en este filtro</td></tr>';
        return;
      }
      tb.innerHTML = filtered.map(it => {
        const prv = prevItems.find(x => x.nombre === it.nombre);
        const diffMeta = it.metaSem > 0 ? Math.round(((it.ejec - it.metaSem) / it.metaSem) * 100) : 0;
        const diffMoM = prv && prv.ejec > 0 ? Math.round(((it.ejec - prv.ejec) / prv.ejec) * 100) : 0;
        const col = sfColor(it.cumpl);
        return `<tr class="clickable-row" onclick="window.openSemaforoModal('${escHtml(it.nombre).replace(/'/g, "\\'")}')">
          <td>${escHtml(it.nombre)}</td>
          <td style="color:#64748B;">${sfFmt(it.metaMes, it.tipo)}</td>
          <td>${sfFmt(it.metaSem, it.tipo)}</td>
          <td style="font-weight:800;color:${col};">${sfFmt(it.ejec, it.tipo)}</td>
          <td class="${diffMeta >= 0 ? 'pos' : 'neg'}" style="font-weight:700;">${diffMeta >= 0 ? '▲ +' : '▼ '}${diffMeta}%</td>
          <td class="${diffMoM >= 0 ? 'pos' : 'neg'}" style="font-weight:700;">${diffMoM >= 0 ? '+' : ''}${diffMoM}%</td>
          <td>
            <div class="sf-prog-wrap">
              <div class="sf-prog-bar"><div class="sf-prog-fill" style="background:${col};width:${Math.min(100, it.cumpl)}%;"></div></div>
              <span style="min-width:42px;text-align:center;font-weight:800;color:${col};">${it.cumpl}%</span>
            </div>
          </td>
        </tr>`;
      }).join('');
    };

    fillTbl('sf-tb-productos', ds.productos, dsPrev.productos);
    fillTbl('sf-tb-kpis', ds.kpis, dsPrev.kpis);
    fillTbl('sf-tb-proyectos', ds.proyectos, dsPrev.proyectos);
  }

  /* ═══════════════════════════════════════════════════════════════
     GUÍA RÁPIDA, EXPORTACIONES & MENÚS
     ═══════════════════════════════════════════════════════════════ */
  function openWelcomeModal() {
    const bd = document.getElementById('welcome-modal-backdrop');
    const md = document.getElementById('welcome-modal');
    if (!bd || !md) return;
    const { A, M, S } = getCut();
    let totReal = 0, totPpto = 0;
    global.LN.forEach(l => {
      totReal += sum(A, M, S, l, 'DOLARES', 'REAL');
      totPpto += sum(A, M, S, l, 'DOLARES', 'PRESUPUESTO');
    });
    const pct = cp(totReal, totPpto);
    const audSum = global.AUDIT_SUMMARY || {};
    const predRep = global.PREDICTIVE_DATA || (typeof global.computeClientPredictiveReport === 'function' ? global.computeClientPredictiveReport(A, M, S, {}) : null);
    const outCnt = Number(predRep?.summary?.outOfHistoryCount || 0);

    const sub = document.getElementById('wm-subtitle');
    if (sub) sub.textContent = `Escenario Sintético Activo: ${currentEcosystem?.scenarioLabel || 'LIVE'} · ${M} ${A} (S${S}) · 6 Líneas y 24 Sub-Líneas`;

    const strip = document.getElementById('wm-live-strip');
    if (strip) {
      strip.innerHTML = `
        <div class="wm-live-item"><span class="wm-live-lbl">Corte Activo</span><span class="wm-live-val">${M.slice(0, 3)} ${A} · S${S}</span></div>
        <div class="wm-live-item"><span class="wm-live-lbl">Ingreso Real Corte</span><span class="wm-live-val" style="color:#0B1B33;">${f$(totReal)}</span></div>
        <div class="wm-live-item"><span class="wm-live-lbl">Cumpl. vs Ppto</span><span class="wm-live-val" style="color:${pct >= 100 ? '#059669' : '#B45309'};">${pct != null ? pct.toFixed(1) + '%' : '—'}</span></div>
        <div class="wm-live-item"><span class="wm-live-lbl">Validación BD</span><span class="wm-live-val" style="color:${audSum.critical > 0 ? '#BE123C' : '#9A7438'};">${audSum.total || 0} hallazgos</span></div>
        <div class="wm-live-item"><span class="wm-live-lbl">Radar Z-MAD</span><span class="wm-live-val" style="color:${outCnt > 0 ? '#B45309' : '#059669'};">${outCnt > 0 ? outCnt + ' señales' : 'Normal'}</span></div>
      `;
    }
    if (typeof global.hydrateIcons === 'function') global.hydrateIcons(md);
    bd.classList.add('open');
    md.classList.add('open');
  }

  function closeWelcomeModal(nextAction = null) {
    document.getElementById('welcome-modal-backdrop')?.classList.remove('open');
    document.getElementById('welcome-modal')?.classList.remove('open');
    if (!nextAction) return;
    if (nextAction === 'ingresos') switchView('view-ingresos');
    else if (nextAction === 'analitica') switchView('view-analitica');
    else if (nextAction === 'semaforo') switchView('view-semaforo');
    else if (nextAction === 'predictivo' && typeof global.openChartModal === 'function') global.openChartModal('comp', 'CLOUD_SAAS', 'predictive');
    else if (nextAction === 'audit' && typeof global.openAuditModal === 'function') global.openAuditModal();
  }

  function toggleExportMenu(e) {
    if (e && e.stopPropagation) e.stopPropagation();
    document.getElementById('export-dropdown')?.classList.toggle('open');
  }

  document.addEventListener('click', e => {
    const wrap = document.getElementById('export-menu-wrap');
    if (wrap && (!wrap.contains(e.target) || e.target.closest('.export-item'))) {
      document.getElementById('export-dropdown')?.classList.remove('open');
    }
  });

  function exportCSV() {
    const { A, M, S } = getCut();
    const rows = [['ANIO', 'MES', 'SEMANA', 'LINEA', 'Q_REAL', 'TARIFA_EFF_USD', 'REAL_USD', 'PPTO_USD', 'BRECHA_USD', 'CUMPL_PCT']];
    global.LN.forEach(l => {
      const r = sum(A, M, S, l, 'DOLARES', 'REAL');
      const p = sum(A, M, S, l, 'DOLARES', 'PRESUPUESTO');
      const q = sum(A, M, S, l, 'CANTIDADES', 'REAL');
      const te = q > 0 ? r / q : 0;
      const c = p > 0 ? ((r / p) * 100).toFixed(2) : '';
      rows.push([A, M, S, global.DISP_MAP[l], q, te.toFixed(4), r.toFixed(2), p.toFixed(2), (r - p).toFixed(2), c]);
    });
    const csv = '\uFEFF' + rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    a.download = `Nexus_FPA_Resumen_${A}_${M}_S${S}.csv`;
    a.click();
    showToast('Resumen financiero exportado a CSV');
  }

  function exportPNG(scale = 2) {
    if (typeof global.html2canvas === 'undefined') {
      showToast('html2canvas no disponible en este entorno');
      return;
    }
    const target = document.getElementById('shell');
    if (!target) return;
    showToast(`Renderizando captura UHD (${scale * 2}K)...`);
    global.html2canvas(target, { scale, backgroundColor: '#F4F6FA', useCORS: true }).then(canvas => {
      const link = document.createElement('a');
      link.download = `Nexus_FPA_Dashboard_${scale * 2}K.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    });
  }

  function exportHTML() {
    const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8;' }));
    a.download = `Nexus_FPA_Snapshot_${currentEcosystem?.scenarioLabel || 'LIVE'}.html`;
    a.click();
    showToast('Instantánea HTML exportada');
  }

  /* ─── ARRANQUE AUTOMÁTICO SIN LOGIN ─── */
  document.addEventListener('DOMContentLoaded', () => {
    if (window.self !== window.top) {
      document.body.classList.add('embedded-mode');
    }
    const initialData = global.NexusSyntheticEngine.generateDataset(20261114);
    boot(initialData, false);
  });

  global.escHtml = escHtml;
  global.f$ = f$;
  global.fN = fN;
  global.fS = fS;
  global.fC = fC;
  global.fP = fP;
  global.fTariff = fTariff;
  global.cp = cp;
  global.vp = vp;
  global.sum = sum;
  global.getCi = getCi;
  global.showToast = showToast;
  global.extTooltip = extTooltip;
  global.getCut = getCut;
  global.collectSublinesForCut = collectSublinesForCut;
  global.computePriceVolume = computePriceVolume;
  global.extractSemaforoData = extractSemaforoData;
  global.switchView = switchView;
  global.renderCurrentView = renderCurrentView;
  global.onYearOrMonthChange = onYearOrMonthChange;
  global.regenerateRandomScenario = regenerateRandomScenario;
  global.filterAnaSublines = filterAnaSublines;
  global.renderAnaSublinesTable = renderAnaSublinesTable;
  global.setSfFilter = setSfFilter;
  global.renderSemaforo = renderSemaforo;
  global.openWelcomeModal = openWelcomeModal;
  global.closeWelcomeModal = closeWelcomeModal;
  global.toggleExportMenu = toggleExportMenu;
  global.exportCSV = exportCSV;
  global.exportPNG = exportPNG;
  global.exportHTML = exportHTML;
})(typeof window !== 'undefined' ? window : globalThis);

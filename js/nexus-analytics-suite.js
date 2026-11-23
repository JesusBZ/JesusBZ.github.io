/*!
 * NEXUS QUANT ANALYTICS & FP&A SUITE v3.0
 * Hybrid Enterprise Data Analytics + 4-Level P&L + Predictive ML Lab + What-If Monte Carlo + CSV Importer
 * Bidirectional Power-BI Cross-Filtering & Dual Theme (Midnight Navy & Champagne Gold / Executive Light)
 * Author: Econ. Jesús Benjamín Zerpa — jesusbz.github.io
 */
(function () {
  'use strict';

  var DATASETS_META = {
    WALMART_WMT: {
      name: 'Walmart Inc. (NYSE: WMT) · Retail Omnicanal & Supercenters',
      regions: [
        { name: 'Walmart U.S. (Norteamérica)', weight: 0.58 },
        { name: 'México & Centroamérica (Walmex)', weight: 0.19 },
        { name: 'Canadá & Cono Sur', weight: 0.13 },
        { name: 'Mercados Internacionales', weight: 0.10 }
      ],
      segments: [
        { name: 'Supercenters & Hipermercados', weight: 0.54, marginBonus: 0.008 },
        { name: 'Omnicanal Pickup & Delivery', weight: 0.28, marginBonus: 0.015 },
        { name: 'Neighborhood Markets & Express', weight: 0.18, marginBonus: -0.008 }
      ],
      units: [
        { name: 'Grocery & Perecederos', baseQ: 340000, price: 54.5, cogsPct: 0.735, opexPct: 0.168, growth: 0.011, seas: [0.95, 0.94, 0.99, 0.98, 1.01, 1.02, 1.03, 1.04, 1.02, 1.05, 1.16, 1.24] },
        { name: 'Mercancía General & Hogar', baseQ: 145000, price: 68.0, cogsPct: 0.695, opexPct: 0.190, growth: 0.009, seas: [0.86, 0.88, 0.94, 0.95, 0.99, 1.01, 1.00, 1.06, 1.02, 1.08, 1.28, 1.38] },
        { name: 'Salud, Farmacia & Óptica', baseQ: 112000, price: 46.8, cogsPct: 0.685, opexPct: 0.192, growth: 0.014, seas: [1.04, 1.02, 1.01, 0.99, 0.98, 0.98, 0.97, 0.99, 1.01, 1.04, 1.07, 1.11] },
        { name: 'Walmart eCommerce & Pickup', baseQ: 128000, price: 62.4, cogsPct: 0.708, opexPct: 0.185, growth: 0.022, seas: [0.92, 0.93, 0.97, 0.99, 1.03, 1.05, 1.08, 1.06, 1.07, 1.12, 1.29, 1.36] },
        { name: "Sam's Club (Mayorista)", baseQ: 82000, price: 118.5, cogsPct: 0.778, opexPct: 0.126, growth: 0.013, seas: [0.93, 0.94, 0.99, 0.98, 1.02, 1.04, 1.03, 1.04, 1.05, 1.07, 1.18, 1.27] },
        { name: 'Walmart Connect & Marketplace', baseQ: 36000, price: 94.0, cogsPct: 0.340, opexPct: 0.295, growth: 0.026, seas: [0.90, 0.92, 0.98, 1.00, 1.04, 1.06, 1.05, 1.08, 1.10, 1.16, 1.32, 1.40] }
      ]
    },
    RETAIL_CLUB: {
      name: 'Club Mayorista & Membresías (Formato Warehouse Retail)',
      regions: [
        { name: 'Estados Unidos & Puerto Rico', weight: 0.62 },
        { name: 'Canadá & México', weight: 0.20 },
        { name: 'Europa (España / Reino Unido)', weight: 0.10 },
        { name: 'Asia-Pacífico', weight: 0.08 }
      ],
      segments: [
        { name: 'Membresía Ejecutiva (2% Recompensa)', weight: 0.52, marginBonus: 0.012 },
        { name: 'Membresía Comercial / B2B', weight: 0.29, marginBonus: 0.004 },
        { name: 'Membresía Estándar & Digital', weight: 0.19, marginBonus: -0.006 }
      ],
      units: [
        { name: 'Alimentos & Frescos Mayorista', baseQ: 210000, price: 88.0, cogsPct: 0.810, opexPct: 0.102, growth: 0.012, seas: [0.94, 0.95, 0.99, 0.98, 1.01, 1.03, 1.03, 1.04, 1.04, 1.06, 1.17, 1.26] },
        { name: 'Marca Propia (Private Label)', baseQ: 135000, price: 74.5, cogsPct: 0.745, opexPct: 0.112, growth: 0.017, seas: [0.95, 0.96, 1.00, 1.00, 1.02, 1.04, 1.04, 1.05, 1.06, 1.08, 1.18, 1.25] },
        { name: 'Electrónica, Hogar & Línea Blanca', baseQ: 64000, price: 162.0, cogsPct: 0.770, opexPct: 0.118, growth: 0.010, seas: [0.85, 0.88, 0.93, 0.95, 1.00, 1.02, 1.01, 1.05, 1.03, 1.09, 1.31, 1.39] },
        { name: 'Farmacia, Óptica & Bienestar', baseQ: 72000, price: 58.0, cogsPct: 0.710, opexPct: 0.145, growth: 0.015, seas: [1.03, 1.01, 1.00, 0.99, 0.99, 0.98, 0.98, 1.00, 1.02, 1.04, 1.08, 1.12] },
        { name: 'Ingresos por Membresías Anuales', baseQ: 95000, price: 65.0, cogsPct: 0.120, opexPct: 0.220, growth: 0.016, seas: [1.02, 0.98, 1.00, 0.99, 1.00, 1.01, 1.00, 1.01, 1.03, 1.04, 1.06, 1.09] },
        { name: 'E-Commerce & Entrega Directa', baseQ: 58000, price: 112.0, cogsPct: 0.760, opexPct: 0.135, growth: 0.021, seas: [0.91, 0.93, 0.97, 0.99, 1.03, 1.05, 1.06, 1.05, 1.07, 1.12, 1.28, 1.35] }
      ]
    },
    RETAIL_OMNI: {
      name: 'Cadena Retail Especializado, Supermercados & Farmacia',
      regions: [
        { name: 'Región Metropolitana Norte', weight: 0.36 },
        { name: 'Corredor Centro-Occidente', weight: 0.28 },
        { name: 'Región Sur & Costa', weight: 0.21 },
        { name: 'Hub Logístico Omnicanal', weight: 0.15 }
      ],
      segments: [
        { name: 'Tiendas Gran Formato', weight: 0.49, marginBonus: 0.010 },
        { name: 'App Móvil & Quick-Commerce', weight: 0.31, marginBonus: 0.012 },
        { name: 'Tiendas de Proximidad / Express', weight: 0.20, marginBonus: -0.010 }
      ],
      units: [
        { name: 'Supermercado & Despensa', baseQ: 185000, price: 31.5, cogsPct: 0.680, opexPct: 0.195, growth: 0.012, seas: [0.96, 0.95, 1.00, 0.99, 1.02, 1.03, 1.04, 1.04, 1.05, 1.07, 1.14, 1.22] },
        { name: 'Farmacia & Salud Clínica', baseQ: 145000, price: 24.8, cogsPct: 0.610, opexPct: 0.210, growth: 0.014, seas: [1.02, 0.99, 1.00, 0.99, 1.01, 1.03, 1.04, 1.03, 1.05, 1.08, 1.11, 1.18] },
        { name: 'Cuidado Personal & Dermo', baseQ: 118000, price: 21.4, cogsPct: 0.570, opexPct: 0.225, growth: 0.015, seas: [0.91, 0.95, 0.99, 1.01, 1.08, 1.03, 1.01, 1.03, 1.05, 1.09, 1.17, 1.26] },
        { name: 'Delivery & Última Milla', baseQ: 96000, price: 28.5, cogsPct: 0.640, opexPct: 0.215, growth: 0.022, seas: [0.94, 0.95, 0.98, 1.00, 1.05, 1.06, 1.05, 1.06, 1.08, 1.12, 1.24, 1.31] },
        { name: 'Hogar & Electrodomésticos', baseQ: 62000, price: 48.0, cogsPct: 0.665, opexPct: 0.205, growth: 0.009, seas: [0.89, 0.91, 0.96, 0.98, 1.02, 1.03, 1.02, 1.04, 1.05, 1.08, 1.22, 1.29] },
        { name: 'Marcas Propias Exclusivas', baseQ: 74000, price: 25.6, cogsPct: 0.520, opexPct: 0.200, growth: 0.019, seas: [0.95, 0.96, 1.00, 1.01, 1.03, 1.05, 1.04, 1.05, 1.08, 1.10, 1.16, 1.23] }
      ]
    }
  };

  var DEFAULT_REGIONS = DATASETS_META.WALMART_WMT.regions;
  var DEFAULT_SEGMENTS = DATASETS_META.WALMART_WMT.segments;

  var MONTHS_SHORT = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

  var state = {
    theme: 'dark',
    activeTab: 'view-bi',
    datasetKey: 'WALMART_WMT',
    seed: 20261121,
    customRecords: null,
    customName: null,
    rawCsvHeaders: [],
    rawCsvRows: [],
    records: [],
    filters: {
      year: 'ALL',
      quarter: 'ALL',
      region: 'ALL',
      segment: 'ALL',
      unit: 'ALL'
    },
    tableSort: { col: 'revReal', asc: false },
    pivotSort: { col: 'revReal', asc: false },
    lab: {
      metric: 'revReal',
      horizon: 12,
      ci: 0.95,
      zThresh: 2.1
    },
    whatIf: {
      dQ: 0,
      dP: 0,
      elast: -0.65,
      dCogs: 0,
      dOpex: 0,
      wacc: 7.5
    },
    pivot: {
      groupBy: 'unit',
      search: ''
    }
  };

  // Safe HTML escaper (strictly prevents XSS on custom CSV uploads)
  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function createRng(seed) {
    var a = (seed >>> 0) || 123456789;
    return function () {
      var t = (a += 0x6D2B79F5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function randNorm(rng) {
    var u1 = Math.max(1e-7, rng());
    var u2 = rng();
    return Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  }

  function fmtMoney(v, compact) {
    if (!isFinite(v)) return '$0';
    var sign = v < 0 ? '-' : '';
    var abs = Math.abs(v);
    if (compact) {
      if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(2) + 'B';
      if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(2) + 'M';
      if (abs >= 1e3) return sign + '$' + (abs / 1e3).toFixed(1) + 'k';
    }
    return sign + '$' + Math.round(abs).toLocaleString('en-US');
  }

  function fmtNum(v) {
    if (!isFinite(v)) return '0';
    if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(2) + 'B';
    if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(2) + 'M';
    return Math.round(v).toLocaleString('en-US');
  }

  var SHORT_UNIT_NAMES = {
    'Mercancía General & Hogar': 'Mercancía General',
    'Salud, Farmacia & Óptica': 'Salud & Farmacia',
    'Walmart eCommerce & Pickup': 'Walmart eCommerce',
    "Sam's Club (Mayorista)": "Sam's Club",
    'Walmart Connect & Marketplace': 'Walmart Connect'
  };

  function shortUnitLabel(name) {
    if (SHORT_UNIT_NAMES[name]) return SHORT_UNIT_NAMES[name];
    var s = String(name || '');
    return s.length > 22 ? (s.slice(0, 20) + '...') : s;
  }

  var SVG_ICONS = {
    sun: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>',
    moon: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>',
    close: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
  };

  function fmtPct(v, plus) {
    if (!isFinite(v)) return '0.0%';
    var p = (v * 100).toFixed(1) + '%';
    return (plus && v > 0) ? '+' + p : p;
  }

  function showToast(msg) {
    var el = document.getElementById('nxToast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el.__t);
    el.__t = setTimeout(function () { el.classList.remove('show'); }, 2800);
  }

  function getPalette() {
    var isLight = state.theme === 'light';
    return {
      paper: isLight ? '#ffffff' : '#102342',
      plot: isLight ? '#FFFFFF' : '#0B1B33',
      card: isLight ? '#f1f5f9' : '#163259',
      text: isLight ? '#102342' : '#FFFFFF',
      sub: isLight ? '#334155' : '#cbd5e1',
      muted: isLight ? '#64748b' : '#94a3b8',
      grid: isLight ? 'rgba(100,116,139,0.18)' : 'rgba(148,163,184,0.14)',
      gold: isLight ? '#9a7432' : '#B8955A',
      goldBright: '#B8955A',
      sky: isLight ? '#0284c7' : '#38bdf8',
      emerald: isLight ? '#059669' : '#10b981',
      rose: isLight ? '#e11d48' : '#f43f5e',
      indigo: isLight ? '#4f46e5' : '#818cf8',
      teal: isLight ? '#0d9488' : '#2dd4bf',
      cobalt: isLight ? '#2563eb' : '#60a5fa',
      series: isLight
        ? ['#0284c7', '#b48228', '#059669', '#e11d48', '#4f46e5', '#0d9488', '#2563eb', '#d97706']
        : ['#38bdf8', '#B8955A', '#10b981', '#f43f5e', '#818cf8', '#2dd4bf', '#60a5fa', '#D9C29A']
    };
  }

  // ============================================================================
  // SYNTHETIC MULTI-DIMENSIONAL GENERATOR (2024 - 2026)
  // ============================================================================
  function buildDataset() {
    if (state.datasetKey === 'CUSTOM' && Array.isArray(state.customRecords) && state.customRecords.length > 0) {
      state.records = state.customRecords;
      populateFilterDropdowns();
      return;
    }

    var meta = DATASETS_META[state.datasetKey] || DATASETS_META.WALMART_WMT;
    var activeRegions = meta.regions || DEFAULT_REGIONS;
    var activeSegments = meta.segments || DEFAULT_SEGMENTS;
    var rng = createRng(state.seed);
    var rows = [];
    var years = [2024, 2025, 2026];

    // Pick two realistic shock months for Z-MAD anomaly demonstration
    var shockIdxPos = 14 + Math.floor(rng() * 10);
    var shockIdxNeg = 24 + Math.floor(rng() * 10);

    for (var yi = 0; yi < years.length; yi++) {
      var yr = years[yi];
      for (var m = 0; m < 12; m++) {
        var t = yi * 12 + m;
        var qtr = 'Q' + (Math.floor(m / 3) + 1);
        var ym = yr + '-' + (m + 1 < 10 ? '0' + (m + 1) : (m + 1));

        for (var ui = 0; ui < meta.units.length; ui++) {
          var u = meta.units[ui];
          var trend = Math.pow(1 + u.growth, t);
          var seas = u.seas[m];

          for (var ri = 0; ri < activeRegions.length; ri++) {
            var reg = activeRegions[ri];
            for (var si = 0; si < activeSegments.length; si++) {
              var seg = activeSegments[si];
              var share = reg.weight * seg.weight;

              var bgtNoise = 1 + 0.02 * randNorm(rng);
              var qBgt = Math.max(1, Math.round(u.baseQ * share * trend * seas * bgtNoise));
              var pBgt = u.price * Math.pow(1.002, t) * (1 + (si === 0 ? 0.06 : si === 2 ? -0.07 : 0));
              var revBgt = qBgt * pBgt;

              var execShock = 1 + 0.05 * randNorm(rng);
              if (t === shockIdxPos && ui === 0) execShock *= 1.24;
              if (t === shockIdxNeg && ui === 1) execShock *= 0.80;

              var discPct = Math.max(0.01, Math.min(0.14, 0.042 + 0.018 * randNorm(rng) - (execShock - 1) * 0.10));
              var qReal = Math.max(1, Math.round(qBgt * execShock));
              var pGross = pBgt * (1 + 0.02 * randNorm(rng));
              var pNet = pGross * (1 - discPct);

              var revGross = qReal * pGross;
              var discountAmt = revGross - (qReal * pNet);
              var revReal = qReal * pNet;

              var cogsRateBgt = Math.max(0.12, u.cogsPct - seg.marginBonus * 0.5);
              var cogsRateReal = Math.max(0.12, cogsRateBgt * (1 + 0.018 * randNorm(rng)));
              var cogsBgt = revBgt * cogsRateBgt;
              var cogsReal = revReal * cogsRateReal;

              var mktSpend = revReal * (0.024 + 0.006 * Math.abs(randNorm(rng)));
              var opexBgt = revBgt * u.opexPct;
              var opexReal = revBgt * u.opexPct * 0.55 + revReal * u.opexPct * 0.45 * (1 + 0.025 * randNorm(rng));

              var ebitdaBgt = revBgt - cogsBgt - opexBgt;
              var ebitdaReal = revReal - cogsReal - opexReal;

              var taxCapex = Math.max(0, ebitdaReal * 0.24) + revReal * 0.026;
              var fcfReal = ebitdaReal - taxCapex;

              rows.push({
                year: String(yr),
                quarter: qtr,
                monthIdx: m,
                ym: ym,
                monthShort: MONTHS_SHORT[m] + ' ' + String(yr).slice(2),
                unit: u.name,
                region: reg.name,
                segment: seg.name,
                qty: qReal,
                qtyBgt: qBgt,
                price: pNet,
                priceBgt: pBgt,
                discPct: discPct,
                discountAmt: discountAmt,
                revGross: revGross,
                mktSpend: mktSpend,
                revReal: revReal,
                revBudget: revBgt,
                cogsReal: cogsReal,
                cogsBudget: cogsBgt,
                opexReal: opexReal,
                opexBudget: opexBgt,
                ebitdaReal: ebitdaReal,
                ebitdaBudget: ebitdaBgt,
                taxCapex: taxCapex,
                fcfReal: fcfReal
              });
            }
          }
        }
      }
    }
    state.records = rows;
    populateFilterDropdowns();
  }

  function uniqueVals(arr, key) {
    var set = {};
    arr.forEach(function (r) { if (r[key] != null) set[r[key]] = true; });
    return Object.keys(set);
  }

  function populateFilterDropdowns() {
    var recs = state.records;
    var years = uniqueVals(recs, 'year').sort();
    var regions = uniqueVals(recs, 'region');
    var segments = uniqueVals(recs, 'segment');
    var units = uniqueVals(recs, 'unit');

    fillSelect('selYear', 'Todos (' + (years[0] || '') + '–' + (years[years.length - 1] || '') + ')', years, state.filters.year);
    fillSelect('selRegion', 'Todas las Regiones', regions, state.filters.region);
    fillSelect('selSegment', 'Todos los Segmentos', segments, state.filters.segment);

    // Render clickable Business Unit Cross-Filter Pills
    var pillBox = document.getElementById('unitPills');
    if (pillBox) {
      var html = '<button type="button" class="nx-pill ' + (state.filters.unit === 'ALL' ? 'active' : '') + '" data-unit="ALL">Todas (' + units.length + ')</button>';
      units.forEach(function (u) {
        var act = state.filters.unit === u ? 'active' : '';
        html += '<button type="button" class="nx-pill ' + act + '" data-unit="' + esc(u) + '" title="' + esc(u) + '">' + esc(shortUnitLabel(u)) + '</button>';
      });
      pillBox.innerHTML = html;
      pillBox.querySelectorAll('.nx-pill').forEach(function (btn) {
        btn.addEventListener('click', function () {
          var val = btn.getAttribute('data-unit');
          state.filters.unit = (state.filters.unit === val && val !== 'ALL') ? 'ALL' : val;
          refreshAll();
        });
      });
    }

    var dsBadge = document.getElementById('activeDatasetLabel');
    if (dsBadge) {
      dsBadge.textContent = state.datasetKey === 'CUSTOM'
        ? ('CSV Local: ' + (state.customName || 'Dataset Usuario'))
        : ('Caso Paramétrico: ' + DATASETS_META[state.datasetKey].name);
    }
  }

  function fillSelect(id, allLabel, items, currentVal) {
    var el = document.getElementById(id);
    if (!el) return;
    if (currentVal !== 'ALL' && items.indexOf(currentVal) === -1) {
      currentVal = 'ALL';
    }
    var h = '<option value="ALL">' + esc(allLabel) + '</option>';
    items.forEach(function (it) {
      h += '<option value="' + esc(it) + '"' + (it === currentVal ? ' selected' : '') + '>' + esc(it) + '</option>';
    });
    el.innerHTML = h;
  }

  function getFilteredRecords(ignoreKey) {
    var f = state.filters;
    return state.records.filter(function (r) {
      if (ignoreKey !== 'year' && f.year !== 'ALL' && r.year !== f.year) return false;
      if (ignoreKey !== 'quarter' && f.quarter !== 'ALL' && r.quarter !== f.quarter) return false;
      if (ignoreKey !== 'region' && f.region !== 'ALL' && r.region !== f.region) return false;
      if (ignoreKey !== 'segment' && f.segment !== 'ALL' && r.segment !== f.segment) return false;
      if (ignoreKey !== 'unit' && f.unit !== 'ALL' && r.unit !== f.unit) return false;
      return true;
    });
  }

  function aggregateRecords(recs) {
    var s = {
      qty: 0, qtyBgt: 0, revGross: 0, discountAmt: 0, mktSpend: 0,
      revReal: 0, revBudget: 0, cogsReal: 0, cogsBudget: 0,
      opexReal: 0, opexBudget: 0, ebitdaReal: 0, ebitdaBudget: 0,
      taxCapex: 0, fcfReal: 0, n: recs.length
    };
    for (var i = 0; i < recs.length; i++) {
      var r = recs[i];
      s.qty += r.qty;
      s.qtyBgt += r.qtyBgt;
      s.revGross += r.revGross;
      s.discountAmt += r.discountAmt;
      s.mktSpend += r.mktSpend;
      s.revReal += r.revReal;
      s.revBudget += r.revBudget;
      s.cogsReal += r.cogsReal;
      s.cogsBudget += r.cogsBudget;
      s.opexReal += r.opexReal;
      s.opexBudget += r.opexBudget;
      s.ebitdaReal += r.ebitdaReal;
      s.ebitdaBudget += r.ebitdaBudget;
      s.taxCapex += r.taxCapex;
      s.fcfReal += r.fcfReal;
    }
    s.grossReal = s.revReal - s.cogsReal;
    s.grossBudget = s.revBudget - s.cogsBudget;
    s.grossMargin = s.revReal > 0 ? s.grossReal / s.revReal : 0;
    s.ebitdaMargin = s.revReal > 0 ? s.ebitdaReal / s.revReal : 0;
    s.fcfMargin = s.revReal > 0 ? s.fcfReal / s.revReal : 0;
    s.attainment = s.revBudget > 0 ? s.revReal / s.revBudget : 0;
    s.avgPrice = s.qty > 0 ? s.revReal / s.qty : 0;
    s.avgPriceBgt = s.qtyBgt > 0 ? s.revBudget / s.qtyBgt : 0;
    return s;
  }

  function groupByKey(recs, key) {
    var map = {};
    var order = [];
    recs.forEach(function (r) {
      var k = r[key] || 'N/A';
      if (!map[k]) {
        map[k] = [];
        order.push(k);
      }
      map[k].push(r);
    });
    return order.map(function (k) {
      var agg = aggregateRecords(map[k]);
      agg.key = k;
      return agg;
    });
  }

  // Robust Median & Z-MAD calculator
  function median(arr) {
    if (!arr.length) return 0;
    var s = arr.slice().sort(function (a, b) { return a - b; });
    var mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : 0.5 * (s[mid - 1] + s[mid]);
  }

  function computeZMadSeries(vals) {
    var med = median(vals);
    var absDevs = vals.map(function (v) { return Math.abs(v - med); });
    var mad = median(absDevs);
    var denom = Math.max(1.4826 * mad, Math.abs(med) * 0.04, 1e-6);
    return vals.map(function (v) { return (v - med) / denom; });
  }

  // ============================================================================
  // RENDER FILTER CHIPS & GLOBAL KPI STRIP
  // ============================================================================
  function renderActiveFilterChips(filteredCount) {
    var box = document.getElementById('activeFilterStrip');
    if (!box) return;
    var f = state.filters;
    var chips = [];
    if (f.year !== 'ALL') chips.push(['Año', f.year, 'year']);
    if (f.quarter !== 'ALL') chips.push(['Trim.', f.quarter, 'quarter']);
    if (f.unit !== 'ALL') chips.push(['Unidad', shortUnitLabel(f.unit), 'unit']);
    if (f.region !== 'ALL') chips.push(['Región', f.region, 'region']);
    if (f.segment !== 'ALL') chips.push(['Segm.', f.segment, 'segment']);

    if (chips.length > 0) {
      box.innerHTML = '<div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;">' +
        chips.map(function (c) {
          return '<span class="nx-filter-chip">' + esc(c[0]) + ': ' + esc(c[1]) + '</span>';
        }).join('') +
        '<span style="font-family:var(--font-mono);">(' + filteredCount.toLocaleString() + ' reg.)</span></div>' +
        '<button type="button" class="nx-reset-btn" id="btnClearFilters">' + SVG_ICONS.close + '<span>Limpiar Filtros</span></button>';
    } else {
      box.innerHTML = '<span style="font-family:var(--font-mono);">Registros: <strong>' + filteredCount.toLocaleString() + '</strong> &middot; <span style="color:var(--gold);">Sin filtros restrictivos (100%)</span></span>';
    }

    var btn = document.getElementById('btnClearFilters');
    if (btn) {
      btn.addEventListener('click', function () {
        state.filters = { year: 'ALL', quarter: 'ALL', region: 'ALL', segment: 'ALL', unit: 'ALL' };
        refreshAll();
        showToast('Filtros dimensionales restablecidos');
      });
    }

    // Sync dropdowns & pills
    ['selYear', 'selQuarter', 'selRegion', 'selSegment'].forEach(function (id) {
      var mapKey = id.replace('sel', '').toLowerCase();
      var el = document.getElementById(id);
      if (el && el.value !== state.filters[mapKey]) el.value = state.filters[mapKey];
    });
    document.querySelectorAll('#unitPills .nx-pill').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-unit') === state.filters.unit);
    });
  }

  function renderGlobalKpis(recs) {
    var agg = aggregateRecords(recs);
    var byMonth = groupByKey(recs, 'ym').sort(function (a, b) { return a.key.localeCompare(b.key); });
    var zSeries = computeZMadSeries(byMonth.map(function (m) { return m.revReal; }));
    var anomalies = zSeries.filter(function (z) { return Math.abs(z) > state.lab.zThresh; }).length;
    var pctInControl = byMonth.length > 0 ? ((byMonth.length - anomalies) / byMonth.length) : 1;

    var byUnitKpi = groupByKey(recs, 'unit');
    var hhi = Math.round(byUnitKpi.reduce(function (acc, u) {
      var s = agg.revReal > 0 ? u.revReal / agg.revReal : 0;
      return acc + s * s * 10000;
    }, 0));

    var gapRev = agg.revReal - agg.revBudget;
    var gapEbitda = agg.ebitdaReal - agg.ebitdaBudget;

    setKpi('kpiRevVal', fmtMoney(agg.revReal, true),
      '<span class="' + (gapRev >= 0 ? 'delta-pos' : 'delta-neg') + '">' + (gapRev >= 0 ? '+' : '') + fmtMoney(gapRev, true) + ' vs Ppto</span>' +
      '<span>Ppto: ' + fmtMoney(agg.revBudget, true) + '</span>');

    setKpi('kpiEbitdaVal', fmtMoney(agg.ebitdaReal, true),
      '<span class="' + (gapEbitda >= 0 ? 'delta-pos' : 'delta-neg') + '">Margen ' + fmtPct(agg.ebitdaMargin) + '</span>' +
      '<span>' + (gapEbitda >= 0 ? '+' : '') + fmtMoney(gapEbitda, true) + '</span>');

    setKpi('kpiFcfVal', fmtMoney(agg.fcfReal, true),
      '<span class="delta-pos">Conv. ' + fmtPct(agg.ebitdaReal > 0 ? agg.fcfReal / agg.ebitdaReal : 0) + '</span>' +
      '<span>FCF/Ing: ' + fmtPct(agg.fcfMargin) + '</span>');

    setKpi('kpiAttVal', fmtPct(agg.attainment),
      '<span class="' + (agg.attainment >= 1 ? 'delta-pos' : 'delta-neg') + '">' + (agg.attainment >= 1 ? 'Sobre Presupuesto' : 'Brecha Negativa') + '</span>' +
      '<span>Bruto: ' + fmtPct(agg.grossMargin) + '</span>');

    setKpi('kpiQtyVal', fmtNum(agg.qty),
      '<span class="delta-neu">Tarifa $/Q: $' + agg.avgPrice.toFixed(2) + '</span>' +
      '<span>vs ' + fmtNum(agg.qtyBgt) + '</span>');

    setKpi('kpiHealthVal', fmtPct(pctInControl),
      '<span class="' + (anomalies === 0 ? 'delta-pos' : 'delta-neu') + '">Atípicos |Z|&gt;' + state.lab.zThresh + ': ' + anomalies + '</span>' +
      '<span>HHI: ' + hhi + '</span>');
  }

  function setKpi(id, valTxt, subHtml) {
    var v = document.getElementById(id);
    var s = document.getElementById(id + 'Sub');
    if (v) v.textContent = valTxt;
    if (s) s.innerHTML = subHtml;
  }

  function baseLayout(pal, extra) {
    return Object.assign({
      paper_bgcolor: pal.paper,
      plot_bgcolor: pal.plot,
      font: { family: 'Plus Jakarta Sans, Inter, sans-serif', color: pal.sub, size: 11.5 },
      margin: { t: 38, r: 22, b: 44, l: 60 },
      hoverlabel: { bgcolor: pal.card, bordercolor: pal.goldBright, font: { color: pal.text, family: 'JetBrains Mono, monospace', size: 11 } },
      legend: { orientation: 'h', x: 0, y: 1.15, bgcolor: 'transparent', font: { color: pal.text, size: 11 } },
      xaxis: { gridcolor: pal.grid, zerolinecolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 }, automargin: true },
      yaxis: { gridcolor: pal.grid, zerolinecolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 }, automargin: true }
    }, extra || {});
  }

  var PLOT_CFG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] };

  function placeDeconflictedBubbleAnnotations(unitStats, xMin, xMax, yMin, yMax, pal) {
    var W = 520, H = 220;
    var items = unitStats.map(function (u) {
      var x = u.attainment * 100;
      var y = u.ebitdaMargin * 100;
      var px = ((x - xMin) / Math.max(0.01, xMax - xMin)) * W;
      var py = (1 - (y - yMin) / Math.max(0.01, yMax - yMin)) * H;
      return { u: u, x: x, y: y, px: px, py: py, lbl: shortUnitLabel(u.key) };
    }).sort(function (a, b) { return a.y - b.y; });

    var placedBoxes = [];
    var candidates = [
      { ax: 32, ay: -6, anchor: 'left' },
      { ax: -32, ay: -6, anchor: 'right' },
      { ax: 38, ay: -28, anchor: 'left' },
      { ax: -38, ay: -28, anchor: 'right' },
      { ax: 38, ay: 26, anchor: 'left' },
      { ax: -38, ay: 26, anchor: 'right' },
      { ax: 48, ay: -52, anchor: 'left' },
      { ax: -48, ay: -52, anchor: 'right' },
      { ax: 48, ay: 52, anchor: 'left' },
      { ax: -48, ay: 52, anchor: 'right' },
      { ax: 0, ay: -42, anchor: 'center' },
      { ax: 0, ay: 42, anchor: 'center' }
    ];

    return items.map(function (item) {
      var bw = item.lbl.length * 6.4 + 12;
      var bh = 18;
      var best = candidates[0];
      var bestScore = Infinity;

      for (var ci = 0; ci < candidates.length; ci++) {
        var c = candidates[ci];
        var tx = item.px + c.ax;
        var ty = item.py + c.ay;
        var left = c.anchor === 'left' ? tx : (c.anchor === 'right' ? tx - bw : tx - bw / 2);
        var right = left + bw;
        var top = ty - bh / 2;
        var bot = top + bh;

        var penalty = 0;
        if (left < 6) penalty += (6 - left) * 40;
        if (right > W - 6) penalty += (right - (W - 6)) * 40;
        if (top < 6) penalty += (6 - top) * 40;
        if (bot > H - 6) penalty += (bot - (H - 6)) * 40;

        for (var pi = 0; pi < placedBoxes.length; pi++) {
          var pb = placedBoxes[pi];
          var ox = Math.max(0, Math.min(right, pb.right) - Math.max(left, pb.left) + 6);
          var oy = Math.max(0, Math.min(bot, pb.bot) - Math.max(top, pb.top) + 4);
          if (ox > 0 && oy > 0) penalty += (ox * oy) + 1200;
        }
        for (var bi = 0; bi < items.length; bi++) {
          var other = items[bi];
          if (other.px >= left - 14 && other.px <= right + 14 && other.py >= top - 14 && other.py <= bot + 14) {
            penalty += 500;
          }
        }
        penalty += Math.abs(c.ax) * 0.25 + Math.abs(c.ay) * 0.35;
        if (penalty < bestScore) {
          bestScore = penalty;
          best = c;
        }
      }

      var ftx = item.px + best.ax;
      var fty = item.py + best.ay;
      var fLeft = best.anchor === 'left' ? ftx : (best.anchor === 'right' ? ftx - bw : ftx - bw / 2);
      placedBoxes.push({ left: fLeft, right: fLeft + bw, top: fty - bh / 2, bot: fty + bh / 2 });

      return {
        x: item.x,
        y: item.y,
        text: item.lbl,
        showarrow: true,
        arrowhead: 0,
        arrowwidth: 1,
        arrowcolor: pal.muted,
        ax: best.ax,
        ay: best.ay,
        xanchor: best.anchor,
        yanchor: 'middle',
        bgcolor: pal.paper,
        bordercolor: pal.grid,
        borderwidth: 1,
        borderpad: 2,
        font: { color: pal.text, size: 10.5 }
      };
    });
  }

  // ============================================================================
  // TAB 1: RESUMEN EJECUTIVO Y FILTRADO BIDIRECCIONAL
  // ============================================================================
  function renderTabBi(recs) {
    var pal = getPalette();

    // 1. Monthly Trend: Ingresos Real vs Ppto + EBITDA
    var byMo = groupByKey(recs, 'ym').sort(function (a, b) { return a.key.localeCompare(b.key); });
    var xMo = byMo.map(function (m) { return m.key; });
    var yRev = byMo.map(function (m) { return Math.round(m.revReal); });
    var yBgt = byMo.map(function (m) { return Math.round(m.revBudget); });
    var yEbitda = byMo.map(function (m) { return Math.round(m.ebitdaReal); });

    Plotly.react('cBiTrend', [
      { x: xMo, y: yBgt, name: 'Presupuesto ($)', type: 'scatter', mode: 'lines', line: { color: pal.muted, width: 2, dash: 'dot' } },
      { x: xMo, y: yRev, name: 'Ingresos Netos ($)', type: 'scatter', mode: 'lines+markers', line: { color: pal.sky, width: 2.6 }, marker: { size: 5, color: pal.sky }, fill: 'tozeroy', fillcolor: 'rgba(56,189,248,0.10)' },
      { x: xMo, y: yEbitda, name: 'EBITDA Operativo ($)', type: 'bar', marker: { color: pal.goldBright, opacity: 0.78 } }
    ], baseLayout(pal, {
      height: 315,
      barmode: 'overlay',
      margin: { t: 40, r: 18, b: 40, l: 60 },
      legend: { orientation: 'h', x: 0, y: 1.15, bgcolor: 'transparent', font: { color: pal.text, size: 11 } },
      xaxis: { nticks: 10, tickangle: 0, gridcolor: pal.grid, zerolinecolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 }, automargin: true },
      yaxis: { tickprefix: '$', gridcolor: pal.grid, zerolinecolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 }, automargin: true }
    }), PLOT_CFG);

    // 2. Business Units Ranking (Click bar -> Cross-Filter Unit)
    var recsForUnits = getFilteredRecords('unit');
    var byUnit = groupByKey(recsForUnits, 'unit').sort(function (a, b) { return a.revReal - b.revReal; });
    var uNames = byUnit.map(function (u) { return u.key; });
    var uShortNames = uNames.map(shortUnitLabel);
    var maxUnitX = Math.max.apply(null, byUnit.map(function (u) { return Math.max(u.revReal, u.revBudget); }).concat([1]));
    var uColors = uNames.map(function (nm) {
      if (state.filters.unit === 'ALL') return pal.sky;
      return state.filters.unit === nm ? pal.goldBright : 'rgba(148,163,184,0.32)';
    });

    var gdUnits = document.getElementById('cBiUnits');
    Plotly.react(gdUnits, [
      {
        y: uShortNames,
        customdata: uNames,
        x: byUnit.map(function (u) { return Math.round(u.revBudget); }),
        name: 'Presupuesto',
        type: 'bar',
        orientation: 'h',
        hovertemplate: '<b>%{customdata}</b><br>Presupuesto: $%{x:,.0f}<extra></extra>',
        marker: { color: 'rgba(148,163,184,0.28)' }
      },
      {
        y: uShortNames,
        customdata: uNames,
        x: byUnit.map(function (u) { return Math.round(u.revReal); }),
        name: 'Ejecución Real',
        type: 'bar',
        orientation: 'h',
        hovertemplate: '<b>%{customdata}</b><br>Ingreso Real: $%{x:,.0f} (%{text})<extra></extra>',
        marker: { color: uColors, line: { color: pal.goldBright, width: 1 } },
        text: byUnit.map(function (u) { return fmtPct(u.ebitdaMargin) + ' EBITDA'; }),
        textposition: 'outside',
        cliponaxis: false,
        textfont: { color: pal.text, size: 10.5, family: 'JetBrains Mono, monospace' }
      }
    ], baseLayout(pal, {
      height: 315,
      barmode: 'overlay',
      margin: { t: 44, r: 68, b: 36, l: 148 },
      legend: { orientation: 'h', x: -0.48, y: 1.14, bgcolor: 'transparent', font: { color: pal.text, size: 10.5 } },
      xaxis: { range: [0, maxUnitX * 1.28], tickprefix: '$', gridcolor: pal.grid, zerolinecolor: pal.grid, tickfont: { color: pal.sub, size: 10 }, automargin: true },
      yaxis: { gridcolor: pal.grid, tickfont: { color: pal.text, size: 10.5 }, automargin: false }
    }), PLOT_CFG);

    if (gdUnits && !gdUnits.__boundClick) {
      gdUnits.__boundClick = true;
      gdUnits.on('plotly_click', function (ev) {
        if (ev && ev.points && ev.points[0]) {
          var clickedUnit = ev.points[0].customdata || ev.points[0].y;
          state.filters.unit = (state.filters.unit === clickedUnit) ? 'ALL' : clickedUnit;
          refreshAll();
          showToast(state.filters.unit === 'ALL' ? 'Filtro por unidad restablecido' : ('Unidad seleccionada: ' + clickedUnit));
        }
      });
    }

    // 3. Regional & Segment Breakdown (Zero Label/Legend Overlap)
    var recsForReg = getFilteredRecords('region');
    var byReg = groupByKey(recsForReg, 'region').sort(function (a, b) { return b.revReal - a.revReal; });
    var totalRegRev = byReg.reduce(function (acc, r) { return acc + r.revReal; }, 0);
    var donutColors = state.theme === 'light'
      ? ['#0284c7', '#9a7432', '#059669', '#4f46e5']
      : ['#0ea5e9', '#B8955A', '#10b981', '#6366f1'];
    var gdReg = document.getElementById('cBiRegions');
    Plotly.react(gdReg, [
      {
        labels: byReg.map(function (r) { return r.key; }),
        values: byReg.map(function (r) { return Math.round(r.revReal); }),
        type: 'pie',
        domain: { x: [0.0, 0.52], y: [0.04, 0.96] },
        hole: 0.60,
        sort: false,
        marker: { colors: donutColors, line: { color: pal.paper, width: 2 } },
        textinfo: 'percent',
        textposition: 'inside',
        insidetextorientation: 'horizontal',
        textfont: { color: '#ffffff', size: 11.5, family: 'JetBrains Mono, monospace' },
        hovertemplate: '<b>%{label}</b><br>Ingresos: $%{value:,.0f} (%{percent})<extra></extra>',
        pull: byReg.map(function (r) { return state.filters.region === r.key ? 0.08 : 0; })
      }
    ], baseLayout(pal, {
      height: 315,
      showlegend: true,
      legend: { orientation: 'v', x: 0.56, y: 0.5, yanchor: 'middle', xanchor: 'left', bgcolor: 'transparent', font: { color: pal.text, size: 11 } },
      margin: { t: 20, r: 16, b: 20, l: 12 },
      annotations: [
        { x: 0.26, y: 0.54, text: '<b>' + fmtMoney(totalRegRev, true) + '</b>', showarrow: false, font: { color: pal.text, size: 14.5, family: 'JetBrains Mono, monospace' } },
        { x: 0.26, y: 0.43, text: 'Ingresos', showarrow: false, font: { color: pal.muted, size: 10.5 } }
      ]
    }), PLOT_CFG);

    if (gdReg && !gdReg.__boundClick) {
      gdReg.__boundClick = true;
      gdReg.on('plotly_click', function (ev) {
        if (ev && ev.points && ev.points[0] && ev.points[0].label) {
          var clickedReg = ev.points[0].label;
          state.filters.region = (state.filters.region === clickedReg) ? 'ALL' : clickedReg;
          refreshAll();
          showToast(state.filters.region === 'ALL' ? 'Filtro regional restablecido' : ('Región seleccionada: ' + clickedReg));
        }
      });
    }

    // 4. Strategic Quadrant Bubble Matrix (Deconflicted Callout Annotations)
    var unitStats = groupByKey(recsForUnits, 'unit');
    var totalUnitsAgg = aggregateRecords(recsForUnits);
    var avgMarginPct = +(totalUnitsAgg.ebitdaMargin * 100).toFixed(2);
    var maxRev = Math.max.apply(null, unitStats.map(function (u) { return u.revReal; }).concat([1]));
    var xs = unitStats.map(function (u) { return +(u.attainment * 100).toFixed(2); });
    var ys = unitStats.map(function (u) { return +(u.ebitdaMargin * 100).toFixed(2); });
    var xMin = Math.floor(Math.min.apply(null, xs.concat([95])) - 2.4);
    var xMax = Math.ceil(Math.max.apply(null, xs.concat([100.5])) + 2.4);
    var yMin = Math.max(0, Math.floor(Math.min.apply(null, ys.concat([8])) - 6));
    var yMax = Math.ceil(Math.max.apply(null, ys.concat([20])) + 7.5);
    var bubAnnots = placeDeconflictedBubbleAnnotations(unitStats, xMin, xMax, yMin, yMax, pal);

    var gdBub = document.getElementById('cBiBubble');
    Plotly.react(gdBub, [
      {
        x: xs,
        y: ys,
        customdata: unitStats.map(function (u) { return u.key; }),
        text: unitStats.map(function (u) { return fmtMoney(u.revReal, true); }),
        mode: 'markers',
        type: 'scatter',
        name: 'Unidades',
        hovertemplate: '<b>%{customdata}</b><br>Cumplimiento: %{x:.1f}%<br>Margen EBITDA: %{y:.1f}%<br>Ingresos: %{text}<extra></extra>',
        marker: {
          size: unitStats.map(function (u) { return Math.max(15, Math.round(36 * Math.sqrt(u.revReal / maxRev))); }),
          color: unitStats.map(function (u, i) {
            if (state.filters.unit !== 'ALL' && state.filters.unit !== u.key) return 'rgba(148,163,184,0.28)';
            return pal.series[i % pal.series.length];
          }),
          opacity: 0.90,
          line: { color: pal.goldBright, width: 1.6 }
        }
      }
    ], baseLayout(pal, {
      height: 315,
      showlegend: false,
      margin: { t: 24, r: 24, b: 46, l: 56 },
      xaxis: { title: 'Cumplimiento Presupuestario (%)', range: [xMin, xMax], gridcolor: pal.grid, zeroline: false, tickfont: { color: pal.sub, size: 10.5 } },
      yaxis: { title: 'Margen EBITDA (%)', range: [yMin, yMax], gridcolor: pal.grid, zeroline: false, tickfont: { color: pal.sub, size: 10.5 } },
      shapes: [
        { type: 'line', x0: 100, x1: 100, y0: 0, y1: 1, yref: 'paper', line: { color: pal.goldBright, width: 1.3, dash: 'dash' } },
        { type: 'line', x0: 0, x1: 1, xref: 'paper', y0: avgMarginPct, y1: avgMarginPct, line: { color: pal.muted, width: 1.1, dash: 'dot' } }
      ],
      annotations: bubAnnots
    }), PLOT_CFG);

    if (gdBub && !gdBub.__boundClick) {
      gdBub.__boundClick = true;
      gdBub.on('plotly_click', function (ev) {
        if (ev && ev.points && ev.points[0]) {
          var cu = ev.points[0].customdata;
          if (!cu) return;
          state.filters.unit = (state.filters.unit === cu) ? 'ALL' : cu;
          refreshAll();
          showToast(state.filters.unit === 'ALL' ? 'Filtro por unidad restablecido' : ('Unidad seleccionada: ' + cu));
        }
      });
    }

    renderBiTable(unitStats, totalUnitsAgg);
  }

  function renderBiTable(unitRows, totalAgg) {
    var col = state.tableSort.col;
    var dir = state.tableSort.asc ? 1 : -1;
    var sorted = unitRows.slice().sort(function (a, b) {
      if (col === 'key') return a.key.localeCompare(b.key) * dir;
      return ((a[col] || 0) - (b[col] || 0)) * dir;
    });

    var tbody = document.getElementById('tbBiUnits');
    var tfoot = document.getElementById('tfBiUnits');
    if (!tbody || !tfoot) return;

    var totalDQ = 0;
    var totalDP = 0;
    tbody.innerHTML = sorted.map(function (u) {
      var gap = u.revReal - u.revBudget;
      var dQ = (u.qty - u.qtyBgt) * u.avgPriceBgt;
      var dP = (u.avgPrice - u.avgPriceBgt) * u.qty;
      totalDQ += dQ;
      totalDP += dP;
      var share = totalAgg.revReal > 0 ? u.revReal / totalAgg.revReal : 0;
      var barCol = u.attainment >= 1 ? 'var(--emerald)' : (u.attainment >= 0.93 ? 'var(--gold)' : 'var(--rose)');
      var selCls = state.filters.unit === u.key ? 'selected-row' : '';
      return '<tr class="' + selCls + '" data-unit="' + esc(u.key) + '">' +
        '<td>' + esc(u.key) + '</td>' +
        '<td>' + fmtNum(u.qty) + '</td>' +
        '<td>$' + u.avgPrice.toFixed(2) + '</td>' +
        '<td>' + fmtMoney(u.revReal) + '</td>' +
        '<td>' + fmtMoney(u.revBudget) + '</td>' +
        '<td class="' + (gap >= 0 ? 'delta-pos' : 'delta-neg') + '">' + (gap >= 0 ? '+' : '') + fmtMoney(gap) + '</td>' +
        '<td><span class="nx-bar-mini"><span style="width:' + Math.min(100, Math.round(u.attainment * 100)) + '%;background:' + barCol + ';"></span></span>' + fmtPct(u.attainment) + '</td>' +
        '<td class="' + (dQ >= 0 ? 'delta-pos' : 'delta-neg') + '">' + fmtMoney(dQ, true) + '</td>' +
        '<td class="' + (dP >= 0 ? 'delta-pos' : 'delta-neg') + '">' + fmtMoney(dP, true) + '</td>' +
        '<td>' + fmtMoney(u.ebitdaReal) + '</td>' +
        '<td class="delta-pos">' + fmtPct(u.ebitdaMargin) + '</td>' +
        '<td>' + fmtMoney(u.fcfReal) + '</td>' +
        '<td>' + fmtPct(share) + '</td>' +
        '</tr>';
    }).join('');

    tbody.querySelectorAll('tr[data-unit]').forEach(function (tr) {
      tr.addEventListener('click', function () {
        var u = tr.getAttribute('data-unit');
        state.filters.unit = (state.filters.unit === u) ? 'ALL' : u;
        refreshAll();
      });
    });

    var tGap = totalAgg.revReal - totalAgg.revBudget;
    tfoot.innerHTML = '<tr>' +
      '<td>TOTAL CONSOLIDADO</td>' +
      '<td>' + fmtNum(totalAgg.qty) + '</td>' +
      '<td>$' + totalAgg.avgPrice.toFixed(2) + '</td>' +
      '<td>' + fmtMoney(totalAgg.revReal) + '</td>' +
      '<td>' + fmtMoney(totalAgg.revBudget) + '</td>' +
      '<td class="' + (tGap >= 0 ? 'delta-pos' : 'delta-neg') + '">' + (tGap >= 0 ? '+' : '') + fmtMoney(tGap) + '</td>' +
      '<td>' + fmtPct(totalAgg.attainment) + '</td>' +
      '<td class="' + (totalDQ >= 0 ? 'delta-pos' : 'delta-neg') + '">' + fmtMoney(totalDQ, true) + '</td>' +
      '<td class="' + (totalDP >= 0 ? 'delta-pos' : 'delta-neg') + '">' + fmtMoney(totalDP, true) + '</td>' +
      '<td>' + fmtMoney(totalAgg.ebitdaReal) + '</td>' +
      '<td>' + fmtPct(totalAgg.ebitdaMargin) + '</td>' +
      '<td>' + fmtMoney(totalAgg.fcfReal) + '</td>' +
      '<td>100.0%</td>' +
      '</tr>';
  }

  // ============================================================================
  // TAB 2: ESTADO DE RESULTADOS (P&G 4 NIVELES) & WATERFALL
  // ============================================================================
  function renderTabPnl(recs) {
    var pal = getPalette();
    var a = aggregateRecords(recs);

    // 1. P&L Structural 4-Level Waterfall
    Plotly.react('cPnlWaterfall', [{
      type: 'waterfall',
      orientation: 'v',
      measure: ['absolute', 'relative', 'total', 'relative', 'total', 'relative', 'total', 'relative', 'total'],
      x: ['Ingresos<br>Brutos', 'Descuentos<br>Com.', 'Ingresos<br>Netos', 'Costo<br>COGS', 'Utilidad<br>Bruta', 'Gastos<br>OPEX', 'EBITDA', 'Impuestos<br>& CAPEX', 'Flujo Caja<br>Libre'],
      y: [
        Math.round(a.revGross),
        -Math.round(a.discountAmt),
        0,
        -Math.round(a.cogsReal),
        0,
        -Math.round(a.opexReal),
        0,
        -Math.round(a.taxCapex),
        0
      ],
      text: [
        fmtMoney(a.revGross, true),
        fmtMoney(-a.discountAmt, true),
        fmtMoney(a.revReal, true),
        fmtMoney(-a.cogsReal, true),
        fmtMoney(a.grossReal, true),
        fmtMoney(-a.opexReal, true),
        fmtMoney(a.ebitdaReal, true),
        fmtMoney(-a.taxCapex, true),
        fmtMoney(a.fcfReal, true)
      ],
      textposition: 'outside',
      cliponaxis: false,
      textfont: { color: pal.text, size: 10, family: 'JetBrains Mono, monospace' },
      connector: { line: { color: pal.goldBright, width: 1.2, dash: 'dot' } },
      increasing: { marker: { color: pal.emerald } },
      decreasing: { marker: { color: pal.rose } },
      totals: { marker: { color: pal.sky, line: { color: pal.goldBright, width: 1.5 } } }
    }], baseLayout(pal, {
      height: 365,
      showlegend: false,
      margin: { t: 42, r: 20, b: 58, l: 64 },
      xaxis: { tickangle: 0, gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10 }, automargin: true },
      yaxis: { range: [0, a.revGross * 1.18], tickprefix: '$', gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 }, automargin: true }
    }), PLOT_CFG);

    // 2. EBITDA Variance Bridge (Ppto -> ΔVolumen -> ΔPrecio -> ΔCOGS -> ΔOPEX -> EBITDA Real)
    var dVol = (a.qty - a.qtyBgt) * a.avgPriceBgt;
    var dPrice = (a.revReal - a.revBudget) - dVol;
    var dCogs = -(a.cogsReal - a.cogsBudget);
    var dOpex = -(a.opexReal - a.opexBudget);
    var bridgeMax = Math.max(a.ebitdaBudget, a.ebitdaReal, a.ebitdaBudget + Math.max(0, dVol) + Math.max(0, dPrice)) * 1.18;

    Plotly.react('cPnlBridge', [{
      type: 'waterfall',
      orientation: 'v',
      measure: ['absolute', 'relative', 'relative', 'relative', 'relative', 'total'],
      x: ['EBITDA<br>Presupuesto', 'Efecto<br>Volumen (ΔQ)', 'Efecto<br>Tarifa (ΔP)', 'Variación<br>COGS', 'Variación<br>OPEX', 'EBITDA<br>Real'],
      y: [
        Math.round(a.ebitdaBudget),
        Math.round(dVol),
        Math.round(dPrice),
        Math.round(dCogs),
        Math.round(dOpex),
        0
      ],
      text: [
        fmtMoney(a.ebitdaBudget, true),
        (dVol >= 0 ? '+' : '') + fmtMoney(dVol, true),
        (dPrice >= 0 ? '+' : '') + fmtMoney(dPrice, true),
        (dCogs >= 0 ? '+' : '') + fmtMoney(dCogs, true),
        (dOpex >= 0 ? '+' : '') + fmtMoney(dOpex, true),
        fmtMoney(a.ebitdaReal, true)
      ],
      textposition: 'outside',
      cliponaxis: false,
      textfont: { color: pal.text, size: 10, family: 'JetBrains Mono, monospace' },
      connector: { line: { color: pal.goldBright, width: 1.2 } },
      increasing: { marker: { color: pal.emerald } },
      decreasing: { marker: { color: pal.rose } },
      totals: { marker: { color: pal.goldBright } }
    }], baseLayout(pal, {
      height: 365,
      showlegend: false,
      margin: { t: 42, r: 20, b: 58, l: 64 },
      xaxis: { tickangle: 0, gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10 }, automargin: true },
      yaxis: { range: [0, Math.max(10, bridgeMax)], tickprefix: '$', gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 }, automargin: true }
    }), PLOT_CFG);

    // 3. 4-Level Corporate P&L Matrix
    var rows = [
      { lvl: 1, sub: false, name: '(+) Facturación Bruta Comercial', real: a.revGross, bgt: a.revBudget * 1.065 },
      { lvl: 1, sub: false, name: '(-) Descuentos, Bonificaciones & Rebates', real: -a.discountAmt, bgt: -a.revBudget * 0.065 },
      { lvl: 1, sub: true, name: '(=) NIVEL 1 · INGRESOS OPERATIVOS NETOS', real: a.revReal, bgt: a.revBudget },
      { lvl: 2, sub: false, name: '(-) Costo Directo de Ventas / Servicios (COGS)', real: -a.cogsReal, bgt: -a.cogsBudget },
      { lvl: 2, sub: true, name: '(=) NIVEL 2 · UTILIDAD BRUTA (GROSS PROFIT)', real: a.grossReal, bgt: a.grossBudget },
      { lvl: 3, sub: false, name: '(-) Inversión Comercial, Marketing & Adquisición', real: -a.mktSpend, bgt: -a.opexBudget * 0.30 },
      { lvl: 3, sub: false, name: '(-) Gastos Operativos I+D, Tecnología & Administración (SG&A)', real: -(a.opexReal - a.mktSpend), bgt: -a.opexBudget * 0.70 },
      { lvl: 3, sub: true, name: '(=) NIVEL 3 · EBITDA OPERATIVO', real: a.ebitdaReal, bgt: a.ebitdaBudget },
      { lvl: 4, sub: false, name: '(-) Impuesto Corporativo Estimado & CAPEX de Mantenimiento', real: -a.taxCapex, bgt: -(Math.max(0, a.ebitdaBudget * 0.24) + a.revBudget * 0.026) },
      { lvl: 4, sub: true, name: '(=) NIVEL 4 · FLUJO DE CAJA LIBRE (FREE CASH FLOW)', real: a.fcfReal, bgt: a.ebitdaBudget - (Math.max(0, a.ebitdaBudget * 0.24) + a.revBudget * 0.026) }
    ];

    var tb = document.getElementById('tbPnl4Levels');
    if (tb) {
      tb.innerHTML = rows.map(function (r) {
        var diff = r.real - r.bgt;
        var diffPct = Math.abs(r.bgt) > 1 ? diff / Math.abs(r.bgt) : 0;
        var vPct = a.revReal > 0 ? r.real / a.revReal : 0;
        var cls = r.sub ? 'pnl-subtotal' : '';
        var dCls = diff >= 0 ? 'delta-pos' : 'delta-neg';
        return '<tr class="' + cls + '">' +
          '<td>' + esc(r.name) + '</td>' +
          '<td>' + fmtMoney(r.real) + '</td>' +
          '<td>' + fmtPct(vPct) + '</td>' +
          '<td>' + fmtMoney(r.bgt) + '</td>' +
          '<td class="' + dCls + '">' + (diff >= 0 ? '+' : '') + fmtMoney(diff) + '</td>' +
          '<td class="' + dCls + '">' + fmtPct(diffPct, true) + '</td>' +
          '</tr>';
      }).join('');
    }
  }

  // ============================================================================
  // TAB 3: LABORATORIO DE DATA ANALYTICS, FORECASTING & CORRELACIÓN
  // ============================================================================
  function renderTabAnalytics(recs) {
    var pal = getPalette();
    var metric = state.lab.metric;
    var horizon = Number(state.lab.horizon) || 12;
    var ci = Number(state.lab.ci) || 0.95;
    var zCrit = ci >= 0.94 ? 1.96 : (ci >= 0.89 ? 1.645 : 1.282);

    var byMo = groupByKey(recs, 'ym').sort(function (a, b) { return a.key.localeCompare(b.key); });
    if (byMo.length < 4) return;

    var yHist = byMo.map(function (m) { return m[metric]; });
    var xHist = byMo.map(function (m) { return m.key; });
    var n = yHist.length;

    // Holt-Winters Additive Seasonal Smoothing (L = 12 if n >= 24 else Damped Holt)
    var L = 12;
    var fitted = [];
    var fcVals = [];
    if (n >= 24) {
      var alpha = 0.42, beta = 0.14, gamma = 0.35;
      var seasonals = [];
      var firstYearAvg = yHist.slice(0, L).reduce(function (a, b) { return a + b; }, 0) / L;
      for (var i = 0; i < L; i++) seasonals[i] = yHist[i] - firstYearAvg;
      var level = firstYearAvg;
      var trend = (yHist[L] - yHist[0]) / L;
      for (var t = 0; t < n; t++) {
        var val = yHist[t];
        var sPrev = seasonals[t % L];
        var pred = level + trend + sPrev;
        fitted.push(pred);
        var lastLevel = level;
        level = alpha * (val - sPrev) + (1 - alpha) * (level + trend);
        trend = beta * (level - lastLevel) + (1 - beta) * trend;
        seasonals[t % L] = gamma * (val - level) + (1 - gamma) * sPrev;
      }
      for (var h = 1; h <= horizon; h++) {
        fcVals.push(Math.max(0, level + h * trend * Math.pow(0.96, h) + seasonals[(n + h - 1) % L]));
      }
    } else {
      var lvl = yHist[0], trd = (yHist[n - 1] - yHist[0]) / Math.max(1, n - 1);
      for (var k = 0; k < n; k++) {
        var p0 = lvl + trd;
        fitted.push(p0);
        var prevL = lvl;
        lvl = 0.5 * yHist[k] + 0.5 * (lvl + trd);
        trd = 0.2 * (lvl - prevL) + 0.8 * trd;
      }
      for (var hh = 1; hh <= horizon; hh++) fcVals.push(Math.max(0, lvl + hh * trd));
    }

    // Compute Forecast Accuracy Metrics & Residuals
    var sqErr = 0, absPct = 0, meanY = yHist.reduce(function (a, b) { return a + b; }, 0) / n, ssTot = 0;
    var residuals = [];
    for (var j = 0; j < n; j++) {
      var err = yHist[j] - fitted[j];
      residuals.push(err);
      sqErr += err * err;
      absPct += Math.abs(err) / Math.max(1, Math.abs(yHist[j]));
      ssTot += (yHist[j] - meanY) * (yHist[j] - meanY);
    }
    var rmse = Math.sqrt(sqErr / n);
    var mape = absPct / n;
    var r2 = Math.max(0, 1 - sqErr / Math.max(1, ssTot));

    // Future month labels
    var lastYm = xHist[n - 1].split('-');
    var baseYr = parseInt(lastYm[0], 10) || 2026;
    var baseMo = parseInt(lastYm[1], 10) || 12;
    var xFut = [xHist[n - 1]];
    var yFutMid = [yHist[n - 1]];
    var yFutUp = [yHist[n - 1]];
    var yFutLo = [yHist[n - 1]];

    for (var fIdx = 1; fIdx <= horizon; fIdx++) {
      var totalM = (baseMo - 1) + fIdx;
      var ny = baseYr + Math.floor(totalM / 12);
      var nm = (totalM % 12) + 1;
      xFut.push(ny + '-' + (nm < 10 ? '0' + nm : nm));
      var spread = zCrit * rmse * Math.sqrt(1 + 0.22 * fIdx);
      yFutMid.push(fcVals[fIdx - 1]);
      yFutUp.push(fcVals[fIdx - 1] + spread);
      yFutLo.push(Math.max(0, fcVals[fIdx - 1] - spread));
    }

    // Z-MAD Anomalies on Detrended Residuals
    var zScores = computeZMadSeries(residuals);
    var anomX = [], anomY = [], anomTxt = [];
    zScores.forEach(function (z, idx) {
      if (Math.abs(z) > state.lab.zThresh) {
        anomX.push(xHist[idx]);
        anomY.push(yHist[idx]);
        anomTxt.push('Z-MAD = ' + z.toFixed(2));
      }
    });

    var labStatsEl = document.getElementById('labModelStats');
    if (labStatsEl) {
      labStatsEl.textContent = 'MAPE: ' + (mape * 100).toFixed(2) + '%  ·  R² Ajuste: ' + (r2 * 100).toFixed(1) + '%  ·  RMSE: ' + fmtNum(rmse) + '  ·  Anomalías |Z|>' + state.lab.zThresh + ': ' + anomX.length;
    }

    Plotly.react('cLabForecast', [
      {
        x: xFut.concat(xFut.slice().reverse()),
        y: yFutUp.concat(yFutLo.slice().reverse()),
        fill: 'toself',
        fillcolor: 'rgba(184, 149, 90, 0.20)',
        line: { color: 'transparent' },
        name: 'Banda IC ' + Math.round(ci * 100) + '%',
        hoverinfo: 'skip',
        type: 'scatter'
      },
      { x: xHist, y: yHist, name: 'Serie Observada', type: 'scatter', mode: 'lines+markers', line: { color: pal.sky, width: 2.5 }, marker: { size: 5 } },
      { x: xHist, y: fitted, name: 'Ajuste Holt-Winters', type: 'scatter', mode: 'lines', line: { color: pal.emerald, width: 1.6, dash: 'dot' } },
      { x: xFut, y: yFutMid, name: 'Pronóstico (+' + horizon + 'm)', type: 'scatter', mode: 'lines+markers', line: { color: pal.goldBright, width: 2.8 }, marker: { size: 5.5, color: pal.goldBright } },
      { x: anomX, y: anomY, text: anomTxt, name: 'Anomalías Z-MAD', type: 'scatter', mode: 'markers', marker: { symbol: 'diamond', size: 11, color: pal.rose, line: { color: '#ffffff', width: 1.5 } } }
    ], baseLayout(pal, { height: 360, margin: { t: 42, r: 20, b: 44, l: 64 }, legend: { orientation: 'h', x: 0, y: 1.14, bgcolor: 'transparent', font: { color: pal.text, size: 11 } } }), PLOT_CFG);

    // 2. Pearson Correlation Matrix 6x6 across Monthly Observations
    var corrLabels = ['Volumen Q', 'Tarifa $/Q', 'Descuento %', 'Marketing $', 'Ingresos $', 'EBITDA $'];
    var vectors = [
      byMo.map(function (m) { return m.qty; }),
      byMo.map(function (m) { return m.avgPrice; }),
      byMo.map(function (m) { return m.revGross > 0 ? m.discountAmt / m.revGross : 0; }),
      byMo.map(function (m) { return m.mktSpend; }),
      byMo.map(function (m) { return m.revReal; }),
      byMo.map(function (m) { return m.ebitdaReal; })
    ];

    function pearson(a, b) {
      var ma = a.reduce(function (s, v) { return s + v; }, 0) / a.length;
      var mb = b.reduce(function (s, v) { return s + v; }, 0) / b.length;
      var num = 0, da = 0, db = 0;
      for (var ii = 0; ii < a.length; ii++) {
        var xa = a[ii] - ma, xb = b[ii] - mb;
        num += xa * xb; da += xa * xa; db += xb * xb;
      }
      return (da > 0 && db > 0) ? +(num / Math.sqrt(da * db)).toFixed(2) : 0;
    }

    var zMat = [];
    var annots = [];
    for (var r = 0; r < corrLabels.length; r++) {
      var row = [];
      for (var c = 0; c < corrLabels.length; c++) {
        var valR = pearson(vectors[r], vectors[c]);
        row.push(valR);
        annots.push({
          x: corrLabels[c], y: corrLabels[r], text: valR.toFixed(2),
          showarrow: false, font: { color: Math.abs(valR) > 0.55 ? '#0B1B33' : pal.text, family: 'JetBrains Mono, monospace', size: 11 }
        });
      }
      zMat.push(row);
    }

    Plotly.react('cLabCorr', [{
      z: zMat, x: corrLabels, y: corrLabels, type: 'heatmap', zmin: -1, zmax: 1,
      colorbar: { tickfont: { color: pal.sub, size: 10 }, thickness: 12 },
      colorscale: [[0, '#f43f5e'], [0.5, pal.plot], [0.78, '#38bdf8'], [1, '#B8955A']]
    }], baseLayout(pal, { height: 340, annotations: annots, margin: { t: 28, r: 20, b: 64, l: 96 } }), PLOT_CFG);

    // 3. OLS Regression: Operating Leverage (Ingresos Mensuales -> EBITDA Mensual)
    var xReg = vectors[4];
    var yReg = vectors[5];
    var mx = xReg.reduce(function (s, v) { return s + v; }, 0) / xReg.length;
    var my = yReg.reduce(function (s, v) { return s + v; }, 0) / yReg.length;
    var covXY = 0, varX = 0;
    for (var qi = 0; qi < xReg.length; qi++) {
      covXY += (xReg[qi] - mx) * (yReg[qi] - my);
      varX += (xReg[qi] - mx) * (xReg[qi] - mx);
    }
    var slope = varX > 0 ? covXY / varX : 0;
    var intercept = my - slope * mx;
    var rOls = pearson(xReg, yReg);
    var xMin = Math.min.apply(null, xReg), xMax = Math.max.apply(null, xReg);

    var regSub = document.getElementById('labOlsFormula');
    if (regSub) {
      regSub.textContent = 'EBITDA = ' + fmtMoney(intercept, true) + ' + ' + slope.toFixed(3) + ' × Ingresos  |  R² = ' + (rOls * rOls * 100).toFixed(1) + '%';
    }

    Plotly.react('cLabReg', [
      {
        x: xReg, y: yReg, text: xHist, mode: 'markers', type: 'scatter', name: 'Observaciones Mensuales',
        marker: { size: 9, color: pal.sky, opacity: 0.85, line: { color: pal.goldBright, width: 1 } }
      },
      {
        x: [xMin, xMax], y: [intercept + slope * xMin, intercept + slope * xMax],
        mode: 'lines', type: 'scatter', name: 'Recta MCO (β₁ = ' + slope.toFixed(2) + ')',
        line: { color: pal.goldBright, width: 2.8 }
      }
    ], baseLayout(pal, {
      height: 340,
      margin: { t: 40, r: 22, b: 48, l: 64 },
      legend: { orientation: 'h', x: 0, y: 1.15, bgcolor: 'transparent', font: { color: pal.text, size: 11 } },
      xaxis: { title: 'Ingresos Netos Mensuales ($)', tickprefix: '$', gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 } },
      yaxis: { title: 'EBITDA Mensual ($)', tickprefix: '$', gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 } }
    }), PLOT_CFG);
  }

  // ============================================================================
  // TAB 4: ANÁLISIS DE SENSIBILIDAD, TORNADO & MONTE CARLO (2,000 ITERACIONES)
  // ============================================================================
  function evalScenario(baseAgg, dQ, dP, elast, dCogs, dOpex, waccPct, nMonths) {
    // Demand elasticity response to price change: Q_eff = Q * (1 + dQ) * (1 + elast * dP)
    var qMult = Math.max(0.2, (1 + dQ) * (1 + elast * dP));
    var pMult = Math.max(0.2, 1 + dP);
    var simRev = baseAgg.revReal * qMult * pMult;
    var simCogs = baseAgg.cogsReal * qMult * (1 + dCogs);
    var simOpex = baseAgg.opexReal * (1 + dOpex);
    var simEbitda = simRev - simCogs - simOpex;
    var simTaxCapex = Math.max(0, simEbitda * 0.24) + simRev * 0.026;
    var simFcf = simEbitda - simTaxCapex;

    // Annualize FCF based on distinct months in filtered slice and compute 5Y Operating NPV
    var wacc = Math.max(0.03, waccPct / 100);
    var annualFcf = simFcf * (12 / Math.max(1, nMonths || 12));
    var npv5y = 0;
    for (var yr = 1; yr <= 5; yr++) {
      npv5y += (annualFcf * Math.pow(1.04, yr - 1)) / Math.pow(1 + wacc, yr);
    }
    return {
      rev: simRev,
      ebitda: simEbitda,
      margin: simRev > 0 ? simEbitda / simRev : 0,
      fcf: simFcf,
      npv5y: npv5y
    };
  }

  function renderTabWhatIf(recs) {
    var pal = getPalette();
    var base = aggregateRecords(recs);
    var nMonths = Math.max(1, groupByKey(recs, 'ym').length);
    var w = state.whatIf;

    var sim = evalScenario(base, w.dQ / 100, w.dP / 100, w.elast, w.dCogs / 100, w.dOpex / 100, w.wacc, nMonths);
    var dEb = sim.ebitda - base.ebitdaReal;

    // 1. Monte Carlo Stochastic Simulation (2,000 iterations) around simulated scenario
    var rng = createRng(987654 + Math.round((w.dQ + w.dP * 3 + w.dCogs * 5 + w.dOpex * 7) * 100));
    var N_SIM = 2000;
    var mcEbitda = new Array(N_SIM);
    var beatTarget = 0;
    for (var i = 0; i < N_SIM; i++) {
      var sQ = (w.dQ / 100) + 0.085 * randNorm(rng);
      var sP = (w.dP / 100) + 0.042 * randNorm(rng);
      var sC = (w.dCogs / 100) + 0.048 * randNorm(rng);
      var sO = (w.dOpex / 100) + 0.038 * randNorm(rng);
      var rSim = evalScenario(base, sQ, sP, w.elast, sC, sO, w.wacc, nMonths);
      mcEbitda[i] = rSim.ebitda;
      if (rSim.ebitda >= base.ebitdaBudget) beatTarget++;
    }
    mcEbitda.sort(function (a, b) { return a - b; });
    var p05 = mcEbitda[Math.floor(0.05 * N_SIM)]; // VaR 95%
    var cvar95 = mcEbitda.slice(0, Math.floor(0.05 * N_SIM)).reduce(function (a, b) { return a + b; }, 0) / Math.max(1, Math.floor(0.05 * N_SIM));
    var p50 = mcEbitda[Math.floor(0.50 * N_SIM)];
    var p90 = mcEbitda[Math.floor(0.90 * N_SIM)];
    var probBeat = beatTarget / N_SIM;

    // Update Simulated KPIs strip
    setKpi('simKpiRev', fmtMoney(sim.rev, true), '<span class="' + (sim.rev >= base.revReal ? 'delta-pos' : 'delta-neg') + '">Base: ' + fmtMoney(base.revReal, true) + '</span>');
    setKpi('simKpiEbitda', fmtMoney(sim.ebitda, true), '<span class="' + (dEb >= 0 ? 'delta-pos' : 'delta-neg') + '">' + (dEb >= 0 ? '+' : '') + fmtMoney(dEb, true) + ' (' + fmtPct(sim.margin) + ')</span>');
    setKpi('simKpiNpv', fmtMoney(sim.npv5y, true), '<span class="delta-neu">WACC ' + w.wacc.toFixed(1) + '% &middot; Base Anual (' + nMonths + 'M)</span>');
    setKpi('simKpiVar', fmtMoney(p05, true), '<span class="delta-neg">CVaR 95%: ' + fmtMoney(cvar95, true) + '</span>');
    setKpi('simKpiProb', fmtPct(probBeat), '<span class="' + (probBeat >= 0.5 ? 'delta-pos' : 'delta-neg') + '">vs Ppto (' + fmtMoney(base.ebitdaBudget, true) + ')</span>');

    // 2. Tornado Chart (±10% swing sensitivity around current state)
    var levers = [
      { label: 'Precio / Tarifa (±10%)', lo: evalScenario(base, w.dQ / 100, w.dP / 100 - 0.10, w.elast, w.dCogs / 100, w.dOpex / 100, w.wacc, nMonths).ebitda - sim.ebitda, hi: evalScenario(base, w.dQ / 100, w.dP / 100 + 0.10, w.elast, w.dCogs / 100, w.dOpex / 100, w.wacc, nMonths).ebitda - sim.ebitda },
      { label: 'Volumen Q (±10%)', lo: evalScenario(base, w.dQ / 100 - 0.10, w.dP / 100, w.elast, w.dCogs / 100, w.dOpex / 100, w.wacc, nMonths).ebitda - sim.ebitda, hi: evalScenario(base, w.dQ / 100 + 0.10, w.dP / 100, w.elast, w.dCogs / 100, w.dOpex / 100, w.wacc, nMonths).ebitda - sim.ebitda },
      { label: 'Costo Directo COGS (∓10%)', lo: evalScenario(base, w.dQ / 100, w.dP / 100, w.elast, w.dCogs / 100 + 0.10, w.dOpex / 100, w.wacc, nMonths).ebitda - sim.ebitda, hi: evalScenario(base, w.dQ / 100, w.dP / 100, w.elast, w.dCogs / 100 - 0.10, w.dOpex / 100, w.wacc, nMonths).ebitda - sim.ebitda },
      { label: 'Gastos OPEX (∓10%)', lo: evalScenario(base, w.dQ / 100, w.dP / 100, w.elast, w.dCogs / 100, w.dOpex / 100 + 0.10, w.wacc, nMonths).ebitda - sim.ebitda, hi: evalScenario(base, w.dQ / 100, w.dP / 100, w.elast, w.dCogs / 100, w.dOpex / 100 - 0.10, w.wacc, nMonths).ebitda - sim.ebitda }
    ].sort(function (a, b) { return (Math.abs(a.hi - a.lo)) - (Math.abs(b.hi - b.lo)); });

    Plotly.react('cSimTornado', [
      { y: levers.map(function (l) { return l.label; }), x: levers.map(function (l) { return Math.round(l.lo); }), name: 'Escenario Adverso', type: 'bar', orientation: 'h', marker: { color: pal.rose } },
      { y: levers.map(function (l) { return l.label; }), x: levers.map(function (l) { return Math.round(l.hi); }), name: 'Escenario Favorable', type: 'bar', orientation: 'h', marker: { color: pal.emerald } }
    ], baseLayout(pal, { height: 310, barmode: 'relative', margin: { t: 40, r: 24, b: 44, l: 165 }, legend: { orientation: 'h', x: 0, y: 1.15, bgcolor: 'transparent', font: { color: pal.text, size: 11 } } }), PLOT_CFG);

    // 3. Monte Carlo Distribution Histogram
    Plotly.react('cSimMonteCarlo', [
      {
        x: mcEbitda,
        type: 'histogram',
        nbinsx: 38,
        name: '2,000 Trayectorias EBITDA',
        marker: { color: 'rgba(56, 189, 248, 0.65)', line: { color: pal.sky, width: 1 } }
      }
    ], baseLayout(pal, {
      height: 310,
      showlegend: false,
      margin: { t: 40, r: 24, b: 48, l: 58 },
      xaxis: { title: 'EBITDA Simulado ($)', tickprefix: '$', gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 } },
      yaxis: { title: 'Frecuencia', gridcolor: pal.grid, tickfont: { color: pal.sub, size: 10.5 } },
      shapes: [
        { type: 'line', x0: p05, x1: p05, y0: 0, y1: 1, yref: 'paper', line: { color: pal.rose, width: 2.2, dash: 'dash' } },
        { type: 'line', x0: p50, x1: p50, y0: 0, y1: 1, yref: 'paper', line: { color: pal.goldBright, width: 2.6 } },
        { type: 'line', x0: p90, x1: p90, y0: 0, y1: 1, yref: 'paper', line: { color: pal.emerald, width: 2.2, dash: 'dot' } }
      ],
      annotations: [
        { x: p05, y: 0.96, yref: 'paper', text: 'VaR 95%: ' + fmtMoney(p05, true), showarrow: false, xanchor: 'right', bgcolor: pal.paper, borderpad: 2, font: { color: pal.rose, size: 10.5 } },
        { x: p50, y: 0.84, yref: 'paper', text: 'P50: ' + fmtMoney(p50, true), showarrow: false, bgcolor: pal.paper, borderpad: 2, font: { color: pal.goldBright, size: 11 } },
        { x: p90, y: 0.96, yref: 'paper', text: 'P90: ' + fmtMoney(p90, true), showarrow: false, xanchor: 'left', bgcolor: pal.paper, borderpad: 2, font: { color: pal.emerald, size: 10.5 } }
      ]
    }), PLOT_CFG);
  }

  // ============================================================================
  // TAB 5: TABLA DINÁMICA (PIVOT EXPLORER) & CARGA SEGURA DE CSV/JSON PROPIO
  // ============================================================================
  function renderTabExplorer(recs) {
    var grpKey = state.pivot.groupBy;
    var q = (state.pivot.search || '').trim().toLowerCase();
    var groups = groupByKey(recs, grpKey);
    var totalRev = groups.reduce(function (s, g) { return s + g.revReal; }, 0);

    // Compute Pareto cumulative % sorted by revReal desc first
    var byRevDesc = groups.slice().sort(function (a, b) { return b.revReal - a.revReal; });
    var cum = 0;
    var paretoMap = {};
    byRevDesc.forEach(function (g) {
      cum += totalRev > 0 ? g.revReal / totalRev : 0;
      paretoMap[g.key] = cum;
    });

    if (q) {
      groups = groups.filter(function (g) { return String(g.key).toLowerCase().indexOf(q) !== -1; });
    }

    var col = state.pivotSort.col;
    var dir = state.pivotSort.asc ? 1 : -1;
    groups.sort(function (a, b) {
      if (col === 'key') return String(a.key).localeCompare(String(b.key)) * dir;
      return ((a[col] || 0) - (b[col] || 0)) * dir;
    });

    var tb = document.getElementById('tbPivot');
    if (!tb) return;
    tb.innerHTML = groups.map(function (g) {
      var share = totalRev > 0 ? g.revReal / totalRev : 0;
      var par = paretoMap[g.key] || 0;
      var parClass = par <= 0.805 ? 'delta-pos' : 'delta-neu';
      return '<tr>' +
        '<td>' + esc(g.key) + '</td>' +
        '<td>' + g.n.toLocaleString() + '</td>' +
        '<td>' + fmtNum(g.qty) + '</td>' +
        '<td>' + fmtMoney(g.revReal) + '</td>' +
        '<td>' + fmtMoney(g.revBudget) + '</td>' +
        '<td class="' + (g.attainment >= 1 ? 'delta-pos' : 'delta-neg') + '">' + fmtPct(g.attainment) + '</td>' +
        '<td>' + fmtMoney(g.ebitdaReal) + '</td>' +
        '<td>' + fmtPct(g.ebitdaMargin) + '</td>' +
        '<td>' + fmtMoney(g.fcfReal) + '</td>' +
        '<td>' + fmtPct(share) + '</td>' +
        '<td class="' + parClass + '">' + fmtPct(par) + (par <= 0.805 ? ' (Top 80%)' : '') + '</td>' +
        '</tr>';
    }).join('');
  }

  // RFC-4180 CSV parser (100% client-side, safe string handling)
  function parseCsvText(text) {
    var lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(function (l) { return l.trim().length > 0; });
    if (lines.length < 2) return null;
    var sep = (lines[0].split(';').length > lines[0].split(',').length) ? ';' : ',';

    function splitLine(line) {
      var out = [], cur = '', inQ = false;
      for (var i = 0; i < line.length; i++) {
        var ch = line[i];
        if (ch === '"') {
          if (inQ && line[i + 1] === '"') { cur += '"'; i++; }
          else { inQ = !inQ; }
        } else if (ch === sep && !inQ) {
          out.push(cur.trim()); cur = '';
        } else {
          cur += ch;
        }
      }
      out.push(cur.trim());
      return out;
    }

    var headers = splitLine(lines[0]).map(function (h, idx) { return h || ('Col_' + (idx + 1)); });
    var rows = [];
    var maxRows = Math.min(lines.length, 15000);
    for (var r = 1; r < maxRows; r++) {
      var cells = splitLine(lines[r]);
      if (cells.length === 1 && !cells[0]) continue;
      var obj = {};
      headers.forEach(function (h, idx) { obj[h] = cells[idx] !== undefined ? cells[idx] : ''; });
      rows.push(obj);
    }
    return { headers: headers, rows: rows };
  }

  function cleanNum(val, fallback) {
    if (typeof val === 'number') return isFinite(val) ? val : fallback;
    var s = String(val || '').replace(/[$€%\s,]/g, '');
    var n = parseFloat(s);
    return isFinite(n) ? n : fallback;
  }

  function openCsvMapper(headers, rows, fileName) {
    state.rawCsvHeaders = headers;
    state.rawCsvRows = rows;
    state.customName = String(fileName || 'Dataset.csv').slice(0, 48);

    var box = document.getElementById('csvMapperBox');
    if (!box) return;
    box.style.display = 'grid';

    function guessCol(regex, defIdx) {
      var found = headers.find(function (h) { return regex.test(h); });
      return found || headers[Math.min(defIdx, headers.length - 1)];
    }

    var mapDefs = [
      { id: 'mapDate', label: 'Columna Fecha / Mes (YYYY-MM)', guess: guessCol(/fecha|date|mes|month|periodo|ym/i, 0) },
      { id: 'mapUnit', label: 'Dimensión Principal (Unidad / Categoría)', guess: guessCol(/unidad|linea|categoria|producto|unit|line/i, 1) },
      { id: 'mapRegion', label: 'Dimensión Región / Canal', guess: guessCol(/region|pais|zona|canal|country/i, 2) },
      { id: 'mapRev', label: 'Ingresos / Ventas Reales ($)', guess: guessCol(/ingreso|venta|revenue|real|monto|sales/i, 3) },
      { id: 'mapBgt', label: 'Presupuesto / Meta ($ opcional)', guess: guessCol(/presupuesto|ppto|meta|budget|target/i, 4) },
      { id: 'mapCost', label: 'Costo Total / COGS ($ opcional)', guess: guessCol(/costo|cogs|gasto|cost|expense/i, 5) },
      { id: 'mapQty', label: 'Cantidad / Volumen Q (opcional)', guess: guessCol(/cantidad|volumen|qty|unidades|units/i, 6) }
    ];

    box.innerHTML = mapDefs.map(function (md) {
      var opts = '<option value="__NONE__">(Auto-estimar)</option>' + headers.map(function (h) {
        return '<option value="' + esc(h) + '"' + (h === md.guess ? ' selected' : '') + '>' + esc(h) + '</option>';
      }).join('');
      return '<div class="nx-field"><label class="nx-label" for="' + md.id + '">' + esc(md.label) + '</label>' +
        '<select class="nx-select" id="' + md.id + '">' + opts + '</select></div>';
    }).join('') + '<div class="nx-field" style="justify-content:flex-end;"><button type="button" class="nx-btn nx-btn-gold" id="btnApplyCsvMap">' + SVG_ICONS.check + '<span>Cargar Registros en el Tablero (' + rows.length.toLocaleString() + ' filas)</span></button></div>';

    document.getElementById('btnApplyCsvMap').addEventListener('click', applyMappedCsv);
  }

  function applyMappedCsv() {
    var g = function (id) { var el = document.getElementById(id); return el ? el.value : '__NONE__'; };
    var cDate = g('mapDate'), cUnit = g('mapUnit'), cReg = g('mapRegion'), cRev = g('mapRev'), cBgt = g('mapBgt'), cCost = g('mapCost'), cQty = g('mapQty');

    var mapped = state.rawCsvRows.map(function (row, idx) {
      var rawDt = cDate !== '__NONE__' ? String(row[cDate] || '').trim() : '';
      var ymMatch = rawDt.match(/(\d{4})[-/](\d{1,2})/);
      var yr = ymMatch ? ymMatch[1] : '2026';
      var mNum = ymMatch ? Math.max(1, Math.min(12, parseInt(ymMatch[2], 10))) : ((idx % 12) + 1);
      var ym = yr + '-' + (mNum < 10 ? '0' + mNum : mNum);
      var qtr = 'Q' + (Math.floor((mNum - 1) / 3) + 1);

      var unit = (cUnit !== '__NONE__' && row[cUnit]) ? String(row[cUnit]).slice(0, 40) : 'Línea Principal';
      var reg = (cReg !== '__NONE__' && row[cReg]) ? String(row[cReg]).slice(0, 35) : 'Consolidado';
      var rev = Math.max(0, cleanNum(cRev !== '__NONE__' ? row[cRev] : 0, 1000));
      var bgt = cBgt !== '__NONE__' ? Math.max(0, cleanNum(row[cBgt], rev * 0.96)) : rev * 0.96;
      var cost = cCost !== '__NONE__' ? Math.max(0, cleanNum(row[cCost], rev * 0.58)) : rev * 0.58;
      var qty = cQty !== '__NONE__' ? Math.max(1, cleanNum(row[cQty], Math.round(rev / 50))) : Math.max(1, Math.round(rev / 50));

      var cogs = cost * 0.58;
      var opex = cost * 0.42;
      var ebitda = rev - cogs - opex;
      var ebitdaBgt = bgt * 0.36;
      var taxCapex = Math.max(0, ebitda * 0.24) + rev * 0.04;

      return {
        year: yr, quarter: qtr, monthIdx: mNum - 1, ym: ym, monthShort: MONTHS_SHORT[mNum - 1] + ' ' + yr.slice(2),
        unit: unit, region: reg, segment: 'General',
        qty: qty, qtyBgt: Math.max(1, Math.round(qty * 0.97)),
        price: rev / qty, priceBgt: bgt / Math.max(1, qty * 0.97),
        discPct: 0.05, discountAmt: rev * 0.05, revGross: rev * 1.05, mktSpend: opex * 0.3,
        revReal: rev, revBudget: bgt, cogsReal: cogs, cogsBudget: bgt * 0.34,
        opexReal: opex, opexBudget: bgt * 0.30, ebitdaReal: ebitda, ebitdaBudget: ebitdaBgt,
        taxCapex: taxCapex, fcfReal: ebitda - taxCapex
      };
    });

    state.customRecords = mapped;
    state.datasetKey = 'CUSTOM';
    state.filters = { year: 'ALL', quarter: 'ALL', region: 'ALL', segment: 'ALL', unit: 'ALL' };
    var selDs = document.getElementById('selDataset');
    if (selDs) {
      if (!selDs.querySelector('option[value="CUSTOM"]')) {
        var opt = document.createElement('option');
        opt.value = 'CUSTOM';
        opt.textContent = 'CSV Local Cargado';
        selDs.appendChild(opt);
      }
      selDs.value = 'CUSTOM';
    }
    buildDataset();
    switchTab('view-bi');
    showToast('Archivo CSV cargado en los 5 módulos analíticos');
  }

  function csvSafeText(s) {
    var v = String(s == null ? '' : s).replace(/"/g, '""');
    if (/^[=+\-@\t\r]/.test(v)) v = "'" + v;
    return '"' + v + '"';
  }

  function exportFilteredCsv() {
    var recs = getFilteredRecords();
    var headers = ['Periodo', 'Anio', 'Trimestre', 'Unidad', 'Region', 'Segmento', 'Volumen_Q', 'Tarifa_USD', 'Ingresos_Reales', 'Presupuesto', 'COGS', 'OPEX', 'EBITDA', 'Flujo_Caja_Libre'];
    var lines = [headers.join(',')];
    recs.forEach(function (r) {
      lines.push([
        r.ym, r.year, r.quarter, csvSafeText(r.unit),
        csvSafeText(r.region), csvSafeText(r.segment),
        Math.round(r.qty), r.price.toFixed(2), Math.round(r.revReal), Math.round(r.revBudget),
        Math.round(r.cogsReal), Math.round(r.opexReal), Math.round(r.ebitdaReal), Math.round(r.fcfReal)
      ].join(','));
    });
    var blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'nexus_analytics_export_' + state.datasetKey.toLowerCase() + '.csv';
    a.click();
    showToast('Archivo CSV exportado (' + recs.length + ' registros)');
  }

  function downloadSampleTemplateCsv() {
    var sample = [
      'Fecha,Unidad,Region,Ingresos_Reales,Presupuesto,Costo_Total,Volumen_Q',
      '2026-01,Grocery & Perecederos,Walmart U.S. (Norteamerica),9850000,9550000,8890000,180700',
      '2026-01,Walmart eCommerce & Pickup,Walmart U.S. (Norteamerica),4620000,4400000,4115000,74000',
      '2026-02,Grocery & Perecederos,Mexico & Centroamerica (Walmex),3420000,3300000,3085000,62750',
      '2026-02,Sams Club (Mayorista),Walmart U.S. (Norteamerica),5180000,5020000,4680000,43700',
      '2026-03,Mercancia General & Hogar,Walmart U.S. (Norteamerica),5640000,5450000,4990000,82900',
      '2026-03,Walmart Connect & Marketplace,Walmart U.S. (Norteamerica),2190000,2010000,1390000,23300'
    ].join('\n');
    var blob = new Blob(['\uFEFF' + sample], { type: 'text/csv;charset=utf-8;' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'plantilla_retail_walmart_nexus.csv';
    a.click();
    showToast('Plantilla CSV Retail (Walmart) descargada — puedes arrastrarla al cargador');
  }

  // ============================================================================
  // CONTROLLER & EVENT WIRING
  // ============================================================================
  function refreshAll() {
    var recs = getFilteredRecords();
    renderActiveFilterChips(recs.length);
    renderGlobalKpis(recs);

    if (state.activeTab === 'view-bi') renderTabBi(recs);
    else if (state.activeTab === 'view-pnl') renderTabPnl(recs);
    else if (state.activeTab === 'view-analytics') renderTabAnalytics(recs);
    else if (state.activeTab === 'view-whatif') renderTabWhatIf(recs);
    else if (state.activeTab === 'view-explorer') renderTabExplorer(recs);
  }

  function switchTab(viewId) {
    state.activeTab = viewId;
    document.querySelectorAll('.nx-tab').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-view') === viewId);
    });
    document.querySelectorAll('.nx-view').forEach(function (v) {
      v.classList.toggle('active', v.id === viewId);
    });
    refreshAll();
  }

  function initEvents() {
    // Tabs
    document.querySelectorAll('.nx-tab').forEach(function (btn) {
      btn.addEventListener('click', function () {
        switchTab(btn.getAttribute('data-view'));
      });
    });

    // Global Slicers
    var bindSel = function (id, filterKey) {
      var el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', function () {
          state.filters[filterKey] = el.value;
          refreshAll();
        });
      }
    };
    bindSel('selYear', 'year');
    bindSel('selQuarter', 'quarter');
    bindSel('selRegion', 'region');
    bindSel('selSegment', 'segment');

    var selDs = document.getElementById('selDataset');
    if (selDs) {
      selDs.addEventListener('change', function () {
        state.datasetKey = selDs.value;
        state.filters = { year: 'ALL', quarter: 'ALL', region: 'ALL', segment: 'ALL', unit: 'ALL' };
        buildDataset();
        refreshAll();
        showToast('Dataset activo: ' + selDs.options[selDs.selectedIndex].text);
      });
    }

    // Randomize Seed
    var btnRand = document.getElementById('btnRandomSeed');
    if (btnRand) {
      btnRand.addEventListener('click', function () {
        if (state.datasetKey === 'CUSTOM') state.datasetKey = 'WALMART_WMT';
        state.seed = (Date.now() ^ Math.floor(Math.random() * 0xFFFFFF)) >>> 0;
        buildDataset();
        refreshAll();
        showToast('Nuevo escenario estocástico Retail generado (36 meses × 6 divisiones)');
      });
    }

    // Theme Toggle (Midnight Navy & Gold <-> Executive Light)
    var btnTheme = document.getElementById('btnToggleTheme');
    if (btnTheme) {
      btnTheme.addEventListener('click', function () {
        state.theme = state.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', state.theme);
        btnTheme.innerHTML = state.theme === 'dark'
          ? (SVG_ICONS.sun + '<span>Modo Claro</span>')
          : (SVG_ICONS.moon + '<span>Navy &amp; Gold</span>');
        refreshAll();
      });
    }

    // Export CSV
    var btnExp = document.getElementById('btnExportCsv');
    if (btnExp) btnExp.addEventListener('click', exportFilteredCsv);
    var btnExp2 = document.getElementById('btnExportCsv2');
    if (btnExp2) btnExp2.addEventListener('click', exportFilteredCsv);

    var btnTpl = document.getElementById('btnDownloadTemplate');
    if (btnTpl) btnTpl.addEventListener('click', downloadSampleTemplateCsv);

    // Sortable Executive Table headers
    document.querySelectorAll('#tblBiUnits thead th[data-col]').forEach(function (th) {
      th.addEventListener('click', function () {
        var c = th.getAttribute('data-col');
        if (state.tableSort.col === c) state.tableSort.asc = !state.tableSort.asc;
        else { state.tableSort.col = c; state.tableSort.asc = false; }
        refreshAll();
      });
    });

    // Lab Controls
    ['labMetric', 'labHorizon', 'labCi', 'labZThresh'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.addEventListener('change', function () {
          state.lab.metric = document.getElementById('labMetric').value;
          state.lab.horizon = parseInt(document.getElementById('labHorizon').value, 10);
          state.lab.ci = parseFloat(document.getElementById('labCi').value);
          state.lab.zThresh = parseFloat(document.getElementById('labZThresh').value);
          refreshAll();
        });
      }
    });

    // What-If Sliders
    var sliderMap = [
      ['slDQ', 'dQ', 'lblDQ', '%', true],
      ['slDP', 'dP', 'lblDP', '%', true],
      ['slElast', 'elast', 'lblElast', '', false],
      ['slDCogs', 'dCogs', 'lblDCogs', '%', true],
      ['slDOpex', 'dOpex', 'lblDOpex', '%', true],
      ['slWacc', 'wacc', 'lblWacc', '%', false]
    ];
    sliderMap.forEach(function (cfg) {
      var el = document.getElementById(cfg[0]);
      if (!el) return;
      el.addEventListener('input', function () {
        var v = parseFloat(el.value);
        state.whatIf[cfg[1]] = v;
        var lbl = document.getElementById(cfg[2]);
        if (lbl) lbl.textContent = (cfg[4] && v > 0 ? '+' : '') + v.toFixed(cfg[1] === 'elast' ? 2 : 1) + cfg[3];
        renderTabWhatIf(getFilteredRecords());
      });
    });

    // What-If Presets
    var applyPreset = function (vals, label) {
      state.whatIf = Object.assign({}, vals);
      sliderMap.forEach(function (cfg) {
        var el = document.getElementById(cfg[0]);
        var lbl = document.getElementById(cfg[2]);
        var v = state.whatIf[cfg[1]];
        if (el) el.value = v;
        if (lbl) lbl.textContent = (cfg[4] && v > 0 ? '+' : '') + v.toFixed(cfg[1] === 'elast' ? 2 : 1) + cfg[3];
      });
      renderTabWhatIf(getFilteredRecords());
      showToast('Escenario aplicado: ' + label);
    };

    var pBase = document.getElementById('preBase');
    if (pBase) pBase.addEventListener('click', function () { applyPreset({ dQ: 0, dP: 0, elast: -0.65, dCogs: 0, dOpex: 0, wacc: 7.5 }, 'Caso Base Retail (WMT)'); });
    var pBull = document.getElementById('preBull');
    if (pBull) pBull.addEventListener('click', function () { applyPreset({ dQ: 12, dP: 3.5, elast: -0.50, dCogs: -2.5, dOpex: -2, wacc: 7.0 }, 'Expansión Omnicanal & Holiday +12%'); });
    var pStress = document.getElementById('preStress');
    if (pStress) pStress.addEventListener('click', function () { applyPreset({ dQ: -8, dP: -2.5, elast: -0.95, dCogs: 4.5, dOpex: 4, wacc: 9.5 }, 'Choque Inflación Cadena de Suministro'); });
    var pLean = document.getElementById('preLean');
    if (pLean) pLean.addEventListener('click', function () { applyPreset({ dQ: 3, dP: 2, elast: -0.55, dCogs: -3.5, dOpex: -8, wacc: 7.5 }, 'Automatización Logística & Retail Media'); });

    // Pivot Explorer Controls
    var pivGrp = document.getElementById('pivGroupBy');
    if (pivGrp) pivGrp.addEventListener('change', function () { state.pivot.groupBy = pivGrp.value; renderTabExplorer(getFilteredRecords()); });
    var pivSrch = document.getElementById('pivSearch');
    if (pivSrch) pivSrch.addEventListener('input', function () { state.pivot.search = pivSrch.value; renderTabExplorer(getFilteredRecords()); });

    document.querySelectorAll('#tblPivot thead th[data-col]').forEach(function (th) {
      th.addEventListener('click', function () {
        var c = th.getAttribute('data-col');
        if (state.pivotSort.col === c) state.pivotSort.asc = !state.pivotSort.asc;
        else { state.pivotSort.col = c; state.pivotSort.asc = false; }
        renderTabExplorer(getFilteredRecords());
      });
    });

    // CSV / JSON Drag & Drop + File Input
    var dz = document.getElementById('csvDropzone');
    var fi = document.getElementById('csvFileInput');
    function handleFile(file) {
      if (!file) return;
      if (file.size > 15 * 1024 * 1024) {
        showToast('Archivo demasiado grande (máx 15 MB)');
        return;
      }
      if (file.size > 2 * 1024 * 1024) { showToast('Archivo excede el límite de seguridad de 2 MB'); return; }
      var reader = new FileReader();
      reader.onload = function (ev) {
        var txt = String(ev.target.result || '');
        if (/\.json$/i.test(file.name)) {
          try {
            var arr = JSON.parse(txt);
            if (Array.isArray(arr) && arr.length > 0 && typeof arr[0] === 'object') {
              openCsvMapper(Object.keys(arr[0]), arr, file.name);
              showToast('JSON leído (' + arr.length + ' registros). Confirma columnas.');
              return;
            }
          } catch (e) {}
        }
        var parsed = parseCsvText(txt);
        if (!parsed || !parsed.rows.length) {
          showToast('No se detectaron filas válidas en el archivo CSV');
          return;
        }
        openCsvMapper(parsed.headers, parsed.rows, file.name);
        showToast('CSV leído (' + parsed.rows.length + ' filas). Haz clic en Inyectar CSV.');
      };
      reader.readAsText(file, 'UTF-8');
    }

    if (dz && fi) {
      dz.addEventListener('click', function () { fi.click(); });
      fi.addEventListener('change', function () { if (fi.files && fi.files[0]) handleFile(fi.files[0]); });
      dz.addEventListener('dragover', function (e) { e.preventDefault(); dz.classList.add('dragover'); });
      dz.addEventListener('dragleave', function () { dz.classList.remove('dragover'); });
      dz.addEventListener('drop', function (e) {
        e.preventDefault();
        dz.classList.remove('dragover');
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleFile(e.dataTransfer.files[0]);
        }
      });
    }

    // Hide "Volver al Post" button when embedded inside Dashboard.html iframe
    if (window.self !== window.top) {
      var backBtn = document.getElementById('btnBackToPost');
      if (backBtn) backBtn.style.display = 'none';
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    buildDataset();
    initEvents();
    refreshAll();
  });
})();


/* ═══════════════════════════════════════════════════════════════════════
   NEXUS QUANT FP&A — MOTOR ESTOCÁSTICO DE DATOS SINTÉTICOS CORPORATIVOS
   6 Líneas de Negocio · 24 Sub-Líneas (Q × Tarifa + Fijo) · 2025–2026
   100% Cliente · Cero Datos Reales Confidenciales · Regenerable On-Demand
   ═══════════════════════════════════════════════════════════════════════ */
(function (global) {
  'use strict';

  const MO = [
    'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
    'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'
  ];

  const LINES_CONFIG = [
    {
      code: 'CLOUD_SAAS',
      shortName: 'Cloud & SaaS',
      displayName: 'Cloud & SaaS Enterprise',
      color: '#0B1B33',
      qtyLabel: 'Licencias / Nodos Activos',
      avgTariffHint: 'Ticket Mensual por Suscripción',
      monthlySeasonality: [0.94, 0.96, 1.01, 0.99, 1.02, 1.05, 1.01, 1.03, 1.07, 1.09, 1.12, 1.18],
      regimePreAbr: [0.22, 0.46, 0.72, 1.00],
      regimePostAbr: [0.54, 0.72, 0.88, 1.00],
      sublines: [
        { code: 'LICENCIAS_ENTERPRISE', label: 'Licencias SaaS Enterprise', hasQty: true, countsMacroQ: true, baseQ: 14800, baseTariff: 118.5, qGrowthMo: 0.014, tariffDrift: 0.002 },
        { code: 'NODOS_API_CLOUD', label: 'Nodos API & Microservicios', hasQty: true, countsMacroQ: true, baseQ: 4200, baseTariff: 164.0, qGrowthMo: 0.018, tariffDrift: 0.001 },
        { code: 'ALMACENAMIENTO_ELASTICO', label: 'Almacenamiento Cloud (TB)', hasQty: true, countsMacroQ: false, baseQ: 6800, baseTariff: 42.5, qGrowthMo: 0.012, tariffDrift: -0.001 },
        { code: 'SOPORTE_MISION_CRITICA', label: 'Retainer Soporte 24/7 (Fijo)', hasQty: false, countsMacroQ: false, baseQ: 0, baseTariff: 0, baseFixed: 285000, fixedGrowthMo: 0.008 }
      ]
    },
    {
      code: 'FINTECH_PAY',
      shortName: 'Fintech & Pagos',
      displayName: 'Pasarela & Pagos Digitales',
      color: '#B8955A',
      qtyLabel: 'Transacciones Liquidadas',
      avgTariffHint: 'Fee Unitario / Tx ($)',
      monthlySeasonality: [0.92, 0.91, 0.98, 0.97, 1.01, 1.04, 1.06, 1.04, 1.08, 1.11, 1.16, 1.24],
      regimePreAbr: [0.24, 0.49, 0.74, 1.00],
      regimePostAbr: [0.27, 0.52, 0.76, 1.00],
      sublines: [
        { code: 'CHECKOUT_TRANSACCIONAL', label: 'Checkout E-Commerce (Q)', hasQty: true, countsMacroQ: true, baseQ: 2450000, baseTariff: 0.68, qGrowthMo: 0.016, tariffDrift: 0.001 },
        { code: 'LIQUIDACION_INSTANTANEA', label: 'Transferencias Instantáneas B2B', hasQty: true, countsMacroQ: true, baseQ: 690000, baseTariff: 0.94, qGrowthMo: 0.019, tariffDrift: 0.0005 },
        { code: 'TOKENIZACION_ANTIFRAUDE', label: 'Scoring Antifraude & Token', hasQty: true, countsMacroQ: true, baseQ: 1120000, baseTariff: 0.29, qGrowthMo: 0.015, tariffDrift: 0.001 },
        { code: 'MEMBRESIAS_COMERCIOS', label: 'Plataforma & Membresía (Fijo)', hasQty: false, countsMacroQ: false, baseQ: 0, baseTariff: 0, baseFixed: 240000, fixedGrowthMo: 0.007 }
      ]
    },
    {
      code: 'DATA_AI_BI',
      shortName: 'Data & BI',
      displayName: 'Data, Analítica & BI',
      color: '#1D4ED8',
      qtyLabel: 'Workspaces & Pipelines',
      avgTariffHint: 'Tarifa Promedio Nodo BI',
      monthlySeasonality: [0.95, 0.97, 1.00, 1.01, 1.03, 1.06, 1.04, 1.05, 1.08, 1.10, 1.12, 1.15],
      regimePreAbr: [0.21, 0.45, 0.71, 1.00],
      regimePostAbr: [0.34, 0.58, 0.79, 1.00],
      sublines: [
        { code: 'SUSCRIPCIONES_SUITE_BI', label: 'Licencias Suite Executive BI', hasQty: true, countsMacroQ: true, baseQ: 3650, baseTariff: 245.0, qGrowthMo: 0.015, tariffDrift: 0.0015 },
        { code: 'PIPELINES_STREAMING_ETL', label: 'Pipelines ETL Tiempo Real', hasQty: true, countsMacroQ: true, baseQ: 1180, baseTariff: 490.0, qGrowthMo: 0.020, tariffDrift: 0.001 },
        { code: 'NODOS_ML_PREDICTIVO', label: 'Modelos Predictivos & Feature Store', hasQty: true, countsMacroQ: true, baseQ: 540, baseTariff: 810.0, qGrowthMo: 0.022, tariffDrift: 0.002 },
        { code: 'GOBIERNO_CATALOGO_DATOS', label: 'Gobierno & Calidad de Datos (Fijo)', hasQty: false, countsMacroQ: false, baseQ: 0, baseTariff: 0, baseFixed: 195000, fixedGrowthMo: 0.009 }
      ]
    },
    {
      code: 'CYBER_SEC',
      shortName: 'Ciberseguridad',
      displayName: 'Ciberseguridad & Zero-Trust',
      color: '#0F766E',
      qtyLabel: 'Endpoints & Identidades',
      avgTariffHint: 'Tarifa Mensual Endpoint',
      monthlySeasonality: [0.96, 0.98, 1.00, 1.02, 1.03, 1.04, 1.05, 1.05, 1.07, 1.09, 1.11, 1.14],
      regimePreAbr: [0.18, 0.44, 0.70, 1.00],
      regimePostAbr: [0.58, 0.76, 0.90, 1.00],
      sublines: [
        { code: 'ENDPOINTS_SOC_MDR', label: 'Endpoints Monitoreados SOC', hasQty: true, countsMacroQ: true, baseQ: 64000, baseTariff: 17.5, qGrowthMo: 0.014, tariffDrift: 0.001 },
        { code: 'IDENTIDADES_ZERO_TRUST', label: 'Gestión Identidades IAM/MFA', hasQty: true, countsMacroQ: true, baseQ: 92000, baseTariff: 8.2, qGrowthMo: 0.015, tariffDrift: 0.0008 },
        { code: 'AUDITORIA_PENTESTING', label: 'Auditorías & Pentesting (Q)', hasQty: true, countsMacroQ: false, baseQ: 34, baseTariff: 8900.0, qGrowthMo: 0.008, tariffDrift: 0.002 },
        { code: 'RETAINER_RESPUESTA_CSIRT', label: 'Retainer Respuesta CSIRT (Fijo)', hasQty: false, countsMacroQ: false, baseQ: 0, baseTariff: 0, baseFixed: 215000, fixedGrowthMo: 0.006 }
      ]
    },
    {
      code: 'CORP_B2B',
      shortName: 'Soluciones B2B',
      displayName: 'Soluciones Corporativas B2B',
      color: '#334155',
      qtyLabel: 'Dispositivos & Contratos',
      avgTariffHint: 'ARPU Corporativo ($/Q)',
      monthlySeasonality: [0.93, 0.95, 0.99, 0.98, 1.01, 1.03, 1.02, 1.04, 1.06, 1.08, 1.10, 1.13],
      regimePreAbr: [0.25, 0.50, 0.75, 1.00],
      regimePostAbr: [0.31, 0.56, 0.80, 1.00],
      sublines: [
        { code: 'TERMINALES_TELEMETRIA_IOT', label: 'Terminales Telemetría IoT', hasQty: true, countsMacroQ: true, baseQ: 18500, baseTariff: 48.0, qGrowthMo: 0.012, tariffDrift: 0.001 },
        { code: 'OUTSOURCING_BPO_FINANZAS', label: 'Procesos BPO Finanzas (Q)', hasQty: true, countsMacroQ: true, baseQ: 3200, baseTariff: 210.0, qGrowthMo: 0.010, tariffDrift: 0.0015 },
        { code: 'MANTENIMIENTO_SLA_CAMPO', label: 'Mantenimiento SLA Hardware', hasQty: true, countsMacroQ: false, baseQ: 4100, baseTariff: 54.0, qGrowthMo: 0.009, tariffDrift: 0.001 },
        { code: 'INTEGRACION_ERP_REGIONAL', label: 'Conectores ERP Multi-País (Fijo)', hasQty: false, countsMacroQ: false, baseQ: 0, baseTariff: 0, baseFixed: 260000, fixedGrowthMo: 0.005 }
      ]
    },
    {
      code: 'STRAT_PMO',
      shortName: 'Consultoría & PMO',
      displayName: 'Consultoría Estratégica & PMO',
      color: '#854D0E',
      qtyLabel: 'Horas & Células Ágiles',
      avgTariffHint: 'Tarifa Horaria / Célula',
      monthlySeasonality: [0.89, 0.94, 1.02, 0.99, 1.01, 1.05, 0.97, 0.98, 1.06, 1.09, 1.10, 1.04],
      regimePreAbr: [0.23, 0.48, 0.73, 1.00],
      regimePostAbr: [0.26, 0.51, 0.76, 1.00],
      sublines: [
        { code: 'HORAS_CONSULTORIA_SENIOR', label: 'Horas Consultoría Estratégica', hasQty: true, countsMacroQ: true, baseQ: 3900, baseTariff: 175.0, qGrowthMo: 0.008, tariffDrift: 0.002 },
        { code: 'CELULAS_AGILES_PMO', label: 'Células Ágiles PMO Dedicadas', hasQty: true, countsMacroQ: true, baseQ: 42, baseTariff: 11200.0, qGrowthMo: 0.011, tariffDrift: 0.0015 },
        { code: 'BOOTCAMPS_EJECUTIVOS', label: 'Programas Executive Analytics', hasQty: true, countsMacroQ: false, baseQ: 18, baseTariff: 6800.0, qGrowthMo: 0.009, tariffDrift: 0.001 },
        { code: 'ESTRUCTURACION_CAPEX_MA', label: 'Estructuración CAPEX & Valuación (Fijo)', hasQty: false, countsMacroQ: false, baseQ: 0, baseTariff: 0, baseFixed: 165000, fixedGrowthMo: 0.006 }
      ]
    }
  ];

  const LN = LINES_CONFIG.map(c => c.code);
  const LL = LINES_CONFIG.map(c => c.shortName);
  const DISP_MAP = Object.fromEntries(LINES_CONFIG.map(c => [c.code, c.displayName]));
  const LINE_COLORS = LINES_CONFIG.map(c => c.color);

  const SUBLINE_META = {};
  const SUB_LABELS = {};
  LINES_CONFIG.forEach(lc => {
    lc.sublines.forEach(sc => {
      const k = `${lc.code}::${sc.code}`;
      SUBLINE_META[k] = { ...sc, lineCode: lc.code };
      SUB_LABELS[sc.code] = sc.label;
    });
  });

  const DRIVER_CARDS_META = [
    { id: 'sf-driver-1', title: 'Licencias SaaS Enterprise (Q)', query: 'LICENCIAS SAAS ENTERPRISE', category: 'PRODUCTOS' },
    { id: 'sf-driver-2', title: 'Volumen Checkout Digital (Tx)', query: 'TRANSACCIONES CHECKOUT DIGITAL', category: 'PRODUCTOS' },
    { id: 'sf-driver-3', title: 'Pipelines Analíticos Activos', query: 'PIPELINES ANALITICOS EN PRODUCCION', category: 'PRODUCTOS' },
    { id: 'sf-driver-4', title: 'Endpoints Protegidos SOC', query: 'ENDPOINTS PROTEGIDOS SOC', category: 'PRODUCTOS' },
    { id: 'sf-driver-5', title: 'Terminales Telemetría IoT', query: 'TERMINALES IOT CONECTADOS', category: 'PRODUCTOS' },
    { id: 'sf-driver-6', title: 'Net Revenue Retention (NRR %)', query: 'NET REVENUE RETENTION', category: 'KPIS' }
  ];

  function createRng(seed) {
    let a = seed >>> 0;
    return function () {
      let t = (a += 0x6D2B79F5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function randNormal(rng) {
    const u1 = Math.max(1e-7, rng());
    const u2 = rng();
    return Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  }

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  function generateDataset(customSeed) {
    const seed = customSeed != null ? (Number(customSeed) >>> 0) : ((Date.now() ^ Math.floor(Math.random() * 0xFFFFFF)) >>> 0);
    const rng = createRng(seed);

    const datos = {};
    const sublineas = {};
    const cierre = {};
    const semaforo = [
      ['ANIO', 'MES', 'SEMANA', 'ESCENARIO', 'FAMILIA', 'TIPO', 'CODIGO', 'INDICADOR', 'UNIDAD', 'VALOR']
    ];

    const ACTIVE_YEAR = 2026;
    const ACTIVE_MONTH = 'NOVIEMBRE';
    const ACTIVE_WEEK = 3;

    // Elegir 2 líneas aleatorias para inducir anomalías realistas en el corte actual (demo Z-MAD & Auditoría)
    const anomalyIdxA = Math.floor(rng() * LN.length);
    const anomalyIdxB = (anomalyIdxA + 1 + Math.floor(rng() * (LN.length - 1))) % LN.length;
    const anomalyLineA = LN[anomalyIdxA]; // Anomalía de volumen + tarifa positiva extrema
    const anomalyLineB = LN[anomalyIdxB]; // Desviación negativa significativa en corte

    const years = [2025, 2026];
    years.forEach(yr => {
      datos[yr] = {};
      sublineas[yr] = {};
      cierre[yr] = {};

      const maxMonthIdx = yr === 2026 ? 10 : 11; // 2025 Ene-Dic, 2026 Ene-Nov (Nov activo S3)
      for (let mIdx = 0; mIdx <= maxMonthIdx; mIdx++) {
        const mo = MO[mIdx];
        const tIdx = (yr - 2025) * 12 + mIdx; // 0..22
        const isNov26 = (yr === ACTIVE_YEAR && mo === ACTIVE_MONTH);
        const isPostApr26 = (yr === 2026 && mIdx >= 3);

        datos[yr][mo] = {};
        sublineas[yr][mo] = {};
        cierre[yr][mo] = {};

        for (let s = 1; s <= 4; s++) {
          datos[yr][mo][s] = {};
          sublineas[yr][mo][s] = {};
        }

        LINES_CONFIG.forEach(lc => {
          const lineCode = lc.code;
          const season = lc.monthlySeasonality[mIdx] || 1.0;
          const shares = isPostApr26 ? lc.regimePostAbr : lc.regimePreAbr;

          // Macro perturbación por mes y línea (realista ~ ±4% ppto, ±7% real)
          const pptoShock = 1 + 0.025 * randNormal(rng);
          const lineExecBias = (lineCode === anomalyLineA && isNov26)
            ? 1.24
            : ((lineCode === anomalyLineB && isNov26) ? 0.78 : (1 + 0.045 * randNormal(rng)));

          let monthS4RealTotal = 0;
          let monthS4PptoTotal = 0;

          lc.sublines.forEach((sc, sIdx) => {
            const cumSubPptoShares = shares;
            const monthFactorQ = Math.pow(1 + (sc.qGrowthMo || 0.01), tIdx) * season;
            const monthFactorT = Math.pow(1 + (sc.tariffDrift || 0.001), tIdx);

            const mPptoQ = sc.hasQty ? Math.round(sc.baseQ * monthFactorQ * (0.98 + 0.04 * rng()) * pptoShock) : 0;
            const mPptoT = sc.hasQty ? sc.baseTariff * monthFactorT : 0;
            const mPptoD = sc.hasQty
              ? mPptoQ * mPptoT
              : (sc.baseFixed * Math.pow(1 + (sc.fixedGrowthMo || 0.006), tIdx) * pptoShock * (0.97 + 0.06 * rng()));

            // En real, aplicamos variación por sub-línea
            let subNoise = 1 + 0.055 * randNormal(rng);
            let tariffSpike = 1 + 0.018 * randNormal(rng);
            if (isNov26 && lineCode === anomalyLineA && sIdx === 0) {
              subNoise = 1.46; // Spike de volumen Q para disparar alerta Z-MAD
              tariffSpike = 1.18; // Ajuste de tarifa notable
            } else if (isNov26 && lineCode === anomalyLineB && sIdx === 0) {
              subNoise = 0.68; // Contracción temporal de Q
            }

            const mRealQ = sc.hasQty ? Math.max(1, Math.round(mPptoQ * clamp(lineExecBias * subNoise, 0.58, 1.65))) : 0;
            const mRealT = sc.hasQty ? Math.max(0.01, mPptoT * clamp(tariffSpike, 0.82, 1.32)) : 0;
            const mRealD = sc.hasQty
              ? mRealQ * mRealT
              : Math.max(1000, mPptoD * clamp(lineExecBias * (1 + 0.03 * randNormal(rng)), 0.75, 1.25));

            monthS4PptoTotal += mPptoD;
            monthS4RealTotal += mRealD;

            // Distribuir acumulativamente en semanas S1..S4
            let prevSubShare = 0;
            for (let s = 1; s <= 4; s++) {
              const targetSh = s === 4 ? 1.0 : clamp(cumSubPptoShares[s - 1] + 0.025 * randNormal(rng), prevSubShare + 0.05, 0.96);
              const realSh = s === 4 ? 1.0 : clamp(cumSubPptoShares[s - 1] + 0.032 * randNormal(rng), prevSubShare + 0.04, 0.97);
              prevSubShare = targetSh;

              const wPptoD = Math.round(mPptoD * targetSh * 100) / 100;
              const wPptoQ = sc.hasQty ? Math.max(1, Math.round(mPptoQ * (sc.code.includes('LICENCIAS') || sc.code.includes('ENDPOINTS') || sc.code.includes('TERMINALES') || sc.code.includes('SUSCRIPCIONES') ? 1.0 : targetSh))) : 0;

              const hasRealThisWeek = !(isNov26 && s > ACTIVE_WEEK);
              const wRealD = hasRealThisWeek ? Math.round(mRealD * realSh * 100) / 100 : 0;
              const wRealQ = (hasRealThisWeek && sc.hasQty)
                ? Math.max(1, Math.round(mRealQ * (sc.code.includes('LICENCIAS') || sc.code.includes('ENDPOINTS') || sc.code.includes('TERMINALES') || sc.code.includes('SUSCRIPCIONES') ? 1.0 : realSh)))
                : 0;

              if (!datos[yr][mo][s][lineCode]) {
                datos[yr][mo][s][lineCode] = {
                  DOLARES: { REAL: 0, PRESUPUESTO: 0 },
                  CANTIDADES: { REAL: 0, PRESUPUESTO: 0 }
                };
              }
              if (!sublineas[yr][mo][s][lineCode]) sublineas[yr][mo][s][lineCode] = {};

              // Acumular a la línea madre
              datos[yr][mo][s][lineCode].DOLARES.PRESUPUESTO = Math.round((datos[yr][mo][s][lineCode].DOLARES.PRESUPUESTO + wPptoD) * 100) / 100;
              datos[yr][mo][s][lineCode].DOLARES.REAL = Math.round((datos[yr][mo][s][lineCode].DOLARES.REAL + wRealD) * 100) / 100;
              if (sc.hasQty && sc.countsMacroQ) {
                datos[yr][mo][s][lineCode].CANTIDADES.PRESUPUESTO += wPptoQ;
                datos[yr][mo][s][lineCode].CANTIDADES.REAL += wRealQ;
              }

              sublineas[yr][mo][s][lineCode][sc.code] = {
                DOLARES: { REAL: wRealD, PRESUPUESTO: wPptoD },
                CANTIDADES: { REAL: wRealQ, PRESUPUESTO: wPptoQ }
              };
            }
          });

          // Cierre Contable para meses cerrados (todos excepto NOVIEMBRE 2026)
          if (!isNov26) {
            const closeAdj = 1 + 0.012 * randNormal(rng);
            cierre[yr][mo][lineCode] = { DOLARES: Math.round(monthS4RealTotal * closeAdj * 100) / 100 };
          } else {
            cierre[yr][mo][lineCode] = { DOLARES: 0 };
          }
        });

        // ─── GENERACIÓN DE MÉTRICAS DEL SEMÁFORO COMERCIAL PARA EL MES/SEMANA ───
        const baseGrowth = Math.pow(1.013, tIdx);
        const semMetrics = [
          // Productos
          { tipo: 'PRODUCTOS', codigo: 'PRD01', ind: 'Licencias SaaS Enterprise', uni: 'NUM', mesMeta: Math.round(14800 * baseGrowth), flow: false, perf: 1.03 + 0.08 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD02', ind: 'Transacciones Checkout Digital', uni: 'NUM', mesMeta: Math.round(2450000 * baseGrowth), flow: true, perf: 1.05 + 0.09 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD03', ind: 'Pipelines Analíticos en Producción', uni: 'NUM', mesMeta: Math.round(1180 * baseGrowth), flow: false, perf: 1.02 + 0.07 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD04', ind: 'Endpoints Protegidos SOC', uni: 'NUM', mesMeta: Math.round(64000 * baseGrowth), flow: false, perf: 1.07 + 0.06 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD05', ind: 'Terminales IoT Conectados', uni: 'NUM', mesMeta: Math.round(18500 * baseGrowth), flow: false, perf: 0.97 + 0.07 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD06', ind: 'Volumen Liquidación Instantánea ($)', uni: 'DOLARES', mesMeta: Math.round(648000 * baseGrowth), flow: true, perf: 1.08 + 0.08 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD07', ind: 'Clientes Cloud Tier-1 Activos', uni: 'NUM', mesMeta: Math.round(310 + tIdx * 4), flow: false, perf: 1.01 + 0.05 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD08', ind: 'Cuentas Zero-Trust Provisionadas', uni: 'NUM', mesMeta: Math.round(92000 * baseGrowth), flow: false, perf: 0.99 + 0.06 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD09', ind: 'Workspaces BI Corporativos', uni: 'NUM', mesMeta: Math.round(3650 * baseGrowth), flow: false, perf: 1.04 + 0.06 * randNormal(rng) },
          { tipo: 'PRODUCTOS', codigo: 'PRD10', ind: 'Células Ágiles PMO Desplegadas', uni: 'NUM', mesMeta: Math.round(42 + Math.floor(tIdx * 0.7)), flow: false, perf: 0.93 + 0.07 * randNormal(rng) },
          // KPIs
          { tipo: 'KPIS', codigo: 'KPI01', ind: 'Net Revenue Retention (NRR %)', uni: 'PORCENTAJE', mesMeta: 112, flow: false, perf: 1.02 + 0.04 * randNormal(rng), pctMode: true },
          { tipo: 'KPIS', codigo: 'KPI02', ind: 'Disponibilidad SLA Cloud (%)', uni: 'PORCENTAJE', mesMeta: 99, flow: false, perf: 1.00 + 0.008 * randNormal(rng), pctMode: true, cap: 100 },
          { tipo: 'KPIS', codigo: 'KPI03', ind: 'Adopción Analítica Predictiva (%)', uni: 'PORCENTAJE', mesMeta: 78, flow: false, perf: 0.98 + 0.08 * randNormal(rng), pctMode: true, cap: 100 },
          { tipo: 'KPIS', codigo: 'KPI04', ind: 'Margen Contribución Bruto (%)', uni: 'PORCENTAJE', mesMeta: 64, flow: false, perf: 1.01 + 0.05 * randNormal(rng), pctMode: true, cap: 95 },
          { tipo: 'KPIS', codigo: 'KPI05', ind: 'Tasa Conversión Checkout (%)', uni: 'PORCENTAJE', mesMeta: 94, flow: false, perf: 0.99 + 0.04 * randNormal(rng), pctMode: true, cap: 99 },
          { tipo: 'KPIS', codigo: 'KPI06', ind: 'Cobertura Automatización FinOps (%)', uni: 'PORCENTAJE', mesMeta: 85, flow: false, perf: 0.89 + 0.08 * randNormal(rng), pctMode: true, cap: 100 },
          // Proyectos Estratégicos
          { tipo: 'PROYECTOS', codigo: 'PRY01', ind: 'Motor Realtime Fraud Scoring IA v3', uni: 'PORCENTAJE', mesMeta: Math.min(100, Math.round(45 + tIdx * 2.4)), flow: false, perf: 1.02 + 0.03 * randNormal(rng), pctMode: true, cap: 100 },
          { tipo: 'PROYECTOS', codigo: 'PRY02', ind: 'Migración Data Mesh Multi-Región', uni: 'PORCENTAJE', mesMeta: Math.min(100, Math.round(40 + tIdx * 2.5)), flow: false, perf: 0.97 + 0.05 * randNormal(rng), pctMode: true, cap: 100 },
          { tipo: 'PROYECTOS', codigo: 'PRY03', ind: 'Certificación ISO 27001 Zero-Trust', uni: 'PORCENTAJE', mesMeta: Math.min(100, Math.round(52 + tIdx * 2.1)), flow: false, perf: 1.01 + 0.03 * randNormal(rng), pctMode: true, cap: 100 },
          { tipo: 'PROYECTOS', codigo: 'PRY04', ind: 'Suite Automatización ERP & Billing', uni: 'PORCENTAJE', mesMeta: Math.min(100, Math.round(35 + tIdx * 2.6)), flow: false, perf: 0.87 + 0.06 * randNormal(rng), pctMode: true, cap: 100 }
        ];

        const maxW = isNov26 ? ACTIVE_WEEK : 4;
        for (let s = 1; s <= 4; s++) {
          const factor = s / 4;
          semMetrics.forEach(m => {
            const pptoVal = m.pctMode ? m.mesMeta : (m.flow ? Math.round(m.mesMeta * factor) : m.mesMeta);
            semaforo.push([yr, mo, s, 'PRESUPUESTO', m.tipo, m.tipo, m.codigo, m.ind, m.uni, pptoVal]);
            if (s <= maxW) {
              let realVal;
              if (m.pctMode) {
                const rawP = Math.round(pptoVal * clamp(m.perf, 0.72, 1.18));
                realVal = m.cap ? Math.min(m.cap, rawP) : rawP;
              } else {
                realVal = Math.max(1, Math.round(pptoVal * clamp(m.perf + (s - 2) * 0.012, 0.65, 1.38)));
              }
              semaforo.push([yr, mo, s, 'REAL', m.tipo, m.tipo, m.codigo, m.ind, m.uni, realVal]);
            }
          });
        }
      }
    });

    // Construir reporte inicial de Auditoría + Anomalías Z-MAD
    const audit = buildAuditReport(datos, sublineas, cierre, seed);

    return {
      isAggregated: true,
      seed,
      scenarioLabel: `SCN-${String(seed).slice(-5).padStart(5, '0')}`,
      lastSync: new Date().toISOString(),
      datos,
      sublineas,
      cierre,
      semaforo,
      audit,
      auditSummary: audit.summary,
      predictive: null
    };
  }

  function _med(arr) {
    if (!arr || !arr.length) return 0;
    const s = [...arr].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
  }

  function buildAuditReport(datos, sublineas, cierre, seed) {
    const issues = [];
    const activeYr = '2026';
    const activeMo = 'NOVIEMBRE';
    const activeS = 3;

    // 1. Escanear anomalías estadísticas Z-MAD en 2026 S3 y cierres históricos
    LN.forEach(line => {
      const histS3 = [];
      Object.keys(datos['2025'] || {}).forEach(mo => {
        const v = datos['2025'][mo]?.[activeS]?.[line]?.DOLARES?.REAL || 0;
        if (v > 0) histS3.push(v);
      });
      Object.keys(datos['2026'] || {}).forEach(mo => {
        if (mo === activeMo) return;
        const v = datos['2026'][mo]?.[activeS]?.[line]?.DOLARES?.REAL || 0;
        if (v > 0) histS3.push(v);
      });

      const curVal = datos[activeYr]?.[activeMo]?.[activeS]?.[line]?.DOLARES?.REAL || 0;
      const curQ = datos[activeYr]?.[activeMo]?.[activeS]?.[line]?.CANTIDADES?.REAL || 0;
      const medV = _med(histS3);
      const madV = Math.max(medV * 0.04, _med(histS3.map(x => Math.abs(x - medV))));
      const z = madV > 0 ? (curVal - medV) / (1.4826 * madV) : 0;

      if (Math.abs(z) > 2.2) {
        issues.push({
          severity: Math.abs(z) > 3.2 ? 'critical' : 'anomaly',
          category: 'HISTORICAL_OUTLIER',
          sheet: `MOD_S${activeS}`,
          cell: `${line}!D${activeS}`,
          period: `${activeMo} ${activeYr} · S${activeS}`,
          line,
          subline: 'Consolidado Línea',
          message: `Desviación estadística Z-MAD = ${z >= 0 ? '+' : ''}${z.toFixed(2)} respecto a la mediana histórica de S${activeS} (Q=${Math.round(curQ).toLocaleString('en-US')}).`,
          formulaOrValue: `$${Math.round(curVal).toLocaleString('en-US')}`,
          expectedHint: `Mediana hist. S${activeS}: $${Math.round(medV).toLocaleString('en-US')}`
        });
      }

      // 2. Conciliación Sub-líneas vs Total Línea
      const lineSubObj = sublineas[activeYr]?.[activeMo]?.[activeS]?.[line] || {};
      const sumSubs = Object.values(lineSubObj).reduce((acc, s) => acc + (s?.DOLARES?.REAL || 0), 0);
      const diffConc = Math.abs(sumSubs - curVal);
      if (diffConc > 5) {
        issues.push({
          severity: 'critical',
          category: 'SUBLINE_MISMATCH',
          sheet: 'SUBLINEAS_DB',
          cell: `${line}!SUM`,
          period: `${activeMo} ${activeYr} · S${activeS}`,
          line,
          subline: 'Reconciliación 4 Sub-Líneas',
          message: `Diferencia de consolidación entre suma de sub-líneas y total de línea ($${diffConc.toFixed(2)}).`,
          formulaOrValue: `$${Math.round(sumSubs).toLocaleString('en-US')}`,
          expectedHint: `$${Math.round(curVal).toLocaleString('en-US')}`
        });
      }
    });

    // 3. Validación de brecha S4 vs Cierre Contable en meses cerrados (nota informativa/warning si >3%)
    ['SEPTIEMBRE', 'OCTUBRE'].forEach(mo => {
      LN.forEach(line => {
        const s4 = datos['2026']?.[mo]?.[4]?.[line]?.DOLARES?.REAL || 0;
        const ci = cierre['2026']?.[mo]?.[line]?.DOLARES || 0;
        if (s4 > 0 && ci > 0) {
          const pctDiff = Math.abs((ci - s4) / s4) * 100;
          if (pctDiff > 2.6) {
            issues.push({
              severity: 'warning',
              category: 'CLOSE_DRIFT',
              sheet: 'CIERRE_CONTABLE',
              cell: `${mo.slice(0, 3)}!${line}`,
              period: `${mo} 2026`,
              line,
              subline: 'S4 Operativo vs Cierre',
              message: `Ajuste contable post-cierre de ${pctDiff.toFixed(2)}% respecto a estimación operativa S4.`,
              formulaOrValue: `$${Math.round(ci).toLocaleString('en-US')}`,
              expectedHint: `S4 Operativo: $${Math.round(s4).toLocaleString('en-US')}`
            });
          }
        }
      });
    });

    const summary = {
      total: issues.length,
      critical: issues.filter(i => i.severity === 'critical').length,
      anomaly: issues.filter(i => i.severity === 'anomaly').length,
      warning: issues.filter(i => i.severity === 'warning').length,
      checkedCells: 23 * 4 * 6 * 4,
      seed,
      timestamp: new Date().toISOString()
    };

    return { summary, issues };
  }

  function buildSyntheticEcosystem(seed) {
    return generateDataset(seed);
  }

  global.MO = MO;
  global.LINES_CONFIG = LINES_CONFIG;
  global.LN = LN;
  global.LL = LL;
  global.DISP_MAP = DISP_MAP;
  global.LINE_COLORS = LINE_COLORS;
  global.SUBLINE_META = SUBLINE_META;
  global.SUB_LABELS = SUB_LABELS;
  global.DRIVER_CARDS_META = DRIVER_CARDS_META;
  global.NexusSyntheticEngine = {
    generateDataset,
    buildSyntheticEcosystem,
    buildAuditReport
  };
})(typeof window !== 'undefined' ? window : globalThis);

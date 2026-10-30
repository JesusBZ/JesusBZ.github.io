/**
 * JesusBZ - Futuristic Corporate FinTech Platform JS
 * Author: Jesús Benjamín Zerpa | Economist & Data Scientist
 * Features:
 *   1. Cinematographic Hero Showcase (Smooth Crossfade + Progress Pills + Touch Swipe)
 *   2. Instant Search & Category Filters for Blog Stream
 *   3. Portfolio Assistant powered by Gemini (original Vercel backend, API key server-side) grounded on a verified knowledge base, with local verified fallback
 *   4. Full Embedded Quantitative Knowledge Base for all 13 R Models & Author Dossier
 *   5. Automatic "Copiar Código" Buttons with Language Badges on all R Code Chunks
 *   6. Dynamic Collision-Free Scroll-to-Top Management
 */

(function () {
  'use strict';

  // =========================================================================
  // 1. Mobile Navigation & Header Scroll State
  // =========================================================================
  function initNavigation() {
    const siteHeader = document.querySelector('.site-header');
    const mobileToggle = document.getElementById('mobileNavToggle');
    const mobileDrawer = document.getElementById('mobileNavDrawer');
    const scrollTopBtn = document.getElementById('scrollTopBtn');

    if (mobileToggle && mobileDrawer) {
      mobileToggle.addEventListener('click', () => {
        mobileDrawer.classList.toggle('open');
        const isOpen = mobileDrawer.classList.contains('open');
        mobileToggle.setAttribute('aria-expanded', isOpen);
      });

      mobileDrawer.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
          mobileDrawer.classList.remove('open');
          mobileToggle.setAttribute('aria-expanded', 'false');
        });
      });
    }

    window.addEventListener('scroll', () => {
      const y = window.scrollY || document.documentElement.scrollTop;
      if (siteHeader) {
        if (y > 20) {
          siteHeader.classList.add('scrolled');
        } else {
          siteHeader.classList.remove('scrolled');
        }
      }
      if (scrollTopBtn) {
        if (y > 350) {
          scrollTopBtn.classList.add('visible');
        } else {
          scrollTopBtn.classList.remove('visible');
        }
      }
    }, { passive: true });

    if (scrollTopBtn) {
      scrollTopBtn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }
  }

  // =========================================================================
  // 2. Cinematographic Hero Showcase Slider
  // =========================================================================
  function initHeroSlider() {
    const slides = document.querySelectorAll('.showcase-slide');
    const progressPills = document.querySelectorAll('.progress-pill-track');
    const prevBtn = document.getElementById('sliderPrevBtn');
    const nextBtn = document.getElementById('sliderNextBtn');
    const sliderContainer = document.getElementById('showcaseSlider');

    if (slides.length === 0 || progressPills.length === 0) return;

    let currentSlide = 0;
    const totalSlides = slides.length;
    const slideDuration = 6000;
    let slideTimer = null;
    let progressInterval = null;
    let progressStartTime = 0;
    let isPaused = false;

    function showSlide(index) {
      if (index >= totalSlides) index = 0;
      if (index < 0) index = totalSlides - 1;

      slides.forEach((s, i) => {
        if (i === index) {
          s.classList.add('active');
        } else {
          s.classList.remove('active');
        }
      });

      progressPills.forEach((p, i) => {
        const fill = p.querySelector('.progress-pill-fill');
        p.classList.remove('active', 'completed');
        if (fill) fill.style.width = '0%';

        if (i < index) {
          p.classList.add('completed');
          if (fill) fill.style.width = '100%';
        } else if (i === index) {
          p.classList.add('active');
        }
      });

      currentSlide = index;
      startProgress();
    }

    function startProgress() {
      clearInterval(progressInterval);
      clearTimeout(slideTimer);
      if (isPaused) return;

      progressStartTime = Date.now();
      const currentFill = progressPills[currentSlide]?.querySelector('.progress-pill-fill');

      progressInterval = setInterval(() => {
        if (isPaused) return;
        const elapsed = Date.now() - progressStartTime;
        const pct = Math.min((elapsed / slideDuration) * 100, 100);
        if (currentFill) currentFill.style.width = `${pct}%`;

        if (elapsed >= slideDuration) {
          clearInterval(progressInterval);
          showSlide(currentSlide + 1);
        }
      }, 50);
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        showSlide(currentSlide - 1);
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        showSlide(currentSlide + 1);
      });
    }

    progressPills.forEach((pill, idx) => {
      pill.addEventListener('click', () => {
        showSlide(idx);
      });
    });

    if (sliderContainer) {
      sliderContainer.addEventListener('mouseenter', () => { isPaused = true; });
      sliderContainer.addEventListener('mouseleave', () => {
        if (isPaused) {
          isPaused = false;
          startProgress();
        }
      });

      // Touch swipe support
      let touchStartX = 0;
      let touchEndX = 0;
      sliderContainer.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
      }, { passive: true });

      sliderContainer.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        if (touchStartX - touchEndX > 50) {
          showSlide(currentSlide + 1);
        } else if (touchEndX - touchStartX > 50) {
          showSlide(currentSlide - 1);
        }
      }, { passive: true });
    }

    showSlide(0);
  }

  // =========================================================================
  // 3. Instant Search & Category Filter System
  // =========================================================================
  function initSearchAndFilter() {
    const searchInput = document.getElementById('searchPostsInput') || document.getElementById('postSearchInput');
    const filterPills = document.querySelectorAll('.filter-pill, .filter-pill-btn');
    const postCards = document.querySelectorAll('.blog-post-card, .feed-post-card');
    const counterStatus = document.getElementById('feedCounterStatus') || document.getElementById('filterCounterStatus');

    if (!searchInput && filterPills.length === 0) return;

    let activeCategory = 'all';
    let activeSearchQuery = '';

    function filterPosts() {
      let visibleCount = 0;

      postCards.forEach(card => {
        const cardCategory = card.getAttribute('data-category') || '';
        const cardText = (card.innerText || '').toLowerCase();
        const matchesCategory = (activeCategory === 'all' || cardCategory.includes(activeCategory));
        const matchesSearch = !activeSearchQuery || cardText.includes(activeSearchQuery);

        if (matchesCategory && matchesSearch) {
          card.style.display = 'flex';
          visibleCount++;
        } else {
          card.style.display = 'none';
        }
      });

      if (counterStatus) {
        counterStatus.textContent = `Mostrando ${visibleCount} de ${postCards.length} trabajos`;
      }
    }

    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        activeSearchQuery = e.target.value.trim().toLowerCase();
        filterPosts();
      });
    }

    filterPills.forEach(pill => {
      pill.addEventListener('click', () => {
        filterPills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeCategory = pill.getAttribute('data-filter') || 'all';
        filterPosts();
      });
    });
  }

  // =========================================================================
  // 4. Automatic "Copiar Código" Buttons with Language Detection
  // =========================================================================
    function initCodeCopyButtons() {
    // Purge ALL existing buttons across the document to prevent any duplicate on re-initialization
    document.querySelectorAll('.btn-copy-code').forEach(btn => btn.remove());
    document.querySelectorAll('[data-has-copy-btn]').forEach(el => el.removeAttribute('data-has-copy-btn'));

    // Only target pre elements (the code block itself)
    const codeBlocks = document.querySelectorAll('pre');
    codeBlocks.forEach(block => {
      // Avoid attaching if already has button
      if (block.querySelector('.btn-copy-code')) return;
      block.dataset.hasCopyBtn = 'true';

      // Detect language or tag
      let langTag = 'R CODE';
      const className = (block.className || '') + ' ' + (block.parentElement?.className || '');
      const textSample = block.innerText || '';
      if (className.includes('python') || textSample.includes('def ') || textSample.includes('import pandas')) {
        langTag = 'PYTHON';
      } else if (textSample.startsWith('##') || textSample.startsWith('>')) {
        langTag = 'CONSOLA R';
      }

      block.setAttribute('data-lang', langTag);

      const btn = document.createElement('button');
      btn.className = 'btn-copy-code';
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Copiar código al portapapeles');
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
        <span>Copiar</span>
      `;

      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const codeElement = block.querySelector('code') || block;
        const textToCopy = codeElement.innerText;

        navigator.clipboard.writeText(textToCopy).then(() => {
          btn.classList.add('copied');
          btn.innerHTML = `
            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            <span>¡Copiado!</span>
          `;
          setTimeout(() => {
            btn.classList.remove('copied');
            btn.innerHTML = `
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              <span>Copiar</span>
            `;
          }, 2000);
        });
      });

      block.style.position = 'relative';
      block.appendChild(btn);
    });
  }

  // =========================================================================
  // Dynamic Moving Posts Carousel Controller
  // =========================================================================
  function initPostsCarousel() {
    const viewport = document.getElementById('carouselViewport');
    const track = document.getElementById('carouselTrack');
    const prevBtn = document.getElementById('carouselScrollPrev');
    const nextBtn = document.getElementById('carouselScrollNext');

    if (!viewport || !track) return;

    // Pause animation when hovering
    viewport.addEventListener('mouseenter', () => {
      track.classList.add('paused');
    });

    viewport.addEventListener('mouseleave', () => {
      track.classList.remove('paused');
    });

    // Arrow navigation
    if (prevBtn) {
      prevBtn.addEventListener('click', (e) => {
        e.preventDefault();
        track.classList.add('paused');
        viewport.scrollBy({ left: -340, behavior: 'smooth' });
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', (e) => {
        e.preventDefault();
        track.classList.add('paused');
        viewport.scrollBy({ left: 340, behavior: 'smooth' });
      });
    }

    // Touch swipe / drag support
    let isDown = false;
    let startX = 0;
    let scrollLeft = 0;

    viewport.addEventListener('mousedown', (e) => {
      isDown = true;
      track.classList.add('paused');
      startX = e.pageX - viewport.offsetLeft;
      scrollLeft = viewport.scrollLeft;
    });

    viewport.addEventListener('mouseleave', () => {
      isDown = false;
    });

    viewport.addEventListener('mouseup', () => {
      isDown = false;
    });

    viewport.addEventListener('mousemove', (e) => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - viewport.offsetLeft;
      const walk = (x - startX) * 1.5;
      viewport.scrollLeft = scrollLeft - walk;
    });
  }

  // =========================================================================
  // 5. VERIFIED KNOWLEDGE BASE (14 Published Quantitative Studies + Career)
  // =========================================================================
  const PROFILE = {
    name: 'Jesús Benjamín Zerpa',
    title: 'Economista y Quantitative Data Scientist',
    summary: 'Profesional de finanzas con más de 14 años de experiencia en planificación financiera corporativa, presupuestos maestros y control de gestión en empresas de diversos sectores económicos. Cuenta con amplias fortalezas en modelización econométrica avanzada, Deep Learning, Business Intelligence y ciencia de datos reproducible en R y Python.',
    interests: 'Planificación financiera corporativa, presupuestos maestros, modelización econométrica avanzada, Deep Learning (Redes Neuronales LSTM en PyTorch) y Business Intelligence.',
    portfolio: 'El portafolio reúne 15 estudios técnicos y modelos cuantitativos publicados entre mayo de 2020 y octubre de 2026 en RStudio, Python (PyTorch / Redes Neuronales LSTM), Excel/VBA y Microsoft Power BI.'
  };

  const CONTACT = {
    email: 'JesusZerpaEconomia@Gmail.Com',
    phone: '+58 424 148 78 70',
    whatsapp: 'https://wa.me/584241487870',
    telegram: '@jesusbz21',
    telegramUrl: 'https://t.me/jesusbz21',
    linkedin: 'https://www.linkedin.com/in/jes%C3%BAs-zerpa-807646129/',
    github: 'https://github.com/JesusBZ',
    rpubs: 'https://rpubs.com/JesusZ',
    form: 'formulario.html'
  };

  const CAREER = [
    {
      company: 'Banesco Banco Universal', role: 'Ejecutivo de Negocios (Servicios Financieros)',
      keys: ['banesco', 'banco', 'banca'],
      detail: 'Inicio de su formación en finanzas dentro del Sistema Financiero Nacional. Gestionó una cartera de clientes naturales y jurídicos: apertura de cuentas, elaboración de expedientes crediticios, asesoría de servicios, ventas y benchmarking.'
    },
    {
      company: 'Grupo Empresarial Admibien', role: 'Subgerente de Finanzas',
      keys: ['admibien'],
      detail: 'Compañías dedicadas a la gestión y financiamiento de recursos económicos. En el área de Finanzas y Presupuesto, apoyando al departamento legal, gestionó y supervisó la planeación y planificación financiera.'
    },
    {
      company: 'CG Security Group (filial Segutronic)', role: 'Gestión Senior de Presupuesto',
      keys: ['segutronic', 'cg security', 'seguridad'],
      detail: 'Empresa de obras de seguridad tecnológica para la Banca Nacional. Encargado de la planificación, elaboración y conducción del presupuesto financiero de más de 32 obras a nivel nacional, supervisión y control del presupuesto operativo, cierre administrativo de obras y estudio de rentabilidad por obra terminada.'
    },
    {
      company: 'Grupo de empresas Multimédica', role: 'Coordinador Corporativo de Presupuesto y Control (Contraloría Corporativa)',
      keys: ['multimedica', 'salud', 'equipos medicos'],
      detail: 'Empresas de importación, distribución y comercialización de equipos médico-quirúrgicos tecnológicos y descartables, con varios proyectos en España. Responsabilidades: planificación, formulación y elaboración del presupuesto, reportes avanzados, supervisión del cierre contable y análisis financiero mensual, proyección del entorno macroeconómico, y evaluación y formulación de proyectos de inversión.'
    },
    {
      company: 'Grupo Mistral', role: 'Planificador Corporativo de Finanzas',
      keys: ['mistral', 'farmacias'],
      detail: 'Grupo con producción industrial de productos de cuidado e higiene personal, distribución y logística nacional, y una cadena de más de 90 farmacias. Responsable del diseño y desarrollo de informes corporativos para la V.P. de Finanzas de las tres divisiones (Empaque, Consumo y Farma): informes financieros, operativos y presupuestarios, análisis del entorno económico, proyección de variables macroeconómicas, premisas presupuestarias e informes avanzados de Business Intelligence.'
    },
    {
      company: 'Consorcio Credicard', role: 'Gerente de Planificación Financiera y Presupuesto',
      keys: ['credicard', 'medios de pago', 'actual', 'actualmente', 'hoy'],
      detail: 'Empresa pionera y líder en servicios de medios de pago, con más de 30 años en el sector (cargo más reciente indicado en su perfil). Diseña, dirige, evalúa y controla el proceso de planificación financiera, el seguimiento financiero y la gestión del presupuesto; proyecciones financieras, formulación de casos de negocio y generación e implementación del modelo presupuestario.'
    }
  ];

  const PROJECTS = [
    {
      n: 15, title: 'Modelización de Volatilidad Asimétrica GARCH, Valor en Riesgo (VaR) y Expected Shortfall (CVaR) del Bitcoin en Python (2014–2026)', file: 'volatilidad-garch-var-cvar-python.html', pubDate: 'Octubre de 2026',
      keys: ['garch python', 'egarch python', 'gjr-garch', 'cvar', 'expected shortfall', 'kupiec', 'christoffersen', 'hansen', 'skewed-t', 'skewt', 'basilea', 'frtb', 'etf bitcoin', 'news impact curve', 'curva de impacto', 'volatility targeting', 'position sizing', 'stop-loss', 'trabajo 15', 'proyecto 15', 'volatilidad 2026'],
      summary: 'Actualización econométrica en Python (Octubre de 2026) del estudio original de Mayo 2020 (Proyecto2.html) sobre 4,425 sesiones diarias de BTC-USD (septiembre de 2014 a octubre de 2026). Cuantifica la transición estructural de tres regímenes de microestructura (incluyendo los ETFs Spot institucionales aprobados en enero de 2024), estima por Máxima Verosimilitud modelos sGARCH, EGARCH(2,1) y GJR-GARCH bajo distribución Skewed Student-t de Hansen, e integra Expected Shortfall (CVaR 99%), backtesting de Kupiec y Christoffersen y reglas de ejecución cuantitativa para inversores y mesas de trading.',
      methods: 'Estimación por Máxima Verosimilitud (MLE) en Python (librería arch, SciPy, statsmodels) de cinco especificaciones AR(1)-GARCH; interpretación de parámetros MLE y cálculo de la Vida Media del choque (Half-Life = 79.9 sesiones); Curva de Impacto de Noticias (News Impact Curve - NIC); ajuste de colas pesadas con distribución Skewed Student-t de Hansen; cono de volatilidad Bootstrap a 90 días (5,000 trayectorias); contrastes de Kupiec (POF) y Christoffersen sobre 2,464 sesiones (2020–2026); y motor de Volatility Targeting, Position Sizing, Stop-Loss condicional y arbitraje de opciones.',
      results: 'Transición de régimen: la volatilidad anualizada se comprimió desde 73.47% en la etapa Pre-Institucional (2014–2020) y 67.97% en el ciclo 2020–2024 (curtosis 25.55) hasta 46.88% en la Era de ETFs Spot (2024–2026, -26.59 pp de reducción estructural), cerrando en 35.59% anual (1.863% diaria) al 29 de octubre de 2026. Ganador MLE: AR(1)-EGARCH(2,1) Skewed-t de Hansen (mu = +0.0998%, phi_1 = -0.0521, omega = 0.0650, alpha_1 = +0.3696, alpha_2 = -0.1580, gamma_1 = +0.0224, beta_1 = 0.9914 con Half-Life = 79.9 días, grados de libertad eta = 2.770, LogLik = -10,767.53, AIC = 21,553.06, superando por +584.64 puntos de LogLik al modelo sGARCH-Normal). En el Backtesting regulatorio 2020–2026 (2,464 días), sGARCH-Normal fue rechazado al 1% (41 violaciones, 1.664%, Kupiec p = 0.0025), mientras que AR(1)-EGARCH(2,1) Skewed-t fue aprobado en Zona Verde de Basilea con 21 violaciones (0.852%, Kupiec LR_uc = 0.572, p = 0.4496; Christoffersen LR_cc = 2.436, p = 0.2958), estimando al cierre un VaR 99% de -4.600% (,000 USD por ), un CVaR 99% de -6.961% (,610 USD por ), un peso óptimo por Volatility Targeting (meta 20% anual) de 56.20% (,961 USD), un Stop-Loss condicional al 99% en -4.600% y un apalancamiento institucional máximo seguro de 4.76x.',
      tools: 'Python 3.11+, arch (Oxford Financial Econometrics), SciPy (scipy.stats), Statsmodels, NumPy, Pandas, yfinance y Plotly.js.'
    },
    {
      n: 14, title: 'Deep Portfolio Optimization con Redes Neuronales LSTM en Python sobre la Cartera del Portafolio Tangente de Markowitz (2020–2026)', file: 'deep-portfolio-lstm-python.html', pubDate: 'Octubre de 2026',
      keys: ['lstm', 'deep learning', 'redes neuronales', 'red neuronal', 'pytorch', 'python', 'deep portfolio', '5000', '5,000', 'actualizacion', '2026', 'sortino', 'sharpe', 'sp500', 's&p 500', 'trabajo 14', 'proyecto 14'],
      summary: 'Actualización cuantitativa (Octubre de 2026) que audita con datos reales de mercado qué habría pasado con un capital inicial de $5,000.00 USD invertido el 30 de abril de 2020 hasta el 29 de octubre de 2026 (1,633 sesiones bursátiles) en las 6 acciones del S&P 500 del Portafolio Tangente original (MSFT, JNJ, MA, PEP, WMT y MCD), y desarrolla un nuevo modelo de Deep Portfolio Optimization con Redes Neuronales Recurrentes (LSTM) en Python y PyTorch.',
      methods: 'Descarga de series diarias ajustadas (2010–2026) con yfinance; construcción de tensores secuenciales 3D (ventana deslizante L=60 sesiones con retornos logarítmicos, momentum de 21 días y volatilidad realizada); red neuronal DeepPortfolioLSTM en PyTorch (2 capas LSTM de 64 unidades, Dropout 0.25 y capa Softmax con restricción long-only w_i >= 0, suma = 1) entrenada mediante función de pérdida diferenciable de Ratio de Sharpe-Sortino y validación walk-forward con costos de transacción (10 bps) y 5 gráficos dinámicos interactivos en Plotly.',
      results: 'Resultados auditados fuera de muestra para $5,000.00 USD (30-Abr-2020 al 29-Oct-2026): (1) Portafolio Tangente de Markowitz 2020 (Buy & Hold): alcanzó $11,208.95 USD (+124.18%, ganancia neta +$6,208.95 USD, CAGR 13.26%, logrando la menor volatilidad anualizada de 13.11% y el menor Max Drawdown en 2022 de -12.85%, Sharpe 0.86, Sortino 1.09). (2) Portafolio Mínima Varianza 2020: alcanzó $8,889.30 USD (+77.79%, CAGR 9.26%, Vol 13.38%, Max DD -12.15%). (3) Portafolio Equiponderado (1/N): alcanzó $10,858.31 USD (+117.17%, CAGR 12.71%). (4) Benchmark S&P 500 (^GSPC): alcanzó $13,132.10 USD (+162.64%, CAGR 16.06%, Vol 16.75%, Max DD -25.43%). (5) Nuevo Deep Portfolio Optimization con LSTM (Python & PyTorch): alcanzó $15,057.19 USD (+201.14%, ganancia neta +$10,057.19 USD, CAGR 18.53%, Vol 16.24%, Ratio de Sharpe 1.02, Ratio de Sortino 1.24, Max DD -18.30%), superando al S&P 500 en +$1,925.09 USD y al Portafolio Tangente estático en +$3,848.24 USD.',
      tools: 'Python 3.11+, PyTorch (torch.nn.LSTM), NumPy, Pandas, SciPy (scipy.optimize SLSQP), Scikit-Learn, yfinance y Plotly.js.'
    },
    {
      n: 1, title: 'Modelo de Pronósticos para Ventas en Volumen en R', file: 'modelo-ventas.html', pubDate: 'Mayo de 2020',
      keys: ['ventas', 'volumen', 'tsstudio', 'sarima', 'arima', 'ets', 'tslm', 'backtesting', 'retail', 'tiendas', 'series temporales', 'series de tiempo', 'pronostico de ventas', 'krispin', 'holt-winters'],
      summary: 'Pronóstico de las ventas en volumen (unidades) de una cadena de tiendas al detal en Venezuela ("empresa X"), período 2014-2019, con horizonte de 12 meses. Adaptación del enfoque de Rami Krispin (2019) con el paquete TSstudio en RStudio.',
      methods: 'Análisis exploratorio, descomposición aditiva y multiplicativa de la serie, análisis estacional y de autocorrelación (ACF/PACF); estimación y comparación de 6 modelos (ARIMA, SARIMA, ETS, Holt-Winters y TSLM) bajo enfoque tradicional (training/test) y validación por Backtesting con intervalos de confianza al 80% y 95%.',
      results: 'La serie presenta un patrón estacional marcado, una ruptura estructural alrededor de 2016 y decrecimiento no lineal. Se selecciona el modelo SARIMA para evaluar residuos y proyectar 12 meses con bandas de confianza.',
      tools: 'R, TSstudio (v0.1.6), forecast, plotly.'
    },
    {
      n: 2, title: 'Modelización de la Volatilidad Condicional y Valor en Riesgo (VaR) del Bitcoin', file: 'Proyecto2.html', pubDate: 'Mayo de 2020',
      keys: ['var', 'valor en riesgo', 'volatilidad', 'garch', 'egarch', 'gjrgarch', 'tgarch', 'sgarch', 'riesgo', 'ljung', 'efecto arch', 'value at risk'],
      summary: 'Evaluación econométrica de la volatilidad condicional y del Valor en Riesgo (VaR) de los retornos diarios del Bitcoin (BTC-USD) entre enero 2014 y enero 2020 en RStudio.',
      methods: 'Modelos sGARCH, TGARCH, eGARCH y gjrGARCH con tres distribuciones de error (Normal, t-Student y GED); selección con AIC, MAE y MSE; pruebas Ljung-Box y de efecto ARCH (LM); backtesting del VaR al 99% (1% de significancia).',
      results: 'El modelo eGARCH(2,1) con distribución t-Student obtuvo el mejor ajuste según el criterio AIC, capturando la asimetría de choques sobre la volatilidad. En el VaR al 1%, se estima el umbral de pérdida diaria máxima esperada con pruebas de excedencias.',
      tools: 'R, rugarch / rmgarch, quantmod, PerformanceAnalytics, zoo.'
    },
    {
      n: 3, title: 'Ciencia de Datos para la Empresa: Aprendizaje Automático (Machine Learning) en R', file: 'proyecto3.html', pubDate: 'Mayo de 2020',
      keys: ['machine learning', 'aprendizaje automatico', 'bicicletas', 'bikeshare', 'bike', 'tidymodels', 'parsnip', 'recipes', 'yardstick', 'ml', 'inteligencia artificial'],
      summary: 'Flujo de Machine Learning en RStudio para predecir, con horizonte de 6 meses, la demanda diaria del sistema Capital Bikeshare (Metro DC, EE. UU.) con el dataset Bike Sharing del repositorio UCI.',
      methods: 'Preprocesamiento e ingeniería de variables con recipes, especificación de regresión en parsnip (motor lm), ensamblaje en workflows, partición entrenamiento/prueba, evaluación con yardstick e intervalos de predicción al 80% y 95%.',
      results: 'Precisión fuera de muestra: RMSE ≈ 1437, R² ≈ 0,379 y MAE ≈ 1045, sirviendo como arquitectura reproducible para pronósticos empresariales.',
      tools: 'R, tidymodels (workflows, parsnip, recipes, yardstick), tidyverse, tidyquant, timetk, plotly, knitr, kableExtra.'
    },
    {
      n: 4, title: 'Portafolios de Inversión: Portafolio Eficiente y Portafolio Tangente de Markowitz', file: 'proyecto4.html', pubDate: 'Mayo de 2020',
      keys: ['markowitz', 'frontera', 'fronteras eficientes', 'portafolio eficiente', 'tangente', 'cartera', 'diversificacion', 'acciones', 'microsoft', 'msft', 'pepsico', 'walmart', 'mcdonald', 'mastercard', 'johnson'],
      summary: 'Optimización Media-Varianza de Markowitz sobre seis acciones líderes del S&P 500 de distintos sectores: Microsoft (MSFT), Johnson & Johnson (JNJ), Mastercard (MA), PepsiCo (PEP), Walmart (WMT) y McDonald\'s (MCD), período enero 2010 - abril 2020. Incluye consultas de audio de la comunidad académica y enlaza con la actualización 2026 en Python y Redes Neuronales LSTM (Trabajo #14).',
      methods: 'Rentabilidad logarítmica diaria, rendimientos esperados y volatilidades, matriz de varianza-covarianza y correlaciones; construcción de la Frontera Eficiente en RStudio con restricción long-only; cálculo del Portafolio de Mínima Varianza Global y del Portafolio Tangente (máximo Ratio de Sharpe).',
      results: 'Pesos del Portafolio Tangente (Abril 2020, máximo Ratio de Sharpe): MA 34,41%, MSFT 17,90%, MCD 16,51%, WMT 15,16%, JNJ 12,16% y PEP 3,85% (retorno medio diario de 0,08% y riesgo diario de 0,99%). Pesos del Portafolio de Mínima Varianza Global (Abril 2020): JNJ 33,42%, MCD 24,49%, PEP 20,53%, WMT 19,65%, MSFT 1,91% y MA 0,00% (retorno medio diario de 0,05% y riesgo mínimo diario de 0,87%). En la actualización de octubre de 2026 (Trabajo #14), $5,000 USD invertidos en este Portafolio Tangente alcanzaron $11,208.95 USD (+124.18%) y con el nuevo modelo LSTM en Python alcanzaron $15,057.19 USD (+201.14%).',
      tools: 'R, fPortfolio, quantmod, PerformanceAnalytics, tseries.'
    },
    {
      n: 5, title: 'Evaluación y Formulación de Proyectos de Inversión: Caso Global Nutrition España', file: 'EvaluacionProyecto.html', pubDate: 'Junio de 2020',
      keys: ['evaluacion', 'formulacion', 'proyecto de inversion', 'proyectos de inversion', 'global nutrition', 'espana', 'nutricion', 'renal', 'estudio de mercado', 'factibilidad', 'inversion', 'van', 'tir', 'wacc'],
      summary: 'Participación de Jesús Zerpa en la evaluación y formulación financiera del proyecto "Global Nutrition España 2017", emprendido por un grupo empresarial del sector salud para penetrar el mercado de la Unión Europea con un complemento nutricional especializado para pacientes con enfermedad renal crónica y gestionar financiamiento institucional en España.',
      methods: 'Identificación del producto, estudio legal, estudio de mercado, estudio técnico (producción tercerizada) y estudio económico-financiero proforma; presentación ejecutiva, informe técnico y cuentas previsionales.',
      results: 'Documenta integralmente la presentación ejecutiva, el informe de factibilidad y el plan de cuentas previsionales del proyecto.',
      tools: 'Modelización Financiera Corporativa, Presupuesto de Capital y documentos de Microsoft Office incrustados.'
    },
    {
      n: 6, title: 'Financial Dashboard Corporativo', file: 'Dashboard.html', pubDate: 'Junio de 2020',
      keys: ['dashboard', 'tablero', 'excel', 'vba', 'visual basic', 'kpi', 'estado de resultados', 'ganancias y perdidas', 'panel de control'],
      summary: 'Cuadro de mando financiero desarrollado por Jesús Zerpa en Excel y Visual Basic (VBA) con cuatro niveles de desagregación e interpretación basados en el Estado de Ganancias y Pérdidas (P&G), diseñado originalmente para la Vicepresidencia de Finanzas de un grupo empresarial (producción, distribución, venta al mayor y retail).',
      methods: 'Centraliza en un solo reporte automatizado múltiples entregables de cierre mensual, incorpora alertas visuales (highlights), exportación automatizada a PowerPoint/PDF, esquema de seguridad en VBA, asistente interactivo de inducción al usuario e integración con Power BI.',
      results: 'Optimiza los tiempos de respuesta en sesiones de directorio y permite el seguimiento en tiempo real de márgenes de ventas, EBITDA y rentabilidad neta.',
      tools: 'Microsoft Excel, Visual Basic for Applications (VBA), Power BI.'
    },
    {
      n: 7, title: 'Exploración de Datos Macroeconómicos con RStudio', file: 'proyecto7.html', pubDate: 'Junio de 2020',
      keys: ['macroeconomia', 'macroeconomicos', 'gapminder', 'pib', 'esperanza de vida', 'preston', 'quandl', 'banco mundial', 'wdi', 'leaflet', 'estadistica espacial', 'exploracion de datos'],
      summary: 'Análisis econométrico y visual de datos globales del paquete Gapminder (esperanza de vida al nacer y PIB per cápita) y descarga automatizada de Indicadores del Desarrollo Mundial (WDI) del Banco Mundial para Venezuela mediante Quandl, cerrando con estadística espacial interactiva en leaflet.',
      methods: 'Gráficos interactivos y animados (plotly, gganimate), suavizado LOESS y GAM, diagramas de caja intercontinentales, Curva de Preston y regresión lineal múltiple lm(lifeExp ~ log(gdpPercap) + pop + continent) con coefplot.',
      results: 'Cuantifica la relación positiva no lineal entre ingreso per cápita y esperanza de vida, destacando la distinción metodológica entre correlación estadística y causalidad.',
      tools: 'R, plotly, gganimate, ggplot2, gapminder, Quandl, knitr, kableExtra, purrr, dygraphs, rnaturalearth, sp, rgeos, leaflet, coefplot, ggrepel, socviz.'
    },
    {
      n: 8, title: 'Sistema Integrado Geográfico (SIG) con Power Map 3D', file: 'powermap.html', pubDate: 'Julio de 2020',
      keys: ['sig', 'geografico', 'geoespacial', 'power map', 'mapa', 'mapas', 'territorial', 'gis', 'geomarketing'],
      summary: 'Análisis geoespacial tridimensional de una cadena de tiendas retail en Venezuela: recorrido histórico de cierre de un modelo de datos de ventas en volumen utilizando Microsoft Power Map 3D.',
      methods: 'Georreferenciación de registros comerciales en una capa cartográfica 3D con gráficos de barras sobre el globo terráqueo para evaluar concentración regional de demanda.',
      results: 'Demostración visual interactiva en video del recorrido espaciotemporal para soporte de decisiones de geomarketing y logística.',
      tools: 'Microsoft Power Map 3D, Bing Maps Engine.'
    },
    {
      n: 9, title: 'Pronósticos con Prophet para el Bitcoin y Ether', file: 'bitcoin-ether-pronosticos-con-prophet.html', pubDate: 'Julio de 2020',
      keys: ['prophet', 'facebook', 'ether', 'eth', 'ethereum'],
      summary: 'Pronósticos cuantitativos mediante el algoritmo Prophet (Core Data Science de Facebook, v0.6.1) sobre los precios de cierre ajustados diarios de Bitcoin (BTC) y Ether (ETH), período 2016-2020, con horizonte predictivo de 31 días.',
      methods: 'Modelización aditiva generalizada de tendencia no lineal por tramos (changepoints), ciclos y estacionalidad; visualización interactiva en dygraphs y descomposición de patrones semanales y anuales.',
      results: 'Estima para el Bitcoin (en julio 2020) soporte estadístico en torno a 9.000 USD con banda entre 7.500 USD y 10.500 USD hacia agosto 2020, detallando las fortalezas de Prophet en series con marcada estacionalidad y deriva.',
      tools: 'R, prophet, tidyverse, dygraphs.'
    },
    {
      n: 10, title: 'Simulación Monte Carlo en la Gestión de Carteras', file: 'modelizacion-monte-carlo-portafolios.html', pubDate: 'Julio de 2020',
      keys: ['monte carlo', 'montecarlo', 'simulacion', 'simulaciones', 'estocastico'],
      summary: 'Aplicación de la Simulación Estocástica de Monte Carlo en RStudio sobre el Portafolio Tangente de Markowitz (MSFT, JNJ, MA, PEP, WMT y MCD, enero 2010 - abril 2020).',
      methods: 'Generación de 100 trayectorias estocásticas basadas en la distribución histórica de los 6 activos para proyectar el crecimiento compuesto de 1 USD invertido durante 120 meses (10 años).',
      results: 'Modela el abanico probabilístico de trayectorias de crecimiento y expone con rigor las premisas y limitaciones de los métodos de Monte Carlo en mercados financieros.',
      tools: 'R, tidyquant, tidyverse, timetk, broom, highcharter.'
    },
    {
      n: 11, title: 'Power BI: Herramienta Líder de Business Intelligence', file: 'power-bi.html', pubDate: 'Agosto de 2020',
      keys: ['power bi', 'business intelligence', 'inteligencia de negocios', 'inteligencia empresarial', 'microsoft'],
      summary: 'Estudio sobre arquitectura de Business Intelligence en Microsoft Power BI con dos cuadros de mando (dashboards) corporativos interactivos desplegados en vivo en la nube de Microsoft.',
      methods: 'Explica la integración de fuentes de datos heterogéneas, el servicio en la nube de Power BI, el posicionamiento en el Cuadrante Mágico de Gartner y despliega dos tableros ejecutivos interactivos.',
      results: 'Permite explorar en tiempo real dos dashboards interactivos de ventas, márgenes y KPIs financieros.',
      tools: 'Microsoft Power BI.'
    },
    {
      n: 12, title: 'Análisis de Procesos Comerciales y de Negocio en RStudio (Data & Process Mining)', file: 'analisis-de-procesos-comerciales-data-mining.html', pubDate: 'Agosto de 2020',
      keys: ['data mining', 'mineria de datos', 'procesos', 'process mining', 'bupar', 'event log', 'eventlog', 'kdd', 'mapa de procesos'],
      summary: 'Fundamentos de Minería de Datos (KDD) y aplicación práctica de Minería de Procesos (Process Mining) en RStudio sobre registros de eventos (Event Logs) de atención de pacientes en un centro de salud privado.',
      methods: 'Construcción de un objeto event-log, auditoría de trazas y frecuencias de actividades, mapas de procesos bajo perfiles de frecuencia y rendimiento (Throughput Time), mapas animados y análisis de precedencia.',
      results: 'Identifica visual y cuantitativamente las rutas críticas, tiempos de procesamiento y cuellos de botella operativos.',
      tools: 'R, suite bupaR (edeaR, processmapR, processanimateR).'
    },
    {
      n: 13, title: 'Bitcoin Trading en RStudio — Capítulo 1: El Análisis Técnico', file: 'trading-medias-moviles-rstudio.html', pubDate: 'Octubre de 2020',
      keys: ['trading', 'analisis tecnico', 'medias moviles', 'media movil', 'rsi', 'macd', 'bollinger', 'momentum', 'roc', 'velas', 'quantmod', 'ttr'],
      summary: 'Fundamentos del Análisis Técnico bursátil (Teoría de Dow, los 3 principios del análisis técnico, pioneros e historia) e implementación programática de indicadores sobre la serie histórica del Bitcoin en RStudio.',
      methods: 'Gráficos de líneas, barras y velas japonesas (Candlesticks), y cálculo algorítmico de Media Móvil Simple (SMA), Media Móvil Exponencial (EMA), Bandas de Bollinger, Momentum, Tasa de Cambio (ROC), MACD y RSI.',
      results: 'Documenta la formulación matemática y las reglas de interpretación de señales (sobrecompra, sobreventa, cruces de medias y divergencias) para cada indicador.',
      tools: 'R, quantmod, TTR.'
    }
  ];

  // =========================================================================
  // 6. AI Quantitative Copilot HUD
  // =========================================================================
  function ensureCopilotMounted() {
    if (document.getElementById('copilotToggleBtn')) return;
    const div = document.createElement('div');
    div.innerHTML = `
      <button id="copilotToggleBtn" class="copilot-bubble-btn" aria-label="Abrir Asistente" title="Consultar con el Asistente del Portafolio">
        <span class="bubble-status-dot"></span>
        <svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>
      </button>

      <div id="copilotChatWindow" class="copilot-chat-window" role="dialog" aria-label="Asistente del Portafolio">
        <div class="copilot-header">
          <div class="header-copilot-title">
            <div class="copilot-avatar-icon">
              <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm0 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm4 8a4 4 0 0 0-8 0v2h8v-2z"/></svg>
            </div>
            <div class="copilot-header-info">
              <span class="copilot-name-label">Asistente del Portafolio</span>
              <span class="copilot-tech-badge">
                <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#10b981;"></span>
                <span>Google Gemini · Base Verificada</span>
              </span>
            </div>
          </div>
          <div class="copilot-header-actions">
            <button id="copilotClearBtn" class="copilot-action-icon-btn" title="Reiniciar conversación">
              <svg viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>
            </button>
            <button id="copilotCloseBtn" class="copilot-action-icon-btn" title="Cerrar asistente">
              <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>

        <div class="copilot-chips-strip">
          <button class="quick-chip-btn" data-prompt="¿Cuánto rindieron $5,000 USD en el Portafolio Tangente de 2020 y cuánto logró el nuevo modelo con Redes Neuronales LSTM en Python (2026)?">Portafolio LSTM 2026 ($5,000 USD)</button>
          <button class="quick-chip-btn" data-prompt="¿Qué proyectos tiene el portafolio de Jesús Zerpa?">Los 15 Estudios</button>
          <button class="quick-chip-btn" data-prompt="¿Cuál es la trayectoria profesional de Jesús Zerpa?">Trayectoria</button>
          <button class="quick-chip-btn" data-prompt="Explícame la actualización 2026 en Python de Volatilidad GARCH, VaR y Expected Shortfall (CVaR) del Bitcoin">GARCH &amp; CVaR Python 2026</button>
          <button class="quick-chip-btn" data-prompt="¿Cómo contacto a Jesús?">Contacto</button>
        </div>

        <div id="copilotHistoryBox" class="copilot-history-box"></div>

        <div class="copilot-input-area">
          <input type="text" id="copilotInput" class="copilot-input-field" placeholder="Pregunta sobre los 15 estudios, Python LSTM, R o trayectoria..." autocomplete="off" />
          <button id="copilotSendBtn" class="copilot-send-btn" aria-label="Enviar mensaje" title="Enviar mensaje">
            <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </div>
      </div>
    `;
    while (div.firstChild) document.body.appendChild(div.firstChild);
  }

  // ---------- Text helpers ----------
  function norm(s) {
    return (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }
  function hasTerm(q, term) {
    const t = norm(term);
    if (t.length <= 3) return new RegExp('(^|[^a-z0-9])' + t.replace(/[.*+?^${}()|[\]\\&]/g, '\\$&') + '([^a-z0-9]|$)').test(q);
    return q.includes(t);
  }
  function hasAny(q, terms) { return terms.some(t => hasTerm(q, t)); }

  // ---------- Answer builders (only verified data) ----------
  function projectLink(p) { return `[Abrir el estudio #${p.n}](${p.file})`; }

  function answerProject(p) {
    return `**Trabajo #${p.n}: ${p.title}** (${p.pubDate})

` +
      `- **Resumen:** ${p.summary}
` +
      `- **Metodología:** ${p.methods}
` +
      `- **Resultados verificados:** ${p.results}
` +
      `- **Herramientas:** ${p.tools}

` + projectLink(p);
  }

  function answerProjectList(list, intro) {
    return (intro || `El portafolio cuenta con **${PROJECTS.length} estudios publicados** (entre mayo de 2020 y octubre de 2026):`) + '\n\n' +
      list.map(p => `- **#${p.n} (${p.pubDate}) — ${p.title}**: [ver estudio](${p.file})`).join('\n') +
      '\n\nPregúntame por cualquiera de ellos (por ejemplo, el nuevo estudio #14 con Redes Neuronales LSTM en Python o el Portafolio Tangente #4) para conocer su metodología y resultados exactos.';
  }

  function answerCareer() {
    return `**Trayectoria profesional de ${PROFILE.name}** (en orden cronológico):

` +
      CAREER.map(c => `- **${c.company}**: ${c.role}`).join('\n') +
      `

${PROFILE.summary}

Puedes preguntarme por cualquiera de estas empresas para conocer el detalle de sus funciones.`;
  }

  function answerCompany(c) {
    return `**${c.company}** — ${c.role}

${c.detail}`;
  }

  function answerContact() {
    return `**Canales de contacto de ${PROFILE.name}:**

` +
      `- **Teléfono / WhatsApp:** [${CONTACT.phone}](${CONTACT.whatsapp})
` +
      `- **Correo electrónico:** [${CONTACT.email}](mailto:${CONTACT.email})
` +
      `- **Telegram:** [${CONTACT.telegram}](${CONTACT.telegramUrl})
` +
      `- **LinkedIn:** [Perfil profesional](${CONTACT.linkedin})
` +
      `- **GitHub:** [JesusBZ](${CONTACT.github}) | **RPubs:** [JesusZ](${CONTACT.rpubs})
` +
      `- **Formulario directo:** [Enviar mensaje](${CONTACT.form})`;
  }

  function answerProfile() {
    return `**${PROFILE.name}** — ${PROFILE.title}.

${PROFILE.summary}

**Áreas de fortaleza:** ${PROFILE.interests}

${PROFILE.portfolio}`;
  }

  function answerTools() {
    return `**Stack tecnológico y librerías utilizadas en los 15 estudios del portafolio:**

` +
      `- **Python & Deep Learning (Estudio #14 — 2026):** Python 3.11+, PyTorch (\`torch.nn.LSTM\`), NumPy, Pandas, SciPy (\`scipy.optimize\` SLSQP), Scikit-Learn, yfinance y Plotly.js.
` +
      `- **R / RStudio (Estudios #1 al #13):** TSstudio, forecast, rugarch / rmgarch, PerformanceAnalytics, tidymodels (recipes, parsnip, workflows, yardstick), tidyquant, timetk, prophet, fPortfolio, tseries, bupaR, quantmod, TTR, Quandl, leaflet, ggplot2, plotly y highcharter.
` +
      `- **Business Intelligence & Finanzas Corporativas:** Microsoft Power BI, Power Query, DAX, Power Map 3D, Microsoft Excel avanzado y Visual Basic (VBA).`;
  }

  function unknownAnswer() {
    return `No tengo esa información específica verificada dentro del portafolio. Puedo responderte con total precisión sobre:

` +
      `- Los **${PROJECTS.length} estudios publicados** (escribe "proyectos" o "LSTM 2026")
- La auditoría de **$5,000 USD (2020–2026)** sobre el Portafolio Tangente y Redes Neuronales LSTM
- La **trayectoria profesional** de Jesús Zerpa (escribe "trayectoria")
- **Herramientas y lenguajes** (R, Python, PyTorch, Power BI, VBA)
- **Datos de contacto** (escribe "contacto")

` +
      `Para consultas personalizadas o casos de negocio puedes escribirle directamente por [WhatsApp](${CONTACT.whatsapp}) o mediante el [formulario de contacto](${CONTACT.form}).`;
  }

  // ---------- Intent router ----------
  function getVerifiedAnswer(raw) {
    const q = norm(raw);

    if (/^(hola|buenas|buenos dias|buenas tardes|buenas noches|saludos|hey)\b/.test(q) && q.length < 30) {
      return `Hola. Soy el asistente técnico del portafolio de **${PROFILE.name}**. Conozco en detalle sus **${PROJECTS.length} estudios cuantitativos** en R y Python (incluyendo el nuevo modelo 2026 de Deep Portfolio Optimization con Redes Neuronales LSTM), su trayectoria profesional y sus datos de contacto. ¿En qué puedo ayudarte?`;
    }
    if (hasAny(q, ['gracias', 'thank'])) return 'Con gusto. Si deseas profundizar en otro estudio (como la actualización 2026 en Python con LSTM) o en la trayectoria de Jesús, estoy a tu disposición.';

    if (hasAny(q, ['5000', '5,000', 'lstm', 'pytorch', 'red neuronal', 'redes neuronales', 'deep portfolio', '2026', 'actualizacion'])) {
      return answerProject(PROJECTS[0]);
    }

    if (hasAny(q, ['vectores autorregresivos', 'vector autorregresivo', 'granger', 'modelo var multivariado'])) {
      return 'El repositorio incluye una práctica técnica en RStudio sobre **Modelización Econométrica de Vectores Autorregresivos VAR(p)** (Noviembre de 2020) con pruebas de raíz unitaria (Dickey-Fuller Aumentado), causalidad de Granger y funciones de impulso-respuesta: [Ver documento técnico](trading-vectores-autoregresivos-en-rstudio.html).';
    }

    if (hasAny(q, ['contacto', 'contactar', 'correo', 'email', 'e-mail', 'telefono', 'whatsapp', 'telegram', 'linkedin', 'escribirle', 'llamar', 'contratar', 'consultoria', 'cotizacion'])) {
      return answerContact();
    }

    if (hasAny(q, ['universidad', 'donde estudio', 'que estudio', 'estudios universitarios', 'titulo universitario', 'formacion academica', 'postgrado', 'maestria', 'doctorado', 'certificacion'])) {
      return `El portafolio indica que ${PROFILE.name} es **Economista y Quantitative Data Scientist**, con más de 14 años de experiencia y amplias fortalezas en planificación financiera corporativa, presupuestos maestros, modelización econométrica avanzada, Deep Learning y Business Intelligence. Para detalles académicos adicionales puedes consultar su [LinkedIn](${CONTACT.linkedin}) o escribirle por el [formulario](${CONTACT.form}).`;
    }

    // Specific company
    const company = CAREER.find(c => hasAny(q, c.keys) && !hasAny(q, ['bitcoin', 'cartera', 'portafolio de']));
    if (company && hasAny(q, ['banesco', 'admibien', 'segutronic', 'cg security', 'multimedica', 'mistral', 'credicard', 'actualmente', 'cargo actual', 'trabaja hoy', 'donde trabaja'])) {
      return answerCompany(company);
    }

    // Project scoring
    const scored = PROJECTS.map(p => {
      let s = 0;
      p.keys.forEach(k => { if (hasTerm(q, k)) s += k.includes(' ') ? 2 : 1; });
      if (hasTerm(q, p.title)) s += 5;
      return { p, s };
    }).filter(x => x.s > 0).sort((a, b) => b.s - a.s);

    if (scored.length) {
      const top = scored[0].s;
      const ties = scored.filter(x => x.s === top).map(x => x.p);
      if (ties.length === 1) return answerProject(ties[0]);
      return answerProjectList(ties, 'Encontré estos estudios relacionados con tu consulta:');
    }

    // Generic "bitcoin / cripto" question
    if (hasAny(q, ['bitcoin', 'btc', 'cripto', 'criptomoneda', 'criptomonedas'])) {
      return answerProjectList(PROJECTS.filter(p => [15, 2, 9, 13].includes(p.n)), 'El portafolio incluye cuatro estudios cuantitativos sobre Bitcoin y criptoactivos (incluyendo la edición 2026 en Python con EGARCH Skewed-t y Expected Shortfall):');
    }

    if (hasAny(q, ['trayectoria', 'experiencia', 'empresas', 'cargos', 'carrera', 'curriculum', 'cv', 'trabajado', 'laboral', 'donde ha trabajado'])) {
      return answerCareer();
    }

    if (hasAny(q, ['proyectos', 'trabajos', 'portafolio', 'publicaciones', 'modelos', 'que has hecho', 'que hace', 'lista', 'estudios'])) {
      return answerProjectList(PROJECTS);
    }

    if (hasAny(q, ['quien es', 'quien eres', 'jesus zerpa', 'jesus benjamin', 'sobre jesus', 'sobre el autor', 'biografia', 'acerca de'])) {
      return answerProfile();
    }

    if (hasAny(q, ['herramientas', 'paquetes', 'librerias', 'software', 'tecnologias', 'habilidades', 'lenguajes', 'stack', 'fortalezas'])) {
      return answerTools();
    }

    return null;
  }

  // ---------- Google Gemini API (Server-side key on Vercel + Local Dev Proxy) ----------
  const GEMINI_BACKEND_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? '/api/chat'
    : 'https://gemini-backend-ecru.vercel.app/api/chat';

  function buildVerifiedContext() {
    const career = CAREER.map(c => `- ${c.company} | ${c.role}: ${c.detail}`).join('\n');
    const projects = PROJECTS.map(p =>
      `### Trabajo #${p.n} (${p.pubDate}): ${p.title} (enlace: ${p.file})
` +
      `De qué trata: ${p.summary}
Metodología: ${p.methods}
Resultados verificados: ${p.results}
Herramientas: ${p.tools}`
    ).join('\n\n');
    return `PERFIL: ${PROFILE.name}. ${PROFILE.title}. ${PROFILE.summary} Áreas de fortaleza: ${PROFILE.interests} ${PROFILE.portfolio}
` +
      `REGLA DE ESTILO DEL AUTOR: Utiliza siempre las expresiones "con amplia experiencia" y "con sólidas fortalezas" para describir las competencias del autor.

` +
      `TRAYECTORIA PROFESIONAL (orden cronológico; Consorcio Credicard es el cargo más reciente indicado en su perfil):
${career}

` +
      `TRABAJOS PUBLICADOS EN EL PORTAFOLIO (${PROJECTS.length} estudios en total, incluyendo el nuevo Trabajo #14 de Octubre 2026 con Redes Neuronales LSTM en Python):
${projects}

` +
      `CONTACTO: WhatsApp/teléfono ${CONTACT.phone} (${CONTACT.whatsapp}); correo ${CONTACT.email}; Telegram ${CONTACT.telegram}; ` +
      `LinkedIn ${CONTACT.linkedin}; GitHub ${CONTACT.github}; RPubs ${CONTACT.rpubs}; formulario: ${CONTACT.form}`;
  }

  function buildGroundedPrompt(question) {
    return `Eres el asistente técnico cuantitativo del portafolio web de ${PROFILE.name}. REGLAS ESTRICTAS:
` +
      `1. Sobre Jesús Benjamín Zerpa, su trayectoria y sus 15 trabajos responde ÚNICAMENTE con el CONTEXTO VERIFICADO de abajo.
` +
      `2. El portafolio tiene ahora 15 estudios publicados (los 13 originales de 2020 en RStudio/BI/Excel y el nuevo Trabajo #14 de Octubre de 2026: "Deep Portfolio Optimization con Redes Neuronales LSTM en Python sobre la Cartera del Portafolio Tangente de Markowitz", archivo deep-portfolio-lstm-python.html).
` +
      `3. Emplea siempre los términos "fortalezas" y "experiencia" para referirte al perfil de Jesús Zerpa.
` +
      `4. No inventes cifras, empresas, cargos ni fechas. Al citar resultados (como la auditoría de $5,000.00 USD de 2020 a 2026 donde el Portafolio Tangente alcanzó $11,208.95 USD [+124.18%] y el modelo LSTM en Python alcanzó $15,057.19 USD [+201.14%]), cita las cifras exactas del contexto.
` +
      `5. Responde en español, con tono técnico financiero y económico, de forma clara y concisa, usando Markdown simple (negritas y viñetas con "- "), sin emojis.
` +
      `6. Cuando menciones un trabajo, incluye siempre su enlace con formato [Ver estudio](archivo.html).

` +
      `CONTEXTO VERIFICADO:
${buildVerifiedContext()}

` +
      `PREGUNTA DEL VISITANTE: ${question}`;
  }

  async function askGemini(question, history) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 25000);
    try {
      const res = await fetch(GEMINI_BACKEND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: buildGroundedPrompt(question), history: history }),
        signal: ctrl.signal
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (!data || !data.text) throw new Error('Respuesta vacía');
      return data.text;
    } finally {
      clearTimeout(timer);
    }
  }

  function initCopilotHUD() {
    ensureCopilotMounted();

    const SESSION_KEY = 'jesus_copilot_session_v2';
    try {
      ['gemini_user_api_key', 'jesus_copilot_history_v2', 'jesus_copilot_history_v3', 'jesus_copilot_session_v1'].forEach(k => {
        localStorage.removeItem(k);
        sessionStorage.removeItem(k);
      });
      const nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
      const isReload = nav ? nav.type === 'reload' : (performance.navigation && performance.navigation.type === 1);
      if (isReload) sessionStorage.removeItem(SESSION_KEY);
    } catch (e) { /* ignore */ }

    const chatToggleBtn = document.getElementById('copilotToggleBtn');
    const chatWindow = document.getElementById('copilotChatWindow');
    const chatCloseBtn = document.getElementById('copilotCloseBtn');
    const chatClearBtn = document.getElementById('copilotClearBtn');
    const chatSendBtn = document.getElementById('copilotSendBtn');
    const chatInput = document.getElementById('copilotInput');
    const chatHistoryBox = document.getElementById('copilotHistoryBox');
    const quickChips = document.querySelectorAll('.quick-chip-btn');
    const WELCOME = `Hola. Soy el asistente técnico del portafolio de **${PROFILE.name}**, conectado con **Google Gemini**. Conozco en detalle sus **${PROJECTS.length} estudios y modelos cuantitativos** en R y Python (incluyendo la auditoría 2020–2026 de $5,000 USD sobre el Portafolio Tangente con Redes Neuronales LSTM), su trayectoria corporativa y sus canales de contacto. ¿Qué te gustaría consultar?`;
    let chatHistory = [];

    function escapeHtml(str) {
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function formatMarkdown(text) {
      let h = escapeHtml(text || '');
      h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
      h = h.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, label, url) => {
        const cleanUrl = String(url || '').trim();
        const isSafe = /^(https?:\/\/|mailto:|tel:|[a-zA-Z0-9_\-\/\.]+\.html(#[a-zA-Z0-9_\-]+)?$)/i.test(cleanUrl);
        if (!isSafe) return label;
        const ext = /^https?:/i.test(cleanUrl);
        return `<a href="${cleanUrl}"${ext ? ' target="_blank" rel="noopener noreferrer"' : ''}>${label}</a>`;
      });
      const lines = h.split('\n');
      let out = '', inList = false;
      lines.forEach(line => {
        const m = line.match(/^\s*-\s+(.*)$/);
        if (m) {
          if (!inList) { out += '<ul style="padding-left:1.15rem;margin:0.35rem 0;">'; inList = true; }
          out += `<li style="margin:0.2rem 0;">${m[1]}</li>`;
        } else {
          if (inList) { out += '</ul>'; inList = false; }
          out += line.trim() ? `${line}<br>` : '<br>';
        }
      });
      if (inList) out += '</ul>';
      return out.replace(/(<br>){3,}/g, '<br><br>');
    }

    function scrollToBottom() { if (chatHistoryBox) chatHistoryBox.scrollTop = chatHistoryBox.scrollHeight; }

    function appendMessage(text, role) {
      if (!chatHistoryBox) return;
      const bubble = document.createElement('div');
      bubble.className = `chat-bubble ${role}`;
      bubble.innerHTML = role === 'bot'
        ? `<strong>Asistente:</strong> ${formatMarkdown(text)}`
        : `<strong>Tú:</strong> ${escapeHtml(text)}`;
      chatHistoryBox.appendChild(bubble);
      scrollToBottom();
    }

    function saveSession() {
      try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(chatHistory.slice(-30))); } catch (e) { /* ignore */ }
    }

    function resetChat() {
      chatHistoryBox.innerHTML = '';
      appendMessage(WELCOME, 'bot');
    }

    resetChat();
    try {
      const saved = JSON.parse(sessionStorage.getItem(SESSION_KEY) || '[]');
      if (Array.isArray(saved) && saved.length) {
        chatHistory = saved;
        saved.forEach(item => appendMessage(item.text, item.role));
      }
    } catch (e) { chatHistory = []; }

    if (chatToggleBtn && chatWindow) {
      chatToggleBtn.addEventListener('click', () => {
        chatWindow.classList.toggle('open');
        if (chatWindow.classList.contains('open')) { chatInput?.focus(); scrollToBottom(); }
      });
      chatCloseBtn?.addEventListener('click', () => chatWindow.classList.remove('open'));
      chatClearBtn?.addEventListener('click', () => {
        chatHistory = [];
        try { sessionStorage.removeItem(SESSION_KEY); } catch (e) { /* ignore */ }
        resetChat();
      });
    }

    quickChips.forEach(chip => {
      chip.addEventListener('click', () => {
        if (!chatInput) return;
        chatInput.value = chip.getAttribute('data-prompt') || chip.textContent.trim();
        sendMessage();
      });
    });

    function showTyping() {
      const el = document.createElement('div');
      el.id = 'copilotTypingIndicator';
      el.className = 'chat-bubble bot';
      el.innerHTML = '<div class="typing-wave-container"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div>';
      chatHistoryBox.appendChild(el);
      scrollToBottom();
    }
    function hideTyping() { document.getElementById('copilotTypingIndicator')?.remove(); }

    let busy = false;
    async function sendMessage() {
      if (!chatInput || busy) return;
      const message = chatInput.value.trim();
      if (!message) return;
      chatInput.value = '';
      appendMessage(message, 'user');
      busy = true;
      if (chatSendBtn) chatSendBtn.disabled = true;
      showTyping();

      const geminiHistory = chatHistory.slice(-8).map(h => ({
        role: h.role === 'user' ? 'user' : 'model',
        parts: [{ text: h.text }]
      }));

      let answer;
      try {
        answer = await askGemini(message, geminiHistory);
      } catch (err) {
        console.warn('Gemini fallback local activado:', err);
        answer = getVerifiedAnswer(message) || unknownAnswer();
      }

      hideTyping();
      appendMessage(answer, 'bot');
      chatHistory.push({ role: 'user', text: message }, { role: 'bot', text: answer });
      saveSession();
      busy = false;
      if (chatSendBtn) chatSendBtn.disabled = false;
      chatInput.focus();
    }

    chatSendBtn?.addEventListener('click', sendMessage);
    chatInput?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
  }

  // =========================================================================
  // Initialize Everything on DOM Ready
  // =========================================================================

  // =========================================================================
  // Remove Disqus "Recommendations" strip (keeps the comments thread intact)
  // =========================================================================
  function initDisqusRecommendationsBlocker() {
    const thread = document.getElementById('disqus_thread');
    if (!thread) return;
    const purge = () => {
      thread.querySelectorAll('iframe').forEach(f => {
        const src = f.getAttribute('src') || '';
        if (src.indexOf('/recommendations') !== -1) f.remove();
      });
    };
    purge();
    new MutationObserver(purge).observe(thread, { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] });
  }

  function initAll() {
    initNavigation();
    initHeroSlider();
    initPostsCarousel();
    initSearchAndFilter();
    initCodeCopyButtons();
    initCopilotHUD();
    initDisqusRecommendationsBlocker();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

})();

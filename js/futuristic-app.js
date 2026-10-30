/**
 * JesusBZ - Futuristic Corporate FinTech Platform JS
 * Author: Jesús Benjamín Zerpa | Economist & Data Scientist
 * Features:
 *   1. Cinematographic Hero Showcase (Smooth Crossfade + Progress Pills + Touch Swipe)
 *   2. Instant Search & Category Filters for Blog Stream
 *   3. AI Quantitative Copilot HUD with Google Gemini Ultra / Pro Direct Integration
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
    const searchInput = document.getElementById('postSearchInput');
    const filterPills = document.querySelectorAll('.filter-pill-btn');
    const postCards = document.querySelectorAll('.feed-post-card');
    const counterStatus = document.getElementById('filterCounterStatus');

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
  // 5. Advanced Knowledge Base of All 13 Models & Author Credentials
  // =========================================================================
  const MODELS_KNOWLEDGE_BASE = {
    "var": {
      title: "Modelización de la Volatilidad y Valor en Riesgo (VaR) del Bitcoin",
      file: "Proyecto2.html",
      methodology: "Modelos GARCH simétricos y asimétricos (sGARCH, tGARCH, eGARCH, gjrGARCH) con distribución de error T-Student mediante el paquete 'rugarch'.",
      key_finding: "El modelo eGARCH(2,1) con distribución T-Student resultó ser el de mejor ajuste econométrico (menor AIC). El análisis de VaR al 99% determinó que una pérdida extrema solo se supera el 1% del tiempo.",
      application: "Gestión cuantitativa de riesgos para fondos que incorporan criptoactivos de alta volatilidad y estimación de reservas de capital de solvencia."
    },
    "ventas": {
      title: "Modelo de Pronósticos para Ventas en Volumen",
      file: "modelo-ventas.html",
      methodology: "Series temporales con modelos ARIMA, descomposición estacional STL y backtesting mediante las paqueterías TSstudio y forecast en R.",
      key_finding: "Permite proyectar volúmenes mensuales de comercialización reduciendo el error humano y optimizando la cadena de suministro.",
      application: "Planificación presupuestaria anual, programación de producción e inventarios y presupuestos maestros."
    },
    "machine learning": {
      title: "Aprendizaje Automático (Machine Learning) en Ciencia de Datos",
      file: "proyecto3.html",
      methodology: "Algoritmos supervisados y no supervisados (Random Forest, SVM, redes neuronales y clustering) en R.",
      key_finding: "Ajuste autónomo del pronóstico a partir de patrones históricos complejos multivariables no lineales.",
      application: "Scoring crediticio, segmentación analítica de clientes y detección de transacciones financieras anómalas."
    },
    "markowitz": {
      title: "Portafolio de Fronteras Eficientes de Markowitz",
      file: "proyecto4.html",
      methodology: "Teoría Moderna de Carteras (Harry Markowitz) con optimización cuadrática, maximización del ratio de Sharpe y minimización de varianza con el paquete 'Portfolio'.",
      key_finding: "Construcción de carteras eficientes con 6 acciones del S&P 500 diversificando el riesgo no sistemático.",
      application: "Gestión institucional de carteras, Asset Allocation estratégico y optimización riesgo-retorno."
    },
    "prophet": {
      title: "Pronósticos con Prophet para Bitcoin y Ether",
      file: "bitcoin-ether-pronosticos-con-prophet.html",
      methodology: "Algoritmo Prophet (Facebook Core Data Science) basado en Modelos Aditivos Generalizados (GAM) con estacionalidades diarias, semanales y anuales.",
      key_finding: "Modelado robusto de tendencias no lineales con detección automática de puntos de quiebre estructural (changepoints).",
      application: "Previsión algorítmica de precios de activos cripto en horizontes de mediano y largo plazo."
    },
    "monte carlo": {
      title: "Simulación Monte Carlo para Gestión de Carteras",
      file: "modelizacion-monte-carlo-portafolios.html",
      methodology: "Generación de 10,000+ trayectorias estocásticas basadas en Movimiento Browniano Geométrico y descomposición de Cholesky en R.",
      key_finding: "Distribución de probabilidad de retornos terminales y cálculo de VaR estocástico multivariante.",
      application: "Pruebas de estrés financiero (stress testing) y análisis de solvencia para carteras corporativas."
    },
    "evaluacion": {
      title: "Evaluación y Formulación de Proyectos de Inversión",
      file: "EvaluacionProyecto.html",
      methodology: "Modelos de flujo de caja libre descontado (DCF), cálculo de VAN, TIR, Payback y costo promedio ponderado de capital WACC. Caso real 'Global Nutrition España'.",
      key_finding: "Determinación de la viabilidad económica y análisis de sensibilidad del retorno ante fluctuaciones macroeconómicas de tipo de cambio y demanda.",
      application: "Decisiones de asignación de capital (CAPEX), M&A y formulación de casos de negocio corporativos."
    },
    "dashboard": {
      title: "Financial Dashboard Ejecutivo en Excel y VBA",
      file: "FinancialDashboard.htm",
      methodology: "Modelado financiero dinámico y automatización mediante Visual Basic for Applications (VBA) y R.",
      key_finding: "Visualización integral de estados de resultados, KPIs operativos clave (EBITDA, ROI, Margen Bruto y Neto) y reporting automatizado.",
      application: "Control presupuestario y seguimiento mensual para comités de dirección y alta gerencia."
    },
    "power bi": {
      title: "Power BI para Business Intelligence Financiero",
      file: "power-bi.html",
      methodology: "Modelado de datos en esquema de estrella, fórmulas DAX avanzadas y ETL en Power Query.",
      key_finding: "Tableros ejecutivos interactivos que conectan datos exógenos con métricas de productividad de la empresa.",
      application: "Inteligencia de negocios y control del comportamiento del ROI en tiempo real."
    },
    "data mining": {
      title: "Análisis de Procesos de Negocio con Data Mining en RStudio",
      file: "analisis-de-procesos-comerciales-data-mining.html",
      methodology: "Metodología KDD (Knowledge Discovery in Databases), reglas de asociación (Apriori) y patrones frecuentes en R.",
      key_finding: "Identificación de relaciones ocultas entre variables comerciales no detectables mediante análisis tradicional.",
      application: "Venta cruzada (cross-selling), análisis de canasta de compra y aumento del ticket promedio comercial."
    },
    "trading": {
      title: "Trading Cuantitativo con Medias Móviles y Análisis Técnico",
      file: "trading-medias-moviles-rstudio.html",
      methodology: "Estrategias de cruces de medias móviles (SMA/EMA), osciladores técnicos (RSI, MACD) y backtesting sistemático.",
      key_finding: "Sistemas cuantitativos con reglas objetivas de entrada/salida y estricto control de drawdown.",
      application: "Trading algorítmico disciplinado eliminando sesgos emocionales en la toma de decisiones."
    },
    "var vectores": {
      title: "Modelos de Vectores Autorregresivos (VAR) en RStudio",
      file: "trading-vectores-autoregresivos-en-rstudio.html",
      methodology: "Sistemas de ecuaciones simultáneas VAR, contrastes de raíces unitarias (ADF), selección de retardos (AIC/BIC) y Causalidad de Granger con el paquete 'vars'.",
      key_finding: "Identificación de interdependencias dinámicas entre múltiples series macroeconómicas y financieras simultáneas.",
      application: "Previsiones multivariantes y modelización de la transmisión de choques financieros en mercados interconectados."
    },
    "gapminder": {
      title: "Exploración de Datos Multidimensionales con Gapminder",
      file: "proyecto7.html",
      methodology: "Visualización dinámica multivariable con ggplot2 y Plotly para datos de panel longitudinales.",
      key_finding: "Descubrimiento de tendencias socioeconómicas globales a largo plazo.",
      application: "Analítica exploratoria de datos para investigación macroeconómica y estudios de mercado."
    },
    "mapas": {
      title: "Visualización Geoespacial 3D y Mapas de Calor Comercial",
      file: "powermap.html",
      methodology: "Mapeo 3D geoespacial, densidad por coordenadas y segmentación geográfica.",
      key_finding: "Localización de puntos calientes de demanda y cobertura de canales de distribución.",
      application: "Logística comercial, apertura de sucursales y optimización territorial."
    }
  };

  const AUTHOR_DOSSIER = {
    name: "Jesús Benjamín Zerpa",
    title: "Economista & Quantitative Data Scientist",
    email: "JesusZerpaEconomia@Gmail.Com",
    telegram: "@jesusbz21",
    linkedin: "https://www.linkedin.com/in/jesús-zerpa-807646129/",
    github: "https://github.com/JesusBZ",
    rpubs: "https://rpubs.com/JesusZ",
    experience: "Más de 14 años de experiencia en planificación financiera, presupuestos maestros, control de gestión y modelación econométrica avanzada.",
    companies: [
      "Consorcio Credicard: Gerente de Planificación Financiera y Presupuesto (Líder en medios de pago)",
      "Grupo Mistral: Planificador Corporativo de Finanzas (Divisiones Empaque, Consumo y Farma con 90+ farmacias)",
      "Grupo de Empresas Multimédica: Coordinador Corporativo de Presupuesto y Control (Sector salud / Proyectos internacionales en España)",
      "Segutronic (CG Security Group): Especialista Senior de Presupuesto (32 obras bancarias de seguridad tecnológica)",
      "Grupo Empresarial Admibien: Subgerente de Finanzas",
      "Banesco Banco Universal: Ejecutivo de Negocios en Servicios Financieros"
    ]
  };

  // =========================================================================
  // 6. AI Quantitative Copilot HUD
  // =========================================================================
  function ensureCopilotMounted() {
    if (document.getElementById('copilotToggleBtn')) return;
    const div = document.createElement('div');
    div.innerHTML = `
      <!-- Floating Copilot Button -->
      <button id="copilotToggleBtn" class="copilot-bubble-btn" aria-label="Abrir Asistente Analítico" title="Consultar con el Asistente Analítico">
        <span class="bubble-status-dot"></span>
        <svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>
      </button>

      <!-- Copilot Chat Window -->
      <div id="copilotChatWindow" class="copilot-chat-window" role="dialog" aria-label="Ventana de Asistente Analítico">
        
        <!-- Header -->
        <div class="copilot-header">
          <div class="header-copilot-title">
            <div class="copilot-avatar-icon">
              <svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2zm0 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm4 8a4 4 0 0 0-8 0v2h8v-2z"/></svg>
            </div>
            <div class="copilot-header-info">
              <span class="copilot-name-label">Asistente Cuantitativo</span>
              <span class="copilot-tech-badge">
                <span id="copilotStatusDot" style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#10b981;"></span>
                <span id="copilotEngineLabel">Gemini Cuantitativo</span>
              </span>
            </div>
          </div>
          <div class="copilot-header-actions">
            <button id="copilotKeyBtn" class="copilot-action-icon-btn" title="Configurar Licencia Google Gemini Ultra / Pro" aria-label="Configurar API Key">
              <svg viewBox="0 0 24 24"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
            </button>
            <button id="copilotClearBtn" class="copilot-action-icon-btn" title="Reiniciar Conversación">
              <svg viewBox="0 0 24 24"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>
            </button>
            <button id="copilotCloseBtn" class="copilot-action-icon-btn" title="Cerrar Asistente">
              <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>

        <!-- Google Gemini Ultra API Key Configuration Drawer -->
        <div id="copilotApiKeyDrawer" class="copilot-api-key-drawer" style="display: none;">
          <div class="api-key-drawer-header">
            <span class="api-drawer-title">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 14.5h-2v-5h2v5zm0-7h-2V7h2v2.5z"/></svg>
              Licencia Google Gemini Ultra / Pro
            </span>
            <button id="closeKeyDrawerBtn" class="btn-close-drawer" aria-label="Cerrar">&times;</button>
          </div>
          <p class="api-drawer-desc">
            Pega tu API Key de Google AI Studio para activar el razonamiento cognitivo más avanzado directamente:
          </p>
          <div class="api-key-input-row">
            <input type="password" id="geminiApiKeyInput" class="gemini-key-input" placeholder="AIzaSy..." autocomplete="off" />
            <button id="saveApiKeyBtn" class="btn-save-key">Guardar</button>
          </div>
          <div id="apiKeyStatusLabel" class="api-status-label"></div>
        </div>

        <!-- Quick Prompt Chips -->
        <div class="copilot-chips-strip">
          <button class="quick-chip-btn" data-prompt="¿En qué consiste el modelo de volatilidad y VaR para Bitcoin?">Modelo VaR Bitcoin</button>
          <button class="quick-chip-btn" data-prompt="¿Qué proyectos de Machine Learning tiene Jesús en el portafolio?">Proyectos Machine Learning</button>
          <button class="quick-chip-btn" data-prompt="¿Cómo se aplica Prophet para predecir Bitcoin y Ether?">Pronósticos con Prophet</button>
          <button class="quick-chip-btn" data-prompt="¿Cuál es la trayectoria profesional de Jesús Zerpa?">Trayectoria Profesional</button>
        </div>

        <!-- Chat History -->
        <div id="copilotHistoryBox" class="copilot-history-box">
          <div class="chat-bubble bot">
            <strong>Asistente Cuantitativo:</strong> Saludos. Soy el asistente técnico del portafolio de <strong>Jesús Zerpa</strong>. Conozco los detalles metodológicos de sus 13 modelos analíticos en R, estimaciones econométricas, algoritmos de Machine Learning y trayectoria corporativa. ¿Sobre qué modelo o requerimiento te gustaría profundizar?
          </div>
        </div>

        <!-- Input Area -->
        <div class="copilot-input-area">
          <input type="text" id="copilotInput" class="copilot-input-field" placeholder="Escribe tu consulta analítica o técnica..." autocomplete="off" />
          <button id="copilotSendBtn" class="copilot-send-btn" aria-label="Enviar Mensaje" title="Enviar Mensaje">
            <svg viewBox="0 0 24 24"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </div>

      </div>
    `;

    while (div.firstChild) {
      document.body.appendChild(div.firstChild);
    }
  }

  function initCopilotHUD() {
    ensureCopilotMounted();

    const vercelURL = 'https://gemini-backend-ecru.vercel.app/api/chat';
    const chatToggleBtn = document.getElementById('copilotToggleBtn');
    const chatWindow = document.getElementById('copilotChatWindow');
    const chatCloseBtn = document.getElementById('copilotCloseBtn');
    const chatClearBtn = document.getElementById('copilotClearBtn');
    const chatKeyBtn = document.getElementById('copilotKeyBtn');
    const keyDrawer = document.getElementById('copilotApiKeyDrawer');
    const closeKeyDrawerBtn = document.getElementById('closeKeyDrawerBtn');
    const apiKeyInput = document.getElementById('geminiApiKeyInput');
    const saveApiKeyBtn = document.getElementById('saveApiKeyBtn');
    const apiKeyStatusLabel = document.getElementById('apiKeyStatusLabel');
    const engineLabel = document.getElementById('copilotEngineLabel');
    const statusDot = document.getElementById('copilotStatusDot');
    const chatSendBtn = document.getElementById('copilotSendBtn');
    const chatInput = document.getElementById('copilotInput');
    const chatHistoryBox = document.getElementById('copilotHistoryBox');
    const quickChips = document.querySelectorAll('.quick-chip-btn');

    const STORAGE_KEY = 'jesus_copilot_history_v2';
    const API_KEY_STORAGE = 'gemini_user_api_key';
    let chatHistory = [];

    // Check stored API key
    function updateKeyStatusUI() {
      const storedKey = localStorage.getItem(API_KEY_STORAGE);
      if (storedKey) {
        if (apiKeyInput) apiKeyInput.value = storedKey;
        if (apiKeyStatusLabel) {
          apiKeyStatusLabel.className = 'api-status-label active';
          apiKeyStatusLabel.textContent = '🟢 Licencia Gemini Ultra / Pro Activa';
        }
        if (engineLabel) engineLabel.textContent = 'Gemini Ultra Direct';
        if (statusDot) statusDot.style.background = '#10b981';
      } else {
        if (apiKeyStatusLabel) {
          apiKeyStatusLabel.className = 'api-status-label';
          apiKeyStatusLabel.textContent = '⚪ Modo: Motor Cuantitativo Local';
        }
        if (engineLabel) engineLabel.textContent = 'Gemini Cuantitativo';
        if (statusDot) statusDot.style.background = '#0052cc';
      }
    }
    updateKeyStatusUI();

    // Toggle API Key Drawer
    if (chatKeyBtn && keyDrawer) {
      chatKeyBtn.addEventListener('click', () => {
        keyDrawer.style.display = keyDrawer.style.display === 'none' ? 'flex' : 'none';
        if (keyDrawer.style.display === 'flex') apiKeyInput?.focus();
      });
    }

    if (closeKeyDrawerBtn && keyDrawer) {
      closeKeyDrawerBtn.addEventListener('click', () => {
        keyDrawer.style.display = 'none';
      });
    }

    if (saveApiKeyBtn && apiKeyInput) {
      saveApiKeyBtn.addEventListener('click', () => {
        const val = apiKeyInput.value.trim();
        if (val) {
          localStorage.setItem(API_KEY_STORAGE, val);
          appendMessage('🔑 **Licencia Google Gemini Ultra / Pro guardada.** A partir de ahora tus consultas analíticas se procesan directamente con la API de Google.', 'bot');
        } else {
          localStorage.removeItem(API_KEY_STORAGE);
          appendMessage('Licencia retirada. Usando motor local de base de conocimiento.', 'bot');
        }
        updateKeyStatusUI();
        if (keyDrawer) keyDrawer.style.display = 'none';
      });
    }

    // Load chat history from localStorage
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        chatHistory = JSON.parse(saved);
        chatHistory.forEach(item => {
          if (item.role === 'user') {
            appendMessage(item.parts[0].text, 'user', false);
          } else if (item.role === 'model') {
            appendMessage(item.parts[0].text, 'bot', false);
          }
        });
      }
    } catch (err) {
      console.warn('Could not load chat history from localStorage', err);
    }

    function saveHistory() {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory.slice(-20)));
      } catch (e) {
        console.warn('Could not save to localStorage', e);
      }
    }

    // Chat Window Open/Close
    if (chatToggleBtn && chatWindow) {
      chatToggleBtn.addEventListener('click', () => {
        chatWindow.classList.toggle('open');
        if (chatWindow.classList.contains('open')) {
          chatInput?.focus();
          scrollToBottom();
        }
      });

      chatCloseBtn?.addEventListener('click', () => {
        chatWindow.classList.remove('open');
      });

      chatClearBtn?.addEventListener('click', () => {
        chatHistory = [];
        localStorage.removeItem(STORAGE_KEY);
        chatHistoryBox.innerHTML = `
          <div class="chat-bubble bot">
            <strong>Asistente Cuantitativo:</strong> Sesión reiniciada. Puedes consultar cualquier duda técnica sobre los 13 modelos analíticos, metodologías VaR, series temporales, Machine Learning o sobre la trayectoria ejecutiva de Jesús Zerpa.
          </div>
        `;
      });
    }

    // Quick Chips click
    quickChips.forEach(chip => {
      chip.addEventListener('click', () => {
        const prompt = chip.getAttribute('data-prompt') || chip.textContent.trim();
        if (chatInput) {
          chatInput.value = prompt;
          sendMessage();
        }
      });
    });

    function formatMarkdown(text) {
      if (!text) return '';
      let formatted = text.replace(/```([a-zA-Z]*)\n([\s\S]*?)```/g, function (match, lang, code) {
        const cleanCode = code.trim();
        return `<pre><code class="language-${lang}">${escapeHtml(cleanCode)}</code></pre>`;
      });
      formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');
      formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      formatted = formatted.replace(/^\s*[-*]\s+(.*)$/gim, '<li>$1</li>');
      formatted = formatted.replace(/(<li>.*<\/li>)/gim, '<ul style="padding-left: 1.25rem; margin: 0.4rem 0;">$1</ul>');
      formatted = formatted.replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
      return formatted;
    }

    function escapeHtml(str) {
      return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function appendMessage(text, role, animate = true) {
      if (!chatHistoryBox) return;

      const bubble = document.createElement('div');
      bubble.className = `chat-bubble ${role}`;

      if (role === 'bot') {
        bubble.innerHTML = `<strong>Asistente:</strong> ${formatMarkdown(text)}`;
      } else {
        bubble.innerHTML = `<strong>Tú:</strong> ${escapeHtml(text)}`;
      }

      chatHistoryBox.appendChild(bubble);
      scrollToBottom();
      initCodeCopyButtons();
    }

    function showTypingIndicator() {
      const indicator = document.createElement('div');
      indicator.id = 'copilotTypingIndicator';
      indicator.className = 'chat-bubble bot';
      indicator.innerHTML = `
        <div class="typing-wave-container">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      `;
      chatHistoryBox.appendChild(indicator);
      scrollToBottom();
    }

    function removeTypingIndicator() {
      const indicator = document.getElementById('copilotTypingIndicator');
      if (indicator) indicator.remove();
    }

    function scrollToBottom() {
      if (chatHistoryBox) {
        chatHistoryBox.scrollTop = chatHistoryBox.scrollHeight;
      }
    }

    // Local knowledge matcher
    function getKnowledgeMatch(query) {
      const q = query.toLowerCase();

      // Check author/trajectory
      if (q.includes('trayectoria') || q.includes('quién es') || q.includes('quien es') || q.includes('jesus zerpa') || q.includes('experiencia') || q.includes('cv') || q.includes('perfil') || q.includes('contacto')) {
        return `**${AUTHOR_DOSSIER.name}** | ${AUTHOR_DOSSIER.title}\n\n${AUTHOR_DOSSIER.experience}\n\n**Trayectoria Corporativa Destacada:**\n- ${AUTHOR_DOSSIER.companies.join('\n- ')}\n\n**Contacto:** [${AUTHOR_DOSSIER.email}](mailto:${AUTHOR_DOSSIER.email}) | Telegram: [${AUTHOR_DOSSIER.telegram}](https://t.me/jesusbz21) | [LinkedIn](${AUTHOR_DOSSIER.linkedin}) | [RPubs](${AUTHOR_DOSSIER.rpubs}).`;
      }

      // Check models
      for (const [key, model] of Object.entries(MODELS_KNOWLEDGE_BASE)) {
        if (q.includes(key)) {
          return `**${model.title}**\n\n- **Metodología Cuantitativa:** ${model.methodology}\n- **Hallazgo Clave:** ${model.key_finding}\n- **Aplicación Empresarial:** ${model.application}\n\n👉 Puedes explorar el código reproducible y visualizaciones en [\`${model.file}\`](${model.file}).`;
        }
      }

      // General finance query fallback
      return null;
    }

    // Direct Google Gemini API Call
    async function callGeminiDirect(apiKey, userPrompt) {
      const systemInstruction = `Eres el Asistente Cuantitativo Ejecutivo del portafolio web de Jesús Benjamín Zerpa (Economista y Quantitative Data Scientist).
Jesús Zerpa cuenta con más de 14 años de experiencia en planificación financiera corporativa, presupuestos maestros, control de gestión y modelación econométrica (en Consorcio Credicard, Grupo Mistral, Multimédica, Segutronic, Admibien y Banesco).
Conoces a profundidad sus 13 modelos cuantitativos desarrollados en R y Python (VaR Bitcoin con rugarch, Pronósticos con TSstudio, Fronteras de Markowitz, Prophet para criptoactivos, Monte Carlo, Power BI, KDD Data Mining, VAR multivariable, etc.).
Responde siempre con rigor técnico y analítico, elegancia corporativa, usando Markdown limpio y citando los modelos del portafolio cuando corresponda.`;

      const contents = [];
      chatHistory.slice(-8).forEach(item => {
        contents.push({
          role: item.role === 'user' ? 'user' : 'model',
          parts: [{ text: item.parts[0].text }]
        });
      });
      contents.push({
        role: 'user',
        parts: [{ text: userPrompt }]
      });

      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`;

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_instruction: {
            parts: [{ text: systemInstruction }]
          },
          contents: contents,
          generationConfig: {
            temperature: 0.3,
            maxOutputTokens: 1024
          }
        })
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error?.message || `HTTP ${res.status}`);
      }

      const data = await res.json();
      return data.candidates?.[0]?.content?.parts?.[0]?.text || 'Sin respuesta generada por Gemini.';
    }

    async function sendMessage() {
      if (!chatInput) return;
      const message = chatInput.value.trim();
      if (!message) return;

      // Detect if user pasted an API Key starting with AIzaSy directly into chat
      if (message.startsWith('AIzaSy') && message.length > 30) {
        localStorage.setItem(API_KEY_STORAGE, message);
        chatInput.value = '';
        updateKeyStatusUI();
        appendMessage('✅ **Licencia Google Gemini Ultra / Pro activada con éxito.** A partir de este momento todas tus consultas analíticas se procesarán directamente con el motor cognitivo de Google Ultra.', 'bot');
        return;
      }

      appendMessage(message, 'user');
      chatInput.value = '';
      if (chatSendBtn) chatSendBtn.disabled = true;

      showTypingIndicator();

      const userApiKey = localStorage.getItem(API_KEY_STORAGE);

      try {
        let botResponse = null;

        if (userApiKey) {
          // 1. Direct call to Google Gemini with user's Ultra/Pro license
          botResponse = await callGeminiDirect(userApiKey, message);
        } else {
          // 2. Try Vercel proxy backend
          const response = await fetch(vercelURL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, history: chatHistory })
          });

          if (response.ok) {
            const data = await response.json();
            botResponse = data.text;
          } else {
            throw new Error('Vercel API offline');
          }
        }

        removeTypingIndicator();

        if (botResponse) {
          appendMessage(botResponse, 'bot');
          chatHistory.push(
            { role: 'user', parts: [{ text: message }] },
            { role: 'model', parts: [{ text: botResponse }] }
          );
          saveHistory();
        }

      } catch (error) {
        console.warn('API connection unavailable, activating local Knowledge Base:', error);
        removeTypingIndicator();

        // 3. Fallback to Local Knowledge Base
        const kbMatch = getKnowledgeMatch(message);
        if (kbMatch) {
          appendMessage(kbMatch, 'bot');
        } else {
          appendMessage(`Puedo responderte con precisión sobre cualquiera de los 13 modelos del portafolio:
- **Modelización VaR y Volatilidad GARCH para Bitcoin** (\`Proyecto2.html\`)
- **Pronósticos de Ventas en Volumen con TSstudio y ARIMA** (\`modelo-ventas.html\`)
- **Machine Learning y Clasificación en R** (\`proyecto3.html\`)
- **Fronteras Eficientes de Markowitz y Optimización de Carteras** (\`proyecto4.html\`)
- **Pronósticos con Prophet de Facebook para Criptoactivos** (\`bitcoin-ether-pronosticos-con-prophet.html\`)
- **Simulación Monte Carlo para Stress Testing Financiero** (\`modelizacion-monte-carlo-portafolios.html\`)
- **Evaluación de Proyectos de Inversión y WACC** (\`EvaluacionProyecto.html\`)
- **Financial Dashboards en R / VBA** (\`Dashboard.html\`)
- **Vectores Autorregresivos (VAR) y Causalidad de Granger** (\`trading-vectores-autoregresivos-en-rstudio.html\`)
- **Trayectoria Ejecutiva de Jesús Zerpa** en Credicard, Grupo Mistral y Banesco.

💡 *Consejo: Puedes conectar tu propia clave de Google Gemini Ultra haciendo clic en el icono 🔑 del encabezado para consultas analíticas profundas.*`, 'bot');
        }
      } finally {
        if (chatSendBtn) chatSendBtn.disabled = false;
        chatInput.focus();
      }
    }

    if (chatSendBtn) {
      chatSendBtn.addEventListener('click', sendMessage);
    }

    if (chatInput) {
      chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });
    }
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

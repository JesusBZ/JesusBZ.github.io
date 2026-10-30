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
  // 5. VERIFIED KNOWLEDGE BASE (extracted only from the published content of
  //    each post and from the author's original biography). Nothing here may
  //    be added unless it appears on the site.
  // =========================================================================
  const PROFILE = {
    name: 'Jesús Benjamín Zerpa',
    title: 'Economista y Científico de Datos (Economist & Data Scientist)',
    summary: 'Profesional de finanzas con más de 14 años de experiencia en las áreas de planificación, presupuesto y control, formado en empresas de diversos sectores económicos. Enfocado en la modelización avanzada de datos para la planificación financiera, presupuestaria y de pronósticos.',
    interests: 'Financial Planning, Business Intelligence, Business Analysis y Data Analytics.',
    portfolio: 'El portafolio reúne códigos en lenguaje R (y Python), pruebas de paqueterías de R, tratamiento y modelaje de datos, pronósticos, dashboards financieros y evaluación de proyectos.'
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

  // Chronological order, as written in the original "Acerca de" page.
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
      company: 'CG Security Group (filial Segutronic)', role: 'Especialista Senior de Presupuesto',
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
      n: 1, title: 'Modelo de Pronósticos para Ventas en Volumen', file: 'modelo-ventas.html',
      keys: ['ventas', 'volumen', 'tsstudio', 'sarima', 'arima', 'ets', 'tslm', 'backtesting', 'retail', 'tiendas', 'series temporales', 'series de tiempo', 'pronostico de ventas', 'krispin'],
      summary: 'Pronóstico de las ventas en volumen (unidades) de una cadena de tiendas al detal en Venezuela ("empresa X"), período 2014-2019, con horizonte de 12 meses. Es una adaptación del trabajo de Rami Krispin (2019) con el paquete TSstudio, aplicada a una base de datos distinta.',
      methods: 'Análisis exploratorio, descomposición de la serie, análisis estacional y de correlación con rezagos; modelos SARIMA, ETS y TSLM (incluye TSLM con flag y polinómico) bajo un enfoque tradicional (training/test) y un enfoque de backtesting.',
      results: 'La serie tiene un patrón estacional fuerte sin estacionalidad múltiple, una ruptura estructural alrededor de 2016 y un decrecimiento no lineal. Se selecciona el modelo SARIMA para evaluar residuos y pronosticar; sus residuos no son normales y conservan correlación, por lo que el autor señala que podrían usarse otros regresores.',
      tools: 'R, TSstudio (v0.1.6), forecast, plotly.'
    },
    {
      n: 2, title: 'Modelización de la volatilidad y Valor en Riesgo (VaR) del Bitcoin', file: 'Proyecto2.html',
      keys: ['var', 'valor en riesgo', 'volatilidad', 'garch', 'egarch', 'gjrgarch', 'tgarch', 'sgarch', 'riesgo', 'ljung', 'efecto arch', 'value at risk'],
      summary: 'Evaluación de la volatilidad y del VaR de los retornos diarios del Bitcoin entre enero 2014 y enero 2020, comparando modelos GARCH simétricos y asimétricos.',
      methods: 'Modelos sGARCH, TGARCH, eGARCH y gjrGARCH con tres distribuciones de error (Normal, t-Student y GED); selección con AIC, MAE y MSE; contraste con GARCH(1,1); pruebas Ljung-Box y de efecto ARCH (LM); backtesting del VaR al 1%; análisis de residuos y pronósticos por tres métodos.',
      results: 'El eGARCH(2,1) con distribución t-Student fue el modelo mejor ajustado según AIC, aunque no dio el mejor pronóstico fuera de muestra (diferencias insignificantes). En las pruebas de VaR ningún modelo fue significativamente superior; se espera que una pérdida promedio del 0,8% se supere solo en el 1% del tiempo.',
      tools: 'R, rmgarch, PerformanceAnalytics, zoo.'
    },
    {
      n: 3, title: 'Aprendizaje Automático (Machine Learning)', file: 'proyecto3.html',
      keys: ['machine learning', 'aprendizaje automatico', 'bicicletas', 'bikeshare', 'bike', 'tidymodels', 'parsnip', 'recipes', 'yardstick', 'ml', 'inteligencia artificial'],
      summary: 'Modelo básico de Machine Learning en R para predecir, con horizonte de 6 meses, los recuentos diarios del sistema de bicicletas compartidas Capital Bikeshare (Metro DC, EE. UU.), con el dataset Bike Sharing del repositorio UCI.',
      methods: 'Flujo de trabajo con recetas de preprocesamiento (recipes), especificación de un modelo de regresión lineal (parsnip, motor lm), workflows, entrenamiento y prueba, métricas con yardstick e intervalos de predicción al 80% y 95%.',
      results: 'Precisión fuera de muestra: RMSE ≈ 1437, R² ≈ 0,379 y MAE ≈ 1045. El autor indica que los residuos no son perfectos, pero el modelo es una base de trabajo.',
      tools: 'workflows, parsnip, recipes, yardstick, tidyverse, tidyquant, timetk, plotly, knitr, kableExtra.'
    },
    {
      n: 4, title: 'Portafolio de Fronteras Eficientes Markowitz', file: 'proyecto4.html',
      keys: ['markowitz', 'frontera', 'fronteras eficientes', 'portafolio eficiente', 'tangente', 'cartera', 'diversificacion', 'acciones', 's&p', 'microsoft', 'msft', 'pepsico', 'walmart', 'mcdonald', 'mastercard', 'johnson'],
      summary: 'Cartera de inversión con seis acciones del S&P 500 de distintos sectores: Microsoft (MSFT), Johnson & Johnson (JNJ), Mastercard (MA), PepsiCo (PEP), Walmart (WMT) y McDonald\'s (MCD), período enero 2010 - abril 2020. El post incluye mensajes de voz con consultas académicas de la comunidad.',
      methods: 'Rentabilidad logarítmica, rendimientos esperados y volatilidades, matriz de varianza-covarianza y correlaciones; frontera eficiente con restricción de solo posiciones largas y tasa libre de riesgo de -0,001; cálculo del portafolio eficiente y del portafolio tangente.',
      results: 'Portafolio eficiente: JNJ 31,9%, PEP 20,4%, WMT 25,6% y MCD 22,1%. Portafolio tangente: MSFT 4,1%, JNJ 27,8%, MA 7,4%, PEP 14,2%, WMT 23% y MCD 23,4%.',
      tools: 'R, paquetes Portfolio y tseries.'
    },
    {
      n: 5, title: 'Evaluación y Formulación de Proyectos de Inversión', file: 'EvaluacionProyecto.html',
      keys: ['evaluacion', 'formulacion', 'proyecto de inversion', 'proyectos de inversion', 'global nutrition', 'espana', 'nutricion', 'renal', 'estudio de mercado', 'factibilidad', 'inversion'],
      summary: 'Participación de Jesús Zerpa en la evaluación y formulación del proyecto "Global Nutrition España 2017", emprendido por un grupo empresarial venezolano del sector salud. Buscaba penetrar mercados de la Comunidad Europea con un complemento nutricional funcional para personas con enfermedad renal crónica (en procedimiento dialítico y regímenes especiales) y solicitar financiamiento ante una institución española.',
      methods: 'Identificación del producto, estudio legal, estudio de mercado, estudio técnico y estudio económico-financiero; presentación, informe del proyecto y cuentas previsionales del primer ejercicio.',
      results: 'El post publica la presentación, el informe y las cuentas previsionales; no expone cifras de rentabilidad en texto.',
      tools: 'Documentos de Microsoft Office incrustados.'
    },
    {
      n: 6, title: 'Financial Dashboard', file: 'Dashboard.html',
      keys: ['dashboard', 'tablero', 'excel', 'vba', 'visual basic', 'kpi', 'estado de resultados', 'ganancias y perdidas', 'panel de control'],
      summary: 'Herramienta de análisis financiero desarrollada por Jesús Zerpa en Excel y Visual Basic (2018), con cuatro niveles de interpretación basados en el Estado de Ganancias y Pérdidas. Su primera versión se diseñó para la V.P. de Finanzas de un grupo empresarial con producción, distribución, venta al mayor, comercialización y una cadena de tiendas al detal.',
      methods: 'Centraliza en un solo reporte la información de varios entregables, con secuencia lógica para el análisis financiero, automatizado e interactivo para el cierre mensual; exporta a PowerPoint o PDF con highlights automáticos y protege el archivo (VB).',
      results: 'La nueva versión es personalizable, incluye un asistente de inducción al usuario y se integra con Power BI.',
      tools: 'Excel, Visual Basic (VBA), Power BI.'
    },
    {
      n: 7, title: 'Exploración de Datos Macroeconómicos con Rstudio', file: 'proyecto7.html',
      keys: ['macroeconomia', 'macroeconomicos', 'gapminder', 'pib', 'esperanza de vida', 'preston', 'quandl', 'banco mundial', 'wdi', 'leaflet', 'estadistica espacial', 'exploracion de datos'],
      summary: 'Exploración de los datos del paquete Gapminder (esperanza de vida al nacer y PIB per cápita) y, en una segunda parte, descarga de indicadores del Banco Mundial (WDI) para Venezuela con Quandl, cerrando con un mapa interactivo con leaflet (estadística espacial).',
      methods: 'Gráficos interactivos, animados y de dispersión; suavizado Loess y GAM; diagramas de caja; Curva de Preston; regresión lm(lifeExp ~ log(gdpPercap) + pop + continent) visualizada con coefplot.',
      results: 'El autor advierte que la correlación entre PIB per cápita y esperanza de vida no implica causalidad.',
      tools: 'plotly, gganimate, ggplot2, gapminder, Quandl, knitr, kableExtra, purrr, dygraphs, rnaturalearth, sp, rgeos, leaflet, coefplot, ggrepel, socviz.'
    },
    {
      n: 8, title: 'Sistema Integrado Geográfico SIG', file: 'powermap.html',
      keys: ['sig', 'geografico', 'geoespacial', 'power map', 'mapa', 'mapas', 'territorial', 'gis'],
      summary: 'Extracto del análisis geoespacial de una cadena de tiendas (retail) en Venezuela: recorrido histórico de cierre de un modelo de datos de ventas en volumen con la herramienta Power Map.',
      methods: '1 capa, gráfico de barras, métrica: ventas en volumen. Explica los conceptos de SIG, datos geoespaciales y Power Map.',
      results: 'Se presenta como visualización/recorrido; no reporta métricas numéricas en texto.',
      tools: 'Microsoft Power Map.'
    },
    {
      n: 9, title: 'Pronósticos con Prophet para el Bitcoin y Ether', file: 'bitcoin-ether-pronosticos-con-prophet.html',
      keys: ['prophet', 'facebook', 'ether', 'eth', 'ethereum'],
      summary: 'Pronósticos con Prophet (equipo Core Data Science de Facebook, v0.6.1) de los precios de cierre ajustados diarios de Bitcoin (BTC) y Ether (ETH), período 2016-2020, datos de investing.com, horizonte de 31 días.',
      methods: 'Análisis de tendencia, ciclos y estacionalidad; primeras predicciones, gráfica interactiva y componentes estacionales.',
      results: 'Para el Bitcoin se observa probabilidad de mantenerse en el soporte de 9.000 USD, con mínimo promedio de 7.500 USD y máximo de 10.500 USD hasta agosto 2020. El autor aclara que Prophet no es el mejor modelo en la mayoría de los casos; rinde mejor en series con estacionalidad, tendencia y deriva.',
      tools: 'prophet, tidyverse, dygraphs.'
    },
    {
      n: 10, title: 'Simulación Monte Carlo', file: 'modelizacion-monte-carlo-portafolios.html',
      keys: ['monte carlo', 'montecarlo', 'simulacion', 'simulaciones', 'estocastico'],
      summary: 'Introducción a la Simulación Monte Carlo usando el Portafolio Tangente obtenido en el trabajo de Markowitz (mismos seis activos del S&P 500, enero 2010 - abril 2020).',
      methods: '100 simulaciones aleatorias basadas en el histórico de los 6 instrumentos para estimar el crecimiento de 1 USD invertido en la cartera durante 120 meses (10 años).',
      results: 'El post enumera limitaciones: ignora lo que no está integrado en el modelo (tendencias macro, factores cíclicos), asume un mercado eficiente y se complica con muchas variables.',
      tools: 'tidyquant, tidyverse, timetk, broom, highcharter.'
    },
    {
      n: 11, title: 'Power BI, una de las mejores herramientas BI', file: 'power-bi.html',
      keys: ['power bi', 'business intelligence', 'inteligencia de negocios', 'inteligencia empresarial', 'microsoft'],
      summary: 'Artículo divulgativo (no es un modelo cuantitativo) sobre Business Intelligence y Power BI.',
      methods: 'Explica qué es un software de BI, sus beneficios, qué es Power BI, cómo funciona el servicio en la nube de Microsoft, las versiones gratuita, pagas y Premium, y razones para usarlo.',
      results: 'No aplica (artículo informativo).',
      tools: 'Power BI.'
    },
    {
      n: 12, title: 'Análisis de procesos de negocio utilizando la plataforma de Rstudio', file: 'analisis-de-procesos-comerciales-data-mining.html',
      keys: ['data mining', 'mineria de datos', 'procesos', 'process mining', 'bupar', 'event log', 'eventlog', 'kdd', 'mapa de procesos'],
      summary: 'Introducción a la minería de datos (KDD) y sus aplicaciones, y análisis de procesos de negocio en RStudio con datos de pacientes de un centro de salud privado.',
      methods: 'Creación de un event-log, análisis exploratorio basado en eventos, frecuencias de actividades, mapas de procesos (perfiles de frecuencia, rendimiento y personalizado), animación del mapa y gráficos de puntos.',
      results: 'El post es demostrativo; no reporta métricas de negocio específicas.',
      tools: 'bupaR y su ecosistema de análisis de procesos.'
    },
    {
      n: 13, title: 'Análisis Técnico del Bitcoin en Rstudio', file: 'trading-medias-moviles-rstudio.html',
      keys: ['trading', 'analisis tecnico', 'medias moviles', 'media movil', 'rsi', 'macd', 'bollinger', 'momentum', 'roc', 'velas', 'quantmod', 'ttr'],
      summary: '"Bitcoin Trading en Rstudio, Capítulo 1 [El Análisis Técnico]" (2020): conceptos de trading y análisis técnico, sus 3 principios, limitaciones y pioneros (Dow, Hamilton, Rhea, Gould, Magee).',
      methods: 'Análisis técnico del histórico del Bitcoin con gráficos de líneas, barras y velas, y los indicadores media móvil simple, media móvil exponencial, Bandas de Bollinger, Momentum, ROC, MACD y RSI, con la interpretación de las señales de cada uno.',
      results: 'Es un capítulo introductorio de indicadores; no publica resultados de rentabilidad de una estrategia.',
      tools: 'quantmod, TTR. Referencia de datos: investing.com.'
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
                <span>Gemini · información verificada</span>
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
          <button class="quick-chip-btn" data-prompt="¿Qué proyectos tiene el portafolio?">Todos los proyectos</button>
          <button class="quick-chip-btn" data-prompt="¿Cuál es la trayectoria profesional de Jesús Zerpa?">Trayectoria</button>
          <button class="quick-chip-btn" data-prompt="Explícame el modelo de volatilidad y VaR del Bitcoin">VaR Bitcoin</button>
          <button class="quick-chip-btn" data-prompt="¿Cómo contacto a Jesús?">Contacto</button>
        </div>

        <div id="copilotHistoryBox" class="copilot-history-box"></div>

        <div class="copilot-input-area">
          <input type="text" id="copilotInput" class="copilot-input-field" placeholder="Pregunta sobre un proyecto o la trayectoria..." autocomplete="off" />
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
  function projectLink(p) { return `[Abrir el trabajo #${p.n}](${p.file})`; }

  function answerProject(p) {
    return `**Trabajo #${p.n}: ${p.title}**\n\n` +
      `- **De qué trata:** ${p.summary}\n` +
      `- **Metodología:** ${p.methods}\n` +
      `- **Resultados / conclusiones del post:** ${p.results}\n` +
      `- **Herramientas:** ${p.tools}\n\n` + projectLink(p);
  }

  function answerProjectList(list, intro) {
    return (intro || `El portafolio tiene **${PROJECTS.length} trabajos publicados**:`) + '\n\n' +
      list.map(p => `- **#${p.n} ${p.title}**: [ver](${p.file})`).join('\n') +
      '\n\nPregúntame por cualquiera de ellos para ver su metodología y resultados.';
  }

  function answerCareer() {
    return `**Trayectoria profesional de ${PROFILE.name}** (en orden cronológico, según su perfil):\n\n` +
      CAREER.map(c => `- **${c.company}**: ${c.role}`).join('\n') +
      `\n\n${PROFILE.summary}\n\nPuedes preguntarme por una empresa en particular para ver sus funciones.`;
  }

  function answerCompany(c) {
    return `**${c.company}**: ${c.role}\n\n${c.detail}`;
  }

  function answerContact() {
    return `**Contacto de ${PROFILE.name}:**\n\n` +
      `- **Teléfono / WhatsApp:** [${CONTACT.phone}](${CONTACT.whatsapp})\n` +
      `- **Correo:** [${CONTACT.email}](mailto:${CONTACT.email})\n` +
      `- **Telegram:** [${CONTACT.telegram}](${CONTACT.telegramUrl})\n` +
      `- **LinkedIn:** [perfil](${CONTACT.linkedin})\n` +
      `- **GitHub:** [JesusBZ](${CONTACT.github}) | **RPubs:** [JesusZ](${CONTACT.rpubs})\n` +
      `- **Formulario:** [Enviar mensaje](${CONTACT.form})`;
  }

  function answerProfile() {
    return `**${PROFILE.name}**: ${PROFILE.title}.\n\n${PROFILE.summary}\n\n**Áreas de interés:** ${PROFILE.interests}\n\n${PROFILE.portfolio}`;
  }

  function answerTools() {
    return `**Herramientas usadas en los trabajos publicados:**\n\n` +
      `- **R / RStudio:** TSstudio, forecast, rmgarch, PerformanceAnalytics, tidymodels (recipes, parsnip, workflows, yardstick), tidyquant, timetk, prophet, Portfolio, tseries, bupaR, quantmod, TTR, Quandl, leaflet, ggplot2, plotly, highcharter.\n` +
      `- **Microsoft:** Excel y Visual Basic (Financial Dashboard), Power BI y Power Map.\n` +
      `- **Técnicas:** series temporales (SARIMA, ETS, TSLM), modelos GARCH y VaR, regresión lineal con Machine Learning, optimización de Markowitz, simulación Monte Carlo, Prophet, process mining y análisis técnico.`;
  }

  function unknownAnswer() {
    return `No tengo información verificada sobre eso en el portafolio, así que prefiero no suponer. Puedo responderte sobre:\n\n` +
      `- Los ${PROJECTS.length} trabajos publicados (escribe "proyectos")\n- La trayectoria profesional (escribe "trayectoria")\n- Herramientas utilizadas (escribe "herramientas")\n- Datos de contacto (escribe "contacto")\n\n` +
      `Para cualquier otra consulta puedes escribirle directamente a Jesús por [WhatsApp](${CONTACT.whatsapp}) o por el [formulario](${CONTACT.form}).`;
  }

  // ---------- Intent router ----------
  function getVerifiedAnswer(raw) {
    const q = norm(raw);

    if (/^(hola|buenas|buenos dias|buenas tardes|buenas noches|saludos|hey)\b/.test(q) && q.length < 30) {
      return `Hola. Soy el asistente del portafolio de **${PROFILE.name}**. Respondo solo con información publicada en este sitio: sus ${PROJECTS.length} trabajos, su trayectoria profesional y sus datos de contacto. ¿Qué te gustaría saber?`;
    }
    if (hasAny(q, ['gracias', 'thank'])) return 'Con gusto. Si quieres, pregúntame por otro trabajo o por la trayectoria de Jesús.';

    if (hasAny(q, ['vectores autorregresivos', 'vector autorregresivo', 'granger', 'modelo var multivariado'])) {
      return 'Existe una página sobre Vectores Autorregresivos (VAR) en el sitio, pero no contiene una descripción publicada que me permita explicarla con precisión. Puedes consultarle directamente a Jesús por el [formulario](formulario.html).';
    }

    if (hasAny(q, ['contacto', 'contactar', 'correo', 'email', 'e-mail', 'telefono', 'whatsapp', 'telegram', 'linkedin', 'escribirle', 'llamar', 'contratar', 'consultoria', 'cotizacion'])) {
      return answerContact();
    }

    if (hasAny(q, ['universidad', 'donde estudio', 'que estudio', 'estudios universitarios', 'titulo universitario', 'formacion academica', 'postgrado', 'maestria', 'doctorado', 'certificacion'])) {
      return `El portafolio indica que ${PROFILE.name} es **Economista**, pero no publica la institución, el año ni otros estudios formales. Para ese detalle puedes revisar su [LinkedIn](${CONTACT.linkedin}) o escribirle por el [formulario](${CONTACT.form}).`;
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
      return answerProjectList(ties, 'Encontré varios trabajos relacionados con tu consulta:');
    }

    // Generic "bitcoin / cripto" question
    if (hasAny(q, ['bitcoin', 'btc', 'cripto', 'criptomoneda', 'criptomonedas'])) {
      return answerProjectList(PROJECTS.filter(p => [2, 9, 13].includes(p.n)), 'Hay tres trabajos sobre Bitcoin y criptomonedas:');
    }

    if (hasAny(q, ['trayectoria', 'experiencia', 'empresas', 'cargos', 'carrera', 'curriculum', 'cv', 'trabajado', 'laboral', 'donde ha trabajado'])) {
      return answerCareer();
    }

    if (hasAny(q, ['proyectos', 'trabajos', 'portafolio', 'publicaciones', 'modelos', 'que has hecho', 'que hace', 'lista'])) {
      return answerProjectList(PROJECTS);
    }

    if (hasAny(q, ['quien es', 'quien eres', 'jesus zerpa', 'jesus benjamin', 'sobre jesus', 'sobre el autor', 'biografia', 'acerca de'])) {
      return answerProfile();
    }

    if (hasAny(q, ['herramientas', 'paquetes', 'librerias', 'software', 'tecnologias', 'habilidades', 'lenguajes', 'stack'])) {
      return answerTools();
    }

    return null;
  }

  // ---------- Gemini (original Vercel backend, API key stays server-side) ----------
  const GEMINI_BACKEND_URL = 'https://gemini-backend-ecru.vercel.app/api/chat';

  function buildVerifiedContext() {
    const career = CAREER.map(c => `- ${c.company} | ${c.role}: ${c.detail}`).join('\n');
    const projects = PROJECTS.map(p =>
      `### Trabajo #${p.n}: ${p.title} (enlace: ${p.file})\n` +
      `De qué trata: ${p.summary}\nMetodología: ${p.methods}\nResultados del post: ${p.results}\nHerramientas: ${p.tools}`
    ).join('\n\n');
    return `PERFIL: ${PROFILE.name}. ${PROFILE.title}. ${PROFILE.summary} Áreas de interés: ${PROFILE.interests} ${PROFILE.portfolio}\n` +
      `EDUCACIÓN: el portafolio solo indica que es Economista; no publica institución, año ni otros estudios.\n\n` +
      `TRAYECTORIA (orden cronológico; Credicard es el cargo más reciente indicado en su perfil):\n${career}\n\n` +
      `TRABAJOS PUBLICADOS (${PROJECTS.length}):\n${projects}\n\n` +
      `NOTA: existe una página sobre Vectores Autorregresivos (VAR) sin contenido descriptivo publicado; no la describas.\n\n` +
      `CONTACTO: WhatsApp/teléfono ${CONTACT.phone} (${CONTACT.whatsapp}); correo ${CONTACT.email}; Telegram ${CONTACT.telegram}; ` +
      `LinkedIn ${CONTACT.linkedin}; GitHub ${CONTACT.github}; RPubs ${CONTACT.rpubs}; formulario: ${CONTACT.form}`;
  }

  function buildGroundedPrompt(question) {
    return `Eres el asistente del portafolio web de ${PROFILE.name}. REGLAS ESTRICTAS:\n` +
      `1. Sobre Jesús, su trayectoria y sus trabajos responde ÚNICAMENTE con el CONTEXTO VERIFICADO de abajo.\n` +
      `2. No inventes cifras, empresas, cargos, fechas, estudios, clientes, paquetes ni resultados. Si algo no está en el contexto, responde: "No tengo esa información verificada en el portafolio" y sugiere contactar a Jesús por WhatsApp o por el formulario.\n` +
      `3. Al citar resultados o conclusiones de un trabajo, repítelos tal como aparecen en el contexto: no agregues interpretaciones, porcentajes de confianza ni conclusiones más favorables, y conserva las salvedades (por ejemplo, si un modelo no fue el mejor fuera de muestra, dilo).\n` +
      `4. Sobre su empleo, di "su cargo más reciente indicado en el portafolio" en lugar de afirmar que trabaja ahí actualmente.\n` +
      `5. Puedes explicar brevemente conceptos técnicos generales (por ejemplo, qué es un modelo GARCH), aclarando que es una explicación general, sin atribuirle a Jesús nada que no esté en el contexto.\n` +
      `6. Responde en español, de forma concisa, con Markdown simple (negritas y viñetas con "- "), sin emojis.\n` +
      `7. Cuando menciones un trabajo, incluye su enlace con formato [Ver trabajo](archivo.html).\n\n` +
      `CONTEXTO VERIFICADO:\n${buildVerifiedContext()}\n\n` +
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

    // Purge any API key or unverified chat history stored by previous versions
    try {
      localStorage.removeItem('gemini_user_api_key');
      localStorage.removeItem('jesus_copilot_history_v2');
    } catch (e) { /* ignore */ }

    const chatToggleBtn = document.getElementById('copilotToggleBtn');
    const chatWindow = document.getElementById('copilotChatWindow');
    const chatCloseBtn = document.getElementById('copilotCloseBtn');
    const chatClearBtn = document.getElementById('copilotClearBtn');
    const chatSendBtn = document.getElementById('copilotSendBtn');
    const chatInput = document.getElementById('copilotInput');
    const chatHistoryBox = document.getElementById('copilotHistoryBox');
    const quickChips = document.querySelectorAll('.quick-chip-btn');
    const STORAGE_KEY = 'jesus_copilot_history_v3';
    const WELCOME = `Hola. Soy el asistente del portafolio de **${PROFILE.name}**. Respondo solo con información publicada en este sitio: sus ${PROJECTS.length} trabajos, su trayectoria profesional y sus datos de contacto. ¿Qué te gustaría saber?`;
    let chatHistory = [];

    function escapeHtml(str) {
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function formatMarkdown(text) {
      let h = escapeHtml(text || '');
      h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      h = h.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, label, url) => {
        const ext = /^https?:/i.test(url);
        return `<a href="${url}"${ext ? ' target="_blank" rel="noopener noreferrer"' : ''}>${label}</a>`;
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

    function saveHistory() {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(chatHistory.slice(-20))); } catch (e) { /* ignore */ }
    }

    function resetChat() {
      chatHistoryBox.innerHTML = '';
      appendMessage(WELCOME, 'bot');
    }

    resetChat();
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      if (Array.isArray(saved)) {
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
        try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
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

      // History sent to Gemini contains the visitor's plain questions and the answers shown
      const geminiHistory = chatHistory.slice(-8).map(h => ({
        role: h.role === 'user' ? 'user' : 'model',
        parts: [{ text: h.text }]
      }));

      let answer;
      try {
        answer = await askGemini(message, geminiHistory);
      } catch (err) {
        // Gemini unavailable (e.g. local preview or network): use verified local answers
        console.warn('Gemini no disponible, usando base verificada local:', err);
        answer = getVerifiedAnswer(message) || unknownAnswer();
      }

      hideTyping();
      appendMessage(answer, 'bot');
      chatHistory.push({ role: 'user', text: message }, { role: 'bot', text: answer });
      saveHistory();
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

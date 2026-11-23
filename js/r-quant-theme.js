/*!
 * Quantitative Institutional Theme Engine v3.0 for RStudio / RMarkdown Posts
 * Exact Curriculum.pdf Brand Palette:
 *   Deep Executive Navy (#0B1B33), Plot Navy (#102342), Elevated Navy (#163259),
 *   Executive Cobalt (#1D4ED8), Champagne Gold (#B8955A), Soft Gold (#D9C29A), Mist Steel (#C7D2E3)
 * Harmonious Series: Electric Sky (#38BDF8), Champagne Gold (#B8955A), Emerald (#10B981),
 *   Crimson Rose (#F43F5E), Cobalt Sky (#60A5FA), Soft Gold (#D9C29A), Aqua Teal (#2DD4BF), Royal Indigo (#818CF8)
 * Full Interactivity Preserved: Hover, Zoom, Pan, Legend Toggle, Rangeslider, Play/Slider Frames & Crosstalk
 * Jesús Benjamín Zerpa — jesusbz.github.io
 */
(function () {
  'use strict';

  var SERIES_PALETTE = [
    '#38BDF8', // 0: Electric Sky (Primary / Actual)
    '#B8955A', // 1: Champagne Gold (Hero / Forecast / Median)
    '#10B981', // 2: Institutional Emerald (Positive / Validation)
    '#F43F5E', // 3: Crimson Rose (Contrast / Risk)
    '#60A5FA', // 4: Cobalt Sky (Secondary Blue)
    '#D9C29A', // 5: Soft Champagne Gold
    '#2DD4BF', // 6: Aqua Teal (Harmonious Cyan-Emerald)
    '#818CF8', // 7: Royal Indigo (Harmonious Navy-Violet)
    '#C7D2E3'  // 8: Mist Steel Blue
  ];

  // 5-stop Personal Gradient for high-count fans (e.g., 100 Monte Carlo paths, 142 countries, 30 boxplots)
  var FAN_STOPS = [
    [29, 78, 216],   // #1D4ED8 Executive Cobalt
    [56, 189, 248],  // #38BDF8 Electric Sky
    [45, 212, 191],  // #2DD4BF Aqua Teal
    [16, 185, 129],  // #10B981 Institutional Emerald
    [184, 149, 90]   // #B8955A Champagne Gold
  ];

  var PERSONAL_COLORSCALE = [
    [0.00, '#0B1B33'],
    [0.25, '#1D4ED8'],
    [0.50, '#38BDF8'],
    [0.75, '#10B981'],
    [1.00, '#B8955A']
  ];

  var BG_PAPER = '#0B1B33';
  var BG_PLOT = '#102342';
  var BG_CARD = '#163259';
  var TEXT_MAIN = '#FFFFFF';
  var TEXT_SUB = '#C7D2E3';
  var GRID_COLOR = 'rgba(199, 210, 227, 0.14)';
  var ZERO_COLOR = 'rgba(184, 149, 90, 0.42)';
  var LINE_AXIS = 'rgba(199, 210, 227, 0.30)';
  var GOLD = '#B8955A';
  var GOLD_LIGHT = '#D9C29A';

  function parseRgb(colorStr) {
    if (!colorStr || typeof colorStr !== 'string') return null;
    var s = colorStr.trim().toLowerCase();
    if (s === 'black') return [0, 0, 0, 1];
    if (s === 'white') return [255, 255, 255, 1];
    if (s === 'red') return [255, 0, 0, 1];
    if (s === 'green') return [0, 128, 0, 1];
    if (s === 'blue') return [0, 0, 255, 1];
    if (s === 'transparent' || s === 'none') return [0, 0, 0, 0];
    var hex = s.match(/^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i);
    if (hex) {
      var h = hex[1];
      if (h.length === 3) {
        return [parseInt(h[0] + h[0], 16), parseInt(h[1] + h[1], 16), parseInt(h[2] + h[2], 16), 1];
      }
      var a = h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1;
      return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16), a];
    }
    var rgba = s.match(/^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/);
    if (rgba) {
      return [parseFloat(rgba[1]), parseFloat(rgba[2]), parseFloat(rgba[3]), rgba[4] !== undefined ? parseFloat(rgba[4]) : 1];
    }
    return null;
  }

  function rgbToHex(r, g, b) {
    var toH = function (v) {
      var s = Math.max(0, Math.min(255, Math.round(v))).toString(16);
      return s.length === 1 ? '0' + s : s;
    };
    return '#' + toH(r) + toH(g) + toH(b);
  }

  function withAlpha(hex, alpha) {
    var rgb = parseRgb(hex) || [56, 189, 248, 1];
    return 'rgba(' + rgb[0] + ',' + rgb[1] + ',' + rgb[2] + ',' + alpha.toFixed(2) + ')';
  }

  function luminance(rgb) {
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2];
  }

  function isDarkColor(colorStr) {
    var rgb = parseRgb(colorStr);
    if (!rgb || rgb[3] < 0.05) return false;
    return luminance(rgb) < 92;
  }

  function isVeryLightColor(colorStr) {
    var rgb = parseRgb(colorStr);
    if (!rgb || rgb[3] < 0.05) return false;
    return luminance(rgb) > 205;
  }

  function interpolateFanColor(t, alpha) {
    var pos = Math.max(0, Math.min(1, t)) * (FAN_STOPS.length - 1);
    var i0 = Math.floor(pos);
    var i1 = Math.min(FAN_STOPS.length - 1, i0 + 1);
    var f = pos - i0;
    var r = Math.round(FAN_STOPS[i0][0] * (1 - f) + FAN_STOPS[i1][0] * f);
    var g = Math.round(FAN_STOPS[i0][1] * (1 - f) + FAN_STOPS[i1][1] * f);
    var b = Math.round(FAN_STOPS[i0][2] * (1 - f) + FAN_STOPS[i1][2] * f);
    if (alpha !== undefined && alpha < 0.99) {
      return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha.toFixed(2) + ')';
    }
    return rgbToHex(r, g, b);
  }

  function buildTraceColorAssignment(traces) {
    if (!Array.isArray(traces)) return [];
    var n = traces.length;
    var isHighCountFan = n >= 18;
    var hasSemanticActual = traces.some(function (t) {
      var n0 = t && t.name ? String(t.name).trim().toLowerCase() : '';
      return n0 === 'actual' || n0 === 'observed' || n0 === 'btc-usd';
    });
    var usedIdx = hasSemanticActual ? 1 : 0;

    return traces.map(function (tr, idx) {
      if (!tr || typeof tr !== 'object') return SERIES_PALETTE[idx % SERIES_PALETTE.length];
      var nm = String(tr.name || '').trim().toLowerCase();
      var rawCol = (tr.line && typeof tr.line.color === 'string' && tr.line.color) ||
                   (tr.marker && typeof tr.marker.color === 'string' && tr.marker.color) || '';
      var rgb = parseRgb(rawCol);

      // Keep truly transparent helper traces transparent
      if (rawCol === 'transparent' || (rgb && rgb[3] < 0.03)) {
        return 'transparent';
      }

      // High-count stochastic / country / seasonal series -> smooth Personal Brand Gradient
      if (isHighCountFan) {
        var alpha = (n >= 50 && tr.type !== 'box') ? 0.68 : 0.92;
        return interpolateFanColor(n > 1 ? idx / (n - 1) : 0.5, alpha);
      }

      // Semantic rules for financial / econometric series names
      if (nm === 'actual' || nm === 'observed' || nm === 'btc-usd' || nm === 'non-seasonal' || nm === 'histogram') {
        return '#38BDF8'; // Electric Sky
      }
      if (nm === 'forecast' || nm === 'forecasted') {
        return '#B8955A'; // Champagne Gold
      }
      if (nm === 'fitted' || nm === 'fitted values') {
        return n <= 4 ? '#B8955A' : '#10B981';
      }
      if (nm.indexOf('ci upper') !== -1 || nm.indexOf('ci lower') !== -1) {
        return '#B8955A';
      }
      if (nm.indexOf('seasonal lag') !== -1) {
        return '#F43F5E';
      }
      if (nm === 'lag-zero') {
        return '#D9C29A';
      }
      if (nm.indexOf('confidence') !== -1 || nm.indexOf('b bands') !== -1) {
        return 'rgba(199, 210, 227, 0.55)';
      }

      // Subtle background scatter points (e.g. raw gray observations behind a fitted curve)
      if (rgb && Math.max(rgb[0], rgb[1], rgb[2]) - Math.min(rgb[0], rgb[1], rgb[2]) < 15 && luminance(rgb) > 130 && n >= 4 && !nm) {
        return 'rgba(199, 210, 227, 0.48)';
      }

      // Otherwise assign guaranteed distinct colors from SERIES_PALETTE
      var pick = SERIES_PALETTE[usedIdx % SERIES_PALETTE.length];
      usedIdx++;
      return pick;
    });
  }

  function applyColorToSingleTrace(tr, assignedColor, idx) {
    if (!tr || typeof tr !== 'object') return tr;
    var t = Object.assign({}, tr);

    if (t.type === 'heatmap' || t.type === 'contour') {
      t.colorscale = PERSONAL_COLORSCALE;
      t.colorbar = Object.assign({}, t.colorbar || {}, {
        tickfont: { color: TEXT_SUB },
        titlefont: { color: TEXT_MAIN },
        outlinecolor: 'rgba(184, 149, 90, 0.40)'
      });
      return t;
    }

    if (t.type === 'candlestick' || t.type === 'ohlc') {
      t.increasing = Object.assign({}, t.increasing || {}, {
        line: { color: '#10B981', width: 1.4 },
        fillcolor: 'rgba(16, 185, 129, 0.45)'
      });
      t.decreasing = Object.assign({}, t.decreasing || {}, {
        line: { color: '#F43F5E', width: 1.4 },
        fillcolor: 'rgba(244, 63, 94, 0.45)'
      });
      return t;
    }

    if (!assignedColor || assignedColor === 'transparent') return t;

    var baseHex = assignedColor.indexOf('rgba') === 0 ? SERIES_PALETTE[idx % SERIES_PALETTE.length] : assignedColor;

    if (t.line && typeof t.line === 'object') {
      t.line = Object.assign({}, t.line);
      if (t.line.color !== 'transparent') {
        t.line.color = assignedColor;
      }
    } else if (!t.type || t.type === 'scatter' || t.type === 'scattergl') {
      if (!t.mode || t.mode.indexOf('lines') !== -1) {
        t.line = Object.assign({}, t.line || {}, { color: assignedColor });
      }
    }

    if (t.marker && typeof t.marker === 'object') {
      t.marker = Object.assign({}, t.marker);
      if (typeof t.marker.color === 'string' && t.marker.color !== 'transparent') {
        t.marker.color = assignedColor;
      } else if (!t.marker.color && (t.type === 'bar' || t.type === 'histogram' || t.type === 'box')) {
        t.marker.color = withAlpha(baseHex, 0.78);
      }
      if (t.marker.line && typeof t.marker.line === 'object') {
        t.marker.line = Object.assign({}, t.marker.line, { color: baseHex });
      }
    } else if (t.type === 'bar' || t.type === 'histogram' || t.type === 'box') {
      t.marker = { color: withAlpha(baseHex, 0.75), line: { color: baseHex, width: 1.2 } };
    }

    if (typeof t.fillcolor === 'string' && t.fillcolor !== 'transparent') {
      var fc = parseRgb(t.fillcolor);
      if (fc && fc[3] > 0.02) {
        var nm = String(t.name || '').toLowerCase();
        if (nm.indexOf('95%') !== -1) {
          t.fillcolor = 'rgba(56, 189, 248, 0.14)';
        } else if (nm.indexOf('80%') !== -1) {
          t.fillcolor = 'rgba(184, 149, 90, 0.22)';
        } else {
          t.fillcolor = withAlpha(baseHex, Math.min(Math.max(fc[3], 0.16), 0.30));
        }
      }
    }
    return t;
  }

  function upgradeAxis(ax) {
    if (!ax || typeof ax !== 'object') return;
    ax.gridcolor = GRID_COLOR;
    ax.zerolinecolor = ZERO_COLOR;
    ax.linecolor = LINE_AXIS;
    ax.tickcolor = LINE_AXIS;
    ax.automargin = true;
    ax.tickfont = Object.assign({}, ax.tickfont || {}, { color: TEXT_SUB, size: 11 });
    if (typeof ax.title === 'string') {
      ax.title = { text: ax.title, font: { color: TEXT_MAIN, size: 13 }, standoff: 10 };
    } else if (ax.title && typeof ax.title === 'object') {
      ax.title = Object.assign({}, ax.title, {
        font: Object.assign({}, ax.title.font || {}, { color: TEXT_MAIN, size: 13 })
      });
    } else if (ax.titlefont) {
      ax.titlefont = Object.assign({}, ax.titlefont, { color: TEXT_MAIN });
    }
    if (ax.rangeslider && typeof ax.rangeslider === 'object') {
      ax.rangeslider = Object.assign({}, ax.rangeslider, {
        bgcolor: '#0B1B33',
        bordercolor: 'rgba(184, 149, 90, 0.45)',
        borderwidth: 1
      });
    }
    if (ax.rangeselector && typeof ax.rangeselector === 'object') {
      ax.rangeselector = Object.assign({}, ax.rangeselector, {
        bgcolor: BG_CARD,
        activecolor: GOLD,
        bordercolor: 'rgba(184, 149, 90, 0.48)',
        borderwidth: 1,
        font: Object.assign({}, ax.rangeselector.font || {}, { color: TEXT_MAIN })
      });
    }
  }

  function hasVisibleExternalRightLegend(data, layout) {
    if (layout && layout.showlegend === false) return false;
    var namedCount = Array.isArray(data) ? data.filter(function (t) {
      return t && t.showlegend !== false && t.name && String(t.name).trim() !== '';
    }).length : 0;
    if (namedCount < 2 && !(layout && layout.showlegend === true)) return false;
    var leg = (layout && layout.legend) || {};
    if (leg.orientation === 'h') return false;
    if (typeof leg.x === 'number' && leg.x < 0.92) return false; // inside legend (e.g. leg.x = 0.6)
    return true;
  }

  function themePlotlySpec(gd, data, layout, frames) {
    var colorMap = buildTraceColorAssignment(data);
    var safeData = Array.isArray(data) ? data.map(function (tr, idx) {
      return applyColorToSingleTrace(tr, colorMap[idx], idx);
    }) : data;

    // Build lookup by trace name too for frame matching
    var nameToColor = {};
    if (Array.isArray(data)) {
      data.forEach(function (tr, idx) {
        if (tr && tr.name && !nameToColor[tr.name]) {
          nameToColor[tr.name] = colorMap[idx];
        }
      });
    }

    var safeFrames = Array.isArray(frames) ? frames.map(function (fr) {
      if (!fr || typeof fr !== 'object' || !Array.isArray(fr.data)) return fr;
      var fCopy = Object.assign({}, fr);
      var traceIndices = Array.isArray(fr.traces) ? fr.traces : null;
      fCopy.data = fr.data.map(function (ftr, j) {
        var origIdx = (traceIndices && typeof traceIndices[j] === 'number') ? traceIndices[j] : j;
        var col = (ftr && ftr.name && nameToColor[ftr.name]) || colorMap[origIdx] || SERIES_PALETTE[origIdx % SERIES_PALETTE.length];
        return applyColorToSingleTrace(ftr, col, origIdx);
      });
      return fCopy;
    }) : frames;

    var safeLayout = layout ? Object.assign({}, layout) : {};
    var hasSliders = Array.isArray(safeLayout.sliders) && safeLayout.sliders.length > 0;
    var hasMenus = Array.isArray(safeLayout.updatemenus) && safeLayout.updatemenus.length > 0;
    var hasRangeSlider = Boolean(safeLayout.xaxis && safeLayout.xaxis.rangeslider && safeLayout.xaxis.rangeslider.visible !== false);
    var extRightLegend = hasVisibleExternalRightLegend(safeData, safeLayout);
    var hasTitle = Boolean(safeLayout.title && (typeof safeLayout.title === 'string' ? safeLayout.title.trim() : safeLayout.title.text));

    // Synchronize outer element width & height so SVG is 100% centered and NEVER clipped
    var targetHeight = (hasSliders || hasMenus) ? 580 : (hasRangeSlider ? 530 : 490);
    safeLayout.autosize = true;
    delete safeLayout.width;
    safeLayout.height = targetHeight;

    if (gd && gd.style) {
      gd.style.width = '100%';
      gd.style.height = targetHeight + 'px';
    }

    // Generous, non-clipping margins inside #0B1B33 paper_bgcolor
    var origM = (typeof safeLayout.margin === 'object' && safeLayout.margin) ? safeLayout.margin : {};
    safeLayout.margin = {
      t: Math.max(origM.t || 0, hasTitle ? 68 : 44),
      r: Math.max(origM.r || 0, extRightLegend ? 152 : 44),
      b: (hasSliders || hasMenus) ? 150 : Math.max(origM.b || 0, hasRangeSlider ? 98 : 68),
      l: Math.max(origM.l || 0, 76),
      pad: 4
    };

    safeLayout.paper_bgcolor = BG_PAPER;
    safeLayout.plot_bgcolor = BG_PLOT;
    safeLayout.colorway = SERIES_PALETTE;
    safeLayout.font = Object.assign({}, safeLayout.font || {}, {
      family: 'Inter, "Segoe UI", system-ui, sans-serif',
      color: TEXT_SUB,
      size: 12
    });

    if (typeof safeLayout.title === 'string') {
      safeLayout.title = { text: safeLayout.title, font: { color: TEXT_MAIN, size: 16 }, x: 0.5, xanchor: 'center' };
    } else if (safeLayout.title && typeof safeLayout.title === 'object') {
      safeLayout.title = Object.assign({}, safeLayout.title, {
        font: Object.assign({}, safeLayout.title.font || {}, { color: TEXT_MAIN, size: 16 }),
        x: safeLayout.title.x !== undefined ? safeLayout.title.x : 0.5
      });
    }

    safeLayout.hoverlabel = Object.assign({}, safeLayout.hoverlabel || {}, {
      bgcolor: BG_CARD,
      bordercolor: GOLD,
      font: { color: TEXT_MAIN, family: '"JetBrains Mono", Consolas, monospace', size: 12 }
    });

    var origLeg = safeLayout.legend || {};
    safeLayout.legend = Object.assign({}, origLeg, {
      bgcolor: 'rgba(16, 35, 66, 0.92)',
      bordercolor: 'rgba(184, 149, 90, 0.48)',
      borderwidth: 1,
      font: { color: TEXT_MAIN, size: 11 }
    });
    if (extRightLegend) {
      safeLayout.legend.x = 1.02;
      safeLayout.legend.xanchor = 'left';
      safeLayout.legend.y = 1.0;
      safeLayout.legend.yanchor = 'top';
    }

    // Style Play/Pause updatemenus cleanly BELOW the x-axis on the left (pixel-padded from y=0, never overlapping plot data!)
    if (hasMenus) {
      safeLayout.updatemenus = safeLayout.updatemenus.map(function (um) {
        return Object.assign({}, um, {
          bgcolor: BG_CARD,
          bordercolor: GOLD,
          borderwidth: 1.4,
          font: { color: TEXT_MAIN, size: 12, family: 'Plus Jakarta Sans, Inter, sans-serif' },
          x: 0.0,
          xanchor: 'left',
          y: 0.0,
          yanchor: 'top',
          direction: 'left',
          pad: { t: 68, r: 10, b: 0, l: 0 },
          showactive: false
        });
      });
    }

    // Style animation sliders cleanly in the dedicated 150px bottom margin strip (aligned with Play button)
    if (hasSliders) {
      safeLayout.sliders = safeLayout.sliders.map(function (sl) {
        var cv = sl.currentvalue || {};
        return Object.assign({}, sl, {
          x: hasMenus ? 0.13 : 0.02,
          len: hasMenus ? 0.85 : 0.96,
          xanchor: 'left',
          y: 0.0,
          yanchor: 'top',
          pad: { t: 52, b: 14 },
          bgcolor: BG_CARD,
          activebgcolor: GOLD,
          bordercolor: 'rgba(184, 149, 90, 0.55)',
          borderwidth: 1,
          tickcolor: '#C7D2E3',
          font: { color: TEXT_SUB, size: 11 },
          currentvalue: Object.assign({}, cv, {
            visible: cv.visible !== false,
            xanchor: 'right',
            offset: 6,
            font: { color: GOLD_LIGHT, size: 13, family: '"JetBrains Mono", Consolas, monospace' }
          })
        });
      });
    }

    if (!safeLayout.xaxis) safeLayout.xaxis = {};
    if (!safeLayout.yaxis) safeLayout.yaxis = {};
    Object.keys(safeLayout).forEach(function (k) {
      if (/^[xyz]axis\d*$/.test(k)) {
        upgradeAxis(safeLayout[k]);
      } else if (/^scene\d*$/.test(k) && safeLayout[k]) {
        safeLayout[k].bgcolor = BG_PLOT;
        ['xaxis', 'yaxis', 'zaxis'].forEach(function (sub) {
          if (safeLayout[k][sub]) {
            safeLayout[k][sub].backgroundcolor = BG_PLOT;
            upgradeAxis(safeLayout[k][sub]);
          }
        });
      }
    });

    if (Array.isArray(safeLayout.annotations)) {
      safeLayout.annotations = safeLayout.annotations.map(function (ann) {
        if (!ann || typeof ann !== 'object') return ann;
        var a = Object.assign({}, ann);
        a.font = Object.assign({}, a.font || {});
        if (!a.font.color || isDarkColor(a.font.color)) {
          a.font.color = TEXT_MAIN;
        }
        if (a.bgcolor && isVeryLightColor(a.bgcolor)) {
          a.bgcolor = 'rgba(22, 50, 89, 0.94)';
          a.bordercolor = 'rgba(184, 149, 90, 0.50)';
        }
        return a;
      });
    }

    if (Array.isArray(safeLayout.shapes)) {
      safeLayout.shapes = safeLayout.shapes.map(function (sh) {
        if (!sh || typeof sh !== 'object') return sh;
        var s = Object.assign({}, sh);
        if (s.fillcolor && isVeryLightColor(s.fillcolor)) {
          s.fillcolor = 'rgba(22, 50, 89, 0.45)';
        }
        if (s.line && s.line.color && isDarkColor(s.line.color)) {
          s.line = Object.assign({}, s.line, { color: 'rgba(184, 149, 90, 0.60)' });
        }
        return s;
      });
    }

    return { data: safeData, layout: safeLayout, frames: safeFrames };
  }

  function scheduleResize(gd) {
    if (!gd || !window.Plotly || !window.Plotly.Plots || typeof window.Plotly.Plots.resize !== 'function') return;
    setTimeout(function () {
      try { window.Plotly.Plots.resize(gd); } catch (e) {}
    }, 60);
    setTimeout(function () {
      try { window.Plotly.Plots.resize(gd); } catch (e) {}
    }, 350);
  }

  function hookPlotly() {
    if (!window.Plotly || window.Plotly.__jbzQuantThemedV2) return false;
    window.Plotly.__jbzQuantThemedV2 = true;

    ['newPlot', 'plot', 'react'].forEach(function (method) {
      var orig = window.Plotly[method];
      if (typeof orig !== 'function') return;
      window.Plotly[method] = function (gd, arg1, arg2, arg3) {
        var el = typeof gd === 'string' ? document.getElementById(gd) : gd;
        try {
          // Case A: R htmlwidgets single-object signature Plotly.plot(graphDiv, x) where x = { data, layout, frames, config }
          if (arg1 && typeof arg1 === 'object' && !Array.isArray(arg1) && Array.isArray(arg1.data)) {
            var spec = Object.assign({}, arg1);
            var themedObj = themePlotlySpec(el, spec.data, spec.layout, spec.frames);
            spec.data = themedObj.data;
            spec.layout = themedObj.layout;
            if (themedObj.frames) spec.frames = themedObj.frames;
            spec.config = Object.assign({ responsive: true }, spec.config || {});
            if (el) el.__jbzThemedV2Done = true;
            var p1 = orig.call(this, gd, spec);
            scheduleResize(el);
            return p1;
          }
          // Case B: Standard signature Plotly.newPlot(gd, data, layout, config)
          if (Array.isArray(arg1)) {
            var themedStd = themePlotlySpec(el, arg1, arg2, null);
            var cfg = Object.assign({ responsive: true }, arg3 || {});
            if (el) el.__jbzThemedV2Done = true;
            var p2 = orig.call(this, gd, themedStd.data, themedStd.layout, cfg);
            scheduleResize(el);
            return p2;
          }
        } catch (e) {}
        return orig.apply(this, arguments);
      };
    });

    if (typeof window.Plotly.addFrames === 'function') {
      var origAddFrames = window.Plotly.addFrames;
      window.Plotly.addFrames = function (gd, frames) {
        var el = typeof gd === 'string' ? document.getElementById(gd) : gd;
        try {
          if (el && el.data && Array.isArray(frames)) {
            var themed = themePlotlySpec(el, el.data, el.layout, frames);
            return origAddFrames.call(this, gd, themed.frames);
          }
        } catch (e) {}
        return origAddFrames.apply(this, arguments);
      };
    }
    return true;
  }

  function restyleExistingPlotlyPlots() {
    if (!window.Plotly) return;
    var plots = document.querySelectorAll('.js-plotly-plot');
    plots.forEach(function (gd) {
      if (gd.__jbzThemedV2Done || !gd.data || !gd.layout) {
        scheduleResize(gd);
        return;
      }
      gd.__jbzThemedV2Done = true;
      try {
        var existingFrames = (gd._transitionData && gd._transitionData._frames) ? gd._transitionData._frames : null;
        var themed = themePlotlySpec(gd, gd.data, gd.layout, existingFrames);
        if (typeof window.Plotly.react === 'function') {
          window.Plotly.react(gd, themed.data, themed.layout, Object.assign({ responsive: true }, gd._context || {}));
        }
        if (themed.frames && typeof window.Plotly.addFrames === 'function') {
          window.Plotly.addFrames(gd, themed.frames);
        }
        scheduleResize(gd);
      } catch (e) {}
    });
  }

  function wrapWidgetInFrame(el, targetHeightPx) {
    if (!el || !el.parentElement) return;
    if (!el.parentElement.classList.contains('r-quant-widget-frame')) {
      var wrapper = document.createElement('div');
      wrapper.className = 'r-quant-widget-frame';
      el.parentElement.insertBefore(wrapper, el);
      wrapper.appendChild(el);
    }
    el.style.width = '100%';
    if (targetHeightPx) {
      el.style.height = targetHeightPx + 'px';
    }
  }

  function restyleDygraphsAndLeaflet() {
    var dyNodes = document.querySelectorAll('.dygraphs.html-widget');
    dyNodes.forEach(function (el) {
      wrapWidgetInFrame(el, 450);
      try {
        var inst = (window.HTMLWidgets && typeof window.HTMLWidgets.getInstance === 'function')
          ? window.HTMLWidgets.getInstance(el)
          : null;
        var dg = (inst && inst.dygraph) || el.dygraph;
        if (dg && typeof dg.updateOptions === 'function') {
          if (!el.__jbzDyThemedV2) {
            el.__jbzDyThemedV2 = true;
            dg.updateOptions({
              colors: ['#38BDF8', '#B8955A', '#10B981', '#F43F5E', '#D9C29A'],
              axisLineColor: 'rgba(199, 210, 227, 0.30)',
              gridLineColor: 'rgba(199, 210, 227, 0.14)',
              strokeWidth: 2
            });
          }
          if (typeof dg.resize === 'function') {
            dg.resize();
          }
        }
      } catch (e) {}
    });

    var lfNodes = document.querySelectorAll('.leaflet.html-widget');
    lfNodes.forEach(function (el) {
      wrapWidgetInFrame(el, 460);
      try {
        var inst = (window.HTMLWidgets && typeof window.HTMLWidgets.getInstance === 'function')
          ? window.HTMLWidgets.getInstance(el)
          : null;
        var map = inst && inst.getMap && inst.getMap();
        if (map && !el.__jbzLeafletDarkV3) {
          el.__jbzLeafletDarkV3 = true;
          if (typeof map.eachLayer === 'function') {
            map.eachLayer(function (layer) {
              if (layer && typeof layer.setUrl === 'function' && layer._url && layer._url.indexOf('Positron') !== -1) {
                layer.setUrl(layer._url.replace(/light_all/g, 'dark_all').replace(/Positron/g, 'DarkMatter'));
              } else if (layer && typeof layer.setStyle === 'function' && layer.options && layer.options.fillColor) {
                layer.setStyle({ color: '#B8955A', weight: 0.7, opacity: 0.7 });
              }
            });
          }
        }
        if (map && typeof map.invalidateSize === 'function') {
          map.invalidateSize();
        }
      } catch (e) {}
    });
  }

  function restyleGraphvizSvgs() {
    var containers = document.querySelectorAll('.grViz.html-widget, .processanimateR.html-widget');
    containers.forEach(function (c) {
      c.style.width = '100%';
      c.style.height = 'auto';
    });

    var svgs = document.querySelectorAll('.grViz svg, .processanimateR > svg:not(.processanimater-control)');
    svgs.forEach(function (svg) {
      svg.style.background = BG_PAPER;
      var shapes = svg.querySelectorAll('polygon, path, ellipse, rect');
      shapes.forEach(function (el) {
        var fill = (el.getAttribute('fill') || '').trim().toLowerCase();
        var stroke = (el.getAttribute('stroke') || '').trim().toLowerCase();
        var isGraphBg = el.parentElement && el.parentElement.classList && el.parentElement.classList.contains('graph');
        if (isGraphBg && (fill === '#ffffff' || fill === 'white' || fill === 'transparent')) {
          el.setAttribute('fill', BG_PAPER);
          el.setAttribute('stroke', 'none');
          return;
        }
        if (fill === '#ffffff' || fill === 'white' || fill === '#f7fbff' || fill === '#deebf7') {
          el.setAttribute('fill', BG_CARD);
        } else if (fill && isVeryLightColor(fill)) {
          el.setAttribute('fill', '#1D4ED8');
        }
        if (stroke === '#000000' || stroke === 'black' || stroke === '#333333') {
          el.setAttribute('stroke', GOLD);
        } else if (stroke && isDarkColor(stroke)) {
          el.setAttribute('stroke', '#38BDF8');
        }
      });
      var texts = svg.querySelectorAll('text');
      texts.forEach(function (t) {
        var fill = (t.getAttribute('fill') || '').trim().toLowerCase();
        if (!fill || isDarkColor(fill)) {
          t.setAttribute('fill', TEXT_MAIN);
        }
      });
    });

    var ctrlSvgs = document.querySelectorAll('.processanimateR svg.processanimater-control');
    ctrlSvgs.forEach(function (csvg) {
      csvg.style.background = BG_PLOT;
      csvg.querySelectorAll('text').forEach(function (t) {
        t.setAttribute('fill', TEXT_SUB);
      });
      csvg.querySelectorAll('path, polygon, rect').forEach(function (el) {
        var f = (el.getAttribute('fill') || '').trim().toLowerCase();
        if (f === '#000000' || f === 'black' || isDarkColor(f)) {
          el.setAttribute('fill', GOLD);
        }
      });
    });
  }

  function applyAll() {
    hookPlotly();
    restyleExistingPlotlyPlots();
    restyleDygraphsAndLeaflet();
    restyleGraphvizSvgs();
  }

  // Hook immediately before HTMLWidgets.staticRender runs
  hookPlotly();
  // Poll briefly during script loading so Plotly is wrapped the instant plotly-latest.min.js evaluates
  var earlyTimer = setInterval(function () {
    if (hookPlotly()) {
      clearInterval(earlyTimer);
    }
  }, 15);
  setTimeout(function () { clearInterval(earlyTimer); }, 5000);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      applyAll();
      setTimeout(applyAll, 300);
      setTimeout(applyAll, 1000);
    });
  } else {
    applyAll();
    setTimeout(applyAll, 300);
    setTimeout(applyAll, 1000);
  }

  window.addEventListener('load', function () {
    applyAll();
    setTimeout(applyAll, 500);
  });

  window.addEventListener('resize', function () {
    document.querySelectorAll('.js-plotly-plot').forEach(scheduleResize);
    restyleDygraphsAndLeaflet();
  });

  if (typeof MutationObserver !== 'undefined') {
    var obs = new MutationObserver(function () {
      restyleGraphvizSvgs();
    });
    document.addEventListener('DOMContentLoaded', function () {
      document.querySelectorAll('.grViz, .processanimateR').forEach(function (t) {
        obs.observe(t, { childList: true, subtree: true });
      });
    });
  }
})();

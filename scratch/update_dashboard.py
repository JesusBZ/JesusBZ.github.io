import re

fpath = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\Dashboard.html"
with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
    c = fp.read()

# 1. Add css/post-enhancement.css if not present
if "post-enhancement.css" not in c:
    c = c.replace('</head>', '  <link rel="stylesheet" href="css/post-enhancement.css" />\n</head>', 1)

# 2. Clean navbar (remove Servicios and Recursos)
nav_old = """<li>
  <a href="https://jesusbezerpa.github.io/"rel="nofollow" target="_blank">Servicios</a>
</li>
   <li class="dropdown">
  <a href="#" class="dropdown-toggle" data-toggle="dropdown" role="button" aria-expanded="false">
   Recursos
     
    <span class="caret"></span>
  </a>
  <ul class="dropdown-menu" role="menu">
    <li>
      <a href="https://onedrive.live.com/download?resid=97B9EE70067CDD34%212341&authkey=ABrxoNLIj1Woc0Q">Manual Excel</a>
    </li> 
     <li>
      <a href="https://jesusbz.github.io/cursos.html" target="_blank">Cursos</a>
    </li>                
   		
      </ul>
    </li>"""

# Normalize spaces/newlines
nav_regex = re.compile(r'<li>\s*<a\s+href="https://jesusbezerpa\.github\.io/"[^>]*>Servicios</a>\s*</li>\s*<li\s+class="dropdown">[\s\S]*?</ul>\s*</li>', re.IGNORECASE)
c = nav_regex.sub('', c)

# 3. Replace old #share block with modern corporate-share-box
share_modern = """<div class="corporate-share-box">
<span class="share-box-title">Compartir este Trabajo Cuantitativo:</span>
<div class="share-buttons-strip">
<a href="https://www.linkedin.com/sharing/share-offsite/?url=https%3A%2F%2Fjesusbz.github.io%2FDashboard.html" target="_blank" rel="noopener noreferrer" class="btn-share-corporate linkedin" title="Compartir en LinkedIn">
<svg viewBox="0 0 24 24"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 8.76a1.64 1.64 0 1 0-.02-3.28 1.64 1.64 0 0 0 .02 3.28m1.4 9.74v-8.37H5.06v8.37h2.8z"/></svg>
<span>LinkedIn</span>
</a>
<a href="https://twitter.com/intent/tweet?url=https%3A%2F%2Fjesusbz.github.io%2FDashboard.html&text=Dashboard%20Financiero%20Ejecutivo%20-%20Jes%C3%BAs%20Zerpa" target="_blank" rel="noopener noreferrer" class="btn-share-corporate twitter-x" title="Compartir en X">
<svg viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
<span>X (Twitter)</span>
</a>
<a href="https://api.whatsapp.com/send?text=Dashboard%20Financiero%20Ejecutivo%20https%3A%2F%2Fjesusbz.github.io%2FDashboard.html" target="_blank" rel="noopener noreferrer" class="btn-share-corporate whatsapp" title="Compartir por WhatsApp">
<svg viewBox="0 0 24 24"><path d="M12.04 2c-5.46 0-9.91 4.45-9.91 9.91 0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.816 9.816 0 0 0 12.04 2m.01 1.67c2.2 0 4.26.86 5.82 2.42a8.225 8.225 0 0 1 2.41 5.83c0 4.54-3.7 8.24-8.24 8.24-1.48 0-2.93-.4-4.2-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.196 8.196 0 0 1-1.26-4.38c0-4.54 3.7-8.24 8.24-8.24m4.52 11.66c-.25-.13-1.47-.72-1.7-.81-.23-.08-.39-.13-.56.13-.17.25-.64.81-.79.97-.14.17-.29.19-.54.06-.25-.13-1.06-.39-2.01-1.24-.74-.66-1.25-1.48-1.39-1.73-.14-.25-.02-.39.11-.51.11-.11.25-.29.37-.43.13-.15.17-.25.25-.42.08-.17.04-.31-.02-.44-.06-.13-.56-1.34-.76-1.84-.2-.49-.4-.42-.56-.43h-.48c-.17 0-.44.06-.67.31-.23.25-.88.86-.88 2.1 0 1.24.9 2.44 1.03 2.61.13.17 1.78 2.71 4.3 3.8 2.53 1.08 2.53.72 2.99.68.45-.04 1.47-.6 1.68-1.18.2-.59.2-1.09.14-1.19-.06-.1-.23-.16-.48-.28z"/></svg>
<span>WhatsApp</span>
</a>
<button type="button" class="btn-share-corporate copylink" onclick="navigator.clipboard.writeText(window.location.href); this.classList.add('copied'); this.querySelector('.btn-label').textContent='¡Enlace Copiado!'; setTimeout(() => { this.classList.remove('copied'); this.querySelector('.btn-label').textContent='Copiar Enlace'; }, 2000);">
<svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
<span class="btn-label">Copiar Enlace</span>
</button>
</div>
</div>"""

share_regex = re.compile(r'<div\s+style="text-align:\s*center;">\s*<span[^>]*><b>Puedes compartir este material:</b></span>\s*<div\s+id=["\']share["\']>[\s\S]*?</div>\s*</div>', re.IGNORECASE)
c = share_regex.sub(share_modern, c)

# 4. Add futuristic-app.js before </body>
if "futuristic-app.js" not in c:
    c = c.replace('</body>', '  <script src="js/futuristic-app.js"></script>\n</body>', 1)

with open(fpath, "w", encoding="utf-8") as fp:
    fp.write(c)

print("Dashboard.html updated successfully!")

import re

fpath = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\cursos.html"
with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
    c = fp.read()

c = re.sub(r'\s*<li>\s*<a\s+href="https://jesusbezerpa\.github\.io/"[^>]*>Servicios</a>\s*</li>\s*<li\s+class="dropdown">[\s\S]*?</ul>\s*</li>', '', c)

with open(fpath, "w", encoding="utf-8") as fp:
    fp.write(c)

print("Cleaned cursos.html navbar")

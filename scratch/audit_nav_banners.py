import glob
import os
import re

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    
    # check for Servicios in <a>
    servicios_links = re.findall(r'<a[^>]*>[^<]*servicios[^<]*</a>', c, re.IGNORECASE)
    recursos_links = re.findall(r'<a[^>]*>[^<]*recursos[^<]*</a>', c, re.IGNORECASE)
    cursos_links = re.findall(r'<a[^>]*>[^<]*cursos[^<]*</a>', c, re.IGNORECASE)
    banners = re.findall(r'<a\s+href="https://jesusbezerpa\.github\.io/"[^>]*><img[^>]*></a>', c, re.IGNORECASE)
    
    print(f"{fname:45} | ServLinks: {len(servicios_links)} | RecLinks: {len(recursos_links)} | CurLinks: {len(cursos_links)} | Banners: {len(banners)}")

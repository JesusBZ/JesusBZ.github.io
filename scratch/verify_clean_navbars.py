import glob
import os
import re

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

found_any = False
for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname or fname in ["_header.html", "_footer.html"]:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    
    # Check in nav tags or navbar classes
    nav_blocks = re.findall(r'(?:<nav[^>]*>|<div[^>]*class=["\'][^"\']*navbar[^"\']*["\'][^>]*>)[\s\S]*?(?:</nav>|</div><!--/\.navbar -->|</div><!--/\.nav-collapse -->)', c, re.IGNORECASE)
    for nb in nav_blocks:
        if "servicios" in nb.lower() or "recursos" in nb.lower():
            print(f"FOUND IN NAVBAR: {fname}")
            found_any = True

if not found_any:
    print("ALL NAVBARS ARE 100% CLEAN OF 'Servicios' AND 'Recursos'!")

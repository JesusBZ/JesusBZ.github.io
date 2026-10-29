import glob
import os
import re

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname or fname == "cursos.html":
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    
    if "compartir" in c.lower() or "id=\"share\"" in c.lower() or "id='share'" in c.lower():
        print(f"{fname:45} has share block")

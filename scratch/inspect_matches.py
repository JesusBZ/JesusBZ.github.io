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
        lines = fp.readlines()

    found = []
    for idx, line in enumerate(lines):
        if re.search(r"(?i)(?:reinventa tu negocio|explora mis servicios|banner.*(?:jpg|png|webp)|class=[\"'].*banner|navbar.*servicios|navbar.*recursos|<li>.*servicios|<li>.*recursos|<li>.*cursos)", line):
            found.append((idx + 1, line.strip()))
    if found:
        print(f"=== {fname} ({len(found)} matches) ===")
        for lno, text in found[:10]:
            print(f"  L{lno}: {text[:110]}")

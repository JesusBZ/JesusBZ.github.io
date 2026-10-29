import glob
import os

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        for idx in range(400):
            line = fp.readline()
            if not line:
                break
            lower = line.lower()
            if "servicios" in lower or "recursos" in lower or "cursos" in lower:
                print(f"{fname} L{idx+1}: {line.strip()[:100]}")

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
    
    matches = re.findall(r'.{0,40}(?:servicios|recursos).{0,40}', c, re.IGNORECASE)
    if matches:
        print(f"=== {fname} ({len(matches)} matches) ===")
        for m in matches[:5]:
            clean_m = " ".join(m.split())
            print(f"   {clean_m}")

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
    
    has_old_share = 'id="share"' in c or "id='share'" in c or "puedes compartir" in c.lower()
    has_new_share = "corporate-share-box" in c
    print(f"{fname:45} | OldShare: {str(has_old_share):5} | NewShare: {str(has_new_share):5}")

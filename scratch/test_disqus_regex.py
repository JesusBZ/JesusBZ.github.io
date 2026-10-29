import glob
import os
import re

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname or fname in ["cursos.html", "acercade.html", "formulario.html", "index.html", "enviado.html", "google071051f5619c1708.html"]:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    
    if "disqus_thread" in c:
        # Find where disqus starts and ends
        m = re.search(r'<div\s+id=["\']disqus_thread["\']></div>[\s\S]*?</noscript>', c)
        if m:
            print(f"File {fname}: matched disqus block (len {len(m.group(0))})")
        else:
            print(f"File {fname}: disqus_thread found but regex did not match full block")
    else:
        print(f"File {fname}: NO disqus_thread")

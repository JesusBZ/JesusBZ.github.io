import glob
import os

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    
    has_script = "futuristic-app.js" in c
    has_css = "futuristic-corporate.css" in c or "post-enhancement.css" in c
    print(f"{fname:45} | Script: {str(has_script):5} | CSS: {str(has_css):5}")

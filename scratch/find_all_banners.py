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
        content = fp.read()
    
    matches = re.finditer(r'(<div[^>]*class=["\']separator["\'][^>]*>\s*)?<a\s+href="https?://jesusbezerpa\.github\.io/?"[^>]*>\s*<img[^>]*banner[^>]*>\s*</a>(\s*</div>)?', content, re.IGNORECASE)
    found = list(matches)
    if found:
        print(f"File {fname}: {len(found)} banner matches found.")
    else:
        # Check any img with banner
        img_banners = list(re.finditer(r'<img[^>]*banner[^>]*>', content, re.IGNORECASE))
        if img_banners:
            print(f"File {fname}: {len(img_banners)} loose img banner matches.")

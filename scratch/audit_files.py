import glob
import os
import re

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

print(f"{'Filename':45} | Ban | Ser | Rec | Cur | Disqus | Copilot")
print("-" * 80)

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        content = fp.read()

    banners = re.findall(r"(?i)(?:reinventa|explora mis servicios|banner)", content)
    servicios = re.findall(r"(?i)servicios", content)
    recursos = re.findall(r"(?i)recursos", content)
    cursos = re.findall(r"(?i)cursos", content)
    disqus = "disqus" in content.lower()
    copilot = "futuristic-app.js" in content.lower()

    print(f"{fname:45} | {len(banners):3} | {len(servicios):3} | {len(recursos):3} | {len(cursos):3} | {str(disqus):6} | {str(copilot):7}")

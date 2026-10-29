import re

files_to_clean = [
    "EvaluacionProyecto.html",
    "Proyecto2.html",
    "modelo-ventas.html",
    "power-bi.html",
    "proyecto3.html",
    "proyecto4.html"
]

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"

banner_regex = re.compile(
    r'(?:<br\s*/?>\s*)*<div\s+class=["\']separator["\'][^>]*>\s*(?:<span[^>]*>)?\s*<a\s+href="https?://jesusbezerpa\.github\.io/?"[^>]*>\s*<img[^>]*banner[^>]*>\s*(?:</a>)?\s*(?:</span>)?\s*</div>(?:\s*<br\s*/?>)*',
    re.IGNORECASE
)

for fname in files_to_clean:
    fpath = f"{repo_dir}\\{fname}"
    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
        content = fp.read()
    
    new_content, count = banner_regex.subn('\n', content)
    with open(fpath, "w", encoding="utf-8") as fp:
        fp.write(new_content)
    print(f"Cleaned {fname}: {count} banners removed.")

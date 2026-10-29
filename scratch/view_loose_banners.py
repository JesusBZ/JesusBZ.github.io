import re

for fname in ["Proyecto2.html", "modelo-ventas.html", "proyecto3.html"]:
    path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\\" + fname
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        lines = fp.readlines()
    for idx, l in enumerate(lines):
        if "banner" in l.lower():
            start = max(0, idx - 2)
            end = min(len(lines), idx + 3)
            print(f"--- {fname} L{idx+1} ---")
            for j in range(start, end):
                print(f"  {j+1}: {lines[j].strip()}")

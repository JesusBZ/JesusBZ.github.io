path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\Proyecto2.html"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    lines = fp.readlines()

for idx, l in enumerate(lines):
    if "compartir" in l.lower() or 'id="share"' in l.lower():
        start = max(0, idx - 4)
        end = min(len(lines), idx + 25)
        print(f"--- Proyecto2.html L{idx+1} ---")
        for j in range(start, end):
            print(f"  {j+1}: {lines[j].strip()}")
        break

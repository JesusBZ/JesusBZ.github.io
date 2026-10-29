path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\Proyecto2.html"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    lines = fp.readlines()

for idx, l in enumerate(lines):
    if "disqus" in l.lower():
        start = max(0, idx - 5)
        end = min(len(lines), idx + 25)
        print(f"--- Proyecto2.html L{idx+1} ---")
        for j in range(start, end):
            print(f"  {j+1}: {lines[j].strip()}")
        break

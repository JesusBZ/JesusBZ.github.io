path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\css\post-enhancement.css"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    lines = fp.readlines()

for idx, l in enumerate(lines):
    if "movetop" in l.lower() or "scroll" in l.lower():
        print(f"L{idx+1}: {l.strip()[:100]}")

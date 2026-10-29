path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\Proyecto2.html"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    lines = fp.readlines()

for idx, l in enumerate(lines):
    if "futuristic-app.js" in l:
        print(f"Proyecto2.html L{idx+1}: {l.strip()}")

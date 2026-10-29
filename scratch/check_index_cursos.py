with open(r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\index.html", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if "curso" in l.lower():
        print(f"L{i+1}: {l.strip()}")

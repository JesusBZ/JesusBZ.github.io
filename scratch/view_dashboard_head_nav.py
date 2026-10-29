path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\Dashboard.html"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    lines = fp.readlines()

print("=== Head lines (1-40) ===")
for l in lines[:40]:
    print(l.rstrip())

print("=== Navbar lines (350-410) ===")
for l in lines[350:410]:
    print(l.rstrip())

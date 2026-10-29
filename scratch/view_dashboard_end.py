path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\Dashboard.html"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    lines = fp.readlines()

print("=== End of Dashboard.html (lines 530-580) ===")
for l in lines[530:580]:
    print(l.rstrip())

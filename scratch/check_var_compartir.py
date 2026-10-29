path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\trading-vectores-autoregresivos-en-rstudio.html"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    c = fp.read()

idx = c.lower().find('compartir')
if idx != -1:
    print("Found compartir at", idx)
    print(c[idx-50:idx+300])
else:
    print("No compartir found")

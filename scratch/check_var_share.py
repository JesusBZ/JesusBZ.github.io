path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\trading-vectores-autoregresivos-en-rstudio.html"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    c = fp.read()

idx = c.find('id="share"')
if idx != -1:
    print("Found id=share at", idx)
    print(c[idx-100:idx+400])
else:
    print("No id=share found")

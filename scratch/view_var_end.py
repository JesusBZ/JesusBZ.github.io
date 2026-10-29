fpath = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\trading-vectores-autoregresivos-en-rstudio.html"
with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
    c = fp.read()

idx = c.find('dynamically load mathjax')
print(c[idx-800:idx])

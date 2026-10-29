with open(r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\Dashboard.html", "r", encoding="utf-8", errors="ignore") as fp:
    c = fp.read()
idx = c.find("disqus_thread")
print(c[idx:idx+500])

for fname in ["FinancialDashboard.htm", "trading-vectores-autoregresivos-en-rstudio.html"]:
    path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\\" + fname
    with open(path, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    print(f"{fname}: len={len(c)}, has_share={'share' in c.lower()}, has_disqus={'disqus' in c.lower()}")

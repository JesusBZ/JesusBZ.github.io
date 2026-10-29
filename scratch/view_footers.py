import os

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"

for fname in ["FinancialDashboard.htm", "trading-vectores-autoregresivos-en-rstudio.html"]:
    fpath = f"{repo_dir}\\{fname}"
    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
        lines = fp.readlines()
    print(f"=== Last 20 lines of {fname} ===")
    for l in lines[-20:]:
        print(l.rstrip())

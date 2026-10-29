import glob
import os
import re

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    
    if "disqus_thread" in c:
        # Find the script block after disqus_thread
        idx = c.find("disqus_thread")
        snippet = c[idx:idx+400]
        has_nested = "<script>\n<script>" in snippet or "<script>\r\n<script>" in snippet or snippet.count("<script>") > 1
        print(f"{fname:45} | Nested script: {has_nested}")

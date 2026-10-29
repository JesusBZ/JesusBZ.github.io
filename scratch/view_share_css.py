path = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io\css\post-enhancement.css"
with open(path, "r", encoding="utf-8", errors="ignore") as fp:
    lines = fp.readlines()

for idx, l in enumerate(lines):
    if "corporate-share-box" in l:
        start = max(0, idx - 1)
        end = min(len(lines), idx + 60)
        print(f"--- post-enhancement.css L{idx+1} ---")
        for j in range(start, end):
            print(f"  {j+1}: {lines[j].rstrip()}")
        break

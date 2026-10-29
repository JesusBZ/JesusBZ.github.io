import glob
import os
import re

repo_dir = r"C:\Users\jesus\OneDrive\Documentos\GitHub\JesusBZ.github.io"
html_files = glob.glob(os.path.join(repo_dir, "*.html")) + glob.glob(os.path.join(repo_dir, "*.htm"))

disqus_template = """<div class="disqus-container-modern">
<div id="disqus_thread"></div>
</div>
<script>
var disqus_config = function () {
this.page.url = 'https://jesusbz.github.io/{page_slug}';
this.page.identifier = '{page_slug}';
};
(function() {
var d = document, s = d.createElement('script');
s.src = 'https://portafolio-11.disqus.com/embed.js';
s.setAttribute('data-timestamp', +new Date());
(d.head || d.body).appendChild(s);
})();
</script>
<noscript>Por favor activa JavaScript para ver los comentarios soportados por <a href="https://disqus.com/?ref_noscript">Disqus</a>.</noscript>"""

for f in sorted(html_files):
    fname = os.path.basename(f)
    if "backup" in fname or fname in ["cursos.html", "acercade.html", "formulario.html", "index.html", "enviado.html", "google071051f5619c1708.html", "_header.html", "_footer.html", "FinancialDashboard.htm"]:
        continue
    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
        c = fp.read()
    
    clean_disqus = disqus_template.replace('{page_slug}', fname)
    
    if "disqus_thread" in c:
        new_c = re.sub(r'<div\s+id=["\']disqus_thread["\']></div>[\s\S]*?</noscript>', clean_disqus, c)
        with open(f, "w", encoding="utf-8") as fp:
            fp.write(new_c)
        print(f"Updated Disqus in {fname}")
    elif fname == "trading-vectores-autoregresivos-en-rstudio.html":
        # Insert before footer hr
        target = '<hr />\n<h5>\n<div>\n<div style="text-align: center;">\n<span style="color: #444444;"><span style="font-family: &quot;arial&quot;'
        if target in c:
            new_c = c.replace(target, clean_disqus + "\n" + target)
            with open(f, "w", encoding="utf-8") as fp:
                fp.write(new_c)
            print(f"Inserted Disqus in {fname}")
        else:
            # alternative insert before bootstrapStylePandocTables
            target2 = '// add bootstrap table styles to pandoc tables'
            idx = c.find(target2)
            if idx != -1:
                script_tag_idx = c.rfind('<script>', 0, idx)
                new_c = c[:script_tag_idx] + clean_disqus + "\n" + c[script_tag_idx:]
                with open(f, "w", encoding="utf-8") as fp:
                    fp.write(new_c)
                print(f"Inserted Disqus in {fname} before pandoc tables script")
            else:
                print(f"Could not find insertion point in {fname}")

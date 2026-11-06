"""Gera a vitrine estática do site (dados fictícios, nada é salvo).

Uso:  python scripts/build_demo_site.py [pasta_saida]
Cria um banco de demonstração, renderiza cada página do site e grava HTML
estático com links relativos, pronto para o GitHub Pages.
"""
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.web import create_app  # noqa: E402
from demo_data import build  # noqa: E402

BANNER = """
<div style="background:#1f6f72;color:#fff;padding:10px 16px;font:14px system-ui,sans-serif;text-align:center">
  Demonstração com dados fictícios: navegue à vontade, mas nada é salvo.
  · <a style="color:#fff" href="https://github.com/LucasAlan03/Organizador-de-estudos">Código no GitHub</a>
</div>
<script>
document.addEventListener('submit', function (e) {
  e.preventDefault();
  alert('Esta é só uma vitrine: os registros funcionam na versão local do app.');
});
</script>
"""


def to_relative(html: str, depth: int) -> str:
    prefix = "../" * depth
    def fix(m):
        attr, path = m.group(1), m.group(2)
        if path and not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
            path += "/"  # pastas com index.html
        target = prefix + path if (prefix or path) else "./"
        return f'{attr}="{target or "./"}"'
    return re.sub(r'(href|src|action)="/(?!/)([^"]*)"', fix, html)


def main(out: Path) -> None:
    tmp = Path(tempfile.mkdtemp())
    build(tmp / "demo.db", date.today())
    client = TestClient(create_app(tmp / "demo.db"))

    topics = re.findall(r'href="/teoria/([^"/]+)"', client.get("/teoria").text)
    urls = ["/", "/teoria", "/listas", "/historico", "/config"]
    urls += [f"/teoria/{t}" for t in dict.fromkeys(topics)]
    urls += [f"/listas/{t}" for t in dict.fromkeys(topics)]

    if out.exists():
        shutil.rmtree(out)
    for url in urls:
        r = client.get(url)
        r.raise_for_status()
        parts = [p for p in url.split("/") if p]
        html = to_relative(r.text, len(parts))
        html = html.replace("<body>", "<body>" + BANNER, 1)
        dest = out.joinpath(*parts, "index.html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html, encoding="utf-8")
    shutil.copytree(ROOT / "app" / "static", out / "static")
    (out / ".nojekyll").write_text("")
    print(f"{len(urls)} páginas em {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "demo-site")

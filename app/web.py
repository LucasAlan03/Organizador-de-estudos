"""Site do organizador (FastAPI + Jinja2). Todas as rotas ficam aqui."""
from __future__ import annotations

from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import stats
from app.catalog import DEFAULT_CATALOG, load_catalog
from app.db import connect, init_schema

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE / "templates"))


def fmt_min(minutes: float | None) -> str:
    """45 -> '45 min'; 90 -> '1h30'; 0 -> '0 min'."""
    if minutes is None:
        return "—"
    total = round(minutes)
    if total < 60:
        return f"{total} min"
    hours, rest = divmod(total, 60)
    return f"{hours}h{rest:02d}"


def pct(done: int, total: int) -> int:
    return round(100 * done / total) if total else 0


templates.env.filters["fmt_min"] = fmt_min
templates.env.globals["pct"] = pct


def redirect(url: str, ok: str | None = None, erro: str | None = None) -> RedirectResponse:
    """Redireciona (303) para `url`, levando um aviso de sucesso ou de erro."""
    params = {k: v for k, v in (("ok", ok), ("erro", erro)) if v}
    if params:
        url = f"{url}?{urlencode(params)}"
    return RedirectResponse(url, status_code=303)


def render(request: Request, name: str, **context) -> HTMLResponse:
    context.setdefault("ok", request.query_params.get("ok"))
    context.setdefault("erro", request.query_params.get("erro"))
    return templates.TemplateResponse(request, name, context)


def create_app(
    db_path: str | Path, today: Callable[[], date] = date.today
) -> FastAPI:
    app = FastAPI(title="Organizador de Estudos MMA")
    app.state.db_path = Path(db_path)
    app.state.today = today

    with closing(connect(app.state.db_path)) as conn:
        init_schema(conn)
        load_catalog(conn, DEFAULT_CATALOG)

    app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

    def get_conn():
        conn = connect(app.state.db_path)
        try:
            yield conn
        finally:
            conn.close()

    @app.get("/", response_class=HTMLResponse)
    def painel(request: Request, conn=Depends(get_conn)):
        dash = stats.dashboard(conn, app.state.today())
        return render(request, "painel.html", d=dash)

    return app

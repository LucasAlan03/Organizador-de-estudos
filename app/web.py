"""Site do organizador (FastAPI + Jinja2). Todas as rotas ficam aqui."""
from __future__ import annotations

from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import stats
from app.catalog import DEFAULT_CATALOG, load_catalog
from app.db import connect, init_schema
from app.logs import LogError, add_page_range_log, parse_minutes

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


def parse_day(raw: str) -> date:
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        raise LogError("Data inválida. Use o formato AAAA-MM-DD.") from None


def parse_int(raw: str, label: str) -> int:
    try:
        return int((raw or "").strip())
    except ValueError:
        raise LogError(f"Informe {label} como número inteiro.") from None


def topic_or_404(conn, topic_id: str):
    row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Assunto não encontrado")
    return row


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

    @app.get("/teoria", response_class=HTMLResponse)
    def teoria(request: Request, conn=Depends(get_conn)):
        return render(request, "teoria.html", topics=stats.topic_progress(conn, "page"))

    @app.get("/teoria/{topic_id}", response_class=HTMLResponse)
    def teoria_detalhe(topic_id: str, request: Request, conn=Depends(get_conn)):
        topic = topic_or_404(conn, topic_id)
        pages = stats.item_rows(conn, topic_id, "page")
        return render(
            request, "teoria_detalhe.html", topic=topic, pages=pages,
            done=sum(1 for p in pages if p.done), total=len(pages),
            today=app.state.today().isoformat(),
        )

    @app.post("/teoria/{topic_id}/registrar")
    def teoria_registrar(
        topic_id: str,
        page_from: str = Form(""), page_to: str = Form(""),
        minutes: str = Form(""), day: str = Form(""),
        conn=Depends(get_conn),
    ):
        topic_or_404(conn, topic_id)
        back = f"/teoria/{topic_id}"
        try:
            results = add_page_range_log(
                conn, topic_id,
                parse_int(page_from, "a página inicial"),
                parse_int(page_to, "a página final"),
                parse_minutes(minutes), parse_day(day), app.state.today(),
            )
        except LogError as exc:
            return redirect(back, erro=str(exc))
        total = parse_minutes(minutes)
        msg = f"Registrado: {len(results)} página(s), {fmt_min(total / len(results))} cada."
        if any(r.is_review for r in results):
            msg += " Algumas páginas já tinham registro: contado como revisão."
        return redirect(back, ok=msg)

    return app

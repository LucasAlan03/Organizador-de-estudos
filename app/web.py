"""Site do organizador (FastAPI + Jinja2). Todas as rotas ficam aqui."""
from __future__ import annotations

import re
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
from app.db import ensure_start_date, get_setting, set_setting
from app.logs import (
    LogError, add_many_item_logs, add_page_range_log, delete_log, parse_minutes, update_log,
)

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


def int_in_range(raw: str, low: int, high: int, label: str) -> int:
    try:
        value = int((raw or "").strip())
    except ValueError:
        raise LogError(f"{label}: informe um número inteiro.") from None
    if not low <= value <= high:
        raise LogError(f"{label}: use um valor de {low} a {high}.")
    return value


def validate_config(form: dict[str, str]) -> dict[str, str]:
    """Valida todos os campos de uma vez; devolve os valores prontos para gravar."""
    goal = int_in_range(form.get("daily_goal_min", ""), 15, 600, "Meta diária (min)")
    snooze = int_in_range(form.get("snooze_min", ""), 5, 180, "Adiamento (min)")
    try:
        exam = date.fromisoformat(form.get("exam_date", "").strip())
    except ValueError:
        raise LogError("Data da prova inválida. Use AAAA-MM-DD.") from None
    try:
        start = date.fromisoformat(form.get("start_date", "").strip())
    except ValueError:
        raise LogError("Data de início inválida. Use AAAA-MM-DD.") from None
    if start > exam:
        raise LogError("A data de início não pode ser depois da prova.")
    alert = form.get("alert_time", "").strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", alert):
        raise LogError("Horário do alerta inválido. Use HH:MM (ex.: 18:30).")
    return {
        "daily_goal_min": str(goal), "snooze_min": str(snooze),
        "exam_date": exam.isoformat(), "start_date": start.isoformat(), "alert_time": alert,
    }


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

    @app.get("/listas", response_class=HTMLResponse)
    def listas(request: Request, conn=Depends(get_conn)):
        return render(request, "listas.html", topics=stats.topic_progress(conn, "exercise"))

    @app.get("/listas/{topic_id}", response_class=HTMLResponse)
    def listas_detalhe(topic_id: str, request: Request, conn=Depends(get_conn)):
        topic = topic_or_404(conn, topic_id)
        rows = stats.item_rows(conn, topic_id, "exercise")
        exercises: dict[int, list] = {}
        for r in rows:
            exercises.setdefault(r.exercise, []).append(r)
        return render(
            request, "listas_detalhe.html", topic=topic, exercises=exercises,
            done=sum(1 for r in rows if r.done), total=len(rows),
            today=app.state.today().isoformat(),
        )

    @app.post("/listas/{topic_id}/registrar")
    async def listas_registrar(topic_id: str, request: Request, conn=Depends(get_conn)):
        topic_or_404(conn, topic_id)
        back = f"/listas/{topic_id}"
        form = await request.form()
        try:
            day = parse_day(str(form.get("day", "")))
            entries: list[tuple[int, float]] = []
            for key, value in form.multi_items():
                if not key.startswith("item_") or value != "on":
                    continue
                item_id = parse_int(key[len("item_"):], "o item")
                row = conn.execute(
                    "SELECT label FROM items WHERE id = ? AND topic_id = ? AND kind = 'exercise'",
                    (item_id, topic_id),
                ).fetchone()
                if row is None:
                    raise LogError("Um dos itens marcados não pertence a esta lista.")
                try:
                    minutes = parse_minutes(str(form.get(f"min_{item_id}", "")))
                except LogError as exc:
                    raise LogError(f"{row['label']}: {exc}") from None
                entries.append((item_id, minutes))
            results = add_many_item_logs(conn, entries, day, app.state.today())
        except LogError as exc:
            return redirect(back, erro=str(exc))
        msg = f"Registrado: {len(results)} item(ns)."
        if any(r.is_review for r in results):
            msg += " Alguns já tinham registro: contado como revisão."
        return redirect(back, ok=msg)

    def log_or_404(conn, log_id: int) -> None:
        if conn.execute("SELECT 1 FROM logs WHERE id = ?", (log_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Registro não encontrado")

    @app.get("/historico", response_class=HTMLResponse)
    def historico(request: Request, conn=Depends(get_conn)):
        goal = int(get_setting(conn, "daily_goal_min"))
        items, topics = stats.reinforcement_views(conn)
        return render(
            request, "historico.html",
            reinforcement_items=items, reinforcement_topics=topics,
            days=[(d, m, m >= goal) for d, m in stats.day_totals(conn)],
            logs=stats.recent_logs(conn), daily_goal=goal,
            today=app.state.today().isoformat(),
        )

    @app.post("/historico/{log_id}/editar")
    def historico_editar(
        log_id: int, minutes: str = Form(""), day: str = Form(""), conn=Depends(get_conn)
    ):
        log_or_404(conn, log_id)
        try:
            update_log(conn, log_id, parse_minutes(minutes), parse_day(day), app.state.today())
        except LogError as exc:
            return redirect("/historico", erro=str(exc))
        return redirect("/historico", ok="Registro atualizado.")

    @app.post("/historico/{log_id}/apagar")
    def historico_apagar(log_id: int, conn=Depends(get_conn)):
        log_or_404(conn, log_id)
        delete_log(conn, log_id)
        return redirect("/historico", ok="Registro apagado.")

    @app.get("/config", response_class=HTMLResponse)
    def config(request: Request, conn=Depends(get_conn)):
        ensure_start_date(conn, app.state.today())
        values = {
            k: get_setting(conn, k)
            for k in ("daily_goal_min", "exam_date", "start_date", "alert_time", "snooze_min")
        }
        try:
            telegram_connected = bool(get_setting(conn, "telegram_chat_id"))
        except KeyError:
            telegram_connected = False
        return render(
            request, "config.html", v=values, telegram_connected=telegram_connected
        )

    @app.post("/config")
    def config_salvar(
        daily_goal_min: str = Form(""), exam_date: str = Form(""),
        start_date: str = Form(""), alert_time: str = Form(""),
        snooze_min: str = Form(""), conn=Depends(get_conn),
    ):
        try:
            values = validate_config({
                "daily_goal_min": daily_goal_min, "exam_date": exam_date,
                "start_date": start_date, "alert_time": alert_time, "snooze_min": snooze_min,
            })
        except LogError as exc:
            return redirect("/config", erro=str(exc))
        for key, value in values.items():
            set_setting(conn, key, value)
        return redirect("/config", ok="Configurações salvas.")

    return app

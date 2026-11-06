# Site do Organizador de Estudos MMA (Fase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o site em `localhost` (catálogo, registro de tempo por item, painel com ritmo/veredito/reforço, histórico e configurações), sem Telegram.

**Architecture:** Um pacote Python `app/` com camadas separadas: `db.py` (SQLite), `catalog.py` (carga do catálogo), `logs.py` (registro), `pace.py` (contas puras), `stats.py` (monta dados do painel a partir do banco) e `web.py` (FastAPI + Jinja2, formulários HTML simples). O relógio (`today`) é injetado para testar datas.

**Tech Stack:** Python 3.11 (instalado: 3.11.8), FastAPI, uvicorn, Jinja2, python-multipart, SQLite (`sqlite3` da stdlib, sem ORM), pytest + httpx (TestClient).

**Spec:** `docs/superpowers/specs/2026-11-06-organizador-estudos-mma-design.md` (Fase 1; o bot é um plano separado, depois).

## Global Constraints

- Idioma de toda a interface: pt-BR. Nenhuma chamada de rede e nenhuma API paga.
- Prova: `2026-12-12`; dias restantes = `(prova - hoje).days` (hoje até 11/12 inclusive).
- Meta diária padrão: `90` (minutos); alerta `18:30`; adiamento `30` (guardados para a Fase 2).
- Minutos válidos: `0 < m <= 600`. Datas de registro no futuro são rejeitadas.
- Média diária = `minutos_totais ÷ max((hoje - início).days + 1, 1)`.
- Estimativa por unidade: média do assunto se tiver ≥ 3 itens feitos da natureza; senão a média global da natureza (≥ 3); senão `None`. Sem estimativas inventadas.
- Veredito: `necessário ≤ 0,9×média` → folga; `≤ 1,1×` → manter; acima → aumentar. Reforço: > `1,5×` a média da natureza, com ≥ 3 itens feitos da natureza.
- Meta da semana: `horas_restantes ÷ max(dias_restantes/7, 1)`, fixada toda segunda-feira.
- Banco: `data/study.db`; backups em `data/backups/`. `data/` e `.env` ficam fora do git.
- Assuntos, em ordem: fourier, pares-impares, conducao-calor, equacao-calor, onda, laplace.

## Review Focus

- Intervalo de páginas invertido (de > até) ou fora do PDF → rejeitado com mensagem, nada gravado.
- Mesmo item registrado duas vezes → aceito como revisão (tempo soma, progresso conta o item uma vez), com aviso.
- Primeiro dia de uso (`hoje == início`) e dia da prova ou depois → sem divisão por zero; mensagens próprias.
- Apagar o último registro de um dia volta o dia de `estudou` para `pendente`.
- Minutos em branco, texto ou com vírgula ("1,5") → vírgula aceita; o resto, erro amigável sem quebrar a página.

---

### Task 1: Esqueleto do projeto, banco e configurações

**Files:**
- Create: `.gitignore`, `requirements.txt`, `app/__init__.py`, `app/db.py`, `tests/conftest.py`, `tests/test_db.py`

**Interfaces:**
- Produces: `connect(path) -> sqlite3.Connection` (row_factory `sqlite3.Row`, `PRAGMA foreign_keys=ON`); `init_schema(conn) -> None`; `get_setting(conn, key: str) -> str`; `set_setting(conn, key: str, value: str) -> None`; `ensure_start_date(conn, today: date) -> date`.
- Tabelas: `settings(key PK, value)`, `topics(id PK, title, position, pdf_title, pdf_pages, list_title)`, `items(id INTEGER PK, key TEXT UNIQUE, kind CHECK IN ('page','exercise'), topic_id, exercise INT NULL, sub TEXT NULL, page INT NULL, label, position)`, `logs(id INTEGER PK, item_id, minutes REAL, day TEXT, created_at TEXT)`, `days(day PK, status CHECK IN ('pendente','vai_estudar','estudou','pulou') DEFAULT 'pendente', last_alert_at TEXT NULL)`, `weekly_goals(week_start PK, minutes REAL, created_at)`.
- Defaults em `settings`: `exam_date=2026-12-12`, `daily_goal_min=90`, `alert_time=18:30`, `snooze_min=30`.

- [ ] **Step 1: Criar o ambiente**: `python -m venv .venv`; `.venv/Scripts/python -m pip install fastapi uvicorn jinja2 python-multipart httpx pytest`; gravar as versões instaladas em `requirements.txt` (`pip freeze`); `.gitignore` com `.venv/`, `__pycache__/`, `data/`, `.env`, `.pytest_cache/`.
- [ ] **Step 2: Write the failing tests** em `tests/test_db.py`, usando a fixture `conn` (`tests/conftest.py`: banco temporário via `tmp_path`, `init_schema` aplicado):
  - `test_init_schema_is_idempotent` (chamar duas vezes não falha; `get_setting(conn,"exam_date") == "2026-12-12"`, `"daily_goal_min" == "90"`).
  - `test_set_and_get_setting` (`set_setting(conn,"daily_goal_min","120")` → `"120"`).
  - `test_ensure_start_date_sets_once` (primeira chamada com `date(2026,11,6)` grava e retorna; segunda com `date(2026,11,9)` retorna `date(2026,11,6)`).
- [ ] **Step 3: Run** `.venv/Scripts/python -m pytest tests/test_db.py -v` → FAIL (módulo inexistente).
- [ ] **Step 4: Implement** `app/db.py` conforme Interfaces. `init_schema` usa `CREATE TABLE IF NOT EXISTS` e `INSERT OR IGNORE` para os defaults.
- [ ] **Step 5: Run** os mesmos testes → PASS.
- [ ] **Step 6: Commit**: `git add -A && git commit -m "feat: esqueleto, banco SQLite e configuracoes"`.

---

### Task 2: Catálogo (assuntos, páginas de teoria, exercícios e subitens)

**Files:**
- Create: `catalog/catalog.json`, `app/catalog.py`, `tests/test_catalog.py`

**Interfaces:**
- Consumes: `connect`, `init_schema` (Task 1).
- Produces: `load_catalog(conn, path: Path) -> None` (idempotente: não duplica itens; atualiza títulos); `DEFAULT_CATALOG: Path` (`catalog/catalog.json`).
- Itens gerados: teoria → `key="{topic}:p{n}"`, `kind="page"`, `label="Página n"`; exercício → `key="{topic}:e{n}"` (sem subitens) ou `"{topic}:e{n}:{sub}"`, `kind="exercise"`, `label="Exercício n"` ou `"Exercício n (sub)"`. `position` crescente dentro do assunto e da natureza (páginas e exercícios têm sequências próprias).

Formato de `catalog/catalog.json`: `{"topics":[{"id","title","position","pdf":{"title","pages"},"list":{"title","exercises":[{"n":int,"subs":[str]}]}}]}`. Conteúdo (dados extraídos dos PDFs; `subs` vazio = exercício único):

| id | title | pdf.pages | exercícios `n: subs` |
|---|---|---|---|
| fourier | Séries de Fourier | 7 | 1: i,ii,iii · 2: a,b · 3: a,c · 4: a–g · 5: a–h · 6, 7, 8: sem subitens |
| pares-impares | Funções Pares e Ímpares | 7 | 1: a–j · 2: a–f · 3: a,b,c · 4: a,b · 5: a,b |
| conducao-calor | Condução do Calor | 7 | 1: a–f · 2: sem subitens · 3: a–d · 4: a,b · 5: a–f · 6: sem subitens · 7: a,b |
| equacao-calor | Equação do Calor | 6 | 1: a,b · 2: a,b · 3: a,b · 4: a,b · 5: sem subitens · 6: a,b,c,c2 (o PDF repete a letra "c"; o segundo vira `c2`) |
| onda | Equação da Onda | 7 | 1: a,b · 2: a,b · 3: a,b,c · 4: a,b · 5: a,b,c · 6: a–e |
| laplace | Equação de Laplace | 7 | 1: a–k |

Títulos de PDF/lista: `"Teoria — {title}"` e `"Lista — {title}"`. As letras `a–k` etc. são escritas por extenso no JSON (uma letra por elemento de `subs`).

- [ ] **Step 1: Write the failing tests** em `tests/test_catalog.py` (fixture `conn` com `load_catalog(conn, DEFAULT_CATALOG)`):
  - `test_counts`: 6 linhas em `topics` na ordem acima; 41 itens `kind='page'`; 111 itens `kind='exercise'`; `SELECT COUNT(*) ... WHERE topic_id='fourier' AND kind='exercise'` = 25.
  - `test_labels`: existe item com `key='fourier:e4:c'` e `label='Exercício 4 (c)'`; item `key='fourier:e6'` com `label='Exercício 6'`; `key='equacao-calor:e6:c2'` existe.
  - `test_idempotent`: carregar duas vezes mantém 152 itens no total (41+111).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Escrever `catalog/catalog.json`** com os dados da tabela e **implementar `load_catalog`** (`INSERT ... ON CONFLICT(key) DO UPDATE` nos itens e `ON CONFLICT(id)` nos assuntos).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: catalogo de listas e teoria (6 assuntos)"`.

---

### Task 3: Registro de estudo (validação, revisão, status do dia)

**Files:**
- Create: `app/logs.py`, `tests/test_logs.py`

**Interfaces:**
- Consumes: `connect`, `init_schema`, `load_catalog`, tabelas `items`, `logs`, `days`.
- Produces:
  - `class LogError(ValueError)` (mensagem em pt-BR própria para exibir ao usuário).
  - `parse_minutes(raw: str) -> float` (aceita `"45"`, `"1,5"`, `"1.5"`; `LogError` para vazio, texto ou fora de `0 < m <= 600`).
  - `@dataclass AddResult: log_id: int; item_id: int; is_review: bool`.
  - `add_item_log(conn, item_id: int, minutes: float, day: date, today: date) -> AddResult` (`LogError` se `day > today` ou item inexistente).
  - `add_page_range_log(conn, topic_id: str, page_from: int, page_to: int, minutes: float, day: date, today: date) -> list[AddResult]` (minutos divididos igualmente entre as páginas do intervalo; `LogError` se `page_from > page_to` ou fora de `1..pdf_pages`; tudo-ou-nada).
  - `update_log(conn, log_id: int, minutes: float, day: date, today: date) -> None`; `delete_log(conn, log_id: int) -> None`.
  - `recompute_day_status(conn, day: date) -> None` (com logs no dia → `estudou`; sem logs e status atual `estudou` → `pendente`; outros status ficam).
- Toda escrita chama `recompute_day_status` (inclusive para o dia antigo em `update_log`) e faz `conn.commit()`.

- [ ] **Step 1: Write the failing tests** (`tests/test_logs.py`, `TODAY = date(2026,11,6)`):
  - `test_parse_minutes_accepts_comma`: `parse_minutes("1,5") == 1.5`; `"45" → 45.0`.
  - `test_parse_minutes_rejects`: `""`, `"abc"`, `"0"`, `"-3"`, `"601"` levantam `LogError`.
  - `test_page_range_splits_equally`: `add_page_range_log(conn,"fourier",2,4,90,TODAY,TODAY)` → 3 resultados, 3 linhas em `logs`, cada uma com `minutes == 30`.
  - `test_page_range_rejects_inverted_and_out_of_range`: `(4,2)` e `(1,8)` (fourier tem 7 páginas) levantam `LogError` e `COUNT(*) FROM logs == 0`.
  - `test_review_flag`: primeiro `add_item_log` → `is_review False`; segundo no mesmo item → `True`; ambas as linhas existem.
  - `test_future_day_rejected`: `day=date(2026,11,7)` → `LogError`.
  - `test_day_status_follows_logs`: após um registro, `days.status == 'estudou'`; após `delete_log` desse único registro, `'pendente'`.
  - `test_update_log_moves_day_status`: registro de 06/11 movido para 05/11 → 05/11 `estudou`, 06/11 `pendente`.
- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/test_logs.py -v` → FAIL.
- [ ] **Step 3: Implement** as funções acima. Mensagens de erro curtas, em pt-BR (ex.: `"Informe os minutos (de 1 a 600)."`, `"As páginas devem ir de 1 a 7."`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: registro de estudo com validacao e status do dia"`.

---

### Task 4: Contas de ritmo — média, estimativas, horas restantes

**Files:**
- Create: `app/pace.py`, `tests/test_pace.py`

**Interfaces:**
- Produces (tudo puro, sem I/O):
  - `@dataclass(frozen=True) ItemStat: item_id: int; kind: str; topic_id: str; position: int; minutes: float; done: bool` (`minutes` = total registrado no item; `done = minutes > 0`).
  - `avg_minutes_per_day(total_minutes: float, start: date, today: date) -> float`.
  - `class Estimates` com `for_item(kind: str, topic_id: str) -> float | None`; `unit_estimates(items: Sequence[ItemStat], min_records: int = 3) -> Estimates`.
  - `remaining_minutes(items: Sequence[ItemStat], est: Estimates) -> float | None` (`None` se algum item pendente não tem estimativa; `0.0` se não há pendentes).
  - `days_left(today: date, exam: date) -> int` (`(exam - today).days`, pode ser ≤ 0).

- [ ] **Step 1: Write the failing tests** (`tests/test_pace.py`; helper `stat(kind, topic, minutes, pos=1)` cria `ItemStat` com ids sequenciais):
  - `test_avg_minutes_per_day`: `avg_minutes_per_day(540, date(2026,11,6), date(2026,11,8)) == 180`; com `today == start` → divide por 1 (`540 → 540`).
  - `test_estimate_uses_topic_when_enough`: três páginas feitas de `fourier` com 10, 20, 30 → `for_item("page","fourier") == 20`.
  - `test_estimate_falls_back_to_global`: além disso, duas páginas de `onda` com 40 e 60 → `for_item("page","onda") == 32` (média das 5: (10+20+30+40+60)/5).
  - `test_estimate_none_when_not_enough_data`: só 2 páginas feitas no total → `for_item("page","fourier") is None`.
  - `test_remaining_minutes`: com estimativa de página = 20 e de exercício = 15, e pendentes 2 páginas + 1 exercício → `55`; se não há estimativa de exercício → `None`; sem pendentes → `0.0`.
  - `test_days_left`: `(date(2026,12,11), date(2026,12,12)) → 1`; `12/12 → 0`; `13/12 → -1`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (média por item feito, agrupando por `(kind, topic_id)` e por `kind`). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: contas de ritmo (media, estimativas, restante)"`.

---

### Task 5: Veredito e meta da semana

**Files:**
- Modify: `app/pace.py`, `tests/test_pace.py`

**Interfaces:**
- Consumes: `remaining_minutes`, `days_left` (Task 4).
- Produces: `@dataclass(frozen=True) Verdict: kind: str; required_per_day: float | None; message: str` com `kind` ∈ `insufficient | done | exam_arrived | folga | manter | aumentar`; `verdict(remaining: float | None, days: int, avg_per_day: float) -> Verdict`; `week_goal(remaining: float | None, days: int) -> float | None`.
- Mensagens (pt-BR): `insufficient` → "Dados insuficientes: registre mais itens para eu estimar o que falta."; `done` → "Tudo feito. Bom trabalho!"; `exam_arrived` → "A prova chegou (ou já passou)."; `folga` → "Dá para folgar: você precisa de ~N min/dia."; `manter` → "No caminho: mantenha ~N min/dia."; `aumentar` → "Aumente para ~N min/dia para fechar até 11/12." (N = `round(required_per_day)`).

- [ ] **Step 1: Write the failing tests**:
  - `test_verdict_insufficient`: `verdict(None, 10, 50).kind == "insufficient"`.
  - `test_verdict_done`: `verdict(0.0, 10, 50).kind == "done"`.
  - `test_verdict_exam_arrived`: `verdict(100.0, 0, 50).kind == "exam_arrived"` (e `days=-2`).
  - `test_verdict_three_branches` com `remaining=600`, `days=10` (necessário 60): `avg=70 → "folga"`, `avg=60 → "manter"`, `avg=40 → "aumentar"` com `required_per_day == 60`; `avg=0 → "aumentar"` sem divisão por zero; a mensagem de `aumentar` contém `"60 min/dia"`.
  - `test_week_goal`: `week_goal(600, 21) == 200`; `week_goal(600, 3) == 600` (mínimo de 1 semana); `week_goal(None, 21) is None`; `week_goal(600, 0) is None`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** com as constantes `FOLGA = 0.9`, `MANTER = 1.1`. **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: veredito de ritmo e meta da semana"`.

---

### Task 6: Reforço e próximo item sugerido

**Files:**
- Modify: `app/pace.py`, `tests/test_pace.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) ReinforcementItem: item_id: int; ratio: float`; `@dataclass(frozen=True) ReinforcementTopic: topic_id: str; kind: str; ratio: float`; `reinforcement(items: Sequence[ItemStat], factor: float = 1.5, min_records: int = 3) -> tuple[list[ReinforcementItem], list[ReinforcementTopic]]` (ambas ordenadas por `ratio` decrescente; `ratio = minutos_do_item ÷ média_global_da_natureza`, ou `média_do_assunto ÷ média_global`); `next_item(items: Sequence[ItemStat], topic_order: Sequence[str]) -> int | None` (primeiro assunto da ordem com pendência: páginas pendentes primeiro por `position`, depois exercícios pendentes; `None` se tudo feito).

- [ ] **Step 1: Write the failing tests**:
  - `test_reinforcement_items`: páginas feitas com 10, 10, 10, 60 → o primeiro `ReinforcementItem` é o item de 60 min, `ratio ≈ 2.67` (60 ÷ 22,5); os de 10 não aparecem.
  - `test_reinforcement_needs_min_records`: só 2 itens feitos → listas vazias.
  - `test_reinforcement_topics`: assunto `a` com páginas 60, 60, 60 e assunto `b` com 10, 10, 10 (média global 35) → `ReinforcementTopic("a","page",≈1.71)` presente e nada de `b`.
  - `test_next_item_order`: com `topic_order=["fourier","onda"]`, fourier com uma página pendente e exercícios pendentes → devolve a página; fourier com só exercícios pendentes → o primeiro exercício por `position`; fourier todo feito → primeiro pendente de `onda`; tudo feito → `None`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: reforco e proximo item sugerido"`.

---

### Task 7: Camada de dados do painel (`stats.py`)

**Files:**
- Create: `app/stats.py`, `tests/test_stats.py`

**Interfaces:**
- Consumes: banco + `pace.py` + `get_setting`/`ensure_start_date` (Task 1), `ItemStat` (Task 4).
- Produces:
  - `item_stats(conn) -> list[ItemStat]` (soma de `logs.minutes` por item).
  - `@dataclass TopicProgress: topic_id: str; title: str; done: int; total: int` e `topic_progress(conn, kind: str) -> list[TopicProgress]` (ordem dos assuntos).
  - `@dataclass Dashboard: days_left: int; total_minutes: float; avg_per_day: float; today_minutes: float; daily_goal: int; within_goal: bool; theory: tuple[int,int]; exercises: tuple[int,int]; verdict: Verdict; remaining_minutes: float | None; week_goal: float | None; week_minutes: float; reinforcement_items: list[...]; reinforcement_topics: list[...]; next_item_label: str | None` e `dashboard(conn, today: date) -> Dashboard`.
  - `ensure_weekly_goal(conn, today: date) -> float | None` (segunda-feira da semana como chave em `weekly_goals`; se já existe, devolve o gravado; se a estimativa ainda é `None`, não grava e devolve `None`).
  - `day_totals(conn, limit: int = 60) -> list[tuple[str, float]]` (dias com registro, mais recentes primeiro).
- `dashboard` chama `ensure_start_date(conn, today)` e `ensure_weekly_goal`.

- [ ] **Step 1: Write the failing tests** (`conn` com catálogo; `today=date(2026,11,6)`):
  - `test_dashboard_empty`: sem registros → `verdict.kind == "insufficient"`, `total_minutes == 0`, `theory == (0, 41)`, `exercises == (0, 111)`, `days_left == 36`, `next_item_label == "Página 1"`, `within_goal is False`.
  - `test_dashboard_after_logs`: registrar 3 páginas de fourier (10, 20, 30) e 3 subitens de exercício (15 cada), hoje, via `logs` → `total_minutes == 105`, `today_minutes == 105`, `within_goal is True` (meta 90), `theory == (3, 41)`, `remaining_minutes` não é `None`, `week_goal` não é `None`.
  - `test_weekly_goal_is_fixed_for_the_week`: `ensure_weekly_goal` na segunda 09/11 grava; novos registros na quarta 11/11 não mudam o valor devolvido; na segunda seguinte (16/11) recalcula.
  - `test_review_does_not_inflate_progress`: dois registros no mesmo item → `theory[0] == 1`, `total_minutes` soma os dois.
  - `test_topic_progress`: `topic_progress(conn,"page")[0] == TopicProgress("fourier","Séries de Fourier",done,7)`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: camada de dados do painel"`.

---

### Task 8: Aplicação web — base, estilo e Painel

**Files:**
- Create: `app/web.py`, `app/templates/base.html`, `app/templates/painel.html`, `app/static/style.css`, `tests/test_web_painel.py`

**Interfaces:**
- Consumes: `connect`, `init_schema`, `load_catalog`, `DEFAULT_CATALOG`, `stats.dashboard`.
- Produces: `create_app(db_path: str | Path, today: Callable[[], date] = date.today) -> FastAPI` (inicializa schema e catálogo ao criar; uma conexão por requisição; `templates` e `/static` montados; helper `redirect(url, ok=None, erro=None)` que devolve 303 com `?ok=`/`?erro=` e o template base exibe esses avisos).
- Rota `GET /` → Painel. Menu em `base.html`: Painel · Teoria · Listas · Histórico e reforço · Configurações.
- Painel mostra: "Faltam N dias para a prova"; barras de progresso (teoria e exercícios, `done/total`); horas totais e média por dia; "Hoje: X / meta min" com selo dentro/abaixo; veredito (mensagem); meta da semana (ou "—") com o feito na semana; até 5 itens e assuntos de reforço; "Próximo sugerido: {label}" (com o assunto).
- Estilo: seguir a skill `frontend-design` ao escrever `style.css` (tokens de cor em `:root`, tema claro/escuro por `prefers-color-scheme`, `<meta viewport>`, layout responsivo, barras de progresso em `div`s). Sem frameworks nem CDN.

- [ ] **Step 1: Write the failing tests** (`create_app(tmp_path/"t.db", today=lambda: date(2026,11,6))` + `TestClient`):
  - `test_painel_ok`: `GET /` → 200; texto contém `"Faltam 36 dias"`, `"Dados insuficientes"`, `"Próximo sugerido"`, `"Página 1"`.
  - `test_static_css`: `GET /static/style.css` → 200.
  - `test_flash_messages`: `GET /?erro=Algo%20deu%20errado` mostra `"Algo deu errado"` (escapado).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: app web com painel"`.

---

### Task 9: Tela de Teoria

**Files:**
- Create: `app/templates/teoria.html`, `app/templates/teoria_detalhe.html`, `tests/test_web_teoria.py`
- Modify: `app/web.py`

**Interfaces:**
- Consumes: `logs.add_page_range_log`, `parse_minutes`, `LogError`, `stats.topic_progress`, `redirect` (Task 8).
- Produces rotas: `GET /teoria` (uma barra por PDF com `done/total` páginas, link para o detalhe); `GET /teoria/{topic_id}` (404 se o assunto não existe; grade das páginas com cada uma marcada feita/pendente e o tempo acumulado; formulário `páginas de [de] a [até]`, `minutos`, `data` com padrão hoje); `POST /teoria/{topic_id}/registrar` (campos `page_from`, `page_to`, `minutes`, `day`; sucesso → redireciona ao detalhe com `ok=` ("Registrado: N páginas, X min cada" e, se houver revisão, o aviso "Algumas páginas já tinham registro: contado como revisão."); `LogError` ou número inválido → redireciona com `erro=` sem gravar).

- [ ] **Step 1: Write the failing tests**:
  - `test_teoria_list`: `GET /teoria` contém `"Teoria — Séries de Fourier"` e `"0/7"`.
  - `test_registrar_pages`: `POST /teoria/fourier/registrar` (`page_from=1,page_to=3,minutes=45,day=2026-11-06`, `follow_redirects=False`) → 303; depois o detalhe mostra `"3/7"` e a página 1 como feita.
  - `test_registrar_rejects_bad_input`: `page_from=4,page_to=2` → 303 com `erro` no `Location`; `minutes=abc` idem; `minutes=1,5` com `page_from=page_to=1` é aceito; nada gravado nos casos de erro.
  - `test_review_notice`: registrar a página 1 duas vezes → o `ok` da segunda contém `"revisão"`.
  - `test_unknown_topic_404`: `GET /teoria/xyz` → 404.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: tela de teoria com registro por intervalo de paginas"`.

---

### Task 10: Tela de Listas

**Files:**
- Create: `app/templates/listas.html`, `app/templates/listas_detalhe.html`, `tests/test_web_listas.py`
- Modify: `app/web.py`

**Interfaces:**
- Consumes: `logs.add_item_log`, `parse_minutes`, `LogError`, `stats.topic_progress`.
- Produces rotas: `GET /listas` (uma barra por lista, `done/total` subitens); `GET /listas/{topic_id}` (404 se inexistente; exercícios agrupados, cada subitem com caixa de marcação `item_<id>`, campo `min_<id>`, e, se já feito, o tempo acumulado; data padrão hoje); `POST /listas/{topic_id}/registrar` (campo `day` e pares `item_<id>=on` + `min_<id>`; cada marcado vira um registro; **tudo-ou-nada**: se qualquer minuto for inválido nada é gravado e volta com `erro=`; sem nenhum marcado → `erro=` "Marque ao menos um item."; sucesso → `ok=`).

- [ ] **Step 1: Write the failing tests**:
  - `test_listas_list`: `GET /listas` contém `"Lista — Séries de Fourier"` e `"0/25"`.
  - `test_registrar_subitems`: marcar `fourier:e4:c` e `fourier:e6` (buscar os ids no banco) com 20 e 35 min → 303; detalhe mostra `"2/25"`.
  - `test_all_or_nothing`: um marcado com minutos válidos e outro com `abc` → 303 com `erro`; `COUNT(*) FROM logs == 0`.
  - `test_nothing_checked`: POST sem marcados → `erro` contém "Marque ao menos um item".
  - `test_unknown_topic_404`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: tela de listas com registro por subitem"`.

---

### Task 11: Reforço e histórico (editar/apagar)

**Files:**
- Create: `app/templates/historico.html`, `tests/test_web_historico.py`
- Modify: `app/web.py`

**Interfaces:**
- Consumes: `logs.update_log`, `logs.delete_log`, `stats.dashboard`/`pace.reinforcement`, `stats.day_totals`.
- Produces rotas: `GET /historico` (seções: **Reforço** — itens e assuntos acima de 1,5× com a razão; **Por dia** — minutos por dia com selo dentro/abaixo da meta diária; **Registros** — lista com assunto, item, minutos, data, e formulários de editar e apagar; apagar pede confirmação com `onsubmit="return confirm(...)"`); `POST /historico/{log_id}/editar` (`minutes`, `day`); `POST /historico/{log_id}/apagar`. Erros e sucessos voltam com `erro=`/`ok=`. `log_id` inexistente → 404.

- [ ] **Step 1: Write the failing tests**:
  - `test_historico_empty`: `GET /historico` → 200 e mensagem de "nenhum registro".
  - `test_delete_log_reverts_day`: registrar um item via POST de teoria, apagar o log → registros vazios e o dia 06/11 voltou a `pendente`.
  - `test_edit_log`: editar minutos de 30 para 45 → a página mostra `45`.
  - `test_edit_invalid_minutes_keeps_data`: `minutes=0` → `erro`, valor anterior mantido.
  - `test_reinforcement_listed`: registrar 4 páginas feitas (10, 10, 10, 60 min) → a seção de reforço cita a página de 60 min.
  - `test_unknown_log_404` para editar e apagar.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit**: `git add -A && git commit -m "feat: historico, reforco e edicao de registros"`.

---

### Task 12: Configurações, backups, execução e README

**Files:**
- Create: `app/backup.py`, `app/__main__.py`, `app/templates/config.html`, `iniciar.bat`, `README.md`, `tests/test_backup.py`, `tests/test_web_config.py`
- Modify: `app/web.py`

**Interfaces:**
- Produces:
  - `backup_db(db_path: Path, backup_dir: Path, today: date, keep: int = 14) -> Path | None` (copia para `study-YYYY-MM-DD.db` se ainda não existe e apaga os mais antigos além de `keep`; devolve o caminho criado ou `None`).
  - Rotas `GET /config` e `POST /config` (campos: `daily_goal_min` inteiro 15–600, `exam_date` e `start_date` em `AAAA-MM-DD`, `alert_time` `HH:MM`, `snooze_min` inteiro 5–180; validação com mensagens em pt-BR; o ID do Telegram aparece como "Telegram: ainda não configurado (Fase 2)").
  - `python -m app` sobe `uvicorn` em `127.0.0.1:8000` com `data/study.db`, chamando `backup_db` na inicialização; `iniciar.bat` ativa `.venv` e roda `python -m app`.
  - `README.md` (pt-BR): o que é, como instalar (`python -m venv`, `pip install -r requirements.txt`), como rodar (`iniciar.bat` ou `python -m app`), como testar (`pytest`), estrutura de pastas, decisões do design e roadmap (Fase 2: bot do Telegram).

- [ ] **Step 1: Write the failing tests**:
  - `test_backup_creates_once_and_prunes`: com 16 arquivos de dias anteriores e `keep=14`, `backup_db(...)` cria o de hoje, devolve o caminho, e restam 14 (os mais recentes); segunda chamada no mesmo dia devolve `None`; sem `db_path` existente devolve `None` sem erro.
  - `test_config_roundtrip`: `POST /config` com `daily_goal_min=120` → 303; `GET /config` mostra `120`; `get_setting(conn,"daily_goal_min") == "120"`.
  - `test_config_validation`: `daily_goal_min=5`, `exam_date=2026-13-40`, `alert_time=25:99`, `snooze_min=0` → cada um dá `erro` e nada muda.
  - `test_config_changes_dashboard`: mudar a meta para 30 e registrar 30 min hoje → o painel mostra o selo "dentro da meta".
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** os arquivos acima. **Step 4: Run** a suíte inteira `.venv/Scripts/python -m pytest -v` → todos PASS.
- [ ] **Step 5: Verificação manual**: rodar `python -m app` em segundo plano, `curl http://127.0.0.1:8000/` e `/teoria`, `/listas`, `/historico`, `/config` devolvem 200; registrar 3 itens pelo site via `curl -d` e conferir o painel; parar o servidor.
- [ ] **Step 6: Commit**: `git add -A && git commit -m "feat: configuracoes, backups, execucao e README"`.

---

## Auto-revisão

- **Cobertura da spec (Fase 1):** catálogo (T2); registro por item e revisão (T3); média acumulada, estimativas sem chute, restante, veredito, meta da semana, reforço, próximo item (T4–T6); painel, teoria, listas, histórico/reforço, configurações (T7–T12); backups (T12); testes unitários e de integração (todas); o relógio injetado vem de `create_app(today=...)`. Fora desta fase: bot, agendador, `last_alert_at` em uso e catch-up (plano da Fase 2; as colunas já existem).
- **Consistência de nomes:** `ItemStat`, `Estimates.for_item`, `Verdict`, `week_goal`, `reinforcement`, `next_item`, `Dashboard`, `TopicProgress`, `redirect`, `create_app` aparecem com a mesma assinatura em todas as tarefas.
- **Decisão registrada:** faixa de páginas com um tempo total divide igualmente entre as páginas (o usuário informa "páginas X a Y e o tempo"); exercícios têm tempo próprio por subitem. A spec foi ajustada para formulários HTML simples (sem HTMX).

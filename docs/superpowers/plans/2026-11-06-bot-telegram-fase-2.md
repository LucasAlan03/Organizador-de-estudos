# Bot do Telegram (Fase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enviar o alerta diário de estudo no Telegram (18:30) com os botões "Consigo agora", "Daqui 30 min" e "Hoje não", sem custo e sem IA.

**Architecture:** Um *tick* a cada 30 s decide, a partir do estado no SQLite e de um relógio injetado, se deve enviar o alerta (isso cobre o horário normal, o adiamento e o catch-up ao ligar o PC com o mesmo código). A decisão é uma função pura (`alerts.py`); o Telegram fica atrás de um cliente fino sobre `httpx` (`telegram_api.py`); `bot.py` junta os dois e roda em uma thread ao lado do site.

**Tech Stack:** Python 3.11, `httpx` (já instalado, sem nova dependência), SQLite, pytest com `httpx.MockTransport` e um cliente falso. Nenhum teste usa rede.

**Spec:** `docs/superpowers/specs/2026-11-06-organizador-estudos-mma-design.md` (seção 6, Alerta diário). Rulings do plano: (1) `httpx` direto em vez de python-telegram-bot, para evitar APScheduler e dependências pesadas, sendo o uso de 4 métodos da API; (2) `vai_estudar` também interrompe os alertas do dia.

## Global Constraints

- Custo zero: sem API paga, sem IA no bot.
- Token só em `.env` (`TELEGRAM_BOT_TOKEN`), nunca em código, log, teste ou commit; mensagens de erro não podem incluir a URL com o token.
- Horário do alerta: `alert_time` (padrão `18:30`); adiamento: `snooze_min` (padrão `30`); **sem alertas depois das 22:00**.
- Sem alerta se o dia já está `estudou` ou `pulou`.
- O primeiro `/start` grava `telegram_chat_id`; depois o bot só responde a esse chat.
- O site não pode depender do bot: falha do Telegram nunca derruba o site.
- Textos em pt-BR.

## Review Focus

- Update de um chat diferente do gravado: ignorado, sem resposta.
- Botão apertado duas vezes ou em mensagem de outro dia: resposta curta, estado não corrompido.
- Telegram fora do ar / sem internet: o tick continua, com espera crescente, e o alerta sai quando voltar (dentro da janela até 22:00).
- Alerta às 21:59 adiado para depois das 22:00: não reenvia.
- Dia vira com o bot ligado: o alerta do novo dia sai uma vez, e o do anterior não repete.
- `alert_time` alterado no site: vale sem reiniciar (lido a cada tick).

---

### Task 1: Regra de alerta e estado do dia

**Files:**
- Create: `app/alerts.py`, `tests/test_alerts.py`
- Modify: `app/db.py` (colunas novas em `days`, migração em `init_schema`), `tests/test_db.py`

**Interfaces:**
- Produces: `days` ganha `snooze_until TEXT` e `alert_count INTEGER NOT NULL DEFAULT 0`; `init_schema` adiciona as colunas a bancos existentes (`ALTER TABLE` se faltarem).
- Produces: `CUTOFF = time(22, 0)`.
- Produces: `should_alert(status: str, now: datetime, alert_time: time, snooze_until: datetime | None, last_alert_at: datetime | None) -> bool`.
- Produces: `get_day(conn, day: date) -> sqlite3.Row` (cria a linha `pendente` se não existir), `mark_alert_sent(conn, now: datetime) -> None` (grava `last_alert_at`, soma `alert_count`, zera `snooze_until`), `apply_action(conn, action: str, now: datetime, snooze_min: int) -> str` com `action` em `agora | adiar | hoje_nao`; devolve o texto de resposta em pt-BR. `agora` → `vai_estudar`; `adiar` → `snooze_until = now + snooze_min`; `hoje_nao` → `pulou`.

- [ ] **Step 1: Write the failing tests** em `tests/test_alerts.py`: `test_no_alert_before_alert_time`; `test_alert_at_alert_time_when_pendente`; `test_catch_up_sends_once_after_alert_time` (19:40, sem `last_alert_at`, devolve True; com `last_alert_at` de hoje, False); `test_no_alert_after_2200` (21:59 True, 22:00 False); `test_no_alert_when_estudou_pulou_or_vai_estudar`; `test_snooze_blocks_until_due` (antes de `snooze_until` False, depois True); `test_snooze_past_2200_never_fires`; `test_apply_action_agora_sets_vai_estudar`; `test_apply_action_hoje_nao_sets_pulou`; `test_apply_action_adiar_sets_snooze_until_now_plus_30`; `test_apply_action_after_estudou_keeps_estudou` (botão tardio não rebaixa o status); `test_mark_alert_sent_clears_snooze_and_counts`. Em `tests/test_db.py`: `test_init_schema_migrates_old_days_table` (cria `days` sem as colunas, roda `init_schema`, colunas existem, linhas preservadas).
- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_alerts.py tests/test_db.py -q`. Expected: FAIL (módulo e colunas ausentes).
- [ ] **Step 3: Implement** `should_alert` como função pura (ordem: status ≠ `pendente` → False; `now.time() >= CUTOFF` → False; `now.time() < alert_time` → False; `snooze_until` definido → `now >= snooze_until`; senão → `last_alert_at` não é de hoje) e as funções de banco; migração por `PRAGMA table_info(days)`.
- [ ] **Step 4: Run** a suíte inteira (`.venv\Scripts\python -m pytest -q`). Expected: tudo passa.
- [ ] **Step 5: Commit** `feat: regra de alerta diário e estado do dia`.

### Task 2: Cliente Telegram e `.env`

**Files:**
- Create: `app/telegram_api.py`, `app/env.py`, `tests/test_telegram_api.py`, `tests/test_env.py`, `.env.example`

**Interfaces:**
- Produces: `load_env(path: Path) -> dict[str, str]` (linhas `CHAVE=valor`, ignora vazias e `#`, remove aspas; arquivo ausente → `{}`).
- Produces: `class TelegramError(RuntimeError)` (mensagem sem token).
- Produces: `class TelegramClient(token: str, http: httpx.Client | None = None)` com `get_updates(offset: int | None, timeout: int = 25) -> list[dict]`, `send_message(chat_id: int, text: str, buttons: list[list[tuple[str, str]]] | None = None) -> int` (devolve `message_id`; botões são `(texto, callback_data)`), `answer_callback(callback_id: str, text: str = "") -> None`, `edit_message(chat_id: int, message_id: int, text: str) -> None` (remove o teclado).
- Todo erro HTTP, de rede ou `ok: false` vira `TelegramError` sem o token na mensagem.

- [ ] **Step 1: Write the failing tests** com `httpx.MockTransport`: `test_send_message_posts_text_and_inline_keyboard` (corpo JSON com `reply_markup.inline_keyboard`, devolve o `message_id` da resposta); `test_get_updates_passes_offset_and_timeout`; `test_ok_false_raises_telegram_error`; `test_network_error_raises_without_token_in_message` (token `123:SECRET`, `"SECRET" not in str(erro)`); `test_edit_message_removes_keyboard`. Em `test_env.py`: `test_load_env_parses_values_quotes_comments`, `test_load_env_missing_file_returns_empty`.
- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_telegram_api.py tests/test_env.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** sobre `httpx.Client` com URL `https://api.telegram.org/bot<token>/<método>`; o timeout do cliente deve ser maior que o `timeout` do long polling. Criar `.env.example` com `TELEGRAM_BOT_TOKEN=`.
- [ ] **Step 4: Run** a suíte inteira. Expected: tudo passa.
- [ ] **Step 5: Commit** `feat: cliente Telegram sobre httpx e leitura de .env`.

### Task 3: Bot (tick, botões, /start)

**Files:**
- Create: `app/bot.py`, `tests/test_bot.py`
- Modify: `tests/conftest.py` (fixture `FakeTelegram` que registra chamadas e entrega updates programados)

**Interfaces:**
- Consumes: Task 1 (`should_alert`, `get_day`, `mark_alert_sent`, `apply_action`) e Task 2 (`TelegramClient`, `TelegramError`).
- Produces: `class Bot(conn: sqlite3.Connection, client, now: Callable[[], datetime])` com `tick() -> bool` (envia o alerta se `should_alert`; devolve se enviou), `handle_update(update: dict) -> None`, `run(stop: threading.Event) -> None`.
- `Bot` recebe também `project_path: str` (pasta do projeto, em texto puro numa linha própria da mensagem, para copiar e colar no Explorador). O alerta e a resposta de "Consigo agora" terminam com `Pasta: <project_path>` (e "Consigo agora" ainda traz `http://127.0.0.1:8765`).
- Alerta: texto `Hora de estudar? Hoje: <min> de <meta> min.` + linha `Pasta: <project_path>` e botões com `callback_data` `agora`, `adiar`, `hoje_nao`, rótulos "Consigo agora", "Daqui 30 min" (usa `snooze_min`), "Hoje não".
- `/start` sem chat gravado grava `telegram_chat_id` (em `settings`) e responde confirmação; `/start` com chat já gravado e vindo de outro chat é ignorado.
- Botão: `apply_action`, `answer_callback`, `edit_message` com o texto resultante (e, em `agora`, o endereço `http://127.0.0.1:8765`).
- `run`: laço de `tick` + `get_updates`; ao receber `TelegramError`, espera 5 s dobrando até 300 s e segue; reinicia a espera depois de sucesso. Sai quando `stop` é acionado. Cada ciclo lê as configurações de novo.

- [ ] **Step 1: Write the failing tests** (relógio injetado, `FakeTelegram`): `test_tick_sends_alert_with_three_buttons_at_alert_time` (o texto contém `Pasta: <project_path>`); `test_callback_agora_message_has_folder_path_and_site_url`; `test_tick_does_not_resend_after_alert_sent`; `test_tick_without_chat_id_sends_nothing`; `test_start_binds_chat_id_and_replies`; `test_start_from_other_chat_is_ignored`; `test_callback_agora_marks_vai_estudar_and_edits_message`; `test_callback_adiar_resends_after_snooze` (avança o relógio 30 min, `tick` envia de novo); `test_callback_hoje_nao_stops_alerts`; `test_callback_from_other_chat_ignored`; `test_double_press_is_harmless`; `test_new_day_alerts_again_once`; `test_alert_time_change_applies_without_restart`; `test_run_backs_off_on_telegram_error_and_recovers` (cliente falha 2 vezes e depois funciona; usa `sleep` injetável, sem esperar de verdade); `test_alert_failure_does_not_mark_sent` (`send_message` levanta erro → `last_alert_at` continua vazio e o próximo tick tenta de novo).
- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_bot.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `Bot`; `mark_alert_sent` só depois de `send_message` bem-sucedido.
- [ ] **Step 4: Run** a suíte inteira. Expected: tudo passa.
- [ ] **Step 5: Commit** `feat: bot do Telegram com alerta, botões e adiamento`.

### Task 4: Subir site e bot juntos, tela de configurações, README

**Files:**
- Modify: `app/__main__.py`, `app/web.py` (estado do Telegram na `/config`), `app/templates/config.html`, `README.md`, `tests/test_web_config.py`
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: `load_env`, `TelegramClient`, `Bot` (Tasks 2-3).
- Produces: `start_bot(root: Path, db_path: Path) -> tuple[threading.Thread, threading.Event] | None` em `app/__main__.py`; devolve `None` se não há token (o site sobe normalmente e imprime "Bot desligado: sem TELEGRAM_BOT_TOKEN no .env"). A thread do bot abre a própria conexão SQLite. `start_bot` passa `str(root)` como `project_path`; `main` sobe o bot antes do uvicorn e aciona `stop` ao sair.
- Produces: na `/config`, a seção Telegram mostra "Conectado" (com `telegram_chat_id` gravado) ou "Aguardando: envie /start para @MMA_MADEIRA_BOT"; o texto "Fase 2" some. O token nunca é exibido.

- [ ] **Step 1: Write the failing tests**: `test_start_bot_returns_none_without_token` (`.env` vazio); `test_start_bot_returns_thread_with_token` (com `TelegramClient` substituído por falso, thread inicia e para com `stop`); `test_config_shows_waiting_without_chat_id`; `test_config_shows_connected_with_chat_id`; `test_config_never_contains_token` (grava `TELEGRAM_BOT_TOKEN` no ambiente do teste e confere que a página não o contém).
- [ ] **Step 2: Run** `.venv\Scripts\python -m pytest tests/test_main.py tests/test_web_config.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement**; atualizar o README (bot, `.env`, como obter o chat id com `/start`, Roadmap sem a Fase 2).
- [ ] **Step 4: Run** a suíte inteira. Expected: tudo passa.
- [ ] **Step 5: Verificação manual** com o token real: `python -m app`; no Telegram, enviar `/start` ao bot e ver "Conectado" em `/config`; mudar o horário do alerta para 2 minutos à frente e conferir o alerta, "Daqui 30 min" (usar `snooze_min` 5 para testar), "Consigo agora" e "Hoje não". Restaurar `18:30`/`30`.
- [ ] **Step 6: Commit** `feat: sobe bot junto com o site; status do Telegram nas configurações`.

---

## Self-Review

- **Cobertura da seção 6 da spec:** alerta 18:30 e exceções (T1, T3); três botões (T3); sem alerta após 22:00 (T1); catch-up (T1, T3); chat id no `/start` e filtro de chat (T3); token em `.env` (T2, T4); Telegram indisponível com espera crescente (T3); site independente (T4).
- **Consistência de tipos:** `apply_action` usa `agora | adiar | hoje_nao`, os mesmos valores do `callback_data` em T3.
- **Proporção:** quatro tarefas, sem corpos de função copiados.

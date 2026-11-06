# Organizador de Estudos MMA — Design

Data: 2026-11-06 · Prova: 12/12/2026 · Idioma da interface: pt-BR

## 1. Objetivo

Ajudar uma pessoa a estudar *Métodos de Matemática Aplicada* até a prova de 12/12/2026:
lembrá-la de estudar todo dia, registrar **quanto tempo cada item levou** (página de teoria,
subitem de exercício) e, com isso, mostrar o progresso, o ritmo, o quanto falta e onde está a
dificuldade.

**Sucesso:** chegar em 12/12 com as 6 listas e os 6 PDFs de teoria feitos, sabendo em cada
semana se o ritmo atual fecha isso a tempo e quais assuntos precisam de reforço.

**Uso:** pessoal, um usuário, uma matéria. Custo zero (nenhuma API paga, nenhuma IA no bot).
O código também será publicado no git como portfólio, então deve ter README, testes e estrutura limpa.

### Fora do escopo (por ora)

- Hospedagem na nuvem (evolução futura; o código não deve impedi-la).
- Registro pelo celular (o site roda em `localhost`; o celular só recebe alertas do Telegram).
- Tutor de IA / explicação de exercícios (isso continua sendo feito em conversa com o Claude).
- Múltiplos usuários, login, outras matérias.

## 2. Arquitetura

Um único programa Python rodando no PC do usuário:

| Parte | Papel |
|---|---|
| **Site** (FastAPI + Jinja2 + HTMX, sem build de front) | Interface em `http://localhost:8000`: painel, teoria, listas, reforço/histórico, configurações |
| **Bot** (python-telegram-bot, *long polling*) | Envia o alerta diário e trata os botões; só lê/escreve estado do dia |
| **Agendador** (job queue do próprio bot) | Dispara o alerta às 18h30 e os adiamentos |
| **Banco** (SQLite, um arquivo) | Catálogo, registros de estudo, dias, configurações |

Lógica de negócio (ritmo, estimativas, reforço, sugestão) fica em módulos puros, sem I/O, para ser testada.

### Estrutura de pastas

```
app/
  main.py            # sobe site + bot juntos
  db.py              # conexão e schema SQLite
  catalog.py         # carrega catalog/catalog.json no banco
  pace.py            # funções puras: média, estimativa, veredito, reforço, sugestão
  routes/            # rotas do site
  templates/         # Jinja2 + HTMX
  static/            # css
  bot.py             # alertas e botões do Telegram
catalog/catalog.json # catálogo (listas, subitens, PDFs, páginas)
tests/
.env.example         # TELEGRAM_BOT_TOKEN (o chat id é capturado no /start)
README.md
```

## 3. Dados

- **Assunto (topic):** Fourier → Pares/Ímpares → Condução do Calor → Equação do Calor → Onda → Laplace (nessa ordem, que é a ordem de dependência).
- **Teoria:** `pdf (topic, título, nº de páginas)`. Páginas: 1..N.
- **Lista:** `list (topic, título)` → `exercise (número)` → `subitem (a, b, ...)`. Exercício sem subitem é um único item.
- **Item** = unidade registrável: uma página de teoria **ou** um subitem (ou exercício sem subitens).
- **Registro (log):** `data, item, minutos`. Cada item tem seu próprio tempo (sem divisão entre itens).
  Registrar o mesmo item de novo **soma tempo** (revisão); o progresso conta itens distintos.
- **Dia (day):** `data, status` ∈ {pendente, vai_estudar, estudou, pulou}, hora do último alerta.
- **Configurações:** data de início (dia do primeiro uso), prova (12/12/2026), **meta diária** (padrão
  90 min, definida pelo usuário), horário do alerta (18:30), intervalo de adiamento (30 min), chat id do Telegram.
  Não há estimativas iniciais: tudo que é estimado vem só dos tempos que o usuário registrou.
- **Meta da semana (calculada, não configurada):** a cada semana (segunda-feira) o sistema recalcula,
  a partir dos registros, quantas horas faltam e quantas semanas restam, e fixa essa meta para a semana.

O catálogo é gerado uma única vez a partir dos PDFs fornecidos e versionado em `catalog/catalog.json`.
Erros de digitação no conteúdo (nomes/enunciados) são aceitos e corrigidos depois; números de
exercícios, subitens e páginas devem estar corretos.

## 4. Telas do site

1. **Painel (home):** dias até a prova; barra geral de progresso (teoria e exercícios); horas totais e
   média por dia; barra da meta da semana; **veredito**; os 5 itens/assuntos de **reforço** mais críticos;
   próximo item sugerido.
2. **Teoria:** uma barra por PDF. Ao abrir um PDF: grade com as páginas (feitas × pendentes) e
   formulário "páginas de _ a _, minutos, data (padrão hoje)". Registrar o restante depois continua a mesma barra.
3. **Listas:** uma barra por lista. Ao abrir: exercícios com seus subitens como caixas de marcação,
   cada marcado recebe seu campo de minutos; salvar registra tudo de uma vez.
4. **Reforço e histórico:** itens e assuntos acima de 1,5× a média, e a lista de registros
   (editar/apagar um registro, com confirmação).
5. **Configurações:** metas, prazo, estimativas iniciais, estado do Telegram.

Layout simples, responsivo, claro/escuro. Detalhes visuais são decididos na implementação e ajustados com uso.

## 5. Cálculos (módulo `pace.py`)

- **Média diária:** `minutos_totais ÷ dias_desde_o_início` (dia atual incluído, dias sem estudo contam como zero). Atualiza todo dia.
- **Meta diária:** valor fixo do usuário (padrão 90 min). Serve só para mostrar se o dia está dentro
  (minutos do dia ≥ meta) ou abaixo, no painel ("hoje: X / 90 min") e no histórico. Não entra nas projeções.
- **Estimativa por unidade:** minutos por página de teoria e minutos por subitem, **somente dos registros do usuário**.
  Para um assunto com ≥ 3 registros da mesma natureza usa-se a média dele; senão a média global da natureza (≥ 3 registros);
  senão **não há estimativa** daquela natureza ainda.
- **Horas restantes:** soma, sobre os itens não feitos, da estimativa de cada um. Se faltar estimativa de alguma
  natureza, o painel mostra "dados insuficientes" para a parte correspondente (esperado nos primeiros dias).
- **Dias restantes:** de hoje até 11/12 (inclusive).
- **Necessário por dia:** `horas_restantes ÷ dias_restantes`.
- **Meta da semana:** recalculada toda segunda-feira (e fixada para a semana) como `horas_restantes ÷ semanas_restantes`;
  o painel mostra o quanto da meta da semana já foi feito.
- **Veredito:** "dados insuficientes" enquanto não houver estimativa; senão compara necessário × média:
  necessário ≤ 0,9× média → "dá para folgar"; ≤ 1,1× → "mantenha ~X min/dia"; acima → "aumente para ~Y min/dia (ou Z dias/semana)".
- **Reforço:** um item cujo tempo total passa de 1,5× a média da sua natureza (com ≥ 3 registros da natureza), e assuntos cuja média por unidade passa de 1,5× a global. Ordenado pelo excesso.
- **Próximo item sugerido:** o primeiro assunto (na ordem) com algo pendente: teoria primeiro, depois exercícios; os itens de reforço aparecem à parte.

## 6. Alerta diário (Telegram)

- **18:30:** mensagem "Hora de estudar?" com 3 botões, **exceto** se o dia já está `estudou` ou `pulou`.
  - **Consigo agora:** responde com o próximo item sugerido; dia → `vai_estudar`; para os adiamentos.
    Se até 23:00 não houver registro, envia um único lembrete "registrou o que estudou?".
  - **Daqui 30 min:** reenvia o alerta depois do intervalo configurado. Sem alertas depois das 22:00.
  - **Hoje não:** dia → `pulou`; para os alertas do dia.
- Um registro de estudo no site marca o dia como `estudou`.
- **PC desligado às 18:30:** ao iniciar, se já passou do horário e o dia está `pendente`, envia o alerta uma vez (dentro da janela até 22:00).
- **Segurança:** o primeiro `/start` registra o chat id; depois, o bot só responde a esse chat. O token fica em `.env` (fora do git).
- **Telegram indisponível:** nova tentativa com espera crescente; o site não depende do bot.

## 7. Erros e casos de borda

- Registro errado: editar ou apagar (com confirmação).
- Minutos inválidos (≤ 0 ou absurdos, > 600): rejeitados com mensagem.
- Página fora do intervalo do PDF: rejeitada.
- Mesmo item registrado de novo: aceito como revisão (soma tempo), com aviso visível.
- Poucos dados: veredito e horas restantes mostram "dados insuficientes" até haver registros suficientes (sem estimativas inventadas).
- Banco corrompido/ausente: criado a partir do schema + catálogo; backup diário do arquivo em `data/backups/`.

## 8. Testes

- **Unitários (pytest):** `pace.py` (média acumulada, estimativa com fallback, horas restantes, veredito nos três ramos e em "dados insuficientes", reforço, próximo item), regras de registro (validações, revisão).
- **Integração:** rotas principais do site com banco temporário; lógica de estados do alerta (agendamento, adiamento, pulou, catch-up) com relógio injetado, sem rede.
- **Manual:** um dia real de uso com o bot de verdade antes de considerar pronto.

## 9. Entrega em fases

1. **Fase 1 — Site + dados:** catálogo, banco, registro de teoria e exercícios, painel com ritmo/veredito/reforço. Não precisa de Telegram.
2. **Fase 2 — Bot:** alertas, botões, estados do dia, catch-up. Precisa do token do bot.
3. **Fase 3 — Polimento:** README, ajustes visuais, backups, correção de dados.

## 10. Decisões tomadas

- Telegram em vez de Google Agenda (a agenda não permite resposta interativa).
- Tempo por item informado pelo usuário (não cronômetro, não divisão igual).
- Média de ritmo acumulada, não janela móvel.
- Só a meta diária é configurada (para ver se o dia ficou dentro); a meta da semana é recalculada semanalmente a partir dos registros. Sem estimativas iniciais.
- Localhost no PC por ora; Cloudflare/nuvem é evolução futura.

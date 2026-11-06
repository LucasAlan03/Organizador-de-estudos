# Organizador de Estudos MMA

[English](README.md) · **Português**

Aplicativo pessoal para estudar *Métodos de Matemática Aplicada* até a prova de 12/12/2026.
Registra **quanto tempo cada item levou** (página de teoria, subitem de exercício) e, com isso,
mostra o progresso, o ritmo, quanto falta e onde está a dificuldade.

Roda só no seu computador (`localhost`), sem custo e sem chamadas de rede.

## O que tem

- **Painel:** dias até a prova, progresso de teoria e exercícios, média diária, meta do dia
  (dentro/abaixo), estimativa do que falta, meta da semana, veredito de ritmo, itens de reforço e o próximo item sugerido.
- **Teoria:** uma barra por PDF; você anota "páginas X a Y e o tempo".
- **Listas:** uma barra por lista; você marca exercícios/subitens e informa o tempo de cada um.
- **Histórico e reforço:** itens e assuntos acima de 1,5× a sua média, minutos por dia e edição/exclusão de registros.
- **Configurações:** meta diária, datas de início e da prova, horário do alerta e adiamento.

## Como o ritmo é calculado

- Média diária = minutos totais ÷ dias desde o início (acumulada, atualiza todo dia).
- Estimativa por unidade usa **só os seus tempos** (média do assunto com ≥ 3 itens feitos; senão a média geral; senão "dados insuficientes").
- Necessário por dia = horas restantes ÷ dias até 11/12, comparado com a sua média (folga / manter / aumentar).
- A meta da semana é recalculada toda segunda-feira a partir dos seus registros.

## Instalação e uso

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt   # Windows
.venv\Scripts\python -m app                      # ou clique em iniciar.bat
```

Abra <http://127.0.0.1:8765>. Os dados ficam em `data/study.db`, com backup diário em `data/backups/` (14 dias).

## Bot do Telegram (alerta diário)

1. Crie um bot no @BotFather e copie `.env.example` para `.env`, preenchendo `TELEGRAM_BOT_TOKEN` (o `.env` não vai para o git).
2. Rode o site (`iniciar.bat`): com o token, o bot liga junto.
3. No Telegram, envie `/start` ao bot. O primeiro `/start` registra o seu chat; depois o bot só responde a ele.
4. Às 18:30 (ou no horário das Configurações) chega o alerta com **Consigo agora**, **Daqui 30 min** e **Hoje não**. A mensagem traz o caminho da pasta do projeto.

Regras: sem alerta se o dia já está `estudou`/`pulou`, nem depois das 22:00. Se o PC estava desligado às 18:30, o alerta sai uma vez ao ligar (até 22:00). Usa `httpx` direto na API do Telegram, sem custo e sem IA. O bot só funciona com o PC ligado e o site aberto.

## Testes

```bash
.venv\Scripts\python -m pytest
```

## Estrutura

```
app/            código (db, catalog, logs, pace, stats, web, backup, alerts, bot, telegram_api)
app/templates/  páginas Jinja2
app/static/     estilos
catalog/        catalog.json: assuntos, páginas de teoria, exercícios e subitens
tests/          testes unitários e de integração
docs/           design e plano de implementação
```

`pace.py` contém as contas (funções puras, sem I/O); `stats.py` lê o banco e monta os dados das telas.

## Roadmap

- Hospedagem na nuvem para registrar pelo celular.

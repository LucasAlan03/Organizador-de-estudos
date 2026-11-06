# Organizador de Estudos MMA

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

Abra <http://127.0.0.1:8000>. Os dados ficam em `data/study.db`, com backup diário em `data/backups/` (14 dias).

## Testes

```bash
.venv\Scripts\python -m pytest
```

## Estrutura

```
app/            código (db, catalog, logs, pace, stats, web, backup)
app/templates/  páginas Jinja2
app/static/     estilos
catalog/        catalog.json: assuntos, páginas de teoria, exercícios e subitens
tests/          testes unitários e de integração
docs/           design e plano de implementação
```

`pace.py` contém as contas (funções puras, sem I/O); `stats.py` lê o banco e monta os dados das telas.

## Roadmap

- **Fase 2:** bot do Telegram com alerta diário (Consigo agora / Daqui 30 min / Hoje não).
- Hospedagem na nuvem para registrar pelo celular.

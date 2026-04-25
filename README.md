<div align="center">

# TaskMaster TW

**A visual UI for [TaskWarrior](https://taskwarrior.org/) — runs 100% on your machine.**

[![Version](https://img.shields.io/badge/version-1.0%20community-6366f1)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![TaskWarrior 2.6+](https://img.shields.io/badge/TaskWarrior-2.6+-red)](https://taskwarrior.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)
[![No Subscription](https://img.shields.io/badge/No%20Subscription-Free%20Forever-success)](LICENSE)

*From busy people, for busy people.*

</div>

---

> **This is the Community Edition — free, local, and open forever.**
> A cloud-based version with mobile features is on the roadmap as a paid product. This edition will never require an account, a subscription, or a network connection. That's a promise.

---

## English

### What is this?

If you already use `task` in your terminal, you don't need to change anything.  
TaskMaster TW is a **local web UI that reads and writes your existing TaskWarrior database** — the same `.task/` folder you've always had.

One command. Browser opens. Your tasks are there.

```bash
tw
# → TaskMaster  →  http://127.0.0.1:7755
```

No account. No cloud sync. No telemetry. No subscription. Just your data, on your machine, through a better interface.

---

### Why TaskMaster TW?

<table>
<tr>
<td width="50%">

**🔒 Radically private**

Your tasks never leave your machine. No cloud backend, no third-party servers, no analytics. TaskWarrior stores everything locally as plain text — TaskMaster just reads it.

</td>
<td width="50%">

**⚡ Zero migration**

Already a TaskWarrior user? Run one install command. Your existing tasks, projects, and tags are immediately visible. Keep using the CLI whenever you want — both views stay in sync.

</td>
</tr>
<tr>
<td width="50%">

**💸 Free. Forever.**

No freemium, no premium tier, no "basic plan". MIT licensed. Run it, fork it, modify it. The only cost is your electricity.

</td>
<td width="50%">

**🤝 Built to be forked**

One Python package. One HTML file. No build pipeline, no webpack, no node_modules. Clone, edit, run. Contributions and forks are explicitly encouraged.

</td>
</tr>
</table>

---

### Features

| | Feature | Description |
|---|---|---|
| 📊 | **Dashboard** | KPI cards, hot-zone tasks, velocity chart, due-date distribution, project health grid |
| ✅ | **Task Management** | Full CRUD with confirmation dialogs, inline editing, urgency sorting, quick-add bar |
| 📅 | **Calendar** | Day / Week / Month views with scheduled work slots — set *when* you'll work on a task, separate from the due date |
| 🗂 | **Projects & Categories** | Rich metadata, color coding, health indicators, category-level metrics |
| 🍅 | **Focus / Pomodoro** | Configurable work/break cycles, task pinning, time tracking (logged as TaskWarrior annotations) |
| 🎧 | **Zen Mode** | YouTube ambient background with auto-volume — stay in flow without leaving the app |
| 🔔 | **Smart Notifications** | 7 built-in alert rules: overdue tasks, project health, velocity drops, and more |
| 📈 | **Reports** | 30-day burndown, weekly velocity, 52-week contribution heatmap, per-project trends |
| 🤖 | **AI Assistant** *(optional)* | Chat with your task data using your own API keys — Anthropic, OpenAI, Gemini, or local Ollama |
| 🌐 | **i18n** | English / Spanish toggle |
| 🎨 | **Themes** | Light / Dark mode |

> **On the AI feature:** Completely optional — if you don't configure a key, the button does nothing.
>
> **Privacy model:** Your API key is stored only in your browser's `localStorage` — never written to disk, never logged, never sent anywhere except your own local server (`127.0.0.1:7755`), which then forwards the request to your chosen AI provider. Your key never touches any third-party infrastructure other than the provider you explicitly chose.
>
> **Cost guide:** Each conversation turn consumes roughly 500–2 000 input tokens (system prompt + your task data + your message) plus 100–400 output tokens. Approximate cost per query:
>
> | Provider / Model | Free tier | ~Cost per query |
> |---|---|---|
> | Google — `gemini-2.0-flash` | ✅ 15 req/min, 1 M tokens/day | $0.00 |
> | Google — `gemini-2.5-flash` | ✅ limited | $0.00 – $0.001 |
> | Anthropic — `claude-haiku-4-5` | ❌ | ~$0.001 |
> | OpenAI — `gpt-4o-mini` | ❌ | ~$0.001 |
> | Anthropic — `claude-sonnet-4` | ❌ | ~$0.01 |
> | OpenAI — `gpt-4o` | ❌ | ~$0.01 |
> | Ollama (local) | ✅ | $0.00 (runs on your GPU) |
>
> For a typical work session of 20–30 queries, even paid models cost less than $0.30. **`gemini-2.0-flash` is recommended for free-tier use.** Check your provider's current pricing page before enabling paid models.

---

### Requirements

| Dependency | Version |
|---|---|
| [TaskWarrior](https://taskwarrior.org/download/) | 2.6+ |
| Python | 3.11+ |
| pipx | any |

**Platform notes**
- **Windows** — TaskWarrior runs inside WSL2. The included `setup.ps1` automates the full setup.
- **macOS / Linux** — TaskWarrior runs natively. Install via your package manager, then install the Python package.

---

### Install

<details open>
<summary><b>macOS</b></summary>

```bash
# 1. Install TaskWarrior
brew install task

# 2. Clone and install
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw
pipx install .

# 3. Configure (one line change)
# Edit tw.toml → set backend = "native"

# 4. Launch
tw
```

</details>

<details>
<summary><b>Linux (Ubuntu / Debian)</b></summary>

```bash
# 1. Install TaskWarrior and pipx
sudo apt update && sudo apt install taskwarrior pipx -y
pipx ensurepath && source ~/.bashrc

# 2. Clone and install
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw
pipx install .

# 3. Configure
# Edit tw.toml → set backend = "native"

# 4. Launch
tw
```

</details>

<details>
<summary><b>Windows (automated)</b></summary>

> Requires Windows 10 21H2+ or Windows 11 with WSL2 available.

```powershell
# 1. Clone
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw

# 2. Run the one-shot setup script (as Administrator the first time)
powershell -ExecutionPolicy Bypass -File setup.ps1
```

The script installs: WSL2 + Ubuntu → TaskWarrior → Python 3.11 → pipx → `tw` command.

```powershell
# 3. Launch
tw
```

</details>

---

### Configuration (`tw.toml`)

```toml
[server]
port              = 7755        # Local port
host              = "127.0.0.1" # Never exposed to the network
auto_open_browser = true

[taskwarrior]
backend    = "wsl"              # "wsl" (Windows) | "native" (macOS/Linux)
wsl_distro = "Ubuntu"           # Only needed for backend = "wsl"
```

---

### Quick-add syntax

The bottom bar accepts a shorthand for rapid task entry — same spirit as the TaskWarrior CLI:

```
!h Fix login bug  @backend  #deploy  due:fri
│   │              │         │         └─ Due date (TW format: fri, tomorrow, 2026-05-01…)
│   │              │         └─ Tag
│   │              └─ Project
│   └─ Description
└─ Priority  (!h = High  !m = Medium  !l = Low)
```

```bash
# Examples
Buy groceries
!h Prepare quarterly report @finance due:2026-05-01
Deploy hotfix @backend #urgent due:tomorrow
```

---

### Scheduling work vs. due dates

TaskMaster introduces a distinction that TaskWarrior CLI doesn't have natively:

| Field | Meaning |
|---|---|
| **Due date** | When the task *must* be done |
| **Scheduled start / end** | When *you plan to work on it* |

Set a work slot on any task from the task detail view or by clicking a calendar time slot. The calendar shows tasks on their **scheduled work day**, not their due date — so your day view reflects your actual plan, not just a list of deadlines.

> Scheduled slots are stored locally in `task_schedule.json` alongside your `tw.toml`.

---

### Project structure

```
task_master_tw/
├── taskmaster/
│   ├── main.py          # FastAPI application + all API routes
│   ├── taskwarrior.py   # Subprocess wrapper around the task CLI
│   ├── parser.py        # Quick-add syntax parser
│   ├── ai.py            # Optional AI assistant (Anthropic / OpenAI compat)
│   ├── tw.py            # CLI entry point  →  the `tw` command
│   └── static/
│       └── index.html   # Entire frontend — one self-contained HTML file
├── pyproject.toml
├── setup.ps1            # Windows one-shot installer
└── tw.toml              # Local config (gitignored)
```

---

### Contributing

TaskMaster TW is intentionally simple: one Python package, one HTML file, no build step.

```bash
# Editable install for development
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw
pipx install -e .

# Enable hot-reload while developing
# Set reload = true in tw.toml, then run: tw
```

**Ways to contribute**
- 🐛 [Report a bug](https://github.com/ivillarroelr/task_master_tw/issues)
- 💡 [Suggest a feature](https://github.com/ivillarroelr/task_master_tw/issues)
- 🔀 Fork it and build your own flavour — that's what MIT is for
- 🌍 Add a new language to the `I18N` object in `index.html`
- 📖 Improve this README

Open an issue before starting large changes. PRs are welcome and will be reviewed promptly.

---

### Troubleshooting

<details>
<summary><code>task: not found</code> in WSL</summary>

```bash
# Inside WSL:
wsl -d Ubuntu
sudo apt update && sudo apt install taskwarrior -y
task --version
```
</details>

<details>
<summary>Wrong WSL distro</summary>

```bash
wsl -l -v   # Find the NAME column
# Then set wsl_distro in tw.toml to match exactly
```
</details>

<details>
<summary>Port already in use</summary>

```toml
# tw.toml
[server]
port = 7756
```
</details>

<details>
<summary><code>wsl: Unknown key</code> warnings in terminal</summary>

Harmless WSL configuration warnings. TaskMaster filters them out automatically — they won't appear in the UI.
</details>

---

### License

[MIT](LICENSE) — free to use, modify, and distribute.

---
---

## Español

### ¿Qué es esto?

Si ya usas `task` en tu terminal, no necesitas cambiar nada.  
TaskMaster TW es una **interfaz web local que lee y escribe tu base de datos de TaskWarrior existente** — la misma carpeta `.task/` que siempre has tenido.

Un comando. Se abre el navegador. Tus tareas están ahí.

```bash
tw
# → TaskMaster  →  http://127.0.0.1:7755
```

Sin cuenta. Sin sincronización en la nube. Sin telemetría. Sin suscripción. Solo tus datos, en tu máquina, con una mejor interfaz.

> **Esta es la Community Edition — gratuita, local y abierta para siempre.**
> En el futuro existirá una versión cloud con funciones mobile como producto de pago. Esta edición nunca requerirá cuenta, suscripción ni conexión a internet. Eso es una promesa.

---

### ¿Por qué TaskMaster TW?

<table>
<tr>
<td width="50%">

**🔒 Privacidad radical**

Tus tareas nunca salen de tu máquina. Sin backend en la nube, sin servidores de terceros, sin analíticas. TaskWarrior guarda todo localmente como texto plano — TaskMaster solo lo lee.

</td>
<td width="50%">

**⚡ Cero migración**

¿Ya usas TaskWarrior? Ejecuta un comando de instalación. Tus tareas, proyectos y etiquetas existentes son visibles de inmediato. Sigue usando el CLI cuando quieras — ambas vistas se mantienen sincronizadas.

</td>
</tr>
<tr>
<td width="50%">

**💸 Gratis. Para siempre.**

Sin freemium, sin nivel premium, sin "plan básico". Licencia MIT. Úsalo, forkéalo, modifícalo. El único costo es tu electricidad.

</td>
<td width="50%">

**🤝 Diseñado para ser forkeado**

Un paquete Python. Un archivo HTML. Sin pipeline de build, sin webpack, sin node_modules. Clona, edita, ejecuta. Las contribuciones y forks son bienvenidos explícitamente.

</td>
</tr>
</table>

---

### Funcionalidades

| | Función | Descripción |
|---|---|---|
| 📊 | **Dashboard** | KPIs, zona caliente, gráfico de velocidad, distribución de fechas, salud de proyectos |
| ✅ | **Gestión de tareas** | CRUD completo con confirmaciones, edición inline, ordenamiento por urgencia, barra de creación rápida |
| 📅 | **Calendario** | Vistas Día / Semana / Mes con slots de trabajo — programa *cuándo* trabajarás en una tarea, separado del due date |
| 🗂 | **Proyectos y Categorías** | Metadata rica, código de colores, indicadores de salud, métricas por categoría |
| 🍅 | **Focus / Pomodoro** | Ciclos configurables, pin de tarea, seguimiento de tiempo (registrado como anotaciones en TaskWarrior) |
| 🎧 | **Modo Zen** | Fondo de YouTube ambiental con volumen automático — mantén el flujo sin salir de la app |
| 🔔 | **Notificaciones inteligentes** | 7 reglas integradas: tareas vencidas, salud de proyectos, caída de velocidad, y más |
| 📈 | **Reportes** | Burndown 30 días, velocidad semanal, heatmap 52 semanas, tendencias por proyecto |
| 🤖 | **Asistente IA** *(opcional)* | Chatea con tus tareas usando tus propias API keys — Anthropic, OpenAI, Gemini, u Ollama local |
| 🌐 | **i18n** | Toggle Inglés / Español |
| 🎨 | **Temas** | Modo claro / oscuro |

> **Sobre la función IA:** Completamente opcional — si no configuras una key, el botón no hace nada.
>
> **Modelo de privacidad:** Tu API key se guarda únicamente en el `localStorage` de tu navegador — nunca se escribe en disco, nunca se registra en logs, nunca se envía a ningún lugar que no sea tu propio servidor local (`127.0.0.1:7755`), que luego reenvía la solicitud al proveedor de IA elegido. Tu key nunca toca infraestructura de terceros salvo el proveedor que tú elegiste explícitamente.
>
> **Guía de costos:** Cada turno de conversación consume aproximadamente 500–2 000 tokens de entrada (system prompt + tus tareas + tu mensaje) y 100–400 tokens de salida. Costo aproximado por consulta:
>
> | Proveedor / Modelo | Tier gratuito | ~Costo por consulta |
> |---|---|---|
> | Google — `gemini-2.0-flash` | ✅ 15 req/min, 1M tokens/día | $0.00 |
> | Google — `gemini-2.5-flash` | ✅ limitado | $0.00 – $0.001 |
> | Anthropic — `claude-haiku-4-5` | ❌ | ~$0.001 |
> | OpenAI — `gpt-4o-mini` | ❌ | ~$0.001 |
> | Anthropic — `claude-sonnet-4` | ❌ | ~$0.01 |
> | OpenAI — `gpt-4o` | ❌ | ~$0.01 |
> | Ollama (local) | ✅ | $0.00 (corre en tu GPU) |
>
> En una sesión de trabajo típica de 20–30 consultas, incluso los modelos de pago cuestan menos de $0.30. **`gemini-2.0-flash` es el recomendado para uso gratuito.** Verifica la página de precios de tu proveedor antes de activar modelos de pago.

---

### Requisitos

| Dependencia | Versión |
|---|---|
| [TaskWarrior](https://taskwarrior.org/download/) | 2.6+ |
| Python | 3.11+ |
| pipx | cualquiera |

---

### Instalación

<details open>
<summary><b>macOS</b></summary>

```bash
brew install task
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw
pipx install .
# Edita tw.toml → backend = "native"
tw
```

</details>

<details>
<summary><b>Linux (Ubuntu / Debian)</b></summary>

```bash
sudo apt update && sudo apt install taskwarrior pipx -y
pipx ensurepath && source ~/.bashrc
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw
pipx install .
# Edita tw.toml → backend = "native"
tw
```

</details>

<details>
<summary><b>Windows (automatizado)</b></summary>

```powershell
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw
powershell -ExecutionPolicy Bypass -File setup.ps1
tw
```

</details>

---

### Agenda vs. fecha límite

TaskMaster introduce una distinción que el CLI de TaskWarrior no tiene nativamente:

| Campo | Significado |
|---|---|
| **Due date** | Cuándo *debe* estar lista la tarea |
| **Inicio / Fin agendado** | Cuándo *planeas trabajar* en ella |

Asigna un slot de trabajo desde el detalle de la tarea o haciendo clic en un slot del calendario. El calendario muestra las tareas en su **día de trabajo agendado**, no en su fecha límite.

---

### Contribuir

```bash
git clone https://github.com/ivillarroelr/task_master_tw.git
cd task_master_tw
pipx install -e .
# Activa reload = true en tw.toml para hot-reload durante desarrollo
```

**Formas de contribuir**
- 🐛 [Reportar un bug](https://github.com/ivillarroelr/task_master_tw/issues)
- 💡 [Proponer una funcionalidad](https://github.com/ivillarroelr/task_master_tw/issues)
- 🔀 Forkear y construir tu propia versión
- 🌍 Agregar un nuevo idioma al objeto `I18N` en `index.html`
- 📖 Mejorar este README

Pull requests bienvenidos. Para cambios grandes, abre un issue primero.

---

### Licencia

[MIT](LICENSE) — libre de usar, modificar y distribuir.

"""AI agent — natural language task/project management."""
import json
import shlex
from typing import AsyncIterator, Any

DESTRUCTIVE_TOOLS = {"delete_task", "delete_project"}

TOOLS = [
    {
        "name": "list_tasks",
        "description": "List tasks with an optional TaskWarrior filter. Multi-word values MUST be quoted.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string",
                           "description": (
                               "TaskWarrior filter string. Examples: "
                               "'status:pending due:today' | "
                               "'description.contains:\"cook a burger\"' | "
                               "'status.not:deleted description.contains:\"keyword\"' | "
                               "'project:web priority:H' | "
                               "'+urgent status:pending'"
                           )}
            }
        }
    },
    {
        "name": "add_task",
        "description": "Create a new task using quick-add syntax.",
        "input_schema": {
            "type": "object",
            "required": ["raw"],
            "properties": {
                "raw": {"type": "string",
                        "description": (
                            "Quick-add syntax: '!h description @project #tag due:2026-05-01'. "
                            "For project names with spaces use double quotes: @\"certamen 1 microeconomia\". "
                            "Single-word projects: @work. Multi-word MUST be quoted: @\"my long project\"."
                        )}
            }
        }
    },
    {
        "name": "modify_task",
        "description": "Edit a task's description, project, priority, due date or tags.",
        "input_schema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                "id":          {"type": "integer"},
                "description": {"type": "string"},
                "project":     {"type": "string"},
                "priority":    {"type": "string", "enum": ["H", "M", "L", ""]},
                "due":         {"type": "string"},
                "tags":        {"type": "array", "items": {"type": "string"}}
            }
        }
    },
    {
        "name": "complete_task",
        "description": "Mark a task as done.",
        "input_schema": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}}
        }
    },
    {
        "name": "undo_task",
        "description": "Reactivate a completed task.",
        "input_schema": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}}
        }
    },
    {
        "name": "delete_task",
        "description": "Permanently delete a task. Always requires explicit user confirmation first.",
        "input_schema": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}}
        }
    },
    {
        "name": "annotate_task",
        "description": "Add a note or annotation to a task. Useful for logging progress, blockers, or any free-form notes.",
        "input_schema": {
            "type": "object",
            "required": ["id", "text"],
            "properties": {
                "id":   {"type": "integer"},
                "text": {"type": "string", "description": "The note text to attach to the task"}
            }
        }
    },
    {
        "name": "get_task_detail",
        "description": "Get full task details including all annotations and pomodoro history.",
        "input_schema": {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}}
        }
    },
    {
        "name": "get_stats",
        "description": "Get dashboard stats: pending, overdue, done today, velocity, project health.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "list_projects",
        "description": "List all projects with metadata and live task stats.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "create_project",
        "description": "Create a new project.",
        "input_schema": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name":        {"type": "string"},
                "description": {"type": "string"},
                "status":      {"type": "string", "enum": ["active", "on-hold", "completed", "archived"]},
                "priority":    {"type": "string", "enum": ["H", "M", "L", ""]},
                "due":         {"type": "string"},
                "color":       {"type": "string"},
                "notes":       {"type": "string"},
                "category":    {"type": "string"}
            }
        }
    },
    {
        "name": "modify_project",
        "description": "Edit a project's metadata. Use new_name to rename.",
        "input_schema": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name":        {"type": "string"},
                "new_name":    {"type": "string"},
                "description": {"type": "string"},
                "status":      {"type": "string"},
                "priority":    {"type": "string"},
                "due":         {"type": "string"},
                "color":       {"type": "string"},
                "notes":       {"type": "string"},
                "category":    {"type": "string"}
            }
        }
    },
    {
        "name": "delete_project",
        "description": "Delete a project and all its tasks. Always requires explicit user confirmation first.",
        "input_schema": {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}}
        }
    },
]

_SYSTEM = """You are the TaskMaster assistant — a personal task and project management helper built on TaskWarrior.

RULES:
1. Respond in the same language the user writes in (Spanish or English).
2. Be concise: one clear sentence per action, not paragraphs.
3. When you create or modify something, always mention the resulting ID or name.
4. For list results with many items, summarize (e.g. "Found 12 tasks, 3 overdue").
5. When the user asks to delete a task or project, CALL delete_task / delete_project immediately.
   The app intercepts those calls automatically and shows a confirmation dialog — do NOT ask
   for confirmation in your text first. Just call the tool.
6. For bulk operations affecting more than 3 items, briefly describe what you will do before executing.

DATE & STATUS RULES (important):
- Today's date and day of week are in the context below — use them for any time-based question.
- When the user asks "what do I have for today / this week / upcoming", ALWAYS filter by
  status:pending so completed tasks are excluded from the answer.
- If a result set has 0 pending tasks, say so explicitly and optionally mention how many were
  completed for that period (call list_tasks again with status:completed if relevant).
- TaskWarrior date keywords: today, tomorrow, yesterday, monday…sunday, eow (end of week),
  eom (end of month), +Nd (N days from now).

FILTER SYNTAX RULES (critical — wrong syntax = 0 results):
- Multi-word values MUST be quoted: description.contains:"cook a burger"  NOT  description.contains:cook a burger
- Description search: description.contains:"keyword"  (partial match, case-insensitive)
- Project search: project:myproject
- Tag search: +tagname  or  -tagname (exclude)
- To search ALL tasks (pending + completed): status.not:deleted description.contains:"X"
- To search only pending: status:pending description.contains:"X"
- When looking for a SPECIFIC task to edit/delete, use status.not:deleted so completed tasks
  are also found. Only restrict to status:pending for workload/schedule queries.

SEMANTIC TASK IDENTIFICATION (critical — users describe tasks in their own words):
The user may refer to a task in a DIFFERENT LANGUAGE or with SYNONYMS or PARAPHRASES.
Example: "cook a burger" may be described as "cocinar una hamburguesa", "la tarea de la
hamburguesa", "burger task", "hacer hamburguesas", etc.

When the user asks to modify, delete, or act on a task by description:
1. First try a keyword search. If 0 results, call list_tasks with filter "status.not:deleted"
   to retrieve ALL tasks, then USE YOUR OWN LANGUAGE UNDERSTANDING to identify the best match
   — cross-language, synonyms, and paraphrases are all valid.
2. When you find one likely match: CONFIRM before acting.
   Say: "Encontré la tarea #N «description» — ¿es esta la que buscas?" (or in English).
   Only proceed after the user says yes.
3. When multiple tasks could match: show all candidates and ask the user to choose.
   Example: "Encontré 2 posibles coincidencias: #3 «make burgers» y #7 «BBQ night» — ¿cuál?"
4. Only when the user confirms the correct task, THEN call the action tool with the known ID.
   Do NOT guess silently — always surface the match for the user to approve.

CAPABILITIES YOU HAVE:
- list_tasks: search with any TaskWarrior filter (project, priority, due, tags, status…)
- add_task: create a task using quick-add syntax (!h desc @project #tag due:date). For project names with spaces use quotes: @"my project name"
- modify_task: change description, project, priority, due date, or tags of any task
- complete_task / undo_task: mark done or reactivate
- annotate_task: add a note/annotation to a task
- delete_task: call it directly when asked — the app shows a confirmation dialog automatically
- get_task_detail: full detail including annotations and pomodoro history
- get_stats: overall dashboard numbers (pending, overdue, velocity, project health)
- list_projects / create_project / modify_project / delete_project: project CRUD

Current UI context: {context}
"""


async def _execute_tool(name: str, inp: dict, tw, store, cat_store, parse_quick_add) -> Any:
    if name == "list_tasks":
        f = inp.get("filter", "status:pending")
        # shlex.split preserves quoted multi-word values:
        # description.contains:"cook a burger" → one token, not three broken pieces
        try:
            parts = shlex.split(f)
        except ValueError:
            parts = f.split()
        had_status = any(p.startswith("status") for p in parts)
        # For time-based / workload queries with no explicit status, default to pending
        # so completed tasks don't pollute "what do I have today?" answers.
        if not had_status:
            parts = ["status:pending"] + parts
        tasks = tw.export(parts)
        # If nothing found and the query was a description/keyword search,
        # retry across all non-deleted tasks (task may be completed).
        if not tasks and not had_status and any("description" in p or "contains" in p for p in parts):
            tasks = tw.export([p for p in parts if not p.startswith("status:")])
        return {"count": len(tasks), "tasks": tasks[:25]}

    if name == "add_task":
        parsed = parse_quick_add(inp["raw"])
        tw.add(**parsed)
        return {"ok": True, "description": parsed["description"]}

    if name == "modify_task":
        tid = inp.pop("id")
        kwargs = {k: v for k, v in inp.items() if v is not None and v != ""}
        tw.modify(tid, **kwargs)
        return {"ok": True, "id": tid}

    if name == "complete_task":
        tw.done(inp["id"])
        return {"ok": True, "id": inp["id"]}

    if name == "undo_task":
        tw.undo(inp["id"])
        return {"ok": True, "id": inp["id"]}

    if name == "delete_task":
        tw.delete(inp["id"])
        return {"ok": True, "id": inp["id"]}

    if name == "annotate_task":
        tw.annotate(inp["id"], inp["text"])
        return {"ok": True, "id": inp["id"]}

    if name == "get_task_detail":
        found = tw.export([f"id:{inp['id']}"])
        if not found:
            found = tw.export(["status:completed", f"id:{inp['id']}"])
        return found[0] if found else {"error": "not found"}

    if name == "get_stats":
        return tw.get_stats()

    if name == "list_projects":
        meta = store.all()
        health = tw.get_stats().get("project_health", [])
        by_name = {h["name"]: h for h in health}
        names = sorted(set(list(meta.keys()) + list(by_name.keys())))
        return [
            {
                "name": n,
                "description": meta.get(n, {}).get("description", ""),
                "status":   meta.get(n, {}).get("status", "active"),
                "pending":  by_name.get(n, {}).get("pending", 0),
                "overdue":  by_name.get(n, {}).get("overdue", 0),
                "completed":by_name.get(n, {}).get("completed", 0),
                "pct":      by_name.get(n, {}).get("pct", 0),
                "health":   by_name.get(n, {}).get("health", "ok"),
            }
            for n in names
        ]

    if name == "create_project":
        n = inp.pop("name")
        store.upsert(n, {k: v for k, v in inp.items() if v is not None})
        return {"ok": True, "name": n}

    if name == "modify_project":
        old = inp.pop("name")
        new = inp.pop("new_name", None)
        if new and new != old:
            tw.rename_project(old, new)
            store.rename(old, new)
            old = new
        store.upsert(old, {k: v for k, v in inp.items() if v is not None})
        return {"ok": True, "name": old}

    if name == "delete_project":
        tw.delete_project(inp["name"])
        store.delete(inp["name"])
        return {"ok": True, "name": inp["name"]}

    return {"error": f"unknown tool: {name}"}


def _confirm_prompt(tool: str, inp: dict) -> str:
    if tool == "delete_task":
        return f"Voy a eliminar permanentemente la tarea #{inp.get('id')}. ¿Confirmas?"
    if tool == "delete_project":
        return f"Voy a eliminar el proyecto @{inp.get('name')} y todas sus tareas. ¿Confirmas?"
    return "¿Confirmas esta acción destructiva?"


async def stream(
    messages: list,
    provider: str,
    model: str,
    api_key: str,
    context: dict,
    store,
    cat_store,
    confirmed_action: dict | None,
    tw,
    parse_quick_add,
) -> AsyncIterator[dict]:
    """Main entry point. Yields SSE-ready dicts."""

    if confirmed_action:
        try:
            result = await _execute_tool(
                confirmed_action["tool"], dict(confirmed_action["input"]),
                tw, store, cat_store, parse_quick_add,
            )
            yield {"type": "tool_call", "name": confirmed_action["tool"]}
            action_name = confirmed_action["tool"]
            inp = confirmed_action["input"]
            if action_name == "delete_task":
                yield {"type": "text", "content": f"✓ Tarea #{inp.get('id')} eliminada."}
            elif action_name == "delete_project":
                yield {"type": "text", "content": f"✓ Proyecto @{inp.get('name')} y sus tareas eliminados."}
            else:
                yield {"type": "text", "content": "✓ Listo."}
        except Exception as e:
            yield {"type": "text", "content": f"⚠ Error: {e}"}
        yield {"type": "done"}
        return

    if provider == "anthropic":
        async for ev in _anthropic(messages, model, api_key, context, store, cat_store, tw, parse_quick_add):
            yield ev
    elif provider in ("openai", "gemini", "ollama"):
        async for ev in _openai_compat(messages, provider, model, api_key, context, store, cat_store, tw, parse_quick_add):
            yield ev
    else:
        yield {"type": "text", "content": f"⚠ Provider '{provider}' not supported."}
        yield {"type": "done"}


async def _anthropic(messages, model, api_key, context, store, cat_store, tw, parse_quick_add):
    try:
        import anthropic as _sdk
    except ImportError:
        yield {"type": "error", "message": "Run: pip install anthropic"}
        yield {"type": "done"}
        return

    client = _sdk.AsyncAnthropic(api_key=api_key)
    system = _SYSTEM.format(context=json.dumps(context))
    msgs = list(messages)

    for _ in range(10):
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            messages=msgs,
            tools=TOOLS,
        )

        for block in response.content:
            if block.type == "text" and block.text:
                yield {"type": "text", "content": block.text}

        if response.stop_reason != "tool_use":
            break

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        tool_results = []

        for tu in tool_uses:
            if tu.name in DESTRUCTIVE_TOOLS:
                yield {"type": "confirm_required",
                       "message": _confirm_prompt(tu.name, tu.input),
                       "action": {"tool": tu.name, "input": dict(tu.input)}}
                yield {"type": "done"}
                return

            try:
                result = await _execute_tool(tu.name, dict(tu.input), tw, store, cat_store, parse_quick_add)
                yield {"type": "tool_call", "name": tu.name}
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, default=str),
                })
            except Exception as e:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": f"Error: {e}",
                    "is_error": True,
                })

        msgs.append({"role": "assistant", "content": response.content})
        msgs.append({"role": "user", "content": tool_results})

    yield {"type": "done"}


def _extract_api_error(e: Exception) -> str:
    """Return a short, human-readable error string from an OpenAI/Gemini SDK exception."""
    s = str(e)
    # OpenAI SDK format: "Error code: NNN - [{'error': {'message': '...', ...}}]"
    # Gemini native format: "[{'error': {'message': '...', ...}}]"
    try:
        bracket = s.find("[{")
        if bracket != -1:
            data = json.loads(s[bracket:])
            inner = data[0].get("error", {})
            code = inner.get("code", "")
            raw_msg = inner.get("message", s)
            # Keep only the first line — Gemini quota errors are multi-line walls of text
            first_line = raw_msg.split("\n")[0].strip()
            hint = ""
            if code == 429 and "free_tier" in raw_msg:
                hint = " → usa gemini-2.0-flash (tier gratuito)"
            elif code == 429:
                hint = " → espera unos segundos y reintenta"
            return f"Error {code} — {first_line}{hint}"
    except Exception:
        pass
    # Fallback: trim at first newline so we don't dump walls of text
    return s.split("\n")[0]


async def _openai_compat(messages, provider, model, api_key, context, store, cat_store, tw, parse_quick_add):
    try:
        import openai as _sdk
    except ImportError:
        yield {"type": "error", "message": "Run: pip install openai"}
        yield {"type": "done"}
        return

    base = {
        "openai":  None,
        "gemini":  "https://generativelanguage.googleapis.com/v1beta/openai/",
        "ollama":  "http://localhost:11434/v1",
    }.get(provider)

    client = _sdk.AsyncOpenAI(
        api_key=api_key if provider != "ollama" else "ollama",
        base_url=base,
    )
    oai_tools = [{"type": "function", "function": {
        "name": t["name"],
        "description": t["description"],
        "parameters": t["input_schema"],
    }} for t in TOOLS]

    sys_msg = {"role": "system", "content": _SYSTEM.format(context=json.dumps(context))}
    msgs = [sys_msg] + list(messages)

    try:
        for _ in range(10):
            resp = await client.chat.completions.create(
                model=model, messages=msgs, tools=oai_tools,
                tool_choice="auto", max_tokens=1024,
            )
            msg = resp.choices[0].message
            if msg.content:
                yield {"type": "text", "content": msg.content}

            if not msg.tool_calls:
                break

            tool_msgs = []
            for tc in msg.tool_calls:
                name = tc.function.name
                inp  = json.loads(tc.function.arguments)

                if name in DESTRUCTIVE_TOOLS:
                    yield {"type": "confirm_required",
                           "message": _confirm_prompt(name, inp),
                           "action": {"tool": name, "input": inp}}
                    yield {"type": "done"}
                    return

                try:
                    result = await _execute_tool(name, inp, tw, store, cat_store, parse_quick_add)
                    yield {"type": "tool_call", "name": name}
                    tool_msgs.append({"role": "tool", "tool_call_id": tc.id,
                                       "content": json.dumps(result, default=str)})
                except Exception as e:
                    tool_msgs.append({"role": "tool", "tool_call_id": tc.id, "content": f"Error: {e}"})

            msgs.append(msg)
            msgs.extend(tool_msgs)

    except Exception as e:
        yield {"type": "error", "message": _extract_api_error(e)}

    yield {"type": "done"}

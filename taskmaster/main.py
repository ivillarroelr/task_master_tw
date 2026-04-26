"""TaskMaster — FastAPI backend."""
import json
import shlex
import tomllib
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from taskmaster import taskwarrior as tw
from taskmaster.parser import parse_quick_add
from taskmaster import ical as ical_store

# ── Config ─────────────────────────────────────────────────────
def _find_cfg_dir() -> Path:
    for p in [Path.cwd() / "tw.toml", Path(__file__).parent / "tw.toml"]:
        if p.exists():
            return p.parent
    return Path.cwd()

_cfg_dir = _find_cfg_dir()
_cfg: dict = {}
_cfg_path = _cfg_dir / "tw.toml"
if _cfg_path.exists():
    with open(_cfg_path, "rb") as _f:
        _cfg = tomllib.load(_f)

tw.BACKEND    = _cfg.get("taskwarrior", {}).get("backend", "wsl")
tw.WSL_DISTRO = _cfg.get("taskwarrior", {}).get("wsl_distro", "")
tw._build_cmd()

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="TaskMaster", version="0.1.0")


# ── Project metadata store ──────────────────────────────────────
class ProjectStore:
    """Persists project metadata (description, status, colour, etc.)
    alongside tw.toml so the data survives reinstalls."""

    def __init__(self) -> None:
        self.path = _cfg_dir / "projects.json"

    def _data(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _write(self, d: dict) -> None:
        self.path.write_text(
            json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def all(self) -> dict:
        return self._data()

    def upsert(self, name: str, fields: dict) -> None:
        d = self._data()
        d.setdefault(name, {"created": datetime.utcnow().isoformat() + "Z"})
        d[name].update({k: v for k, v in fields.items() if v is not None})
        self._write(d)

    def rename(self, old: str, new: str) -> None:
        d = self._data()
        if old in d:
            d[new] = d.pop(old)
            self._write(d)

    def delete(self, name: str) -> None:
        d = self._data()
        d.pop(name, None)
        self._write(d)


_store = ProjectStore()


# ── Category metadata store ──────────────────────────────────────
class CategoryStore:
    def __init__(self) -> None:
        self.path = _cfg_dir / "categories.json"

    def _data(self) -> list:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _write(self, d: list) -> None:
        self.path.write_text(
            json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def all(self) -> list:
        return self._data()

    def upsert(self, name: str, fields: dict) -> None:
        cats = self._data()
        existing = next((c for c in cats if c["name"] == name), None)
        if existing:
            existing.update({k: v for k, v in fields.items() if v is not None})
        else:
            cats.append({"name": name, "created": datetime.utcnow().isoformat() + "Z",
                         **{k: v for k, v in fields.items() if v is not None}})
        self._write(cats)

    def rename(self, old: str, new: str) -> None:
        cats = self._data()
        for c in cats:
            if c["name"] == old:
                c["name"] = new
                break
        self._write(cats)

    def delete(self, name: str) -> None:
        self._write([c for c in self._data() if c["name"] != name])


_cat_store = CategoryStore()


# ── Schedule store ───────────────────────────────────────────────
class ScheduleStore:
    """Stores per-task scheduled start/end (ISO local datetime strings)."""

    def __init__(self) -> None:
        self.path = _cfg_dir / "task_schedule.json"

    def _data(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _write(self, d: dict) -> None:
        self.path.write_text(
            json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get(self, uuid: str) -> dict:
        return self._data().get(uuid, {})

    def set(self, uuid: str, fields: dict) -> None:
        d = self._data()
        clean = {k: v for k, v in fields.items() if v is not None and v != ""}
        if clean:
            d[uuid] = clean
        else:
            d.pop(uuid, None)
        self._write(d)

    def all(self) -> dict:
        return self._data()

    def delete(self, uuid: str) -> None:
        d = self._data()
        d.pop(uuid, None)
        self._write(d)


_sched_store = ScheduleStore()


# ── Helpers ─────────────────────────────────────────────────────
def _merge_projects(meta: dict, health_list: list) -> list:
    by_name = {h["name"]: h for h in health_list}
    names   = sorted(set(list(meta.keys()) + list(by_name.keys())))
    result  = []
    for name in names:
        m = meta.get(name, {})
        h = by_name.get(name, {})
        result.append({
            "name":        name,
            "description": m.get("description", ""),
            "status":      m.get("status", "active"),
            "priority":    m.get("priority", ""),
            "due":         m.get("due", ""),
            "color":       m.get("color", ""),
            "created":     m.get("created", ""),
            "notes":       m.get("notes", ""),
            "category":    m.get("category", ""),
            "pending":     h.get("pending",   0),
            "overdue":     h.get("overdue",   0),
            "completed":   h.get("completed", 0),
            "pct":         h.get("pct",       0),
            "health":      h.get("health",    "ok"),
        })
    return result


# ── Routes ─────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(STATIC / "index.html")


@app.get("/api/stats")
async def stats():
    try:
        data = tw.get_stats()
        meta = _store.all()
        active_statuses = {"active", "on-hold"}
        data["project_health"] = [
            p for p in data["project_health"]
            if meta.get(p["name"], {}).get("status", "active") in active_statuses
        ]
        ph = data["project_health"]
        data["portfolio"] = {
            "labels":  [f"@{p['name']}" for p in ph],
            "done":    [p["completed"]              for p in ph],
            "pending": [p["pending"] - p["overdue"] for p in ph],
            "overdue": [p["overdue"]                for p in ph],
        }
        return data
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/api/hot")
async def hot():
    try:
        return tw.get_hot_tasks()
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/api/tasks")
async def tasks(filter: str = "status:pending"):
    try:
        return tw.export(shlex.split(filter))
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/api/reports")
async def reports():
    try:
        return tw.get_reports()
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/api/tags")
async def tags():
    try:
        task_list = tw.export(["status:pending"])
        all_tags: set[str] = set()
        for t in task_list:
            all_tags.update(t.get("tags") or [])
        return sorted(all_tags)
    except RuntimeError as e:
        raise HTTPException(503, str(e))


# ── Projects CRUD ───────────────────────────────────────────────

@app.get("/api/projects")
async def list_projects():
    try:
        meta   = _store.all()
        health = tw.get_stats().get("project_health", [])
        return _merge_projects(meta, health)
    except RuntimeError as e:
        raise HTTPException(503, str(e))


class ProjectBody(BaseModel):
    name:        str
    description: str | None = None
    status:      str | None = "active"
    priority:    str | None = None
    due:         str | None = None
    color:       str | None = None
    notes:       str | None = None
    category:    str | None = None


@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectBody):
    _store.upsert(body.name, body.model_dump(exclude={"name"}))
    return {"ok": True}


@app.patch("/api/projects/{project_name}")
async def update_project(project_name: str, body: ProjectBody):
    new_name = body.name
    fields   = body.model_dump(exclude={"name"})
    if new_name != project_name:
        try:
            tw.rename_project(project_name, new_name)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        _store.rename(project_name, new_name)
    _store.upsert(new_name, fields)
    return {"ok": True}


@app.delete("/api/projects/{project_name}")
async def delete_project(project_name: str, delete_tasks: bool = Query(True)):
    if delete_tasks:
        try:
            tw.delete_project(project_name)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
    _store.delete(project_name)
    return {"ok": True}


# ── Categories CRUD ─────────────────────────────────────────────

class CategoryBody(BaseModel):
    name:        str
    description: str | None = None
    color:       str | None = None


@app.get("/api/categories")
async def list_categories():
    return _cat_store.all()


@app.post("/api/categories", status_code=201)
async def create_category(body: CategoryBody):
    _cat_store.upsert(body.name, body.model_dump(exclude={"name"}))
    return {"ok": True}


@app.patch("/api/categories/{cat_name}")
async def update_category(cat_name: str, body: CategoryBody):
    new_name = body.name
    if new_name != cat_name:
        _cat_store.rename(cat_name, new_name)
        proj_data = _store._data()
        for p in proj_data.values():
            if p.get("category") == cat_name:
                p["category"] = new_name
        _store._write(proj_data)
    _cat_store.upsert(new_name, body.model_dump(exclude={"name"}))
    return {"ok": True}


@app.delete("/api/categories/{cat_name}")
async def delete_category(cat_name: str):
    _cat_store.delete(cat_name)
    return {"ok": True}


# ── Tasks CRUD ──────────────────────────────────────────────────

class AddRequest(BaseModel):
    raw: str


@app.post("/api/tasks", status_code=201)
async def add_task(body: AddRequest):
    try:
        uuid = tw.add(**parse_quick_add(body.raw))
        return {"ok": True, "uuid": uuid}
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400 if isinstance(e, ValueError) else 503, str(e))


@app.patch("/api/tasks/{task_id}/done")
async def complete_task(task_id: int):
    try:
        tw.done(task_id)
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.patch("/api/tasks/{task_id}/undo")
async def undo_task(task_id: int):
    try:
        tw.undo(task_id)
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.patch("/api/tasks/uuid/{uuid}/undo")
async def undo_task_by_uuid(uuid: str):
    try:
        tw.undo_by_uuid(uuid)
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


class AnnotateRequest(BaseModel):
    text: str


@app.post("/api/tasks/{task_id}/annotate")
async def annotate_task(task_id: int, body: AnnotateRequest):
    try:
        tw.annotate(task_id, body.text)
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


class ModifyRequest(BaseModel):
    description: str | None = None
    project:     str | None = None
    priority:    str | None = None
    due:         str | None = None
    tags:        list[str] | None = None


@app.patch("/api/tasks/{task_id}")
async def modify_task(task_id: int, body: ModifyRequest):
    try:
        kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
        tw.modify(task_id, **kwargs)
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.delete("/api/tasks/purge")
async def purge_deleted_tasks():
    try:
        count = tw.purge_deleted()
        return {"ok": True, "purged": count}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    try:
        tw.delete(task_id)
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: int):
    try:
        found = tw.export([f"id:{task_id}"])
        if not found:
            found = tw.export(["status:completed", f"id:{task_id}"])
        if not found:
            raise HTTPException(404, "Task not found")
        task = found[0]
        sched = _sched_store.get(task.get("uuid", ""))
        task["sched_start"] = sched.get("sched_start")
        task["sched_end"]   = sched.get("sched_end")
        return task
    except RuntimeError as e:
        raise HTTPException(503, str(e))


# ── Calendar ─────────────────────────────────────────────────────

@app.get("/api/calendar")
async def calendar_range(start: str = Query(...), end: str = Query(...)):
    """Return all tasks (pending + recently completed) relevant to [start, end]."""
    try:
        pending   = tw.export(["status:pending"])
        completed = tw.export(["status:completed", f"end.after:{start.replace('-','')}T000000Z"])
        sched_all = _sched_store.all()

        result = []
        for task in pending + completed:
            uuid  = task.get("uuid", "")
            sched = sched_all.get(uuid, {})
            task["sched_start"] = sched.get("sched_start")
            task["sched_end"]   = sched.get("sched_end")

            # Include if task falls in range by sched_start, due, or completion date
            in_range = False
            if task["sched_start"]:
                in_range = start <= task["sched_start"][:10] <= end
            if not in_range and task.get("due"):
                d = task["due"]
                due_date = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
                in_range = start <= due_date <= end
            if not in_range and task.get("end") and task.get("status") == "completed":
                e = task["end"]
                end_date = f"{e[0:4]}-{e[4:6]}-{e[6:8]}"
                in_range = start <= end_date <= end

            if in_range:
                result.append(task)
        return result
    except RuntimeError as e:
        raise HTTPException(503, str(e))


class ScheduleRequest(BaseModel):
    sched_start: str | None = None
    sched_end:   str | None = None


@app.patch("/api/tasks/{task_id}/schedule")
async def schedule_task(task_id: int, body: ScheduleRequest):
    try:
        found = tw.export([f"id:{task_id}"])
        if not found:
            found = tw.export(["status:completed", f"id:{task_id}"])
        if not found:
            raise HTTPException(404, "Task not found")
        uuid = found[0].get("uuid", "")
        _sched_store.set(uuid, {"sched_start": body.sched_start, "sched_end": body.sched_end})
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@app.patch("/api/tasks/uuid/{uuid}/schedule")
async def schedule_task_by_uuid(uuid: str, body: ScheduleRequest):
    """Schedule by stable UUID — avoids integer-ID lookup failures."""
    _sched_store.set(uuid, {"sched_start": body.sched_start, "sched_end": body.sched_end})
    return {"ok": True}


# ── AI Chat ─────────────────────────────────────────────────────

@app.get("/api/ai/status")
async def ai_status():
    """Returns which AI SDKs are available in this environment."""
    result = {}
    for pkg in ("anthropic", "openai"):
        try:
            mod = __import__(pkg)
            result[pkg] = {"available": True, "version": getattr(mod, "__version__", "?")}
        except ImportError:
            result[pkg] = {"available": False}
    return result


class AIChatRequest(BaseModel):
    messages:          list
    provider:          str = "anthropic"
    model:             str = "claude-haiku-4-5-20251001"
    api_key:           str = ""
    context:           dict = {}
    confirmed_action:  dict | None = None


@app.post("/api/ai/chat")
async def ai_chat(body: AIChatRequest):
    from taskmaster import ai as _ai
    from taskmaster.parser import parse_quick_add as _pqa

    async def generate():
        try:
            async for event in _ai.stream(
                messages=body.messages,
                provider=body.provider,
                model=body.model,
                api_key=body.api_key,
                context=body.context,
                store=_store,
                cat_store=_cat_store,
                confirmed_action=body.confirmed_action,
                tw=tw,
                parse_quick_add=_pqa,
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
            yield f"data: {json.dumps({'type':'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── iCal feeds ──────────────────────────────────────────────────

class ICalFeedBody(BaseModel):
    name:  str
    url:   str
    color: str = "#4285f4"

class ICalFeedUpdate(BaseModel):
    name:    str | None = None
    url:     str | None = None
    color:   str | None = None
    enabled: bool | None = None

@app.get("/api/ical/feeds")
async def get_ical_feeds():
    return ical_store.list_feeds()

@app.post("/api/ical/feeds", status_code=201)
async def create_ical_feed(body: ICalFeedBody):
    return ical_store.add_feed(body.name, body.url, body.color)

@app.patch("/api/ical/feeds/{idx}")
async def update_ical_feed(idx: int, body: ICalFeedUpdate):
    try:
        return ical_store.update_feed(idx, **body.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(404, str(e))

@app.delete("/api/ical/feeds/{idx}")
async def delete_ical_feed(idx: int):
    try:
        ical_store.delete_feed(idx)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))

@app.get("/api/ical/events")
async def get_ical_events(start: str = Query(...), end: str = Query(...)):
    from datetime import date as _date
    try:
        s = _date.fromisoformat(start)
        e = _date.fromisoformat(end)
        return ical_store.fetch_events(s, e)
    except Exception as ex:
        raise HTTPException(400, str(ex))

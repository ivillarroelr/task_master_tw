"""Subprocess wrapper around TaskWarrior via WSL2 (or native)."""
import json
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

# Configured by main.py after reading tw.toml
BACKEND    = "wsl"
WSL_DISTRO = ""
_BASE_CMD: list[str] = []


def _build_cmd() -> None:
    pass  # kept for compatibility; _run builds the command directly


def _run(*args: str) -> tuple[str, str]:
    import shlex
    task_parts = ["task", "rc.confirmation=no", "rc.verbose=nothing", *args]
    if BACKEND == "wsl":
        prefix = ["wsl"]
        if WSL_DISTRO:
            prefix += ["-d", WSL_DISTRO]
        # Use bash so /usr/bin is in PATH — /bin/sh invoked by plain `wsl task` has a minimal PATH
        cmd = prefix + ["sh", "-c", " ".join(shlex.quote(p) for p in task_parts)]
    else:
        cmd = task_parts
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", timeout=15,
        )
        # Filter out harmless WSL config warnings (lines starting with "wsl:")
        stderr_clean = "\n".join(
            l for l in r.stderr.splitlines() if not l.startswith("wsl:")
        ).strip()
        if r.returncode != 0 and stderr_clean:
            raise RuntimeError(stderr_clean)
        return r.stdout, r.stderr
    except FileNotFoundError:
        raise RuntimeError(
            "WSL not found. Install WSL2 + Ubuntu and run: sudo apt install taskwarrior"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("TaskWarrior timed out (>15 s).")


def _parse_export(raw: str) -> list[dict]:
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


# ── Public CRUD ────────────────────────────────────────────────

def export(filter_args: list[str] | None = None) -> list[dict]:
    args = list(filter_args or []) + ["export"]
    out, _ = _run(*args)
    return _parse_export(out)


def add(description: str, project: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        due: str | None = None) -> str:
    if not description:
        raise ValueError("Description cannot be empty.")
    args = ["add", description]
    if project:  args += [f"project:{project}"]
    if priority: args += [f"priority:{priority.upper()}"]
    for tag in (tags or []): args += [f"+{tag}"]
    if due:      args += [f"due:{due}"]
    _run(*args)
    out, _ = _run("+LATEST", "export")
    tasks = _parse_export(out)
    return tasks[0].get("uuid", "") if tasks else ""


def done(task_id: int) -> None:
    _run(str(task_id), "done")


def modify(task_id: int, **kwargs) -> None:
    args = [str(task_id), "modify"]
    for k, v in kwargs.items():
        if not v:
            continue
        if k == "tags":
            for t in v: args.append(f"+{t}")
        elif k == "description":
            args.append(v)
        else:
            args.append(f"{k}:{v}")
    _run(*args)


def delete(task_id: int) -> None:
    _run(str(task_id), "delete")


def purge_deleted() -> int:
    deleted = export(["status:deleted"])
    if deleted:
        _run("status:deleted", "purge")
    return len(deleted)


def rename_project(old_name: str, new_name: str) -> None:
    _run(f"project:{old_name}", "modify", f"project:{new_name}")


def delete_project(name: str) -> None:
    _run(f"project:{name}", "delete")


def annotate(task_id: int, text: str) -> None:
    _run(str(task_id), "annotate", text)


def undo(task_id: int) -> None:
    _run(str(task_id), "modify", "status:pending")


def undo_by_uuid(uuid: str) -> None:
    _run(uuid, "modify", "status:pending")


# ── Date helpers ───────────────────────────────────────────────

def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").date()
    except (ValueError, TypeError):
        return None


def _due_category(task: dict) -> str | None:
    d = _parse_date(task.get("due"))
    if d is None:
        return None
    today = date.today()
    if d < today:  return "overdue"
    if d == today: return "today"
    return None


def _days_overdue(task: dict) -> int | None:
    d = _parse_date(task.get("due"))
    return (date.today() - d).days if d and d < date.today() else None


# ── Aggregated stats for dashboard ────────────────────────────

def get_stats() -> dict[str, Any]:
    today = date.today()
    pending    = export(["status:pending"])
    done_today = export(["status:completed", "end:today"])

    # Velocity — completions per day, last 14 days
    cutoff = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    recent = export(["status:completed", f"end.after:{cutoff}"])
    vel_by_day: dict[str, int] = defaultdict(int)
    for t in recent:
        d = _parse_date(t.get("end"))
        if d: vel_by_day[str(d)] += 1

    vel_labels, vel_data = [], []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        vel_labels.append("today" if i == 0 else f"{d.day}/{d.month}")
        vel_data.append(vel_by_day.get(str(d), 0))

    # Due buckets
    buckets = {k: 0 for k in ("overdue", "today", "3d", "7d", "30d", "later")}
    for t in pending:
        d = _parse_date(t.get("due"))
        if d is None: continue
        delta = (d - today).days
        if   delta < 0:   buckets["overdue"] += 1
        elif delta == 0:  buckets["today"]   += 1
        elif delta <= 3:  buckets["3d"]      += 1
        elif delta <= 7:  buckets["7d"]      += 1
        elif delta <= 30: buckets["30d"]     += 1
        else:             buckets["later"]   += 1

    # Project health
    completed_all = export(["status:completed"])
    proj_names = sorted({
        t.get("project", "") for t in pending + completed_all
        if t.get("project")
    })

    project_health = []
    for proj in proj_names:
        p_pend = [t for t in pending       if t.get("project") == proj]
        p_done = [t for t in completed_all if t.get("project") == proj]
        over   = sum(1 for t in p_pend if _due_category(t) == "overdue")
        total  = len(p_pend) + len(p_done)
        pct    = round(len(p_done) / total * 100) if total else 0
        health = (
            "critical" if over >= 2 or (over >= 1 and pct < 40)
            else "warning" if over >= 1 or pct < 55
            else "ok"
        )
        project_health.append({
            "name": proj, "pending": len(p_pend), "overdue": over,
            "completed": len(p_done), "pct": pct, "health": health,
        })

    return {
        "total":     len(pending),
        "overdue":   sum(1 for t in pending if _due_category(t) == "overdue"),
        "due_today": sum(1 for t in pending if _due_category(t) == "today"),
        "done_today": len(done_today),
        "velocity_labels": vel_labels,
        "velocity_data":   vel_data,
        "due_buckets": buckets,
        "by_priority": dict(Counter(t.get("priority") or "" for t in pending)),
        "project_health": project_health,
        "portfolio": {
            "labels":  [f"@{p['name']}" for p in project_health],
            "done":    [p["completed"]               for p in project_health],
            "pending": [p["pending"] - p["overdue"]  for p in project_health],
            "overdue": [p["overdue"]                 for p in project_health],
        },
    }


def get_hot_tasks() -> list[dict]:
    pending = export(["status:pending"])
    hot = []
    for t in pending:
        cat = _due_category(t)
        if cat is None and t.get("priority") == "H":
            cat = "high_no_due"
        if cat is not None:
            hot.append({**t, "_category": cat,
                        "_days_overdue": _days_overdue(t)})
    hot.sort(key=lambda t: t.get("urgency") or 0, reverse=True)
    return hot


def get_reports() -> dict[str, Any]:
    today  = date.today()
    cutoff = (today - timedelta(days=84)).strftime("%Y-%m-%d")
    recent = export(["status:completed", f"end.after:{cutoff}"])

    added_by_day: dict[str, int] = defaultdict(int)
    done_by_day:  dict[str, int] = defaultdict(int)
    proj_done:    dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for t in recent:
        d = _parse_date(t.get("end"))
        if d:
            done_by_day[str(d)] += 1
            proj = t.get("project", "")
            if proj: proj_done[proj][str(d)] += 1

    pending = export(["status:pending"])
    for t in pending:
        d = _parse_date(t.get("entry"))
        if d and d >= today - timedelta(days=30):
            added_by_day[str(d)] += 1

    bd_labels, bd_added, bd_done = [], [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        bd_labels.append("today" if i == 0 else f"{d.day}/{d.month}")
        bd_added.append(added_by_day.get(str(d), 0))
        bd_done.append(done_by_day.get(str(d), 0))

    # Weekly velocity — last 8 weeks
    wk_labels, wk_data = [], []
    for w in range(7, -1, -1):
        wk_start = today - timedelta(days=today.weekday() + 7 * w)
        wk_end   = wk_start + timedelta(days=6)
        count = sum(v for k, v in done_by_day.items()
                    if wk_start <= date.fromisoformat(k) <= wk_end)
        wk_labels.append("this wk" if w == 0 else f"W-{w}")
        wk_data.append(count)

    # Per-project: completions per day, last 14 days
    proj_trends: dict[str, list[int]] = {}
    for proj, by_day in proj_done.items():
        counts = []
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            counts.append(by_day.get(str(d), 0))
        proj_trends[proj] = counts

    return {
        "burndown_labels": bd_labels,
        "burndown_added":  bd_added,
        "burndown_done":   bd_done,
        "weekly_labels":   wk_labels,
        "weekly_data":     wk_data,
        "proj_trends":     proj_trends,
        "heatmap_data":    dict(done_by_day),
    }

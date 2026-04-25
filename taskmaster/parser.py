"""Parse quick-add syntax into TaskWarrior kwargs."""
import re


def parse_quick_add(raw: str) -> dict:
    """
    '!h Fix login bug @work #deploy due:fri'
    '!m Study @"certamen 1 microeconomia" due:fri'
    → {'description': ..., 'project': ..., 'priority': ..., 'tags': [...], 'due': ...}

    @project      → single-word project name
    @"my project" → multi-word project name (use quotes)
    """
    text = raw.strip()
    priority, proj, tags, due = None, None, [], None

    # Priority: !h / !m / !l standalone token
    m = re.search(r'(?<!\S)!(h|m|l)(?=\s|$)', text, re.I)
    if m:
        priority = m.group(1).upper()
        text = (text[:m.start()] + text[m.end():]).strip()

    # Project: @"multi word name" first, then @singleword fallback
    m = re.search(r'@"([^"]+)"', text)
    if m:
        proj = m.group(1).strip()
        text = (text[:m.start()] + text[m.end():]).strip()
    else:
        m = re.search(r'@(\S+)', text)
        if m:
            proj = m.group(1).strip()
            text = (text[:m.start()] + text[m.end():]).strip()

    # Due date: due:value
    m = re.search(r'(?i)\bdue:(\S+)', text)
    if m:
        due = m.group(1)
        text = (text[:m.start()] + text[m.end():]).strip()

    # Tags: #tag
    tags = re.findall(r'#(\S+)', text)
    text = re.sub(r'#\S+', '', text)

    description = ' '.join(text.split())
    if not description:
        raise ValueError("Task description cannot be empty.")

    return dict(description=description, project=proj,
                priority=priority, tags=tags, due=due)

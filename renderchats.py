from __future__ import annotations

from datetime import datetime, timezone
from html import escape


def _format_time(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    diff = now - dt
    diff_mins = int(diff.total_seconds() // 60)
    diff_hours = int(diff.total_seconds() // 3600)
    diff_days = int(diff.total_seconds() // 86400)

    if diff_mins < 1:
        return "now"
    if diff_mins < 60:
        return f"{diff_mins}m ago"
    if diff_hours < 24:
        return f"{diff_hours}h ago"
    if diff_days < 7:
        return f"{diff_days}d ago"

    return dt.date().isoformat()


def render_messages_html(message_list: list[dict], current_username: str) -> str:
    if not message_list:
        return '<div class="empty-state"><h3>No messages yet</h3><p>Start the conversation!</p></div>'

    parts: list[str] = []
    for msg in message_list:
        sender = str(msg.get("sender", ""))
        text = str(msg.get("text", ""))
        timestamp = msg.get("timestamp")

        sender_safe = escape(sender)
        text_safe = escape(text).replace("\n", "<br>")
        time_safe = escape(_format_time(timestamp if isinstance(timestamp, datetime) else None))

        own = sender == current_username
        cls = "own" if own else "other"

        parts.append(
            f'<div class="message {cls}">'
            f"  <div>"
            f'    <div class="message-bubble">{text_safe}</div>'
            f'    <div class="message-info"><span>{sender_safe}</span> • <span>{time_safe}</span></div>'
            f"  </div>"
            f"</div>"
        )

    return "".join(parts)

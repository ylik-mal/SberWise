"""Shared presentation for SberWise room invitations."""

import html


def build_room_invite_caption(room_name: str, creator_name: str | None = None) -> str:
    """Create the safe, compact HTML caption used by every invite channel."""
    safe_room_name = html.escape((room_name or "Комната SberWise").strip()[:240])
    safe_creator_name = html.escape((creator_name or "").strip()[:120])
    invitation_line = (
        f"{safe_creator_name} приглашает тебя в комнату" if safe_creator_name
        else "Тебя приглашают в общую комнату"
    )
    return (
        "✨ <b>SberWise</b>\n\n"
        f"{invitation_line}\n"
        f"<b>«{safe_room_name}»</b>\n\n"
        "Веди общие расходы, следи за долгами\n"
        "и контролируй бюджет вместе.\n\n"
        "Нажми кнопку ниже, чтобы присоединиться 👇"
    )

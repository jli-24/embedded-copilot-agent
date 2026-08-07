from __future__ import annotations

from .contracts import ConversationTurn


def rank_turns(turns: tuple[ConversationTurn, ...]) -> tuple[ConversationTurn, ...]:
    return tuple(
        sorted(
            turns,
            key=lambda item: (len(item.references), len(item.content_summary), item.turn_id),
            reverse=True,
        )
    )


__all__ = ["rank_turns"]

"""User service and LLM context builder."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from ..storage.repositories import UserRepository

if TYPE_CHECKING:
    from ..storage.models import User


class UserContextBuilder:
    """Build LLM system prompt context from user profiles."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UserRepository(session)

    async def build_prompt_context(self) -> str:
        """
        Return a system prompt addition listing known users.

        Returns empty string if no users are configured.
        """
        users = await self.repo.list()
        if not users:
            return ""

        lines = ["Known people in this household/organization:"]
        for user in users:
            aliases = json.loads(user.aliases or "[]")
            if aliases:
                alias_str = ", ".join(aliases)
                lines.append(f"- {user.name} (also known as: {alias_str})")
            else:
                lines.append(f"- {user.name}")

        lines.append(
            "When classifying documents, if the content refers to any of these people, "
            "add a 'user:{name}' tag using their primary name."
        )

        return "\n".join(lines)

    def get_person_tags(self, text: str, users) -> list[str]:
        """
        Check if any known user/alias appears in text.

        Returns list of 'user:{name}' tags for any matches.
        """
        text_lower = text.lower()
        tags = []
        for user in users:
            names_to_check = [user.name]
            aliases = json.loads(user.aliases or "[]")
            names_to_check.extend(aliases)

            for name in names_to_check:
                if name.lower() in text_lower:
                    tags.append(f"user:{user.name}")
                    break  # Don't double-tag same user

        return tags

    @staticmethod
    def get_user_names(users) -> list[str]:
        """Return list of user names for prompt injection."""
        return [u.name for u in users]

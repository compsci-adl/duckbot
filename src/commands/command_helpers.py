from functools import wraps
from typing import Any, Callable


def require_admin(require_guild: bool = True) -> Callable:
    """Enforce admin role and optional guild context for command handlers."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            # Locate the Interaction object in args or kwargs
            interaction = kwargs.get("interaction")
            if interaction is None:
                for a in args:
                    if hasattr(a, "response") and hasattr(a, "user"):
                        interaction = a
                        break

            # If no interaction found, call through
            if interaction is None:
                return await func(*args, **kwargs)

            # Determine if bound method and has check_admin attribute
            is_bound = len(args) > 0
            has_check = is_bound and hasattr(args[0], "check_admin")

            # Evaluate admin check
            if has_check:
                ok = await args[0].check_admin(interaction)
            else:
                member = interaction.user
                ok = False
                if interaction.guild and hasattr(member, "roles"):
                    try:
                        role_names = {r.name for r in member.roles}
                        ok = "Exec Committee" in role_names or "Mods" in role_names
                    except Exception:
                        ok = False

            if not ok:
                # If the interaction has already been responded to (for example
                # by a class-level `check_admin` method), don't try to respond
                # again — that raises InteractionResponded. Only send the
                # permission message if no response has been sent yet.
                try:
                    already_responded = interaction.response.is_done()
                except Exception:
                    already_responded = False

                if not already_responded:
                    await interaction.response.send_message(
                        "You don't have permission to execute that command.",
                        ephemeral=True,
                    )
                return

            # Guild requirement
            if require_guild and not interaction.guild:
                try:
                    already_responded = interaction.response.is_done()
                except Exception:
                    already_responded = False

                if not already_responded:
                    await interaction.response.send_message(
                        "Guild context required.", ephemeral=True
                    )
                return

            return await func(*args, **kwargs)

        return wrapper

    return decorator

import logging

from discord.enums import EventStatus


def get_event_role_name(event_name: str) -> str:
    """Return the role name for a given event, clamped to Discord's 100 character limit."""
    name = f"Event: {event_name.strip()}"
    return name[:100]


class EventRoleManager:
    """Manages auto-assignment and deletion of event notification roles."""

    def __init__(self, bot):
        self.bot = bot

    async def on_scheduled_event_user_add(self, event, user):
        """Auto-assigns a notification role (per event) when a user is interested in an event."""
        guild = self.bot.get_guild(event.guild_id)
        if not guild:
            return
        member = guild.get_member(user.id)
        if not member:
            member = await guild.fetch_member(user.id)
        role_name = get_event_role_name(event.name)
        role = next((r for r in guild.roles if r.name == role_name), None)
        if not role:
            try:
                role = await guild.create_role(
                    name=role_name, reason=f"Auto-created for event: {event.name}"
                )
                logging.info(f"Created new event notification role: {role_name}")
            except Exception as e:
                logging.error(f"Failed to create event notification role: {e}")
                return
        if role and member:
            try:
                await member.add_roles(
                    role, reason=f"Interested in event: {event.name}"
                )
                logging.info(
                    f"Added event notification role '{role_name}' to {member.display_name} for event {event.name}"
                )
            except Exception as e:
                logging.error(f"Failed to add event notification role: {e}")

    async def on_scheduled_event_user_remove(self, event, user):
        """Removes the notification role (per event) if user is no longer interested in the event."""
        guild = self.bot.get_guild(event.guild_id)
        if not guild:
            return
        member = guild.get_member(user.id)
        if not member:
            member = await guild.fetch_member(user.id)
        role_name = get_event_role_name(event.name)
        role = next((r for r in guild.roles if r.name == role_name), None)
        if role and member:
            try:
                await member.remove_roles(
                    role, reason=f"No longer interested in event: {event.name}"
                )
                logging.info(
                    f"Removed event notification role '{role_name}' from {member.display_name} for event {event.name}"
                )
            except Exception as e:
                logging.error(f"Failed to remove event notification role: {e}")

    async def on_scheduled_event_update(self, before, after):
        """Handles event updates: renames roles if event is renamed, and deletes roles when all instances end."""
        guild = self.bot.get_guild(after.guild_id)
        if not guild:
            return

        # If event was renamed, rename the corresponding notification role
        if before.name != after.name:
            old_role_name = get_event_role_name(before.name)
            new_role_name = get_event_role_name(after.name)
            role = next((r for r in guild.roles if r.name == old_role_name), None)
            if role:
                try:
                    await role.edit(
                        name=new_role_name,
                        reason=f"Event renamed from '{before.name}' to '{after.name}'",
                    )
                    logging.info(
                        f"Renamed event notification role '{old_role_name}' to '{new_role_name}'"
                    )
                except Exception as e:
                    logging.error(f"Failed to rename event notification role: {e}")

        # Deletes the notification role after the event ends or is cancelled,
        # unless there are other scheduled or active instances with the same name.
        if before.status != after.status and after.status in (
            EventStatus.completed,
            EventStatus.cancelled,
        ):
            has_active_sibling = any(
                ev.id != after.id
                and ev.name == after.name
                and ev.status not in (EventStatus.completed, EventStatus.cancelled)
                for ev in guild.scheduled_events
            )
            if has_active_sibling:
                logging.info(
                    f"Preserving event notification role for '{after.name}' as other scheduled instances remain."
                )
                return

            role_name = get_event_role_name(after.name)
            role = next((r for r in guild.roles if r.name == role_name), None)
            if not role:
                return
            try:
                await role.delete(
                    reason=f"Event {after.name} ended or was cancelled; auto-deleted notification role."
                )
                logging.info(
                    f"Deleted event notification role '{role_name}' after event {after.name} ended or was cancelled."
                )
            except Exception as e:
                logging.error(f"Failed to delete event notification role: {e}")

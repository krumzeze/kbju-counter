from sqlalchemy.ext.asyncio import AsyncSession

from belok.db.models import AdminAction, User


def log_action(
    session: AsyncSession,
    admin: User,
    action: str,
    target_user_id: int | None = None,
    **details,
) -> None:
    session.add(
        AdminAction(
            admin_id=admin.id,
            action=action,
            target_user_id=target_user_id,
            details=details or None,
        )
    )

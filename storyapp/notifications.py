import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def push_notification(user_id, event_type, message):
    """
    Send a live WebSocket message to one user.

    The Notification row is already saved in the database, so if Redis is
    unavailable we log the error instead of failing the request.
    """
    try:
        async_to_sync(get_channel_layer().group_send)(
            f"user_notifications_{user_id}",
            {
                "type": "send_notification",
                "event_type": event_type,
                "message": message,
            },
        )
    except Exception:
        logger.exception("Could not push %s notification to user %s", event_type, user_id)

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken


@database_sync_to_async
def get_user_from_token(raw_token):
    auth = JWTAuthentication()
    try:
        validated_token = auth.get_validated_token(raw_token)
        return auth.get_user(validated_token)
    except (InvalidToken, AuthenticationFailed):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Browsers can't send an Authorization header on WebSockets, so the
    access token comes in the query string: ws/notifications/<id>/?token=<access>
    """

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get('query_string', b'').decode())
        token = query.get('token', [None])[0]

        scope['user'] = await get_user_from_token(token) if token else AnonymousUser()

        return await super().__call__(scope, receive, send)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import UserRegisterSerializer, LoginSerializer, UserProfileSerializer, AuthorSerializer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef
from .models import User
from storyapp.models import Story, Chapter
from django.shortcuts import get_object_or_404


def refresh_cookie_options():
    # Production: the Netlify frontend is a different site, which needs
    # SameSite=None, and browsers only accept that together with Secure (HTTPS).
    # Local http://localhost development uses Lax instead.
    if settings.DEBUG:
        return {"secure": False, "samesite": "Lax"}
    return {"secure": True, "samesite": "None"}


def set_refresh_cookie(response, token):
    response.set_cookie(key="refresh_token", value=token, httponly=True, path="/", **refresh_cookie_options())


class RegisterView(APIView):
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        response = Response({"access": str(refresh.access_token)}, status=status.HTTP_200_OK)
        set_refresh_cookie(response, str(refresh))
        return response
        
        
class CookieRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "no refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = self.get_serializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            # Expired or blacklisted token: 401, as Simple JWT's own view does.
            raise InvalidToken(e.args[0])
        
        data = serializer.validated_data
        response = Response({"access": data["access"]}, status=status.HTTP_200_OK)

        if "refresh" in data:
            set_refresh_cookie(response, data["refresh"])

        return response
    
    
class LogoutView(APIView):
    # Logout only needs the refresh cookie. The access token may already be
    # expired (it lives 5 minutes), so don't authenticate or require it.
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh = request.COOKIES.get("refresh_token")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # already expired or blacklisted: nothing left to revoke
        response = Response({"detail": "Logged out"}, status=status.HTTP_205_RESET_CONTENT)
        response.delete_cookie(key="refresh_token", path="/", samesite=refresh_cookie_options()["samesite"])
        return response
        
        
        
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        
        serailizer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serailizer.data)
    
    def patch(self, request):
        serilaizer = UserProfileSerializer(request.user, data=request.data, partial=True, context={"request": request})
        if serilaizer.is_valid():
            serilaizer.save()
            return Response(serilaizer.data, status=status.HTTP_200_OK)
        return Response(serilaizer.errors, status=status.HTTP_400_BAD_REQUEST)
    
  
    @transaction.atomic
    def delete(self, request):
        user = request.user

        # Stories where this user is the last remaining author would have nobody
        # left to vote on proposals, so they become completed. Their chapters
        # stay in place as "Anonymous" (Chapter.author is SET_NULL).
        user_chapters = Chapter.objects.filter(story=OuterRef('pk'), author=user)
        other_author_chapters = (
            Chapter.objects.filter(story=OuterRef('pk'), author__isnull=False)
            .exclude(author=user)
        )
        Story.objects.filter(
            Exists(user_chapters),
            ~Exists(other_author_chapters),
            is_completed=False,
        ).update(is_completed=True)

        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
class AuthorView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        author = get_object_or_404(User, pk=pk)
        serializer = AuthorSerializer(author,  context={"request": request})
        return Response(serializer.data)
        
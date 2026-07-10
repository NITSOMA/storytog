from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import UserRegisterSerializer, LoginSerializer, UserProfileSerializer, AuthorSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from .models import User
from django.shortcuts import get_object_or_404


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
        
        cookie_secure = not settings.DEBUG
        cookie_samesite = "Lax" if settings.DEBUG else "None"
            
        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            httponly=True,
            secure=cookie_secure,
            samesite=cookie_samesite,
            path="/"
        )
        return response
        
        
class CookieRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")
        if not refresh_token:
            return Response({"detail": "no refresh token"}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = self.get_serializer(data={"refresh": refresh_token})  
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        response = Response({"access": data["access"]}, status=status.HTTP_200_OK)
    
        
        
            
        if "refresh" in data:
            cookie_secure = not settings.DEBUG
            cookie_samesite = "Lax" if settings.DEBUG else "None"
            response.set_cookie(
                key="refresh_token",
                value=data["refresh"],
                httponly=True,
                secure=cookie_secure,
                samesite=cookie_samesite,
                path="/"
            )

        return response
    
    
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        refresh = request.COOKIES.get("refresh_token")
        if refresh:
            try:
                token = RefreshToken(refresh)
                token.blacklist()
            except:
                pass
        response =  Response({"detail": "Logged out"}, status=status.HTTP_205_RESET_CONTENT)
        response.delete_cookie(key="refresh_token", path="/", samesite="None")
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
    
  
    def delete(self, request):
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    
class AuthorView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        author = get_object_or_404(User, pk=pk)
        serializer = AuthorSerializer(author,  context={"request": request})
        return Response(serializer.data)
        
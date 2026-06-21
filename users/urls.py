from .views import RegisterView, LoginView, CookieRefreshView, ProfileView, LogoutView
from django.urls import path


urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("login/", LoginView.as_view()),
    path("logout/", LogoutView.as_view()),
    path("refresh/", CookieRefreshView.as_view()),
    path("profile/", ProfileView.as_view()),
    
    
]

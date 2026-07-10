from .views import VoteCreateView, CommentDetailView, CommentCreateView
from django.urls import path


urlpatterns = [
    path("vote/", VoteCreateView.as_view()),
    path('comment/', CommentCreateView.as_view(), name='comment-create'),
    path('comment/<int:pk>/', CommentDetailView.as_view(), name='comment-detail'),
    
  
    
    
    
]

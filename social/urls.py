from .views import CommentDetailView, CommentCreateView
from django.urls import path


urlpatterns = [
    path('comment/', CommentCreateView.as_view(), name='comment-create'),
    path('comment/<int:pk>/', CommentDetailView.as_view(), name='comment-detail'),
    
  
    
    
    
]

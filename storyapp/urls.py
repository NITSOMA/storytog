from django.urls import path
from .views import (
    StoryView, 
    RequestedChapterView, 
    VoteChapterView, 
    VoteFinishView, 
   NotificationListView,
    NotificationDetailView, 
    StoryDetailView, 
    ChapterDeleteView,
    ChapterFetchView
)

urlpatterns = [
   
    path('', StoryView.as_view(), name='story-list'),
    path('<int:story_pk>/', StoryDetailView.as_view(), name='story-detail'),
    path('requests/<int:story_pk>/', RequestedChapterView.as_view(), name='story-requests'),
    path('requests/vote/<int:request_pk>/', VoteChapterView.as_view(), name='vote-chapter'),
    path('finish/<int:story_pk>/', VoteFinishView.as_view(), name='vote-finish'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<int:notification_pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('chapter/<int:pk>/', ChapterDeleteView.as_view(), name='chapter-delete'),
    path('chapters/<int:story_pk>/<int:chapter_number>/', ChapterFetchView.as_view(), name='fetch-chapter')
    
    
]
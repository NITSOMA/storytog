from django.shortcuts import get_object_or_404
from django.db.models import Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.pagination import PageNumberPagination
import threading
import asyncio
from channels.layers import get_channel_layer


from .models import Story, Chapter, RequestChapter, VoteChapter, VoteFinish, Notification
from .serializers import (
    StoryListSerializer, StoryReadSerializer, StoryCreateSerializer,
    RequestChapterReadSerializer, RequestChapterWriteSerializer,
    VoteChapterSerializer, VoteFinishSerializer, NotificationSerializer
)

class StoryPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100



class StoryView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StoryPagination

    def get(self, request):
        
        queryset = Story.objects.annotate(
            chapters_count=Count('chapters', distinct=True),
            co_authors_count=Count('chapters__author', distinct=True)
        )

       
        ordering = request.query_params.get('ordering', 'latest')
        
        allowed_ordering_fields = {
            'latest': '-created_at',
            'oldest': 'created_at',
            'most_chapters': '-chapters_count',
            'fewest_chapters': 'chapters_count',
            'most_authors': '-co_authors_count',
        }
        
        db_ordering = allowed_ordering_fields.get(ordering, '-created_at')
        queryset = queryset.order_by(db_ordering)

       
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        
        if page is not None:
            serializer = StoryListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = StoryListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = StoryCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StoryDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, story_pk):
        
        story = get_object_or_404(Story, pk=story_pk)
        serializer = StoryReadSerializer(story)
        return Response(serializer.data, status=status.HTTP_200_OK)



class RequestedChapterView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, story_pk):
        story = get_object_or_404(Story, pk=story_pk)
        chapters_waiting = RequestChapter.objects.filter(story=story, status='pending')
        serializer = RequestChapterReadSerializer(chapters_waiting, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, story_pk):
        story = get_object_or_404(Story, pk=story_pk)
        serializer = RequestChapterWriteSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            try:
                new_request = serializer.save(story=story)
                
                
                co_authors = Chapter.objects.filter(story=story).values_list('author', flat=True).distinct()


                notifications_to_create = [
                    Notification(user_id=author_id, requested_chapter=new_request)
                    for author_id in co_authors
                ]
                Notification.objects.bulk_create(notifications_to_create)

               
                def send_redis_notifications(author_ids, story_title):
                    channel_layer = get_channel_layer()
                    
                    
                    async def run_broadcast():
                        for author_id in author_ids:
                            try:
                                await channel_layer.group_send(
                                    f"user_notifications_{author_id}",
                                    {
                                        "type": "send_notification",
                                        "message": f"A new chapter proposal was requested for '{story_title}'!"
                                    }
                                )
                            except Exception as redis_err:
                                print(f"Redis Async Error for user {author_id}: {redis_err}")

                 
                    asyncio.run(run_broadcast())

                
                target_authors = [aid for aid in co_authors]
                
              
                threading.Thread(
                    target=send_redis_notifications, 
                    args=(target_authors, story.title),
                    daemon=True
                ).start()
               

                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except ValueError as e:
                return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
       
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class VoteChapterView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_pk):
        requested_chapter = get_object_or_404(RequestChapter, pk=request_pk)
        
        if requested_chapter.status != 'pending':
            return Response(
                {"detail": "Voting is closed for this chapter proposal."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        vote_instance = VoteChapter.objects.filter(requested_chapter=requested_chapter, user=request.user).first()
        
        if vote_instance and vote_instance.choice == request.data.get('choice'):
            serializer = VoteChapterSerializer(vote_instance)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = VoteChapterSerializer(instance=vote_instance, data=request.data)
        
        if serializer.is_valid():
            serializer.save(requested_chapter=requested_chapter, user=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VoteFinishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, story_pk):
        story = get_object_or_404(Story, pk=story_pk)
        vote_instance = VoteFinish.objects.filter(story=story, author=request.user).first()
        
        serializer = VoteFinishSerializer(instance=vote_instance, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(story=story, author=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_notifications = Notification.objects.filter(user=request.user)
        serializer = NotificationSerializer(user_notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_pk):
        notification = get_object_or_404(Notification, pk=notification_pk, user=request.user)
        serializer = NotificationSerializer(notification, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
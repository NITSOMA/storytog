from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.pagination import PageNumberPagination

from .models import Story, Chapter, RequestChapter, VoteChapter, VoteFinish, Notification
from .notifications import push_notification
from .serializers import (
    StoryListSerializer, StoryReadSerializer, StoryCreateSerializer,
    RequestChapterReadSerializer, RequestChapterWriteSerializer,
    VoteChapterSerializer, VoteFinishSerializer, NotificationListSerializer,
    NotificationDetailSerializer, ChapterReadSerializer
)

class StoryPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = 'page_size'
    max_page_size = 100

class StoryView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StoryPagination

    def get(self, request):
        queryset = Story.objects.with_list_data()
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

class ChapterDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, pk):
        chapter = get_object_or_404(Chapter, pk=pk, author=request.user)
        story = chapter.story
        # Published chapters are shared work. Only a story with a single chapter
        # can be removed, and removing its chapter removes the story.
        if story.chapters.count() > 1:
            return Response(
                {"detail": "Chapters can't be deleted once other chapters have been added to the story."},
                status=status.HTTP_400_BAD_REQUEST
            )
        story.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RequestedChapterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, story_pk):
        story = get_object_or_404(Story, pk=story_pk)

        chapters_waiting = RequestChapter.objects.filter(
            story=story,
            status='pending'
        )

        serializer = RequestChapterReadSerializer(
            chapters_waiting,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    @transaction.atomic
    def post(self, request, story_pk):
        story = get_object_or_404(Story, pk=story_pk)

        serializer = RequestChapterWriteSerializer(
            data=request.data,
            context={
                'request': request,
                'story': story
            }
        )

        if serializer.is_valid():
            try:
              
                new_request = serializer.save(story=story)

               
                co_authors = set(
                    Chapter.objects.filter(story=story, author__isnull=False)
                    .exclude(author=request.user)
                    .values_list('author', flat=True)
                )

              
                notifications_to_create = [
                    Notification(
                        user_id=author_id,
                        requested_chapter=new_request,
                        notification_type='vote_request'
                    )
                    for author_id in co_authors
                ]

                Notification.objects.bulk_create(
                    notifications_to_create
                )

               
                Notification.objects.create(
                    user=request.user,
                    requested_chapter=new_request,
                    notification_type='proposal_update'
                )


                def send_new_request_notifications():
                    message = f"A new chapter proposal was requested for '{story.title}'!"
                    for author_id in co_authors:
                        push_notification(author_id, "new_request", message)

                # Notify only once the proposal is really saved in the database.
                transaction.on_commit(send_new_request_notifications)

                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED
                )

            except ValueError as e:
                return Response(
                    {"detail": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    
    
    


class VoteChapterView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, request_pk):
        requested_chapter = get_object_or_404(
            RequestChapter,
            pk=request_pk
        )

        # Lock the story row until this request finishes. Other votes on the
        # same story wait here, so two votes can't both close a proposal or
        # create the same chapter. Re-read the proposal after getting the lock.
        story = Story.objects.select_for_update().get(pk=requested_chapter.story_id)
        requested_chapter.refresh_from_db()

   
        is_eligible_author = Chapter.objects.filter(
            story=story,
            author=request.user
        ).exists()

        if (
            not is_eligible_author
            or request.user == requested_chapter.author
        ):
            return Response(
                {"detail": "Only eligible story authors can vote."},
                status=status.HTTP_403_FORBIDDEN
            )

        
        if requested_chapter.status != 'pending':
            return Response(
                {"detail": "Voting is closed for this chapter proposal."},
                status=status.HTTP_400_BAD_REQUEST
            )

     
        vote_instance = VoteChapter.objects.filter(
            requested_chapter=requested_chapter,
            user=request.user
        ).first()

        if vote_instance:
            return Response(
                {
                    "detail": (
                        "You have already voted. "
                        "Your decision is final."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = VoteChapterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

       
        serializer.save(
            requested_chapter=requested_chapter,
            user=request.user
        )

      
        Notification.objects.filter(
            user=request.user,
            requested_chapter=requested_chapter,
            notification_type='vote_request'
        ).update(is_read=True)

       
        # Anonymous chapters (deleted accounts) don't count: nobody can vote for them.
        total_authors = (
            Chapter.objects.filter(story=story, author__isnull=False)
            .values('author')
            .distinct()
            .count()
        )

        
        approvals = requested_chapter.votes.filter(
            choice=True
        ).count()

       
        is_proposer_existing_author = Chapter.objects.filter(
            story=story,
            author=requested_chapter.author
        ).exists()

        if is_proposer_existing_author:
            approvals += 1

        rejections = requested_chapter.votes.filter(
            choice=False
        ).count()

     
        final_status = None

        if approvals > total_authors / 2:
            final_status = 'approved'

        elif rejections >= total_authors / 2:
            final_status = 'rejected'

        if final_status is not None:

           
            requested_chapter.status = final_status
            requested_chapter.save(
                update_fields=['status']
            )

         
            if final_status == 'approved':
                Chapter.objects.create(
                    story=story,
                    author=requested_chapter.author,
                    content=requested_chapter.content
                )

           
            Notification.objects.filter(
                requested_chapter=requested_chapter,
                notification_type='vote_request',
                is_read=True
            ).delete()

            
            remaining_notifications = list(Notification.objects.filter(
                requested_chapter=requested_chapter,
                is_read=False
            ).values_list(
                'user_id',
                'notification_type'
            ))

            def send_closed_notifications():
                for author_id, notification_type in remaining_notifications:

                    if notification_type == 'proposal_update':

                        if final_status == 'approved':
                            message = (
                                f"Your chapter proposal for "
                                f"'{story.title}' was approved "
                                f"and added to the story!"
                            )
                        else:
                            message = (
                                f"Your chapter proposal for "
                                f"'{story.title}' was rejected."
                            )

                    else:

                        if final_status == 'approved':
                            message = (
                                f"A chapter proposal for "
                                f"'{story.title}' has been approved."
                            )
                        else:
                            message = (
                                f"A chapter proposal for "
                                f"'{story.title}' has been rejected."
                            )

                    push_notification(author_id, "request_closed", message)

            # Only notify once the new chapter is really saved in the database.
            transaction.on_commit(send_closed_notifications)

            
            if final_status == 'approved':
                return Response(
                    {
                        "detail": (
                            "Proposal approved and successfully "
                            "integrated into the story."
                        )
                    },
                    status=status.HTTP_200_OK
                )

            return Response(
                {"detail": "Chapter proposal rejected."},
                status=status.HTTP_200_OK
            )

       
        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )



class VoteFinishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, story_pk):
        story = get_object_or_404(Story, pk=story_pk)

        author_ids = Chapter.objects.filter(story=story, author__isnull=False).values_list('author', flat=True).distinct()
        if request.user.id not in author_ids:
            return Response({"detail": "Only story authors can vote to finish."}, status=status.HTTP_403_FORBIDDEN)
        if story.is_completed:
            return Response({"detail": "This story is already completed."}, status=status.HTTP_400_BAD_REQUEST)

        vote_instance = VoteFinish.objects.filter(story=story, author=request.user).first()
        serializer = VoteFinishSerializer(instance=vote_instance, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(story=story, author=request.user)

            # Only votes from current authors count; stale or stranger votes are ignored.
            total_co_authors = len(author_ids)
            finish_votes = VoteFinish.objects.filter(story=story, choice=True, author__in=author_ids).count()

            if finish_votes > total_co_authors / 2:
                story.is_completed = True
                story.save()
                return Response({"detail": "Story marked as completed!"}, status=status.HTTP_200_OK)
                
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).select_related(
            'requested_chapter__story',
            'requested_chapter__author'
        ).order_by('-created_at')

        serializer = NotificationListSerializer(
            user_notifications,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, notification_pk):
        notification = get_object_or_404(
            Notification,
            pk=notification_pk,
            user=request.user,
            is_read=False
        )

        serializer = NotificationDetailSerializer(notification)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, notification_pk):
        notification = get_object_or_404(
            Notification,
            pk=notification_pk,
            user=request.user,
            is_read=False
        )

        
        if notification.requested_chapter.status == 'pending':
            return Response(
                {
                    "detail": (
                        "You cannot acknowledge a proposal "
                        "while voting is still open."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        notification.is_read = True
        notification.save(update_fields=['is_read'])

        return Response(
            {"detail": "Notification acknowledged."},
            status=status.HTTP_200_OK
        )

    
class ChapterFetchView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, story_pk, chapter_number):
        story = get_object_or_404(Story, pk=story_pk)
        chapter = get_object_or_404(Chapter, story=story, chapter_number=chapter_number)
        serializer = ChapterReadSerializer(chapter)
        return Response(serializer.data, status=status.HTTP_200_OK)
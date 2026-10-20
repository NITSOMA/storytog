from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.db.models.functions import Substr


class StoryQuerySet(models.QuerySet):
    def with_list_data(self):
        """Everything StoryListSerializer shows, computed in the same SQL query."""
        first_chapter = Chapter.objects.filter(story=OuterRef('pk'), chapter_number=1)
        return self.annotate(
            chapters_count=Count('chapters', distinct=True),
            co_authors_count=Count('chapters__author', distinct=True),
            co_authors=ArrayAgg(
                'chapters__author__username',
                distinct=True,
                filter=Q(chapters__author__isnull=False),
                default=[],
            ),
            # 201 characters is enough to know whether the snippet needs "..."
            first_chapter_start=Substr(Subquery(first_chapter.values('content')[:1]), 1, 201),
        )


class Story(models.Model):
    title = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_completed = models.BooleanField(default=False)

    objects = StoryQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "Stories"

    def __str__(self):
        return self.title


class Chapter(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='chapters')
    # Chapters belong to the shared story: if the author deletes their account,
    # the chapter stays and becomes anonymous (author = NULL).
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    chapter_number = models.PositiveIntegerField()
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('story', 'chapter_number')
        ordering = ['chapter_number']

    def __str__(self):
        return f"{self.story.title} - Ch {self.chapter_number}"

    def save(self, *args, **kwargs):
        if not self.pk:
            max_number = Chapter.objects.filter(story=self.story).aggregate(Max('chapter_number'))['chapter_number__max']
            self.chapter_number = (max_number + 1) if max_number is not None else 1 
        super().save(*args, **kwargs)
    
    
class RequestChapter(models.Model):
    STATUS_CHOICES = [
        ('pending', 'PENDING'), 
        ('approved', 'APPROVED'), 
        ('rejected', 'REJECTED')
    ]
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='requests')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    chapter_number = models.PositiveIntegerField()
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Request by {self.author.username} for Ch {self.chapter_number} ({self.status})"

    def save(self, *args, **kwargs):
        if self.story.is_completed:
            raise ValueError("This story is marked as completed. You cannot add new chapters.")
            
        if not self.pk:
            max_approved = Chapter.objects.filter(story=self.story).aggregate(Max('chapter_number'))['chapter_number__max']
            self.chapter_number = (max_approved + 1) if max_approved is not None else 1
        super().save(*args, **kwargs)


class VoteChapter(models.Model):
    requested_chapter = models.ForeignKey(RequestChapter, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    choice = models.BooleanField()  

    class Meta:
        unique_together = ('requested_chapter', 'user')

    def __str__(self):
        vote_type = "Approve" if self.choice else "Reject"
        return f"{self.user.username} voted to {vote_type} request {self.requested_chapter.id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        
    
    
class VoteFinish(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='finish_votes')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    choice = models.BooleanField()  

    class Meta:
        unique_together = ('story', 'author')

    def __str__(self):
        vote_type = "Finish" if self.choice else "Keep Open"
        return f"{self.author.username} voted to {vote_type} {self.story.title}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('vote_request', 'Vote Request'),
        ('proposal_update', 'Proposal Update'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    requested_chapter = models.ForeignKey(
        RequestChapter,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='vote_request'
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.notification_type} for "
            f"{self.user.username} - Read: {self.is_read}"
        )
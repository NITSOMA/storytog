from django.db import models
from django.utils import timezone
from django.conf import settings
from django.db.models import Max

class Story(models.Model):
    title = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_completed = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Stories"

    def __str__(self):
        return self.title


class Chapter(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='chapters')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        story_obj = self.story
        
        if not story_obj.is_completed:
            total_co_authors = Chapter.objects.filter(story=story_obj).values('author').distinct().count()
            finish_requests = story_obj.finish_votes.filter(choice=True).count()
            
            if finish_requests > (total_co_authors / 2):
                story_obj.is_completed = True
                story_obj.save()


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    requested_chapter = models.ForeignKey(RequestChapter, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username} - Read: {self.is_read}"
from django.db import models
from django.utils import timezone
from django.conf import settings
from storyapp.models import Story

class Comments(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    story_id = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="comments")
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now) 
    
class Vote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    story_id = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='votes')
    vote_number = models.SmallIntegerField(default=0)  
    
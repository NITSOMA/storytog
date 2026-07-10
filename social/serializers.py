from rest_framework import serializers
from django.db.models import Sum
from .models import Vote, Comments
from storyapp.models import Story

from rest_framework import serializers
from .models import Vote

class VoteSerializer(serializers.ModelSerializer):
    story_title = serializers.CharField(source='story_id.title', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Vote
        fields = ['id', 'user', 'vote_number', 'story_id', 'story_title', 'user_username', 'created_at']
        read_only_fields = ['user']

    def validate(self, attrs):
       
        request = self.context.get('request')
        user = request.user
        story_id = attrs.get('story_id')

       
        if Vote.objects.filter(user=user, story_id=story_id).exists():
            raise serializers.ValidationError("You have already voted on this story. Votes cannot be changed.")
            
        return attrs

class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    
    class Meta:
        model = Comments
        fields = ['id', 'author', 'story_id', 'content', 'created_at', 'author_username']
        read_only_fields = ['author']
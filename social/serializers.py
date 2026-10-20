from rest_framework import serializers
from .models import Comments

class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    
    class Meta:
        model = Comments
        fields = ['id', 'author', 'story_id', 'content', 'created_at', 'author_username']
        read_only_fields = ['author']
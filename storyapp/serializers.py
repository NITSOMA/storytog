from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Story, Chapter, RequestChapter, VoteChapter, VoteFinish, Notification

User = get_user_model()

class ChapterReadSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = Chapter
        fields = ['id', 'chapter_number', 'content', 'author_username', 'created_at', 'author']
        read_only_fields = ['author']

class StoryCreateSerializer(serializers.ModelSerializer):
    first_chapter_content = serializers.CharField(write_only=True)

    class Meta:
        model = Story
        fields = ['id', 'title', 'first_chapter_content', 'created_at']

    def create(self, validated_data):
        chapter_content = validated_data.pop('first_chapter_content')
        user = self.context['request'].user
        story = Story.objects.create(**validated_data)
        Chapter.objects.create(
            story=story,
            author=user,
            content=chapter_content
        )
        return story

class StoryListSerializer(serializers.ModelSerializer):
    chapters_count = serializers.IntegerField(read_only=True)
    co_authors_count = serializers.IntegerField(read_only=True)
    first_chapter_snippet = serializers.SerializerMethodField()
    co_authors = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            'id', 'title', 'created_at', 'is_completed', 
            'chapters_count', 'co_authors_count', 
            'first_chapter_snippet', 'co_authors'
        ]

    def get_first_chapter_snippet(self, obj):
        first_chap = obj.chapters.filter(chapter_number=1).first()
        if first_chap:
            return first_chap.content[:200] + "..." if len(first_chap.content) > 200 else first_chap.content
        return ""

    def get_co_authors(self, obj):
        return list(obj.chapters.values_list('author__username', flat=True).distinct())

class StoryReadSerializer(serializers.ModelSerializer):
    first_chapter = serializers.SerializerMethodField()
    co_authors = serializers.SerializerMethodField()
    total_chapters = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = ['id', 'title', 'created_at', 'is_completed', 'first_chapter', 'co_authors', 'total_chapters']

    def get_first_chapter(self, obj):
        first_chap = obj.chapters.filter(chapter_number=1).first()
        if first_chap:
            return ChapterReadSerializer(first_chap).data
        return None

    def get_co_authors(self, obj):
        return list(obj.chapters.values_list('author__username', flat=True).distinct())

    def get_total_chapters(self, obj):
        return obj.chapters.count()

class VoteChapterSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = VoteChapter
        fields = ['id', 'user_username', 'choice']

class VoteFinishSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = VoteFinish
        fields = ['id', 'story', 'author_username', 'choice']
        read_only_fields = ['author']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)

class RequestChapterWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestChapter
        fields = ['id', 'content']

    def validate(self, data):
        user = self.context['request'].user
        story = self.context.get('story')
        if story:
            next_chapter_number = story.chapters.count() + 1
            existing_request = RequestChapter.objects.filter(
                story=story,
                author=user,
                chapter_number=next_chapter_number
            ).exists()
            if existing_request:
                raise serializers.ValidationError("You have already submitted a proposal for this chapter.")
        return data

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        try:
            return super().create(validated_data)
        except ValueError as e:
            raise serializers.ValidationError({"detail": str(e)})

class RequestChapterReadSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    votes = VoteChapterSerializer(many=True, read_only=True)
    total_approvals = serializers.SerializerMethodField()
    total_rejections = serializers.SerializerMethodField()

    class Meta:
        model = RequestChapter
        fields = [
            'id', 'story', 'author_username', 'chapter_number', 
            'content', 'status', 'created_at', 'votes', 
            'total_approvals', 'total_rejections'
        ]

    def get_total_approvals(self, obj):
        return obj.votes.filter(choice=True).count()

    def get_total_rejections(self, obj):
        return obj.votes.filter(choice=False).count()

class NotificationListSerializer(serializers.ModelSerializer):
    story_title = serializers.CharField(source='requested_chapter.story.title', read_only=True)
    author_username = serializers.CharField(source='requested_chapter.author.username', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'is_read', 'created_at', 'story_title', 'author_username']
        read_only_fields = ['id', 'created_at']

class NotificationDetailSerializer(serializers.ModelSerializer):
    requested_chapter = RequestChapterReadSerializer(read_only=True)
    story_title = serializers.CharField(source='requested_chapter.story.title', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'is_read', 'created_at', 'story_title', 'requested_chapter']
        read_only_fields = ['id', 'created_at']

class UserProfileSerializer(serializers.ModelSerializer):
    notifications = NotificationListSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'notifications']
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from storyapp.serializers import NotificationSerializer, StoryListSerializer
from storyapp.models import Story

User = get_user_model()

class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    profile_image = serializers.ImageField(required=False, allow_null=True)
    cover_image = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = ["username", "email", "password", "about", "profile_image", "cover_image"]
        
    def create(self, validated_data):
        
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
   
class LoginSerializer(serializers.Serializer):
    login_id = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, data):
        login_id = data.get("login_id")
        password = data.get("password")
        
        username = login_id
     
        if "@" in login_id:
            user_obj = User.objects.filter(email=login_id).first()
            if user_obj:
                username = user_obj.username
            else:
                raise serializers.ValidationError("Invalid login credentials")
                
        user = authenticate(username=username, password=password)
        
        if not user:
            raise serializers.ValidationError("Invalid login credentials")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")
            
        data["user"] = user
        return data
    

class UserProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.ImageField(required=False, allow_null=True)
    cover_image = serializers.ImageField(required=False, allow_null=True)
    notifications = NotificationSerializer(many=True, read_only=True)
    contributed_stories = serializers.SerializerMethodField()
    

    class Meta:
        model = User
        fields = ["id", "username", "email", "about", "profile_image", "cover_image", 'notifications', 'contributed_stories']
        read_only_fields = ("id", "email")
        
        
    def get_contributed_stories(self, obj):

        stories = Story.objects.filter(chapters__author=obj).distinct()
        
        
        return StoryListSerializer(stories, many=True).data
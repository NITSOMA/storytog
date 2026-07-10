from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import VoteSerializer, CommentSerializer
from django.shortcuts import get_object_or_404
from .models import Comments

class VoteCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = VoteSerializer(data=request.data,  context={'request': request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
    
class CommentCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CommentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        comment = get_object_or_404(Comments, pk=pk)
        
   
        if comment.author != request.user:
            return Response({"detail": "You do not have permission to edit this comment."}, status=status.HTTP_403_FORBIDDEN)
            
     
        serializer = CommentSerializer(comment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
    
        comment = get_object_or_404(Comments, pk=pk)
    
        if comment.author != request.user:
            return Response({"detail": "You do not have permission to delete this comment."}, status=status.HTTP_403_FORBIDDEN)
            
        comment.delete()
        return Response({"detail": "Comment deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
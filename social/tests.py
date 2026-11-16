from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from storyapp.models import Story
from .models import Comments

User = get_user_model()


class CommentPermissionTests(APITestCase):

    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.bill = User.objects.create_user(username='bill', email='bill@example.com', password='pass')
        self.story = Story.objects.create(title='Some story')
        self.comment = Comments.objects.create(author=self.ana, story_id=self.story, content='Some comment')
        self.url = f'/social/comment/{self.comment.pk}/'

    # --- editing ---

    def test_author_can_edit_own_comment(self):
        self.client.force_authenticate(self.ana)

        response = self.client.put(self.url, {'content': 'Changed comment'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, 'Changed comment')

    def test_other_user_cannot_edit_comment(self):
        self.client.force_authenticate(self.bill)

        response = self.client.put(self.url, {'content': 'Hacked!'}, format='json')

        self.assertEqual(response.status_code, 403)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, 'Some comment')   # unchanged

    # --- deleting ---

    def test_author_can_delete_own_comment(self):
        self.client.force_authenticate(self.ana)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Comments.objects.exists())

    def test_other_user_cannot_delete_comment(self):
        self.client.force_authenticate(self.bill)

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Comments.objects.exists())               # still there
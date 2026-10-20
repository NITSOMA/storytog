from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from social.models import Comments
from storyapp.models import Story, Chapter

User = get_user_model()


class DeleteAccountTests(APITestCase):
    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.ben = User.objects.create_user(username='ben', email='ben@example.com', password='pass')

        # Shared story: ben stays, so it remains open.
        self.shared = Story.objects.create(title='Shared')
        Chapter.objects.create(story=self.shared, author=self.ana, content='Ana 1')
        Chapter.objects.create(story=self.shared, author=self.ben, content='Ben 2')

        # Ana's solo story: nobody is left after she goes.
        self.solo = Story.objects.create(title='Solo')
        Chapter.objects.create(story=self.solo, author=self.ana, content='Ana only')

        Comments.objects.create(author=self.ana, story_id=self.shared, content='Nice!')

        self.client.force_authenticate(self.ana)
        self.response = self.client.delete('/user/profile/')

    def test_account_is_deleted(self):
        self.assertEqual(self.response.status_code, 204)
        self.assertFalse(User.objects.filter(pk=self.ana.pk).exists())

    def test_chapters_stay_as_anonymous(self):
        self.assertEqual(Chapter.objects.filter(author__isnull=True).count(), 2)
        self.assertEqual(self.shared.chapters.count(), 2)

    def test_story_with_remaining_author_stays_open(self):
        self.shared.refresh_from_db()
        self.assertFalse(self.shared.is_completed)

    def test_story_without_remaining_authors_is_completed(self):
        self.solo.refresh_from_db()
        self.assertTrue(self.solo.is_completed)

    def test_comments_are_deleted(self):
        self.assertFalse(Comments.objects.exists())


class LogoutTests(APITestCase):
    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        response = self.client.post('/user/login/', {'login_id': 'ana', 'password': 'pass'}, format='json')
        self.assertEqual(response.status_code, 200)
        # The test client keeps the refresh_token cookie from the login response.

    def test_logout_works_without_valid_access_token(self):
        # Access tokens live 5 minutes; logout must still work with only the refresh cookie.
        response = self.client.post('/user/logout/')

        self.assertEqual(response.status_code, 205)
        self.assertEqual(response.cookies['refresh_token'].value, '')

    def test_refresh_token_is_unusable_after_logout(self):
        old_refresh = self.client.cookies['refresh_token'].value

        self.client.post('/user/logout/')
        self.client.cookies['refresh_token'] = old_refresh
        response = self.client.post('/user/refresh/')

        self.assertEqual(response.status_code, 401)

    def test_logout_without_cookie_still_succeeds(self):
        del self.client.cookies['refresh_token']

        self.assertEqual(self.client.post('/user/logout/').status_code, 205)

    def test_logout_ignores_expired_access_token_header(self):
        # The Angular interceptor still sends the old (expired) access token.
        self.client.credentials(HTTP_AUTHORIZATION='Bearer expired.or.invalid')

        response = self.client.post('/user/logout/')

        self.assertEqual(response.status_code, 205)

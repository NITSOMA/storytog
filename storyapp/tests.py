import threading
from unittest import mock

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from writespace.asgi import application
from .models import Story, Chapter, RequestChapter, VoteFinish, Notification

User = get_user_model()


class VoteFinishTests(APITestCase):
    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.ben = User.objects.create_user(username='ben', email='ben@example.com', password='pass')
        self.stranger = User.objects.create_user(username='bob', email='bob@example.com', password='pass')

        self.story = Story.objects.create(title='Test story')
        Chapter.objects.create(story=self.story, author=self.ana, content='Chapter 1')
        Chapter.objects.create(story=self.story, author=self.ben, content='Chapter 2')
        self.url = f'/story/finish/{self.story.pk}/'

    def vote(self, user, choice=True):
        self.client.force_authenticate(user)
        return self.client.post(self.url, {'story': self.story.pk, 'choice': choice}, format='json')

    def test_non_author_cannot_vote(self):
        response = self.vote(self.stranger)

        self.assertEqual(response.status_code, 403)
        self.story.refresh_from_db()
        self.assertFalse(self.story.is_completed)
        self.assertFalse(VoteFinish.objects.filter(author=self.stranger).exists())

    def test_half_of_authors_does_not_complete_story(self):
        self.vote(self.ana)

        self.story.refresh_from_db()
        self.assertFalse(self.story.is_completed)

    def test_author_majority_completes_story(self):
        self.vote(self.ana)
        self.vote(self.ben)

        self.story.refresh_from_db()
        self.assertTrue(self.story.is_completed)

    def test_existing_stranger_vote_is_not_counted(self):
        # A vote saved before the fix, from someone who never wrote a chapter.
        VoteFinish.objects.create(story=self.story, author=self.stranger, choice=True)

        self.vote(self.ana)

        self.story.refresh_from_db()
        self.assertFalse(self.story.is_completed)

    def test_cannot_vote_on_completed_story(self):
        self.story.is_completed = True
        self.story.save()

        response = self.vote(self.ana)

        self.assertEqual(response.status_code, 400)


# In-memory channel layer so tests don't need Redis running.
@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
class NotificationConsumerTests(TransactionTestCase):
    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.bob = User.objects.create_user(username='bob', email='bob@example.com', password='pass')

    async def can_connect(self, path):
        communicator = WebsocketCommunicator(application, path)
        connected, _ = await communicator.connect()
        if connected:
            await communicator.disconnect()
        return connected

    async def test_rejects_missing_token(self):
        self.assertFalse(await self.can_connect(f'/ws/notifications/{self.ana.id}/'))

    async def test_rejects_invalid_token(self):
        self.assertFalse(await self.can_connect(f'/ws/notifications/{self.ana.id}/?token=not-a-real-token'))

    async def test_rejects_other_users_id(self):
        token = AccessToken.for_user(self.bob)
        self.assertFalse(await self.can_connect(f'/ws/notifications/{self.ana.id}/?token={token}'))

    async def test_accepts_own_id_with_valid_token(self):
        token = AccessToken.for_user(self.ana)
        self.assertTrue(await self.can_connect(f'/ws/notifications/{self.ana.id}/?token={token}'))


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
class VoteChapterTests(TransactionTestCase):
    def setUp(self):
        # Three authors, so a proposal needs 2 approvals (more than half).
        self.authors = [
            User.objects.create_user(username=name, email=f'{name}@example.com', password='pass')
            for name in ('ana', 'ben', 'cat')
        ]
        self.dan = User.objects.create_user(username='dan', email='dan@example.com', password='pass')

        self.story = Story.objects.create(title='Test story')
        for author in self.authors:
            Chapter.objects.create(story=self.story, author=author, content=f'By {author.username}')

        self.proposal = RequestChapter.objects.create(story=self.story, author=self.dan, content='Proposed')
        self.url = f'/story/requests/vote/{self.proposal.pk}/'

    def vote(self, user, choice=True):
        client = APIClient(raise_request_exception=False)
        client.force_authenticate(user)
        return client.post(self.url, {'choice': choice}, format='json')

    def test_majority_approval_adds_one_chapter_and_closes_voting(self):
        ana, ben, cat = self.authors

        self.assertEqual(self.vote(ana).status_code, 200)
        self.assertEqual(self.vote(ben).status_code, 200)
        self.assertEqual(self.vote(cat).status_code, 400)  # voting is closed

        self.proposal.refresh_from_db()
        self.assertEqual(self.proposal.status, 'approved')
        self.assertEqual(Chapter.objects.filter(story=self.story, content='Proposed').count(), 1)

    def test_simultaneous_votes_add_only_one_chapter(self):
        barrier = threading.Barrier(len(self.authors))
        status_codes = []

        def vote_at_same_time(user):
            barrier.wait()  # all threads send their vote together
            try:
                status_codes.append(self.vote(user).status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=vote_at_same_time, args=(author,)) for author in self.authors]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(status_codes), [200, 200, 400])
        self.assertEqual(Chapter.objects.filter(story=self.story, content='Proposed').count(), 1)


class ChapterDeleteTests(APITestCase):
    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.ben = User.objects.create_user(username='ben', email='ben@example.com', password='pass')
        self.story = Story.objects.create(title='Test story')
        self.first = Chapter.objects.create(story=self.story, author=self.ana, content='Chapter 1')

    def delete(self, user, chapter):
        self.client.force_authenticate(user)
        return self.client.delete(f'/story/chapters/{chapter.pk}/')

    def test_deleting_only_chapter_removes_story(self):
        response = self.delete(self.ana, self.first)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Story.objects.filter(pk=self.story.pk).exists())

    def test_cannot_delete_own_chapter_once_story_has_more(self):
        second = Chapter.objects.create(story=self.story, author=self.ben, content='Chapter 2')

        self.assertEqual(self.delete(self.ben, second).status_code, 400)
        self.assertEqual(self.delete(self.ana, self.first).status_code, 400)
        self.assertEqual(self.story.chapters.count(), 2)

    def test_cannot_delete_someone_elses_chapter(self):
        self.assertEqual(self.delete(self.ben, self.first).status_code, 404)
        self.assertTrue(Chapter.objects.filter(pk=self.first.pk).exists())


class AnonymousAuthorTests(APITestCase):
    """Chapters whose author deleted their account (author=None)."""

    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.dan = User.objects.create_user(username='dan', email='dan@example.com', password='pass')
        self.story = Story.objects.create(title='Test story')
        Chapter.objects.create(story=self.story, author=None, content='Chapter 1')
        Chapter.objects.create(story=self.story, author=self.ana, content='Chapter 2')

    def test_anonymous_chapters_do_not_count_as_authors(self):
        # Only ana is a real author, so her single approval is a majority.
        proposal = RequestChapter.objects.create(story=self.story, author=self.dan, content='Proposed')
        self.client.force_authenticate(self.ana)

        response = self.client.post(f'/story/requests/vote/{proposal.pk}/', {'choice': True}, format='json')

        self.assertEqual(response.status_code, 200)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'approved')

    def test_proposing_does_not_notify_anonymous_author(self):
        self.client.force_authenticate(self.dan)

        response = self.client.post(f'/story/requests/{self.story.pk}/', {'content': 'Proposed'}, format='json')

        self.assertEqual(response.status_code, 201)

    def test_story_shows_anonymous_byline_and_hides_it_from_co_authors(self):
        response = self.client.get(f'/story/{self.story.pk}/')

        self.assertEqual(response.data['first_chapter']['author_username'], 'Anonymous')
        self.assertIsNone(response.data['first_chapter']['author'])
        self.assertEqual(response.data['co_authors'], ['ana'])


class QueryCountTests(APITestCase):
    """List pages should use the same number of queries for 2 items or 10 (no N+1)."""

    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.ben = User.objects.create_user(username='ben', email='ben@example.com', password='pass')
        self.dan = User.objects.create_user(username='dan', email='dan@example.com', password='pass')
        self.story_count = 0

    def make_stories(self, n):
        for _ in range(n):
            self.story_count += 1
            story = Story.objects.create(title=f'Story {self.story_count}')
            Chapter.objects.create(story=story, author=self.ana, content='x' * 300)
            Chapter.objects.create(story=story, author=self.ben, content='Chapter 2')
            proposal = RequestChapter.objects.create(story=story, author=self.dan, content='Proposed')
            Notification.objects.create(user=self.ana, requested_chapter=proposal)

    def count_queries(self, url):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return len(queries)

    def assert_constant_queries(self, url):
        self.make_stories(2)
        few = self.count_queries(url)
        self.make_stories(8)
        many = self.count_queries(url)
        self.assertEqual(few, many, f'{url}: {few} queries for 2 items, {many} for 10')

    def test_story_list(self):
        self.assert_constant_queries('/story/')

    def test_author_page(self):
        self.client.force_authenticate(self.dan)
        self.assert_constant_queries(f'/user/author/{self.ana.pk}/')

    def test_profile(self):
        self.client.force_authenticate(self.ana)
        self.assert_constant_queries('/user/profile/')

    def test_notification_list(self):
        self.client.force_authenticate(self.ana)
        self.assert_constant_queries('/story/notifications/')

    def test_story_list_content(self):
        self.make_stories(1)

        story = self.client.get('/story/').data['results'][0]

        self.assertEqual(story['first_chapter_snippet'], 'x' * 200 + '...')
        self.assertEqual(sorted(story['co_authors']), ['ana', 'ben'])
        self.assertEqual(story['chapters_count'], 2)
        self.assertEqual(story['co_authors_count'], 2)


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
class ProposalNotificationTests(TransactionTestCase):
    # TransactionTestCase so transaction.on_commit callbacks really run.

    def setUp(self):
        self.ana = User.objects.create_user(username='ana', email='ana@example.com', password='pass')
        self.dan = User.objects.create_user(username='dan', email='dan@example.com', password='pass')
        self.story = Story.objects.create(title='Test story')
        Chapter.objects.create(story=self.story, author=self.ana, content='Chapter 1')

        self.client = APIClient()
        self.client.force_authenticate(self.dan)

    def propose(self):
        return self.client.post(f'/story/requests/{self.story.pk}/', {'content': 'Proposed'}, format='json')

    def test_co_author_receives_live_notification(self):
        layer = get_channel_layer()
        channel = async_to_sync(layer.new_channel)()
        async_to_sync(layer.group_add)(f'user_notifications_{self.ana.pk}', channel)

        self.assertEqual(self.propose().status_code, 201)

        message = async_to_sync(layer.receive)(channel)
        self.assertEqual(message['event_type'], 'new_request')
        self.assertIn('Test story', message['message'])

    def test_proposal_is_saved_even_if_redis_is_down(self):
        with mock.patch('storyapp.notifications.get_channel_layer', side_effect=ConnectionError('Redis down')), \
                self.assertLogs('storyapp.notifications', level='ERROR'):
            response = self.propose()

        self.assertEqual(response.status_code, 201)
        self.assertTrue(RequestChapter.objects.filter(story=self.story, author=self.dan).exists())
        self.assertTrue(Notification.objects.filter(user=self.ana, notification_type='vote_request').exists())

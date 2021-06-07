from unittest import mock

from django.contrib.auth.models import Permission
from django.http import HttpRequest
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from wagtail.core.models import Page
from wagtail.core.signals import page_published
from wagtail.tests.testapp.models import SimplePage
from wagtail.tests.utils import WagtailTestUtils


class TestBulkPublish(TestCase, WagtailTestUtils):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)

        # Add child pages
        self.child_pages = [
            SimplePage(title=f"Hello world!-{i}", slug=f"hello-world-{i}", content=f"hello-{i}", live=False)
            for i in range(1, 5)
        ]
        self.pages_to_be_published = self.child_pages[:3]
        self.pages_not_to_be_published = self.child_pages[3:]

        for child_page in self.child_pages:
            self.root_page.add_child(instance=child_page)

        self.url = reverse('wagtailadmin_bulk_publish', args=(self.root_page.id, )) + '?' + f'id={self.pages_to_be_published[2].id}'
        self.redirect_url = reverse('wagtailadmin_explore', args=(self.root_page.id, ))

        self.user = self.login()

    def test_publish_view(self):
        """
        This tests that the publish view responds with an publish confirm page
        """
        # Request confirm publish page
        response = self.client.get(self.self.url)

        # # Check that the user received an publish confirm page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailadmin/pages/bulk_actions/confirm_bulk_publish.html')

    def test_publish_view_invalid_page_id(self):
        """
        This tests that the publish view returns an error if the page id is invalid
        """
        # Request confirm publish page but with illegal page id
        response = self.client.get(reverse('wagtailadmin_bulk_publish', args=(12345, )))

        # Check that the user received a 404 response
        self.assertEqual(response.status_code, 404)

    def test_publish_view_bad_permissions(self):
        """
        This tests that the publish view doesn't allow users without publish permissions
        """
        # Remove privileges from user
        self.user.is_superuser = False
        self.user.user_permissions.add(
            Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')
        )
        self.user.save()

        # Request confirm publish page
        response = self.client.get(self.self.url)

        # Check that the user received a 302 redirected response
        self.assertEqual(response.status_code, 302)

    def test_publish_view_post(self):
        """
        This posts to the publish view and checks that the page was published
        """
        # Connect a mock signal handler to page_published signal
        mock_handler = mock.MagicMock()
        page_published.connect(mock_handler)

        # Post to the publish page
        response = self.client.post(self.self.url)

        # Should be redirected to explorer page
        self.assertRedirects(response, self.redirect_url)

        # Check that the child pages were published
        self.assertTrue(SimplePage.objects.get(id=self.pages_to_be_published[2].id).live)

        # Check that the child pages not to be published remain
        for child_page in self.pages_not_to_be_published:
            self.assertFalse(SimplePage.objects.get(id=child_page.id).live)

        # Check that the page_published signal was fired
        self.assertEqual(mock_handler.call_count, 1)

        mock_call = mock_handler.mock_calls[0][2]
        child_page = self.pages_to_be_published[2]
        self.assertEqual(mock_call['sender'], child_page.specific_class)
        self.assertEqual(mock_call['instance'], child_page)
        self.assertIsInstance(mock_call['instance'], child_page.specific_class)

    def test_after_publish_page(self):
        def hook_func(request, page):
            self.assertIsInstance(request, HttpRequest)
            self.assertEqual(page.id, self.pages_to_be_published[2].id)

        with self.register_hook('after_publish_page', hook_func):
            response = self.client.post(self.self.url)

        self.assertEqual(response.status_code, 302)

        child_page = self.pages_to_be_published[2]
        child_page.refresh_from_db()
        self.assertEqual(child_page.status_string, _("live"))

    def test_before_publish_page(self):
        def hook_func(request, page):
            self.assertIsInstance(request, HttpRequest)
            self.assertEqual(page.id, self.pages_to_be_published[2].id)
            self.assertEqual(page.status_string, _("draft"))

        with self.register_hook('before_publish_page', hook_func):
            response = self.client.post(self.self.url)

        self.assertEqual(response.status_code, 302)

    def test_publish_descendants_view(self):
        """
        This tests that the publish view responds with an publish confirm page that does not contain the form field 'include_descendants'
        """
        # Get publish page for page with no descendants
        response = self.client.get(self.self.url)

        # Check that the user received an publish confirm page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailadmin/pages/bulk_actions/confirm_bulk_publish.html')
        # Check the form does not contain the checkbox field include_descendants
        self.assertNotContains(response, '<input id="id_include_descendants" name="include_descendants" type="checkbox">')


class TestBulkPublishIncludingDescendants(TestCase, WagtailTestUtils):
    def setUp(self):
        self.root_page = Page.objects.get(id=2)

        # Add child pages
        self.child_pages = [
            SimplePage(title=f"Hello world!-{i}", slug=f"hello-world-{i}", content=f"hello-{i}", live=False)
            for i in range(1, 5)
        ]
        self.pages_to_be_published = self.child_pages[:3]
        self.pages_not_to_be_published = self.child_pages[3:]

        for child_page in self.child_pages:
            self.root_page.add_child(instance=child_page)

        # map of the form { page: [child_pages] } to be added
        self.grandchildren_pages = {
            self.pages_to_be_published[0]: [SimplePage(title="Hello world!-a", slug="hello-world-a", content="hello-a", live=False)],
            self.pages_to_be_published[1]: [
                SimplePage(title="Hello world!-b", slug="hello-world-b", content="hello-b", live=False),
                SimplePage(title="Hello world!-c", slug="hello-world-c", content="hello-c", live=False)
            ]
        }
        for child_page, grandchild_pages in self.grandchildren_pages.items():
            for grandchild_page in grandchild_pages:
                child_page.add_child(instance=grandchild_page)

        self.url = reverse('wagtailadmin_bulk_publish', args=(self.root_page.id, )) + '?'
        for child_page in self.pages_to_be_published:
            self.url += f'&id={child_page.id}'
        self.redirect_url = reverse('wagtailadmin_explore', args=(self.root_page.id, ))

        self.user = self.login()

    def test_publish_descendants_view(self):
        """
        This tests that the publish view responds with an publish confirm page that contains the form field 'include_descendants'
        """
        # Get publish page
        response = self.client.get(self.url)

        # Check that the user received an publish confirm page
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'wagtailadmin/pages/bulk_actions/confirm_bulk_publish.html')
        # Check the form contains the checkbox field include_descendants
        self.assertContains(response, '<input id="id_include_descendants" name="include_descendants" type="checkbox">')

    def test_publish_include_children_view_post(self):
        """
        This posts to the publish view and checks that the page and its descendants were published
        """
        # Post to the publish page
        response = self.client.post(self.url, {'include_descendants': 'on'})

        # Should be redirected to explorer page
        self.assertRedirects(response, self.redirect_url)

        # Check that the child pages were published
        for child_page in self.pages_to_be_published:
            self.assertTrue(SimplePage.objects.get(id=child_page.id).live)

        # Check that the child pages not to be published remain
        for child_page in self.pages_not_to_be_published:
            self.assertFalse(SimplePage.objects.get(id=child_page.id).live)

        for grandchild_pages in self.grandchildren_pages.values():
            for grandchild_page in grandchild_pages:
                self.assertTrue(SimplePage.objects.get(id=grandchild_page.id).live)

    def test_publish_not_include_children_view_post(self):
        """
        This posts to the publish view and checks that the page was published but its descendants were not
        """
        # Post to the publish page
        response = self.client.post(self.url, {})

        # Should be redirected to explorer page
        self.assertRedirects(response, reverse('wagtailadmin_explore', args=(self.root_page.id, )))

        # Check that the child pages were published
        for child_page in self.pages_to_be_published:
            self.assertTrue(SimplePage.objects.get(id=child_page.id).live)

        # Check that the descendant pages were not published
        for grandchild_pages in self.grandchildren_pages.values():
            for grandchild_page in grandchild_pages:
                self.assertFalse(SimplePage.objects.get(id=grandchild_page.id).live)
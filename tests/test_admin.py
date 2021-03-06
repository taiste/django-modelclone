import shutil

import django
from django.contrib.auth.models import User
from django.contrib.admin import site as default_admin_site
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.conf import settings
from django.forms.formsets import DEFAULT_MAX_NUM

from django_webtest import WebTest
from webtest import Upload
import mock
import pytest

from posts.models import Post, Comment, Tag, Multimedia
from modelclone import ClonableModelAdmin

from .asserts import *


class ClonableModelAdminTests(WebTest):

    def setUp(self):
        rm_rf(settings.MEDIA_ROOT)
        User.objects.all().delete()
        User.objects.create_superuser(
            username='admin',
            password='admin',
            email='admin@sampleproject.com'
        )
        self.tag1 = Tag.objects.create(name='django')
        self.tag2 = Tag.objects.create(name='sports')

        self.post = Post.objects.create(
            title = 'How to learn windsurf',
            content = 'Practice a lot!',
        )

        self.post_with_comments = Post.objects.create(
            title = 'How to learn Django',
            content = 'Read https://docs.djangoproject.com/'
        )
        Comment.objects.create(
            author = 'Bob',
            content = 'Thanks! It really helped',
            post = self.post_with_comments
        )
        Comment.objects.create(
            author = 'Alice',
            content = 'Oh, really?!',
            post = self.post_with_comments
        )

        self.post_with_tags = Post.objects.create(
            title = 'Django resable apps',
        )
        self.post_with_tags.tags.add(self.tag1)

        self.post_url = '/admin/posts/post/{0}/clone/'.format(
            self.post.id)
        self.post_with_comments_url = '/admin/posts/post/{0}/clone/'.format(
            self.post_with_comments.id)
        self.post_with_tags_url = '/admin/posts/post/{0}/clone/'.format(
            self.post_with_tags.id)

        self.multimedia = Multimedia.objects.create(
            title = 'Jason Polakow',
            image = File(open('tests/files/img.jpg')),
            document = File(open('tests/files/file.txt')),
        )
        self.multimedia_url = '/admin/posts/multimedia/{0}/clone/'.format(
            self.multimedia.id)


    def test_clone_view_is_wrapped_as_admin_view(self):
        model = mock.Mock()
        admin_site = mock.Mock()
        admin_site.admin_view.return_value = '<wrapped clone view>'

        model_admin = ClonableModelAdmin(model, admin_site)
        clone_view_urlpattern = model_admin.get_urls()[0]

        if django.VERSION >= (1, 8):
            assert '<wrapped clone view>' == clone_view_urlpattern._callback_str
        else:
            assert '<wrapped clone view>' == clone_view_urlpattern.callback


    def test_clone_view_url_name(self):
        post_id = self.post.id
        expected_url = '/admin/posts/post/{0}/clone/'.format(post_id)

        assert reverse('admin:posts_post_clone', args=(post_id,)) == expected_url


    def test_clone_link_method_for_list_display_renders_object_clone_url(self):
        model_admin = ClonableModelAdmin(Post, default_admin_site)
        expected_link = '<a href="{0}">{1}</a>'.format(
            reverse('admin:posts_post_clone', args=(self.post.id,)),
            model_admin.clone_verbose_name)

        assert model_admin.clone_link(self.post) == expected_link


    def test_clone_link_methods_for_list_display_should_allow_tags_and_have_short_description(self):
        assert ClonableModelAdmin.clone_link.allow_tags is True
        assert ClonableModelAdmin.clone_link.short_description == \
               ClonableModelAdmin.clone_verbose_name


    def test_clone_should_display_clone_verbose_name_as_title(self):
        response = self.app.get(self.post_url, user='admin')

        # default value
        assert 'Duplicate' == ClonableModelAdmin.clone_verbose_name

        # customized value in sampleproject/posts/admin.py
        assert_page_title(response, 'Clone it! post | Django site admin')
        assert_content_title(response, 'Clone it! post')
        assert_breadcrums_title(response, 'Clone it! post')


    def test_clone_should_not_display_delete_button_on_submit_row(self):
        response = self.app.get(self.post_url, user='admin')

        refute_delete_button(response)


    def test_clone_should_raise_permission_denied(self):
        model_admin = ClonableModelAdmin(Post, default_admin_site)
        model_admin.has_add_permission = mock.Mock(return_value=False)

        request = object()
        object_id = object()

        with pytest.raises(PermissionDenied):
            model_admin.clone_view(request, object_id)

        model_admin.has_add_permission.assert_called_once_with(request)


    # clone object

    def test_clone_should_pre_fill_all_form_fields(self):
        response = self.app.get(self.post_url, user='admin')

        # post
        assert_input(response, name='title', value='How to learn windsurf (duplicate)')
        assert_input(response, name='content', value='Practice a lot!')

        # csrf
        assert_input(response, name='csrfmiddlewaretoken')


    def test_clone_should_create_new_object_on_POST(self):
        response = self.app.get(self.post_url, user='admin')
        response.form.submit()

        assert Post.objects.filter(title=self.post.title).exists()
        assert Post.objects.filter(title=self.post.title + ' (duplicate)').exists()


    def test_clone_should_return_404_if_object_does_not_exist(self):
        response = self.app.get('/admin/posts/post/999999999/clone/', user='admin',
                                expect_errors=True)
        assert 404 == response.status_code


    # clone object with inlines

    def test_clone_should_pre_fill_all_form_fields_including_inlines_on_GET(self):
        response = self.app.get(self.post_with_comments_url, user='admin')

        # management form data
        assert_management_form_inputs(response, total=4, initial=0, max_num=DEFAULT_MAX_NUM)

        # comment 1
        assert_input(response, name='comment_set-0-author', value='Bob')
        assert_input(response, name='comment_set-0-content', value='Thanks! It really helped')
        assert_input(response, name='comment_set-0-id', value='')
        assert_input(response, name='comment_set-0-post', value='')
        assert_input(response, name='comment_set-0-DELETE', value='')

        # comment 2
        assert_input(response, name='comment_set-1-author', value='Alice')
        assert_input(response, name='comment_set-1-content', value='Oh, really?!')
        assert_input(response, name='comment_set-1-id', value='')
        assert_input(response, name='comment_set-1-post', value='')
        assert_input(response, name='comment_set-1-DELETE', value='')

        # first extra
        assert_input(response, name='comment_set-2-author', value='')
        assert_input(response, name='comment_set-2-content', value='')
        assert_input(response, name='comment_set-2-id', value='')
        assert_input(response, name='comment_set-2-post', value='')
        refute_input(response, name='comment_set-2-DELETE')

        # second extra
        assert_input(response, name='comment_set-3-author', value='')
        assert_input(response, name='comment_set-3-content', value='')
        assert_input(response, name='comment_set-3-id', value='')
        assert_input(response, name='comment_set-3-post', value='')
        refute_input(response, name='comment_set-3-DELETE')

    def test_clone_should_honor_tweaked_inline_fields(self):
        # In the sample project, we have an inline tweak that filters out comments with an
        # author 'do-not-clone'. We test here that we honor that tweak.
        # This comment below is added as the 3rd comment of self.post_with_comments
        Comment.objects.create(
            author = 'do-not-clone',
            content = 'whatever',
            post = self.post_with_comments
        )
        response = self.app.get(self.post_with_comments_url, user='admin')
        assert_input(response, name='comment_set-2-author', value='')

    def test_clone_with_inlines_should_display_the_necessary_number_of_forms(self):
        extra = 2   # CommentInline.extra on sampleproject/posts

        for i in range(4):
            Comment.objects.create(
                author = 'Author ' + str(i),
                content = 'Content ' + str(i),
                post = self.post,
            )

        response = self.app.get(self.post_url, user='admin')

        for i in range(4):
            i = str(i)
            assert_input(response, name='comment_set-'+i+'-author', value='Author ' + i)
            assert_input(response, name='comment_set-'+i+'-content', value='Content ' + i)
            assert_input(response, name='comment_set-'+i+'-id', value='')
            assert_input(response, name='comment_set-'+i+'-post', value='')

        assert_management_form_inputs(response, total=4+extra, initial=0, max_num=DEFAULT_MAX_NUM)


    def test_clone_should_create_new_object_with_inlines_on_POST(self):
        response = self.app.get(self.post_with_comments_url, user='admin')
        response.form.submit()

        post1 = Post.objects.get(title=self.post_with_comments.title)
        post2 = Post.objects.get(title=self.post_with_comments.title + ' (duplicate)')

        assert 2 == post1.comment_set.count()
        assert 2 == post2.comment_set.count()


    def test_clone_should_ignore_initial_data_of_inline_form_if_delete_is_checked(self):
        response = self.app.get(self.post_with_comments_url, user='admin')
        response.form.set('comment_set-0-DELETE', 'on')  # delete first comment
        response.form.submit()

        cloned_post = Post.objects.latest('id')

        assert 1 == cloned_post.comment_set.count()


    def test_clone_with_m2m_fields_should_prefill_m2m_fields(self):
        response = self.app.get(self.post_with_tags_url, user='admin')

        tag1_option = select_element(response, 'select[name=tags] option[value="{id}"]'
            .format(id=self.tag1.id))
        tag2_option = select_element(response, 'select[name=tags] option[value="{id}"]'
            .format(id=self.tag2.id))

        assert tag1_option.get('selected')
        assert not tag2_option.get('selected')


    def test_clone_with_m2m_fields_should_keep_modified_m2m_field_values_after_validation_error(self):
        response = self.app.get(self.post_with_tags_url, user='admin')

        # original post has tag1 selected and tag2 disabled. will disable tag1
        # and select tag2.
        #
        # with a blank title the page will return a validation error, should keep
        # my selected options
        response.form.set('title', '')
        response.form.set('tags', [self.tag2.id])
        response = response.form.submit()

        assert 'Please correct the error below' in response.content

        tag1_option = select_element(response, 'select[name=tags] option[value="{id}"]'
            .format(id=self.tag1.id))
        tag2_option = select_element(response, 'select[name=tags] option[value="{id}"]'
            .format(id=self.tag2.id))

        assert not tag1_option.get('selected')
        assert tag2_option.get('selected')


    def test_clone_save_and_continue_editing_should_redirect_to_new_object_edit_page(self):
        response = self.app.get(self.post_url, user='admin')
        response = response.form.submit('_continue')

        new_id = Post.objects.latest('id').id

        assert 302 == response.status_code
        assert 'http://testserver/admin/posts/post/{0}/'.format(new_id) == response['Location']


    # clone with images and files

    def test_clone_should_keep_file_path_from_original_object(self):
        response = self.app.get(self.multimedia_url, user='admin')

        image = select_element(response, '.field-image p.file-upload a')
        document = select_element(response, '.field-document p.file-upload a')

        assert '/media/images/img.jpg' == image.get('href')
        assert '/media/documents/file.txt' == document.get('href')


    def test_clone_should_keep_file_path_from_original_object_on_submit(self):
        response = self.app.get(self.multimedia_url, user='admin')
        response.form.submit()

        multimedia = Multimedia.objects.latest('id')

        assert 'images/img.jpg' == str(multimedia.image)
        assert 'documents/file.txt' == str(multimedia.document)


    def test_clone_should_override_file_from_original_object_on_submit_if_new_file_was_chosen(self):
        response = self.app.get(self.multimedia_url, user='admin')
        response.form['image'] = Upload('tests/files/img-2.jpg')
        response.form['document'] = Upload('tests/files/file-2.txt')
        response.form.submit()

        multimedia = Multimedia.objects.latest('id')

        assert 'images/img-2.jpg' == str(multimedia.image)
        assert 'documents/file-2.txt' == str(multimedia.document)


def rm_rf(path):
    try:
        shutil.rmtree(path)
    except OSError:
        pass

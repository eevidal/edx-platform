'''
Tests for student activation and login
'''
import json
import unittest
from mock import patch

from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse, NoReverseMatch
from student.tests.factories import UserFactory, RegistrationFactory, UserProfileFactory
from student.views import _parse_course_id_from_string, _get_course_enrollment_domain

from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase, mixed_store_config
from xmodule.modulestore.inheritance import own_metadata
from xmodule.modulestore.django import editable_modulestore

from external_auth.models import ExternalAuthMap

TEST_DATA_MIXED_MODULESTORE = mixed_store_config(settings.COMMON_TEST_DATA_ROOT, {})


class LoginTest(TestCase):
    '''
    Test student.views.login_user() view
    '''

    def setUp(self):
        # Create one user and save it to the database
        self.user = UserFactory.build(username='test', email='test@edx.org')
        self.user.set_password('test_password')
        self.user.save()

        # Create a registration for the user
        RegistrationFactory(user=self.user)

        # Create a profile for the user
        UserProfileFactory(user=self.user)

        # Create the test client
        self.client = Client()
        cache.clear()

        # Store the login url
        try:
            self.url = reverse('login_post')
        except NoReverseMatch:
            self.url = reverse('login')

    def test_login_success(self):
        response, mock_audit_log = self._login_response('test@edx.org', 'test_password', patched_audit_log='student.models.AUDIT_LOG')
        self._assert_response(response, success=True)
        self._assert_audit_log(mock_audit_log, 'info', [u'Login success', u'test@edx.org'])

    def test_login_success_unicode_email(self):
        unicode_email = u'test' + unichr(40960) + u'@edx.org'
        self.user.email = unicode_email
        self.user.save()

        response, mock_audit_log = self._login_response(unicode_email, 'test_password', patched_audit_log='student.models.AUDIT_LOG')
        self._assert_response(response, success=True)
        self._assert_audit_log(mock_audit_log, 'info', [u'Login success', unicode_email])

    def test_login_fail_no_user_exists(self):
        nonexistent_email = u'not_a_user@edx.org'
        response, mock_audit_log = self._login_response(nonexistent_email, 'test_password')
        self._assert_response(response, success=False,
                              value='Email or password is incorrect')
        self._assert_audit_log(mock_audit_log, 'warning', [u'Login failed', u'Unknown user email', nonexistent_email])

    def test_login_fail_wrong_password(self):
        response, mock_audit_log = self._login_response('test@edx.org', 'wrong_password')
        self._assert_response(response, success=False,
                              value='Email or password is incorrect')
        self._assert_audit_log(mock_audit_log, 'warning', [u'Login failed', u'password for', u'test@edx.org', u'invalid'])

    def test_login_not_activated(self):
        # De-activate the user
        self.user.is_active = False
        self.user.save()

        # Should now be unable to login
        response, mock_audit_log = self._login_response('test@edx.org', 'test_password')
        self._assert_response(response, success=False,
                              value="This account has not been activated")
        self._assert_audit_log(mock_audit_log, 'warning', [u'Login failed', u'Account not active for user'])

    def test_login_unicode_email(self):
        unicode_email = u'test@edx.org' + unichr(40960)
        response, mock_audit_log = self._login_response(unicode_email, 'test_password')
        self._assert_response(response, success=False)
        self._assert_audit_log(mock_audit_log, 'warning', [u'Login failed', unicode_email])

    def test_login_unicode_password(self):
        unicode_password = u'test_password' + unichr(1972)
        response, mock_audit_log = self._login_response('test@edx.org', unicode_password)
        self._assert_response(response, success=False)
        self._assert_audit_log(mock_audit_log, 'warning', [u'Login failed', u'password for', u'test@edx.org', u'invalid'])

    def test_logout_logging(self):
        response, _ = self._login_response('test@edx.org', 'test_password')
        self._assert_response(response, success=True)
        logout_url = reverse('logout')
        with patch('student.models.AUDIT_LOG') as mock_audit_log:
            response = self.client.post(logout_url)
        self.assertEqual(response.status_code, 302)
        self._assert_audit_log(mock_audit_log, 'info', [u'Logout', u'test'])

    def test_login_ratelimited_success(self):
        # Try (and fail) logging in with fewer attempts than the limit of 30
        # and verify that you can still successfully log in afterwards.
        for i in xrange(20):
            password = u'test_password{0}'.format(i)
            response, _audit_log = self._login_response('test@edx.org', password)
            self._assert_response(response, success=False)
        # now try logging in with a valid password
        response, _audit_log = self._login_response('test@edx.org', 'test_password')
        self._assert_response(response, success=True)

    def test_login_ratelimited(self):
        # try logging in 30 times, the default limit in the number of failed
        # login attempts in one 5 minute period before the rate gets limited
        for i in xrange(30):
            password = u'test_password{0}'.format(i)
            self._login_response('test@edx.org', password)
        # check to see if this response indicates that this was ratelimited
        response, _audit_log = self._login_response('test@edx.org', 'wrong_password')
        self._assert_response(response, success=False, value='Too many failed login attempts')

    def _login_response(self, email, password, patched_audit_log='student.views.AUDIT_LOG'):
        ''' Post the login info '''
        post_params = {'email': email, 'password': password}
        with patch(patched_audit_log) as mock_audit_log:
            result = self.client.post(self.url, post_params)
        return result, mock_audit_log

    def _assert_response(self, response, success=None, value=None):
        '''
        Assert that the response had status 200 and returned a valid
        JSON-parseable dict.

        If success is provided, assert that the response had that
        value for 'success' in the JSON dict.

        If value is provided, assert that the response contained that
        value for 'value' in the JSON dict.
        '''
        self.assertEqual(response.status_code, 200)

        try:
            response_dict = json.loads(response.content)
        except ValueError:
            self.fail("Could not parse response content as JSON: %s"
                      % str(response.content))

        if success is not None:
            self.assertEqual(response_dict['success'], success)

        if value is not None:
            msg = ("'%s' did not contain '%s'" %
                   (str(response_dict['value']), str(value)))
            self.assertTrue(value in response_dict['value'], msg)

    def _assert_audit_log(self, mock_audit_log, level, log_strings):
        """
        Check that the audit log has received the expected call as its last call.
        """
        method_calls = mock_audit_log.method_calls
        name, args, _kwargs = method_calls[-1]
        self.assertEquals(name, level)
        self.assertEquals(len(args), 1)
        format_string = args[0]
        for log_string in log_strings:
            self.assertIn(log_string, format_string)


class UtilFnTest(TestCase):
    """
    Tests for utility functions in student.views
    """
    def test__parse_course_id_from_string(self):
        """
        Tests the _parse_course_id_from_string util function
        """
        COURSE_ID = u'org/num/run'                                # pylint: disable=C0103
        COURSE_URL = u'/courses/{}/otherstuff'.format(COURSE_ID)  # pylint: disable=C0103
        NON_COURSE_URL = u'/blahblah'                             # pylint: disable=C0103
        self.assertEqual(_parse_course_id_from_string(COURSE_URL), COURSE_ID)
        self.assertIsNone(_parse_course_id_from_string(NON_COURSE_URL))


@override_settings(MODULESTORE=TEST_DATA_MIXED_MODULESTORE)
class ExternalAuthShibTest(ModuleStoreTestCase):
    """
    Tests how login_user() interacts with ExternalAuth, in particular Shib
    """
    def setUp(self):
        self.store = editable_modulestore()
        self.course = CourseFactory.create(org='Stanford', number='456', display_name='NO SHIB')
        self.shib_course = CourseFactory.create(org='Stanford', number='123', display_name='Shib Only')
        self.shib_course.enrollment_domain = 'shib:https://idp.stanford.edu/'
        self.store.update_item(self.shib_course, '**replace_user**')
        self.user_w_map = UserFactory.create(email='withmap@stanford.edu')
        self.extauth = ExternalAuthMap(external_id='withmap@stanford.edu',
                                       external_email='withmap@stanford.edu',
                                       external_domain='shib:https://idp.stanford.edu/',
                                       external_credentials="",
                                       user=self.user_w_map)
        self.user_w_map.save()
        self.extauth.save()
        self.user_wo_map = UserFactory.create(email='womap@gmail.com')
        self.user_wo_map.save()

    @unittest.skipUnless(settings.FEATURES.get('AUTH_USE_SHIB'), "AUTH_USE_SHIB not set")
    def test_login_page_redirect(self):
        """
        Tests that when a shib user types their email address into the login page, they get redirected
        to the shib login.
        """
        response = self.client.post(reverse('login'), {'email': self.user_w_map.email, 'password': ''})
        self.assertEqual(response.status_code, 200)
        obj = json.loads(response.content)
        self.assertEqual(obj, {
            'success': False,
            'redirect': reverse('shib-login'),
        })

    @unittest.skipUnless(settings.FEATURES.get('AUTH_USE_SHIB'), "AUTH_USE_SHIB not set")
    def test__get_course_enrollment_domain(self):
        """
        Tests the _get_course_enrollment_domain utility function
        """
        self.assertIsNone(_get_course_enrollment_domain("I/DONT/EXIST"))
        self.assertIsNone(_get_course_enrollment_domain(self.course.id))
        self.assertEqual(self.shib_course.enrollment_domain, _get_course_enrollment_domain(self.shib_course.id))

    @unittest.skipUnless(settings.FEATURES.get('AUTH_USE_SHIB'), "AUTH_USE_SHIB not set")
    def test_login_required_dashboard(self):
        """
        Tests redirects to when @login_required to dashboard, which should always be the normal login,
        since there is no course context
        """
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], 'http://testserver/accounts/login?next=/dashboard')

    @unittest.skipUnless(settings.FEATURES.get('AUTH_USE_SHIB'), "AUTH_USE_SHIB not set")
    def test_externalauth_login_required_course_context(self):
        """
        Tests the redirects when visiting course-specific URL with @login_required.
        Should vary by course depending on its enrollment_domain
        """
        TARGET_URL = reverse('courseware', args=[self.course.id])            # pylint: disable=C0103
        noshib_response = self.client.get(TARGET_URL, follow=True)
        self.assertEqual(noshib_response.redirect_chain[-1],
                         ('http://testserver/accounts/login?next={url}'.format(url=TARGET_URL), 302))
        self.assertContains(noshib_response, ("Log into your {platform_name} Account | {platform_name}"
                                              .format(platform_name=settings.PLATFORM_NAME)))
        self.assertEqual(noshib_response.status_code, 200)

        TARGET_URL_SHIB = reverse('courseware', args=[self.shib_course.id])  # pylint: disable=C0103
        shib_response = self.client.get(**{'path': TARGET_URL_SHIB,
                                           'follow': True,
                                           'REMOTE_USER': self.extauth.external_id,
                                           'Shib-Identity-Provider': 'https://idp.stanford.edu/'})
        # Test that the shib-login redirect page with ?next= and the desired page are part of the redirect chain
        # The 'courseware' page actually causes a redirect itself, so it's not the end of the chain and we
        # won't test its contents
        self.assertEqual(shib_response.redirect_chain[-3],
                         ('http://testserver/shib-login/?next={url}'.format(url=TARGET_URL_SHIB), 302))
        self.assertEqual(shib_response.redirect_chain[-2],
                         ('http://testserver{url}'.format(url=TARGET_URL_SHIB), 302))
        self.assertEqual(shib_response.status_code, 200)

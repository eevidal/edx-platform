# -*- coding: utf-8 -*-

import json
import uuid
from django.test import TestCase
from django.core.urlresolvers import reverse


class TestLongUsernameEmail(TestCase):

    def setUp(self):
        self.url = reverse('create_account')
        self.url_params = {
            'username': 'foo',
            'email': 'foo_bar' + '@bar.com',
            'name': 'foo bar',
            'password': '123',
            'terms_of_service': 'true',
            'honor_code': 'true',
        }

    def test_long_username(self):
        """
        Test username must be maximum of 30 characters long.
        """

        self.url_params['username'] = 'foo' + uuid.uuid4().hex
        response = self.client.post(self.url, self.url_params)

        # Status code should bee 400.
        self.assertEqual(response.status_code, 400)

        obj = json.loads(response.content)
        self.assertEqual(
            obj['value'],
            "Username must be maximum of 30 characters long",
        )

    def test_long_email(self):
        """
        Test email must be maximum of 75 characters long.
        """

        self.url_params['email'] = '{0}@bar.com'.format('foo_bar' * 15)
        response = self.client.post(self.url, self.url_params)

        # Status code should bee 400.
        self.assertEqual(response.status_code, 400)

        obj = json.loads(response.content)
        self.assertEqual(
            obj['value'],
            "Email must be maximum of 75 characters long",
        )

"""
Defines forms for providing validation of embargo admin details.
"""

from django import forms
from django.core.exceptions import ValidationError

from embargo.models import EmbargoedCourse, EmbargoedState, IPException

from xmodule.course_module import CourseDescriptor


class EmbargoedCourseForm(forms.ModelForm):  # pylint: disable=incomplete-protocol
    """Form providing validation of entered Course IDs."""

    class Meta:  # pylint: disable=missing-docstring
        model = EmbargoedCourse

    def clean_course_id(self):
        """Validate the course id"""
        course_id = self.cleaned_data["course_id"]
        try:
            # Try to get the course descriptor, if we can do that,
            # it's a real course.
            course_loc = CourseDescriptor.id_to_location(course_id)
            # if this doesn't work may also need to try loading in from modulestore
            #from xmodule.modulestore.django import modulestore
            #modulestore().get_instance(course_id, course_loc, depth=1)
        except (KeyError, ItemNotFoundError, InvalidLocationError) as exc:
            msg = 'Error encountered ({0})'.format(str(exc).capitalize())
            msg += u' --- Entered course id was: "{0}". '.format(course_id)
            msg += 'Please recheck that you have supplied a valid course id.'
            raise forms.ValidationError(msg)

        return course_id


class EmbargoedStateForm(forms.ModelForm):  # pylint: disable=incomplete-protocol
    """Form validating entry of states to embargo"""

    class Meta:  # pylint: disable=missing-docstring
        model = EmbargoedState

    def _is_valid_code(self, code):
        """Whether or not code is a valid country code"""
        ## TODO use pygeoip library to look up country to check validity.
        if len(code) > 2:
            return False
        return True

    def clean_embargoed_countries(self):
        """Validate the country list"""
        embargoed_countries = self.cleaned_data["embargoed_countries"]
        validated_countries = []
        error_countries = []

        for country in embargoed_countries.split(','):
            country = country.strip().upper()
            if self._is_valid_code(country):
                validated_countries.append(country)
            else:
                error_countries.append(country)

        if error_countries:
            msg = 'Could not parse country code(s) for: {0}'.format(error_countries)
            ## TODO add a URL here
            msg += ' Please visit [URL] to see a list of valid country codes.'
            raise forms.ValidationError(msg)

        return validated_countries

class IPExceptionForm(forms.ModelForm):  # pylint: disable=incomplete-protocol
    """Form validating entry of IP addresses"""

    class Meta:  # pylint: disable=missing-docstring
        model = IPException

    def _is_valid_ip(self, address):
        """Whether or not address is a valid ipv4 or ipv6 address"""
        # TODO
        if address == 'Sarina':
            return False
        return True

    def _valid_ip_addresses(self, addresses):
        """
        Checks if a csv string of IP addresses contains valid values.

        If not, raises a ValidationError.
        """
        validated_addresses = []
        error_addresses = []
        for address in addresses.split(','):
            if self._is_valid_ip(address):
                validated_addresses.append(address)
            else:
                error_addresses.append(address)
        if error_addresses:
            msg = 'Invalid IP Address(es): {0}'.format(error_addresses)
            msg += ' Please fix the error(s) and try again.'
            raise forms.ValidationError(msg)

        return validated_addresses


    def clean_whitelist(self):
        """Validates the whitelist"""
        whitelist = self.cleaned_data["whitelist"]
        return self._valid_ip_addresses(whitelist)

    def clean_blacklist(self):
        """Validates the blacklist"""
        blacklist = self.cleaned_data["blacklist"]
        return self._valid_ip_addresses(blacklist)

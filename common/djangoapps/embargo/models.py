"""
Models for embargoing visits to certain courses by IP address.

WE'RE USING MIGRATIONS!

If you make changes to this model, be sure to create an appropriate migration
file and check it in at the same time as your model changes. To do that,

1. Go to the edx-platform dir
2. ./manage.py lms schemamigration embargo --auto description_of_your_change
3. Add the migration file created in edx-platform/common/djangoapps/embargo/migrations/
"""
from django.db import models

from config_models.models import ConfigurationModel


class EmbargoConfig(ConfigurationModel):
    """
    Configuration for the embargo feature
    """
    embargoed_countries = models.TextField(
        blank=True,
        help_text="A comma-separated list of country codes that fall under U.S. embargo restrictions"
    )

    embargoed_courses = models.TextField(
        blank = True,
        help_text = "A comma-separated list of course IDs that we are enforcing the embargo for"
    )

    @property
    def embargoed_countries_list(self):
        if not self.embargoed_countries.strip():
            return []
        return [country.strip() for country in self.embargoed_countries.split(',')]

    @property
    def embargoed_courses_list(self):
        if not self.embargoed_courses.strip():
            return []
        return [course.strip() for course in self.embargoed_courses.split(',')]

class EmbargoedCourse(models.Model):
    """
    Enable course embargo on a course-by-course basis.
    """
    # The course to embargo
    course_id = models.CharField(max_length=255, db_index=True, unique=True)

    # Whether or not to embargo
    embargoed = models.BooleanField(default=False)

    @classmethod
    def is_embargoed(cls, course_id):
        """
        Returns whether or not the given course id is embargoed.

        If course has not been explicitly embargoed, returns False.
        """
        try:
            record = cls.objects.get(course_id=course_id)
            return record.embargoed
        except cls.DoesNotExist:
            return False

    def __unicode__(self):
        not_em = "Not "
        if self.embargoed:
            not_em = ""
        return u"Course '{}' is {}Embargoed".format(self.course_id, not_em)


class EmbargoedState(models.Model):
    """
    Register countries to be embargoed.
    """
    # The countries to embargo
    embargoed_countries = models.TextField(
        blank=True,
        help_text="A comma-separated list of country codes that fall under U.S. embargo restrictions"
    )

    @property
    def embargoed_countries_list(self):
        # EmbargoedStateForm validates this entry and converts it to
        # a Python list of upper-cased entries
        return self.embargoed_countries


# TODO: IP whitelist, blacklist. See models.GenericIPAddressField
class IPException(models.Model):
    """
    Register specific IP addresses to explicitly block or unblock.
    """
    whitelist = models.TextField(
        blank=True,
        help_text="A comma-separated list of IP addresses that should not fall under embargo restrictions."
    )

    blacklist = models.TextField(
        blank=True,
        help_text="A comma-separated list of IP addresses that should fall under embargo restrictions."
    )

    @property
    def whitelist_ips(self):
        # IPExceptionForm validates this entry and converts it to
        # a Python list of valid IP addresses
        return self.whitelist

    @property
    def blacklist_ips(self):
        # IPExceptionForm validates this entry and converts it to
        # a Python list of valid IP addresses
        return self.blacklist

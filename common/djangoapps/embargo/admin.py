"""
Django admin page for embargo models
"""
from django.contrib import admin

from embargo.models import EmbargoedCourse, EmbargoedState, IPException
from embargo.forms import EmbargoedCourseForm, EmbargoedStateForm, IPExceptionForm

class EmbargoedCourseAdmin(admin.ModelAdmin):
    """Admin for embargoed course ids"""
    form = EmbargoedCourseForm


class EmbargoedStateAdmin(admin.ModelAdmin):
    """Admin for embargoed countries"""
    form = EmbargoedStateForm

class EmbargoedCourseAdmin(admin.ModelAdmin):
    """Admin for blacklisting/whitelisting specific IP addresses"""
    form = IPExceptionForm

admin.site.register(EmbargoedCourse, EmbargoedCourseAdmin)
admin.site.register(EmbargoedState, EmbargoedStateAdmin)
admin.site.register(IPException, IPExceptionAdmin)

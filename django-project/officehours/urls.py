from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
	url(r'^list/(?P<course_id>\d+)/', 'officehours.views.list'),
)

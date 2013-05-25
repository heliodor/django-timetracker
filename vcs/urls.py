'''
Module that maps incoming URL requests to functions which return responses
'''

from django.conf.urls import patterns, include, url
from timetracker.vcs import views

urlpatterns = patterns('',
                       (r'insert/?$', views.vcs),
)
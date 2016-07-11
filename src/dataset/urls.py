from django.conf.urls import url, include
import django.contrib.auth.views as auth_views
from django.views.generic import RedirectView

from . import views


app_name = 'dataset'
urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^sign-in/$', auth_views.login, {'template_name': 'dataset/sign-in.html'}, name='sign-in'),
    url(r'^logout/$', views.logout, name='logout'),
    url(r'^register/', views.register, name='register'),
    url(r'^stats/', views.stats, name='stats'),
    url(r'^dataset/', views.dataset, name='dataset'),
    url(r'^downloads/([0-9]+)/', views.download_dataset, name='download_dataset'),
    url(r'^downloads/', RedirectView.as_view(pattern_name='dataset:dataset')),
]

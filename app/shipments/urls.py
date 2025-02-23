from django.urls import path
from . import views

urlpatterns = [
	path('shipments/', views.list, name='list'),
]
from django.urls import path
from . import views

urlpatterns = [
	path('invoices/', views.list, name='list'),
]
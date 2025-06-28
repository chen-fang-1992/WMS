from django.urls import path
from . import views

urlpatterns = [
	path('products/', views.list, name='list'),
	path('products/create/', views.create_product, name='create_product'),
]
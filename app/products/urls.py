from django.urls import path
from . import views

urlpatterns = [
	path('products/', views.list, name='list'),
	path('products/create/', views.create_product, name='create_product'),
	path('products/delete/<int:id>/', views.delete_product, name='delete_product'),
	path('products/detail/<int:id>/', views.product_detail, name='product_detail'),
	path('products/update/<int:id>/', views.update_product, name='update_product'),
]
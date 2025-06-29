from django.urls import path
from . import views

urlpatterns = [
	path('orders/', views.list, name='list'),
	path('orders/create/', views.create_order, name='create_order'),
	path('orders/delete/<int:id>/', views.delete_order, name='delete_order'),
	path('orders/detail/<int:id>/', views.order_detail, name='order_detail'),
	path('orders/update/<int:id>/', views.update_order, name='update_order'),
]
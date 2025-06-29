from django.urls import path
from . import views

urlpatterns = [
	path('inbounds/', views.list, name='list'),
	path('inbounds/create/', views.create_inbound, name='create_inbound'),
	path('inbounds/delete/<int:id>/', views.delete_inbound, name='delete_inbound'),
	path('inbounds/detail/<int:id>/', views.inbound_detail, name='inbound_detail'),
	path('inbounds/update/<int:id>/', views.update_inbound, name='update_inbound'),
]
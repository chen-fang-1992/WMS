from django.urls import path
from . import views

urlpatterns = [
	path('refunds/', views.list, name='refund_list'),
	path('refunds/create/', views.create, name='create_refund'),
	path('refunds/detail/<int:id>/', views.detail, name='refund_detail'),
	path('refunds/detail-json/<int:id>/', views.detail_json, name='refund_detail_json'),
	path('refunds/update/<int:id>/', views.update, name='update_refund'),
	path('refunds/status/<int:id>/', views.update_status, name='update_refund_status'),
	path('refunds/cancel/<int:id>/', views.cancel, name='cancel_refund'),
]

from django.urls import path

from . import views


urlpatterns = [
	path('aftersales/', views.list, name='aftersale_list'),
	path('aftersales/create/', views.create, name='create_aftersale'),
	path('aftersales/detail-json/<int:id>/', views.detail_json, name='aftersale_detail_json'),
	path('aftersales/update/<int:id>/', views.update, name='update_aftersale'),
]


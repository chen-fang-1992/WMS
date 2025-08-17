from django.urls import path
from . import views

urlpatterns = [
	path('stocks/', views.list, name='list'),
	path('stocks/detail/<int:id>/', views.stock_detail, name='stock_detail'),
	path('stocks/export/', views.export_stocks, name='stocks_export'),
]
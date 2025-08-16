"""
URL configuration for tms project.

The `urlpatterns` list routes URLs to views. For more information please see:
	https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
	1. Add an import:  from my_app import views
	2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
	1. Add an import:  from other_app.views import Home
	2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
	1. Import the include() function: from django.urls import include, path
	2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.urls import re_path
from django.conf import settings
from django.conf.urls.static import static
from tms.views import page_not_found as page_not_found_view

urlpatterns = [
	path('admin/', admin.site.urls),
	path('', include('app.home.urls')),
	path('', include('app.shipments.urls')),
	path('', include('app.customers.urls')),
	path('', include('app.invoices.urls')),
	path('', include('app.products.urls')),
	path('', include('app.inbounds.urls')),
	path('', include('app.orders.urls')),
	path('', include('app.stocks.urls')),
	path('accounts/', include('app.accounts.urls')),
]

if settings.DEBUG:
	urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
	urlpatterns += static(settings.MEDIA_URL, document_root=getattr(settings, 'MEDIA_ROOT', None))

urlpatterns += [
	re_path(r'^(?!static/|media/).*$', page_not_found_view),
]

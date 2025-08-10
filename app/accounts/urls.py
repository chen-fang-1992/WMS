from django.urls import path
from .views import register, RememberMeLoginView, DoLogoutView

app_name = 'accounts'

urlpatterns = [
	path('register/', register, name='register'),
	path('login/', RememberMeLoginView.as_view(), name='login'),
	path('logout/', DoLogoutView.as_view(), name='logout'),
]
from django.urls import path
from .views import register, RememberMeLoginView, DoLogoutView
from .views import ProfileUpdateView, MyPasswordChangeView, MyPasswordChangeDoneView

app_name = 'accounts'

urlpatterns = [
	path('register/', register, name='register'),
	path('login/', RememberMeLoginView.as_view(), name='login'),
	path('logout/', DoLogoutView.as_view(), name='logout'),
	path('profile/', ProfileUpdateView.as_view(), name='profile'),
	path('password/', MyPasswordChangeView.as_view(), name='password_change'),
	path('password/done/', MyPasswordChangeDoneView.as_view(), name='password_change_done'),
]
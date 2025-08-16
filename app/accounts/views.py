from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, get_user_model
from django.shortcuts import render, redirect
from django.conf import settings

from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
User = get_user_model()

class SignUpForm(UserCreationForm):
	username = UsernameField(
		label="用户名",
		widget=forms.TextInput(attrs={"autofocus": True}),
		error_messages={"unique": "该用户名已存在"},
	)
	first_name = forms.CharField(max_length=30, required=True, label="名")
	last_name = forms.CharField(max_length=30, required=True, label="姓")
	email = forms.EmailField(
		required=True,
		label="邮箱",
		error_messages={
			'invalid': '请输入有效的邮箱地址',
			'required': '请输入邮箱',
		}
	)

	class Meta:
		model = User
		fields = (
			"username",
			"first_name",
			"last_name",
			"email",
			"password1",
			"password2",
		)

	def clean_email(self):
		email = self.cleaned_data.get("email")
		if User.objects.filter(email__iexact=email).exists():
			raise forms.ValidationError("该邮箱已被使用")
		return email

class RememberMeLoginView(LoginView):
	template_name = 'accounts/login.html'
	authentication_form = AuthenticationForm

	def form_valid(self, form):
		remember = self.request.POST.get('remember')
		response = super().form_valid(form)
		if remember:
			# 14 天
			self.request.session.set_expiry(1209600)
		else:
			self.request.session.set_expiry(0)
		return response

class DoLogoutView(LogoutView):
	next_page = None

def register(request):
	if request.method == "POST":
		form = SignUpForm(request.POST)
		if form.is_valid():
			user = form.save()
			login(request, user)
			return redirect(getattr(settings, "LOGIN_REDIRECT_URL", "/"))
	else:
		form = SignUpForm()
	return render(request, "accounts/register.html", {"form": form})

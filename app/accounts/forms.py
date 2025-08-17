from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class ProfileForm(forms.ModelForm):
	class Meta:
		model = User
		fields = ['username', 'email', 'first_name', 'last_name']
		widgets = {
			'username': forms.TextInput(attrs={'class': 'form-control'}),
			'email': forms.EmailInput(attrs={'class': 'form-control'}),
			'first_name': forms.TextInput(attrs={'class': 'form-control'}),
			'last_name': forms.TextInput(attrs={'class': 'form-control'}),
		}

	def __init__(self, *args, **kwargs):
		self.user = kwargs.pop('user', None)
		super().__init__(*args, **kwargs)

	def clean_email(self):
		email = (self.cleaned_data.get('email') or '').strip()
		if not email:
			return email
		qs = User.objects.filter(email__iexact=email)
		if self.user:
			qs = qs.exclude(pk=self.user.pk)
		if qs.exists():
			raise forms.ValidationError('该邮箱已被使用')
		return email

	def clean_username(self):
		username = (self.cleaned_data.get('username') or '').strip()
		if not username:
			return username
		qs = User.objects.filter(username__iexact=username)
		if self.user:
			qs = qs.exclude(pk=self.user.pk)
		if qs.exists():
			raise forms.ValidationError('该用户名已被使用')
		return username

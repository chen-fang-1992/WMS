from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve

class LoginRequiredMiddleware:
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		print(f"[LoginRequiredMW] path={request.path} user.auth={getattr(request.user, 'is_authenticated', None)}")

		# 白名单 URL（不需要登录）
		whitelist = [
			'/accounts/register/',
			'/accounts/login/',
			'/accounts/logout/',
			settings.STATIC_URL,
			settings.MEDIA_URL,
		]

		# 如果当前 URL 以白名单路径开头，则放行
		for path in whitelist:
			if path and request.path.rstrip('/').startswith(path.rstrip('/')):
				return self.get_response(request)

		# 如果未登录 -> 跳转到登录页
		if not request.user.is_authenticated:
			return redirect(f"{settings.LOGIN_URL}?next={request.path}")

		# 已登录 -> 正常处理
		return self.get_response(request)
from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import get_resolver, Resolver404

def page_not_found(request, exception=None):
	if (request.method in ('GET','HEAD')
		and getattr(settings, 'APPEND_SLASH', True)
		and not request.path.endswith('/')):
		try:
			match = get_resolver().resolve(request.path + '/')
			return redirect(request.path + '/')
		except Resolver404:
			pass
	return render(request, 'errors/404.html', status=404)

from django.shortcuts import render

def page_not_found(request, exception=None):
	return render(request, 'errors/404.html', status=404)

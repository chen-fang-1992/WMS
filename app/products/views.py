from django.shortcuts import render
from ..products.models import Product

def list(request):
	products = Product.objects.all()
	return render(request, 'products/list.html', {'products': products})
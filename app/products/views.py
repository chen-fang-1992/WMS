from django.shortcuts import render
from ..products.models import Product

def list(request):
	products = Product.objects.all()
	categories = Product.get_all_categories()
	manufacturers = Product.get_all_manufacturers()
	return render(request, 'products/list.html', {'products': products, 'categories': categories, 'manufacturers': manufacturers})
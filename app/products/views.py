from django.shortcuts import render
from ..products.models import Product

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal, InvalidOperation

def list(request):
	products = Product.objects.all()
	categories = Product.get_all_categories()
	manufacturers = Product.get_all_manufacturers()
	return render(request, 'products/list.html', {'products': products, 'categories': categories, 'manufacturers': manufacturers})

def parse_decimal(value):
	try:
		return Decimal(str(value).replace(',', '').strip())
	except (InvalidOperation, ValueError, TypeError):
		return Decimal('0')

@csrf_exempt
def create_product(request):
	if request.method == 'POST':
		data = json.loads(request.body)

		Product.objects.create(
			name_en = data['name_en'],
			category = data['category'],
			manufacturer = data['manufacturer'],
			name_cn = data['name_cn'],
			sku = data['sku'],
			barcode = data['barcode'],
			image_url = data['image_url'],
			package_length = data['package_length'],
			package_width = data['package_width'],
			package_height = data['package_height'],
			shipping_volume = data['shipping_volume'],
			weight = parse_decimal(data['weight']),
			cost_rmb = parse_decimal(data['cost_rmb']),
			cost_aud = parse_decimal(data['cost_aud']),
			sea_shipping_cost = parse_decimal(data['sea_shipping_cost']),
			total_cost = parse_decimal(data['total_cost']),
			actual_price = parse_decimal(data['actual_price']),
			profit = parse_decimal(data['profit']),
		)

		return JsonResponse({'success': True})

	return JsonResponse({'success': False, 'error': 'Invalid method'})

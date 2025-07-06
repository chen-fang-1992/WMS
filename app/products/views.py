from django.shortcuts import render
from ..products.models import Product

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal, InvalidOperation
from django.db.models import Q

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

@csrf_exempt
def delete_product(request, id):
	if request.method == 'POST':
		try:
			product = Product.objects.filter(id=id).first()
			if not product:
				return JsonResponse({'success': False, 'error': '未找到产品'})

			product.delete()
			return JsonResponse({'success': True})
		
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

@csrf_exempt
def product_detail(request, id):
	if request.method == 'GET':
		try:
			product = Product.objects.filter(id=id).values().first()
			if not product:
				return JsonResponse({'success': False, 'error': '未找到产品'})

			return JsonResponse({'success': True, 'product': product})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return JsonResponse({'success': False, 'error': '仅支持 GET 请求'})

@csrf_exempt
def update_product(request, id):
	if request.method == 'POST':
		data = json.loads(request.body)

		try:
			product = Product.objects.get(id=id)
			product.name_en = data['name_en']
			product.category = data['category']
			product.manufacturer = data['manufacturer']
			product.name_cn = data['name_cn']
			product.sku = data['sku']
			product.barcode = data['barcode']
			product.package_length = data['package_length']
			product.package_width = data['package_width']
			product.package_height = data['package_height']
			product.shipping_volume = data['shipping_volume']
			product.weight = parse_decimal(data['weight'])
			product.cost_rmb = parse_decimal(data['cost_rmb'])
			product.cost_aud = parse_decimal(data['cost_aud'])
			product.sea_shipping_cost = parse_decimal(data['sea_shipping_cost'])
			product.total_cost = parse_decimal(data['total_cost'])
			product.actual_price = parse_decimal(data['actual_price'])
			product.profit = parse_decimal(data['profit'])
			product.save()

			return JsonResponse({'success': True})
		except Product.DoesNotExist:
			return JsonResponse({'success': False, 'error': '未找到产品'})
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

def search_products(request):
	q = request.GET.get('q', '')
	results = []

	if q:
		products = Product.objects.filter(
			Q(name_cn__icontains=q) |
			Q(name_en__icontains=q) |
			Q(barcode__icontains=q)
		)[:50]  # 限制最多返回50条

		results = [
			{
				'id': p.id,
				'name_cn': p.name_cn,
				'name_en': p.name_en,
				'barcode': p.barcode
			}
			for p in products
		]

	return JsonResponse({'results': results})

from django.shortcuts import render
from ..products.models import Product
from ..products.models import ProductBOM

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal, InvalidOperation
from django.db.models import Q

def list(request):
	products = Product.objects.all()
	categories = Product.get_all_categories()
	manufacturers = Product.get_all_manufacturers()
	types = Product.get_all_types()
	return render(request, 'products/list.html', {'products': products, 'types': types, 'categories': categories, 'manufacturers': manufacturers})

def parse_decimal(value):
	try:
		return Decimal(str(value).replace(',', '').strip())
	except (InvalidOperation, ValueError, TypeError):
		return Decimal('0')

@csrf_exempt
def create_product(request):
	if request.method == 'POST':
		data = json.loads(request.body)

		try:
			product = Product.objects.create(
				name_en = data['name_en'],
				type = data['type'],
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

			# 处理 BOM 数据
			for item in data.get('bom_items', []):
				component_id = int(item['component_id'])
				quantity = int(item['quantity'])
				if component_id and quantity > 0:
					ProductBOM.objects.create(
						product=product,
						component_id=component_id,
						quantity=quantity
					)

			return JsonResponse({'success': True})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

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
			product = Product.objects.filter(id=id).first()
			if not product:
				return JsonResponse({'success': False, 'error': '未找到产品'})

			# 产品字段
			product_data = {
				'id': product.id,
				'name_en': product.name_en,
				'type': product.type,
				'category': product.category,
				'manufacturer': product.manufacturer,
				'name_cn': product.name_cn,
				'sku': product.sku,
				'barcode': product.barcode,
				'package_length': product.package_length,
				'package_width': product.package_width,
				'package_height': product.package_height,
				'shipping_volume': product.shipping_volume,
				'weight': str(product.weight or 0),
				'cost_rmb': str(product.cost_rmb or 0),
				'cost_aud': str(product.cost_aud or 0),
				'sea_shipping_cost': str(product.sea_shipping_cost or 0),
				'total_cost': str(product.total_cost or 0),
				'actual_price': str(product.actual_price or 0),
				'profit': str(product.profit or 0),
			}

			# BOM 组件列表
			bom_items = []
			for bom in product.bom_items.select_related('component'):
				bom_items.append({
					'component_id': bom.component.id,
					'name': bom.component.name_cn or bom.component.name_en or bom.component.sku,
					'quantity': bom.quantity
				})

			return JsonResponse({'success': True, 'product': product_data, 'bom_items': bom_items})
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
			product.type = data['type']
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

			# 清空旧的 BOM
			ProductBOM.objects.filter(product=product).delete()

			# 添加新的 BOM
			for item in data.get('bom_items', []):
				component_id = int(item['component_id'])
				quantity = int(item['quantity'])
				if component_id and quantity > 0:
					ProductBOM.objects.create(
						product=product,
						component_id=component_id,
						quantity=quantity
					)

			return JsonResponse({'success': True})
		except Product.DoesNotExist:
			return JsonResponse({'success': False, 'error': '未找到产品'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

def search_products(request):
	q = request.GET.get('q', '')
	only_type = request.GET.get('type', '')
	results = []

	if q:
		products = Product.objects.filter(
			Q(name_cn__icontains=q) |
			Q(name_en__icontains=q) |
			Q(barcode__icontains=q) |
			Q(sku__icontains=q)
		)

		if only_type:
			products = products.filter(type=only_type)

		products = products[:50]

		results = [
			{
				'id': p.id,
				'name_cn': p.name_cn,
				'name_en': p.name_en,
				'barcode': p.barcode,
				'sku': p.sku
			}
			for p in products
		]

	return JsonResponse({'results': results})

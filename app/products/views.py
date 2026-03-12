from django.shortcuts import render
from ..products.models import Product
from ..products.models import ProductBOM

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from decimal import Decimal, InvalidOperation
from django.db.models import Q
import openpyxl
import numbers

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

def clean_cell_text(value):
	if value is None:
		return ''
	if isinstance(value, numbers.Integral):
		return str(value)
	if isinstance(value, numbers.Real) and not isinstance(value, bool):
		if float(value).is_integer():
			return str(int(value))
		return format(value, 'f').rstrip('0').rstrip('.')
	return str(value).strip()

def normalize_sku(value):
	text = clean_cell_text(value)
	if not text:
		return ''
	return ''.join(text.split())

def upsert_product_by_sku(sku, defaults):
	product = Product.objects.filter(sku=sku).first()
	if not product:
		return Product.objects.create(sku=sku, **defaults), True

	for field, value in defaults.items():
		if value in ['', None] and getattr(product, field) not in ['', None]:
			continue
		setattr(product, field, value)
	product.save()
	return product, False

@csrf_exempt
def import_products(request):
	if not request.user.is_superuser:
		return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

	if request.method != 'POST':
		return JsonResponse({'success': False, 'error': 'Invalid method'})

	upload = request.FILES.get('file')
	if not upload:
		return JsonResponse({'success': False, 'error': 'Please upload an Excel file'})

	try:
		workbook = openpyxl.load_workbook(upload, data_only=True)
		sheet = workbook.active

		parent_rows = {}
		current_parent_sku = ''
		current_parent_barcode = ''
		for row in sheet.iter_rows(min_row=3, values_only=True):
			sku = normalize_sku(row[1] if len(row) > 1 else '')
			parent_barcode = clean_cell_text(row[2] if len(row) > 2 else '')
			bom_sku = normalize_sku(row[3] if len(row) > 3 else '')
			bom_barcode = clean_cell_text(row[4] if len(row) > 4 else '')
			length = clean_cell_text(row[5] if len(row) > 5 else '')
			width = clean_cell_text(row[6] if len(row) > 6 else '')
			height = clean_cell_text(row[7] if len(row) > 7 else '')
			cbn = clean_cell_text(row[8] if len(row) > 8 else '')
			weight = clean_cell_text(row[9] if len(row) > 9 else '')

			if not sku and not bom_sku:
				continue

			if sku:
				parent_sku = sku
				current_parent_sku = sku
				current_parent_barcode = parent_barcode
			else:
				if not current_parent_sku:
					continue
				parent_sku = current_parent_sku
				parent_barcode = parent_barcode or current_parent_barcode

			entry = parent_rows.setdefault(parent_sku, {
				'sku': parent_sku,
				'barcode': parent_barcode,
				'rows': [],
			})
			if parent_barcode and not entry['barcode']:
				entry['barcode'] = parent_barcode
			entry['rows'].append({
				'bom_sku': bom_sku or parent_sku,
				'bom_barcode': bom_barcode,
				'length': length,
				'width': width,
				'height': height,
				'cbn': cbn,
				'weight': weight,
			})

		created_count = 0
		updated_count = 0
		bom_relation_count = 0

		for parent_sku, entry in parent_rows.items():
			rows = entry['rows']
			with_bom = any(item['bom_sku'] and item['bom_sku'] != parent_sku for item in rows)
			parent_barcode = entry['barcode']

			parent_row = None
			for item in rows:
				if item['bom_sku'] == parent_sku:
					parent_row = item
					break
			if parent_row is None and rows:
				parent_row = rows[0]

			parent_defaults = {
				'name_cn': '',
				'name_en': '',
				'type': '成品(有BOM)' if with_bom else '成品(无BOM)',
				'category': '',
				'manufacturer': '',
				'barcode': parent_barcode,
				'package_length': parent_row['length'] if parent_row and not with_bom else '',
				'package_width': parent_row['width'] if parent_row and not with_bom else '',
				'package_height': parent_row['height'] if parent_row and not with_bom else '',
				'shipping_volume': parent_row['cbn'] if parent_row and not with_bom else '',
				'weight': parse_decimal(parent_row['weight']) if parent_row and not with_bom else Decimal('0'),
			}
			parent_product, created = upsert_product_by_sku(parent_sku, parent_defaults)
			if created:
				created_count += 1
			else:
				updated_count += 1

			ProductBOM.objects.filter(product=parent_product).delete()

			if not with_bom:
				continue

			component_counter = {}
			component_rows = {}
			for item in rows:
				component_sku = item['bom_sku']
				if not component_sku or component_sku == parent_sku:
					continue
				component_counter[component_sku] = component_counter.get(component_sku, 0) + 1
				component_rows.setdefault(component_sku, item)

			for component_sku, quantity in component_counter.items():
				component_row = component_rows[component_sku]
				component_defaults = {
					'name_cn': '',
					'name_en': '',
					'type': '组件',
					'category': '',
					'manufacturer': '',
					'barcode': component_row['bom_barcode'],
					'package_length': component_row['length'],
					'package_width': component_row['width'],
					'package_height': component_row['height'],
					'shipping_volume': component_row['cbn'],
					'weight': parse_decimal(component_row['weight']),
				}
				component_product, created = upsert_product_by_sku(component_sku, component_defaults)
				if created:
					created_count += 1
				else:
					updated_count += 1

				ProductBOM.objects.create(
					product=parent_product,
					component=component_product,
					quantity=quantity,
				)
				bom_relation_count += 1

		return JsonResponse({
			'success': True,
			'created_count': created_count,
			'updated_count': updated_count,
			'bom_relation_count': bom_relation_count,
			'product_count': len(parent_rows),
		})
	except Exception as e:
		return JsonResponse({'success': False, 'error': str(e)})

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
			if request.user.is_staff or request.user.is_superuser:
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

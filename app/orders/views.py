from django.shortcuts import render
import builtins
from ..orders.models import Order, OrderLine
from ..products.models import Product
from ..stocks.models import Stock
from .constants import ORDER_STATUS, ORDER_ROUTE_RECORD, ORDER_WOO_STATUS

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, CharField
from django.db.models.functions import Cast
import json
import re

import csv
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from ..orders.cron import push_order_to_wc, sync_woo_order_completed
from ..services.shippit_client import get_shipping_quote, build_parcel_attributes, normalize_parcel_attributes
from ..orders.cron import sync_wc_orders

def parse_bool(value):
	if isinstance(value, bool):
		return value
	if value is None:
		return False
	return str(value).strip().lower() in ['1', 'true', 'yes', 'on']

def _clean_param(request, key):
	return (request.GET.get(key) or '').strip()

def _parse_decimal_value(value):
	if value is None:
		return None
	try:
		return Decimal(str(value).replace(',', '').strip())
	except (InvalidOperation, ValueError, TypeError):
		return None

def _apply_text_filter(queryset, field, raw):
	if not raw:
		return queryset
	return queryset.filter(**{f'{field}__icontains': raw})

def _apply_number_filter(queryset, field, raw):
	raw = (raw or '').strip()
	if not raw:
		return queryset

	op_match = re.match(r'^(<=|>=|<|>|=|!=)\s*(.+)$', raw)
	range_match = re.match(r'^(.+?)(?:\.\.|-)(.+)$', raw)

	if op_match:
		op, rhs_raw = op_match.groups()
		rhs = _parse_decimal_value(rhs_raw)
		if rhs is None:
			return queryset

		if op == '!=':
			return queryset.exclude(**{field: rhs})

		lookup_map = {
			'<=': 'lte',
			'>=': 'gte',
			'<': 'lt',
			'>': 'gt',
			'=': 'exact',
		}
		lookup = lookup_map.get(op)
		if not lookup:
			return queryset
		return queryset.filter(**{f'{field}__{lookup}': rhs})

	if range_match:
		left_raw, right_raw = range_match.groups()
		left = _parse_decimal_value(left_raw)
		right = _parse_decimal_value(right_raw)
		if left is None or right is None:
			return queryset
		low = min(left, right)
		high = max(left, right)
		return queryset.filter(**{f'{field}__gte': low, f'{field}__lte': high})

	value = _parse_decimal_value(raw)
	if value is None:
		return queryset
	return queryset.filter(**{field: value})

def _apply_date_filter(queryset, field, raw):
	raw = (raw or '').strip()
	if not raw:
		return queryset

	def parse_token(token):
		token = (token or '').strip()
		if re.fullmatch(r'\d{4}', token):
			return ('year', int(token))
		if re.fullmatch(r'\d{4}-\d{2}', token):
			year, month = token.split('-')
			return ('month', int(year), int(month))
		d = parse_date(token)
		if d:
			return ('date', d)
		return None

	def apply_exact(qs, parsed):
		kind = parsed[0]
		if kind == 'year':
			return qs.filter(**{f'{field}__year': parsed[1]})
		if kind == 'month':
			return qs.filter(**{f'{field}__year': parsed[1], f'{field}__month': parsed[2]})
		return qs.filter(**{f'{field}__date': parsed[1]})

	def apply_exclude_exact(qs, parsed):
		kind = parsed[0]
		if kind == 'year':
			return qs.exclude(**{f'{field}__year': parsed[1]})
		if kind == 'month':
			return qs.exclude(**{f'{field}__year': parsed[1], f'{field}__month': parsed[2]})
		return qs.exclude(**{f'{field}__date': parsed[1]})

	def token_as_date(parsed):
		kind = parsed[0]
		if kind == 'date':
			return parsed[1]
		return None

	op_match = re.match(r'^(<=|>=|<|>|=|!=)\s*(.+)$', raw)
	range_match = re.match(r'^(.+?)\.\.(.+)$', raw)
	if not range_match:
		range_match = re.match(r'^(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})$', raw)

	if op_match:
		op, rhs_raw = op_match.groups()
		parsed = parse_token(rhs_raw)
		if not parsed:
			return queryset
		if op == '=':
			return apply_exact(queryset, parsed)
		if op == '!=':
			return apply_exclude_exact(queryset, parsed)

		rhs_date = token_as_date(parsed)
		if rhs_date is None:
			return queryset

		lookup_map = {
			'<=': 'lte',
			'>=': 'gte',
			'<': 'lt',
			'>': 'gt',
		}
		lookup = lookup_map.get(op)
		if not lookup:
			return queryset
		return queryset.filter(**{f'{field}__date__{lookup}': rhs_date})

	if range_match:
		left_raw, right_raw = range_match.groups()
		left_parsed = parse_token(left_raw)
		right_parsed = parse_token(right_raw)
		left_date = token_as_date(left_parsed) if left_parsed else None
		right_date = token_as_date(right_parsed) if right_parsed else None
		if left_date is None or right_date is None:
			return queryset
		low = min(left_date, right_date)
		high = max(left_date, right_date)
		return queryset.filter(**{f'{field}__date__gte': low, f'{field}__date__lte': high})

	parsed = parse_token(raw)
	if not parsed:
		# Fallback to substring matching (similar to previous frontend behavior),
		# e.g. input "22" can match datetimes whose rendered value contains "22".
		alias = f'_{field}_str'
		return queryset.annotate(**{alias: Cast(field, CharField())}).filter(**{f'{alias}__icontains': raw})
	return apply_exact(queryset, parsed)

def list(request):
	orders = Order.objects.all()
	needs_distinct = False

	for field in ['reference', 'contact_name', 'phone', 'suburb', 'postcode', 'state', 'special_fees', 'customer_notes', 'notes']:
		orders = _apply_text_filter(orders, field, _clean_param(request, field))

	orders = _apply_date_filter(orders, 'date', _clean_param(request, 'date'))
	orders = _apply_number_filter(orders, 'total', _clean_param(request, 'total'))
	orders = _apply_number_filter(orders, 'shipping', _clean_param(request, 'shipping'))

	woo_status = _clean_param(request, 'woo_status')
	if woo_status:
		orders = orders.filter(woo_status=woo_status)

	route_record = _clean_param(request, 'route_record')
	if route_record:
		orders = orders.filter(route_record=route_record)

	status_param_present = 'status' in request.GET
	status = _clean_param(request, 'status')
	if status_param_present:
		if status == 'Open':
			orders = orders.exclude(status__in=['Completed', 'Cancelled'])
		elif status:
			orders = orders.filter(status=status)
	else:
		orders = orders.exclude(status__in=['Completed', 'Cancelled'])

	products = _clean_param(request, 'products')
	if products:
		orders = orders.filter(
			Q(lines__raw_sku__icontains=products) |
			Q(lines__product__sku__icontains=products) |
			Q(lines__product__barcode__icontains=products) |
			Q(lines__product__name_cn__icontains=products) |
			Q(lines__product__name_en__icontains=products)
		)
		needs_distinct = True

	if needs_distinct:
		orders = orders.distinct()

	orders = orders.prefetch_related('lines').order_by('-date')

	return render(request, 'orders/list.html', {
		'orders': orders,
		'woo_statuses': ORDER_WOO_STATUS,
		'statuses': ORDER_STATUS,
		'route_records': ORDER_ROUTE_RECORD,
	})

@csrf_exempt
def create_order(request):
	if request.method == 'POST':
		data = json.loads(request.body)
		reference = data.get('reference')
		contact_name = data.get('contact_name')
		phone = data.get('phone')
		email = data.get('email')
		address = data.get('address')
		suburb = data.get('suburb')
		postcode = data.get('postcode')
		state = data.get('state')
		route_record = data.get('route_record')
		notes = data.get('notes')
		customer_notes = data.get('customer_notes', '')
		status = data.get('status')
		urgent = parse_bool(data.get('urgent', False))
		date = data.get('date')
		tracking_number = data.get('tracking_number', '')
		delivery_date = data.get('delivery_date', '')
		parcel_attributes = normalize_parcel_attributes(data.get('parcel_attributes'))
		if delivery_date == '':
			delivery_date = '1970-01-01'
		products = data.get('products', [])

		meta = {}
		if parcel_attributes:
			meta['parcel_attributes'] = parcel_attributes
		order = Order.objects.create(reference=reference, date=date, contact_name=contact_name, phone=phone, email=email, 
			address=address, suburb=suburb, postcode=postcode, state=state, route_record=route_record, notes=notes, customer_notes=customer_notes, status=status, urgent=urgent, tracking_number=tracking_number, delivery_date=delivery_date, meta=meta or None)

		for item in products:
			product = Product.objects.filter(id=item.get('product_id')).first()
			OrderLine.objects.create(
				order=order,
				product=product,
				quantity=item.get('quantity', 0)
			)

		Stock.recalculate_all()
		push_order_to_wc(order.id)
		return JsonResponse({'success': True})

	return JsonResponse({'success': False, 'error': 'Invalid method'})

@csrf_exempt
def delete_order(request, id):
	if request.method == 'POST':
		try:
			order = Order.objects.filter(id=id).first()
			if not order:
				return JsonResponse({'success': False, 'error': '未找到订单'})

			order.delete()
			Stock.recalculate_all()
			return JsonResponse({'success': True})
		
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

@csrf_exempt
def order_detail(request, id):
	if request.method == 'GET':
		try:
			order = Order.objects.get(id=id)
			lines = order.lines.all()

			if order.delivery_date and order.delivery_date.strftime('%Y-%m-%d') == '1970-01-01':
				order.delivery_date = None

			data = {
				'id': order.id,
				'reference': order.reference,
				'date': str(order.date),
				'contact_name': order.contact_name,
				'phone': order.phone,
				'email': order.email,
				'address': order.address,
				'suburb': order.suburb,
				'postcode': order.postcode,
				'state': order.state,
				'route_record': order.route_record,
				'notes': order.notes,
				'customer_notes': order.customer_notes,
				'status': order.status,
				'urgent': order.urgent,
				'tracking_number': order.tracking_number,
				'delivery_date': order.delivery_date,
				'parcel_attributes': normalize_parcel_attributes((order.meta or {}).get('parcel_attributes')) or build_parcel_attributes(order),
				'products': [
					{
						'product_id': line.product.id if line.product else '',
						'name': line.product.name_cn if line.product else '',
						'barcode': line.product.barcode if line.product else '',
						'sku': line.product.sku if line.product else line.raw_sku,
						'quantity': line.quantity,
					} for line in lines
				]
			}
			return JsonResponse({'success': True, 'order': data})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return JsonResponse({'success': False, 'error': '仅支持 GET 请求'})

@csrf_exempt
def update_order(request, id):
	if request.method == 'POST':
		try:
			data = json.loads(request.body)

			reference = data.get('reference')
			date = data.get('date')
			contact_name = data.get('contact_name')
			phone = data.get('phone')
			email = data.get('email')
			address = data.get('address')
			suburb = data.get('suburb')
			postcode = data.get('postcode')
			state = data.get('state')
			route_record = data.get('route_record')
			notes = data.get('notes')
			customer_notes = data.get('customer_notes', '')
			status = data.get('status')
			urgent = parse_bool(data.get('urgent', False))
			tracking_number = data.get('tracking_number', '')
			delivery_date = data.get('delivery_date', '')
			parcel_attributes = normalize_parcel_attributes(data.get('parcel_attributes'))
			if delivery_date == '':
				delivery_date = '1970-01-01'
			products = data.get('products', [])

			order = Order.objects.get(id=id)
			order.reference = reference
			order.date = date
			order.contact_name = contact_name
			order.phone = phone
			order.email = email
			order.address = address
			order.suburb = suburb
			order.postcode = postcode
			order.state = state
			order.route_record = route_record
			order.notes = notes
			order.customer_notes = customer_notes
			order.status = status
			order.urgent = urgent
			order.tracking_number = tracking_number
			order.delivery_date = delivery_date
			meta = order.meta if isinstance(order.meta, dict) else {}
			if parcel_attributes:
				meta['parcel_attributes'] = parcel_attributes
			else:
				meta.pop('parcel_attributes', None)
			order.meta = meta or None
			order.save()

			# 删除旧的明细行
			order.lines.all().delete()

			# 添加新的明细行
			for item in products:
				product = None
				product_id = item.get('product_id')
				quantity = item.get('quantity', 0)

				if product_id:
					product = Product.objects.filter(id=product_id).first()

				OrderLine.objects.create(
					order=order,
					product=product,
					raw_sku=item.get('sku', ''),
					quantity=quantity
				)

			Stock.recalculate_all()
			if order.status == "Completed":
				sync_woo_order_completed(order)
			return JsonResponse({'success': True})

		except Order.DoesNotExist:
			return JsonResponse({'success': False, 'error': '未找到订单'})
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

@csrf_exempt
def batch_update_order(request):
	if request.method != 'POST':
		return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

	try:
		data = json.loads(request.body or '{}')
	except json.JSONDecodeError:
		return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})

	raw_ids = data.get('ids') or []
	status = (data.get('status') or '').strip()

	if not isinstance(raw_ids, builtins.list):
		return JsonResponse({'success': False, 'error': '订单ID格式错误'}, status=400)

	id_list = []
	for item in raw_ids:
		try:
			id_list.append(int(item))
		except (TypeError, ValueError):
			continue
	id_list = tuple(dict.fromkeys(id_list))

	if not id_list:
		return JsonResponse({'success': False, 'error': '请先勾选要更新的订单'}, status=400)

	valid_status_values = {value for value, _ in ORDER_STATUS}
	if status not in valid_status_values:
		return JsonResponse({'success': False, 'error': '请选择有效的订单状态'}, status=400)

	orders = Order.objects.filter(id__in=id_list)
	if not orders:
		return JsonResponse({'success': False, 'error': '未找到可更新的订单'}, status=404)

	updated_count = 0
	for order in orders:
		if order.status == status:
			continue
		order.status = status
		order.save(update_fields=['status'])
		updated_count += 1

	return JsonResponse({
		'success': True,
		'updated_count': updated_count,
		'matched_count': len(orders),
	})

@csrf_exempt
def _export_orders_excel_response(orders, filename):
	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = 'Order Export'

	headers = [
		'Order No',
		'Order Date',
		'Status',
		'Woo Status',
		'Customer',
		'Phone',
		'Email',
		'Address',
		'Suburb',
		'Postcode',
		'State',
		'Products',
		'Total',
		'Shipping',
		'Special Fee',
		'Tracking No',
		'Delivery Date',
		'Route Record',
		'Customer Notes',
		'Notes',
	]
	ws.append(headers)
	woo_status_map = dict(ORDER_WOO_STATUS)

	for order in orders:
		order_dt = order.date
		if order_dt and timezone.is_aware(order_dt):
			order_dt = timezone.localtime(order_dt)
		delivery_date_str = ''
		if order.delivery_date and order.delivery_date.strftime('%Y-%m-%d') != '1970-01-01':
			delivery_date_str = order.delivery_date.strftime('%Y-%m-%d')
		product_lines = '\n'.join([
			f'{(line.raw_sku or (line.product.sku if (line.product and line.product.sku) else ""))} x {line.quantity}'
			for line in order.lines.all()
		])

		ws.append([
			order.reference or '',
			order_dt.strftime('%Y-%m-%d %H:%M:%S') if order_dt else '',
			order.status or '',
			woo_status_map.get(order.woo_status, order.woo_status or ''),
			order.contact_name or '',
			order.phone or '',
			order.email or '',
			order.address or '',
			order.suburb or '',
			order.postcode or '',
			order.state or '',
			product_lines,
			str(order.total or ''),
			str(order.shipping or ''),
			order.special_fees or '',
			order.tracking_number or '',
			delivery_date_str,
			order.route_record or '',
			order.customer_notes or '',
			order.notes or '',
		])

	header_font = Font(name='Arial', size=11, bold=True)
	body_font = Font(name='Arial', size=10)
	alignment = Alignment(vertical='top', wrap_text=True)
	header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

	for row_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column), start=1):
		for cell in row:
			cell.font = header_font if row_idx == 1 else body_font
			cell.alignment = header_alignment if row_idx == 1 else alignment

	ws.freeze_panes = 'A2'

	def text_width(val):
		return sum(2 if ord(c) > 127 else 1 for c in str(val))

	for col in ws.columns:
		max_length = 0
		col_letter = get_column_letter(col[0].column)
		for cell in col:
			if cell.value:
				max_length = max(max_length, text_width(cell.value))
		ws.column_dimensions[col_letter].width = max(12, min((max_length + 2) * 1.1, 60))

	for i in range(2, ws.max_row + 1):
		ws.row_dimensions[i].height = 36

	response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	wb.save(response)
	return response


@csrf_exempt
def export_orders(request):
	ids = (request.GET.get('ids') or '').strip()
	if ids:
		export_type = (request.GET.get('export_type') or '').strip().lower()
		if export_type == 'orders':
			id_list = [int(x) for x in ids.split(',') if x.isdigit()]
			if not id_list:
				return JsonResponse({'success': False, 'error': '请先选择要导出的订单'}, status=400)

			orders = (
				Order.objects
				.filter(id__in=id_list)
				.order_by('date', 'id')
				.prefetch_related('lines')
			)
			filename = f'orders_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.xlsx'
			return _export_orders_excel_response(orders, filename)
		return export_orders_delivery(request)

	start_date_raw = (request.GET.get('start_date') or '').strip()
	end_date_raw = (request.GET.get('end_date') or '').strip()
	start_date = parse_date(start_date_raw) if start_date_raw else None
	end_date = parse_date(end_date_raw) if end_date_raw else None

	if not start_date or not end_date:
		return JsonResponse({'success': False, 'error': '请提供开始日期和结束日期'}, status=400)

	if start_date > end_date:
		return JsonResponse({'success': False, 'error': '开始日期不能晚于结束日期'}, status=400)

	orders = (
		Order.objects
		.filter(date__date__gte=start_date, date__date__lte=end_date)
		.order_by('date', 'id')
		.prefetch_related('lines')
	)

	filename = f'orders_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.xlsx'
	return _export_orders_excel_response(orders, filename)

@csrf_exempt
def export_orders_delivery(request):
	ids = request.GET.get('ids', '')
	id_list = [int(x) for x in ids.split(',') if x.isdigit()]

	if not id_list:
		return JsonResponse({'success': False, 'error': '请先选择要导出的订单'}, status=400)

	orders = Order.objects.filter(id__in=id_list).prefetch_related('lines')

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = 'Orders'

	font = Font(name='Arial', size=14)
	alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

	from openpyxl.styles import Border, Side
	thin_border = Border(
		left=Side(style='thin'),
		right=Side(style='thin'),
		top=Side(style='thin'),
		bottom=Side(style='thin')
	)

	# 行高
	for i in range(1, len(orders) + 10):
		ws.row_dimensions[i].height = 74.25

	# 抬头日期（次日）
	header_date = (timezone.localtime() + timedelta(days=1)).strftime('%m-%d-%Y')
	ws.append(['DELIVERY LIST'] + [''] * 11 + ['DATE', header_date])

	# 第二行：表头
	headers = [
		'NUMBER',
		'ITEM DESCRIPTION',
		'DELIVERY INSTRUCTION',
		'PACKAGE',
		'CUSTOMER NAME',
		'CONTACT NO.',
		'ADDRESS',
		'SUBURB',
		'POST CODE',
		'STATE',
		'Invoice No.',
		'NOTE',
		'SIGNATURE OF RECEIPIENT',
		'DATE',
	]
	ws.append(headers)

	# 数据行
	for order in orders:
		product_lines = '\n'.join([
			f'{line.raw_sku} × {line.quantity}'
			for line in order.lines.all()
		])

		packages = []
		for line in order.lines.all():
			product = line.product
			if not product:
				packages.append(f'{line.raw_sku} x {line.quantity}')
				continue

			bom_items = product.bom_items.select_related('component').all()
			if bom_items.exists():
				for bom in bom_items:
					packages.append(f'{bom.component.sku} × {bom.quantity * line.quantity}')
			else:
				packages.append(f'{product.sku} × {line.quantity}')
		packages = '\n'.join(packages)

		ws.append([
			order.reference,
			product_lines,
			'',
			packages,
			order.contact_name or '',
			order.phone or '',
			order.address or '',
			order.suburb or '',
			order.postcode or '',
			order.state or '',
			'',
			order.notes or '',
			'',
			header_date
		])

	# 样式 + 边框
	for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
		for cell in row:
			cell.font = font
			cell.alignment = alignment
			cell.border = thin_border

	# 列宽自适应（考虑中文宽度）
	def text_width(val):
		return sum(2 if ord(c) > 127 else 1 for c in str(val))

	for col in ws.columns:
		max_length = 0
		col_letter = get_column_letter(col[0].column)
		for cell in col:
			if cell.value:
				val_length = text_width(cell.value)
				if val_length > max_length:
					max_length = val_length
		adjusted_width = max(15, min((max_length + 2) * 1.2, 50))
		ws.column_dimensions[col_letter].width = adjusted_width

	# 页面设置
	ws.sheet_properties.pageSetUpPr.fitToPage = True
	ws.page_setup.fitToHeight = False
	ws.page_setup.fitToWidth = 1
	ws.page_setup.scale = 55
	ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE

	filename = f'delivery_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.xlsx'
	response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	wb.save(response)

	return response

@csrf_exempt
def shipping_quotes(request, id):
	try:
		result = get_shipping_quote(id)
		if not result:
			return JsonResponse({'success': False, 'error': '未获取到任何报价'})
		return JsonResponse({
			'success': True,
			'quotes': result['all'],
			'best': result['best'],
			'parcel_attributes': result['parcel_attributes'],
		})
	except Exception as e:
		return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
def sync_orders(request):
	if request.method == 'POST':
		try:
			sync_wc_orders()
			return JsonResponse({'success': True})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

from django.shortcuts import render
from ..orders.models import Order, OrderLine
from ..products.models import Product
from ..stocks.models import Stock
from .constants import ORDER_STATUS, ORDER_ROUTE_RECORD

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

import csv
from django.http import HttpResponse
from django.utils import timezone
from datetime import timedelta

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

def list(request):
	orders = Order.objects.order_by('-date')
	return render(request, 'orders/list.html', {'orders': orders, 'statuses': ORDER_STATUS, 'route_records': ORDER_ROUTE_RECORD})

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
		date = data.get('date')
		products = data.get('products', [])

		order = Order.objects.create(reference=reference, date=date, contact_name=contact_name, phone=phone, email=email, 
			address=address, suburb=suburb, postcode=postcode, state=state, route_record=route_record, notes=notes, customer_notes=customer_notes, status=status)

		for item in products:
			product = Product.objects.filter(id=item.get('product_id')).first()
			OrderLine.objects.create(
				order=order,
				product=product,
				quantity=item.get('quantity', 0)
			)

		Stock.recalculate_all()
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
				'products': [
					{
						'product_id': line.product.id if line.product else '',
						'name': line.product.name_cn if line.product else '',
						'quantity': line.quantity,
						'sku': line.product.sku if line.product else line.raw_sku,
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
			return JsonResponse({'success': True})

		except Order.DoesNotExist:
			return JsonResponse({'success': False, 'error': '未找到订单'})
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

@csrf_exempt
def export_orders(request):
	ids = request.GET.get('ids', '')
	id_list = [int(x) for x in ids.split(',') if x.isdigit()]

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
		product_lines = '; '.join([
			f'{line.display_name()} × {line.quantity}'
			for line in order.lines.all()
		])

		ws.append([
			order.reference,
			product_lines,
			'',
			'',
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

	filename = f'orders_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.xlsx'
	response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	wb.save(response)

	return response

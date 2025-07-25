from django.shortcuts import render
from ..orders.models import Order, OrderLine
from ..products.models import Product
from ..stocks.models import Stock

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.forms.models import model_to_dict

def list(request):
	orders = Order.objects.all()
	return render(request, 'orders/list.html', {'orders': orders})

@csrf_exempt
def create_order(request):
	if request.method == 'POST':
		data = json.loads(request.body)
		reference = data.get('reference')
		contact_name = data.get('contact_name')
		address = data.get('address')
		route_record = data.get('route_record')
		notes = data.get('notes')
		status = data.get('status')
		date = data.get('date')
		products = data.get('products', [])

		order = Order.objects.create(reference=reference, date=date, contact_name=contact_name, 
			address=address, route_record=route_record, notes=notes, status=status)

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
				'address': order.address,
				'route_record': order.route_record,
				'notes': order.notes,
				'status': order.status,
				'products': [
					{
						'product_id': line.product.id,
						'name': line.product.name_cn,
						'quantity': line.quantity
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
			address = data.get('address')
			route_record = data.get('route_record')
			notes = data.get('notes')
			status = data.get('status')
			products = data.get('products', [])

			order = Order.objects.get(id=id)
			order.reference = reference
			order.date = date
			order.contact_name = contact_name
			order.address = address
			order.route_record = route_record
			order.notes = notes
			order.status = status
			order.save()

			# 删除旧的明细行
			order.lines.all().delete()

			# 添加新的明细行
			for item in products:
				product_id = item.get('product_id')
				quantity = item.get('quantity', 0)

				if product_id:
					try:
						product = Product.objects.get(id=product_id)
						OrderLine.objects.create(
							order=order,
							product=product,
							quantity=quantity
						)
					except Product.DoesNotExist:
						continue  # 如果产品ID无效，就跳过这条

			Stock.recalculate_all()
			return JsonResponse({'success': True})

		except Order.DoesNotExist:
			return JsonResponse({'success': False, 'error': '未找到订单单'})
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

from django.shortcuts import render
from ..inbounds.models import Inbound, InboundLine
from ..products.models import Product
from ..stocks.models import Stock
from ..stocks.constants import STOCK_WAREHOUSE

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.forms.models import model_to_dict

def list(request):
	inbounds = Inbound.objects.all().order_by('-date')
	return render(request, 'inbounds/list.html', {'inbounds': inbounds, 'warehouses': STOCK_WAREHOUSE})

@csrf_exempt
def create_inbound(request):
	if request.method == 'POST':
		data = json.loads(request.body)
		warehouse = data.get('warehouse')
		reference = data.get('reference')
		date = data.get('date')
		products = data.get('products', [])

		inbound = Inbound.objects.create(warehouse=warehouse, reference=reference, date=date)

		for item in products:
			product = Product.objects.filter(id=item.get('product_id')).first()
			InboundLine.objects.create(
				inbound=inbound,
				product=product,
				quantity=item.get('quantity', 0)
			)

		Stock.recalculate_all()
		return JsonResponse({'success': True})

	return JsonResponse({'success': False, 'error': 'Invalid method'})

@csrf_exempt
def delete_inbound(request, id):
	if request.method == 'POST':
		try:
			inbound = Inbound.objects.filter(id=id).first()
			if not inbound:
				return JsonResponse({'success': False, 'error': '未找到入库'})

			inbound.delete()
			Stock.recalculate_all()
			return JsonResponse({'success': True})
		
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

@csrf_exempt
def inbound_detail(request, id):
	if request.method == 'GET':
		try:
			inbound = Inbound.objects.get(id=id)
			lines = inbound.lines.all()

			data = {
				'id': inbound.id,
				'warehouse': inbound.warehouse,
				'reference': inbound.reference,
				'date': str(inbound.date),
				'products': [
					{
						'product_id': line.product.id,
						'name': line.product.name_cn,
						'quantity': line.quantity,
						'sku': line.product.sku
					} for line in lines
				]
			}
			return JsonResponse({'success': True, 'inbound': data})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})
	
	return JsonResponse({'success': False, 'error': '仅支持 GET 请求'})

@csrf_exempt
def update_inbound(request, id):
	if request.method == 'POST':
		try:
			data = json.loads(request.body)

			warehouse = data.get('warehouse')
			reference = data.get('reference')
			date = data.get('date')
			products = data.get('products', [])

			inbound = Inbound.objects.get(id=id)
			inbound.warehouse = warehouse
			inbound.reference = reference
			inbound.date = date
			inbound.save()

			# 删除旧的明细行
			inbound.lines.all().delete()

			# 添加新的明细行
			for item in products:
				product_id = item.get('product_id')
				quantity = item.get('quantity', 0)

				if product_id:
					try:
						product = Product.objects.get(id=product_id)
						InboundLine.objects.create(
							inbound=inbound,
							product=product,
							quantity=quantity
						)
					except Product.DoesNotExist:
						continue  # 如果产品ID无效，就跳过这条

			Stock.recalculate_all()
			return JsonResponse({'success': True})

		except Inbound.DoesNotExist:
			return JsonResponse({'success': False, 'error': '未找到入库单'})
		except json.JSONDecodeError:
			return JsonResponse({'success': False, 'error': '无效的 JSON 格式'})
		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

	return JsonResponse({'success': False, 'error': '仅支持 POST 请求'})

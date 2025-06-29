from django.shortcuts import render
from ..stocks.models import Stock
from ..inbounds.models import InboundLine
from ..orders.models import OrderLine

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def list(request):
	stocks = Stock.objects.all()
	return render(request, 'stocks/list.html', {'stocks': stocks})

@csrf_exempt
def stock_detail(request, id):
	if request.method == 'GET':
		try:
			stock = Stock.objects.get(id=id)
			product = stock.product

			# 获取入库记录
			inbound_lines = InboundLine.objects.filter(product=product).select_related('inbound')
			inbound_data = [
				{
					'type': '入库',
					'date': str(line.inbound.date),
					'reference': line.inbound.reference,
					'quantity': line.quantity
				}
				for line in inbound_lines
			]

			# 获取出库记录
			order_lines = OrderLine.objects.filter(product=product).select_related('order')
			order_data = [
				{
					'type': '出库',
					'date': str(line.order.date),
					'reference': line.order.reference,
					'quantity': -line.quantity
				}
				for line in order_lines
			]

			# 合并并按日期排序
			history = inbound_data + order_data
			history.sort(key=lambda x: x['date'])

			data = {
				'id': stock.id,
				'product': product.name_cn or product.name_en or product.sku,
				'current_quantity': stock.quantity,
				'history': history
			}
			return JsonResponse({'success': True, 'stock': data})

		except Exception as e:
			return JsonResponse({'success': False, 'error': str(e)})

	return JsonResponse({'success': False, 'error': '仅支持 GET 请求'})

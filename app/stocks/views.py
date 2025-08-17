from django.shortcuts import render
from ..stocks.models import Stock
from ..inbounds.models import InboundLine
from ..orders.models import OrderLine

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

import csv
from django.http import HttpResponse
from django.db.models import Q
from django.utils import timezone

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

def export_stocks(request):
	"""
	支持可选参数：
	?q=关键字（按中英文名/sku/条码模糊）
	?only_nonzero=1（只导出数量非0）
	"""
	q = (request.GET.get('q') or '').strip()
	only_nonzero = (request.GET.get('only_nonzero') or '').lower() in ('1', 'true', 'yes')

	qs = Stock.objects.select_related('product')
	if q:
		qs = qs.filter(
			Q(product__name_cn__icontains=q) |
			Q(product__name_en__icontains=q) |
			Q(product__sku__icontains=q) |
			Q(product__barcode__icontains=q)
		)
	if only_nonzero:
		qs = qs.exclude(quantity=0)

	qs = qs.order_by('product__name_cn', 'product__name_en', 'product__sku')

	filename = f'stocks_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv'
	response = HttpResponse(content_type='text/csv; charset=utf-8')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'

	# 写入 UTF-8 BOM，避免 Excel 中文乱码
	response.write('\ufeff')

	writer = csv.writer(response)
	writer.writerow(['产品', 'SKU', '条码', '数量'])

	for s in qs:
		p = s.product
		name = p.name_cn or p.name_en or ''
		writer.writerow([name, p.sku or '', p.barcode or '', s.quantity])

	return response
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ..orders.models import Order
from .constants import (
	AFTERSALE_ISSUE_CATEGORY,
	AFTERSALE_STATUS,
	DELIVERY_INFO_OPTIONS,
)
from .models import Aftersale

FILTER_FIELDS = [
	'order_date',
	'order_ref',
	'sku_summary',
	'issue',
	'result',
	'status',
	'remark',
	'issue_category',
	'delivery_info',
	'domestic_tracking',
	'product_optimization',
]

def _get_order_by_ref(order_ref):
	order_ref = (order_ref or '').strip()
	if not order_ref:
		return None
	return Order.objects.prefetch_related('lines__product').filter(reference=order_ref).first()


def _serialize_aftersale(item):
	order_dt = item.order.date
	if order_dt and timezone.is_aware(order_dt):
		order_dt = timezone.localtime(order_dt)

	return {
		'id': item.id,
		'order_ref': item.order.reference,
		'order_date': order_dt.strftime('%Y-%m-%d %H:%M:%S') if order_dt else '',
		'sku_summary': item.sku_summary(),
		'issue': item.issue or '',
		'result': item.result or '',
		'status': item.status or '',
		'remark': item.remark or '',
		'issue_category': item.issue_category or '',
		'delivery_info': item.delivery_info or '',
		'domestic_tracking': item.domestic_tracking or '',
		'product_optimization': item.product_optimization or '',
		'updated_at': timezone.localtime(item.updated_at).strftime('%Y-%m-%d %H:%M') if item.updated_at else '',
	}


def _list_queryset():
	return (
		Aftersale.objects
		.select_related('order')
		.prefetch_related('order__lines__product')
		.order_by('-created_at', '-id')
	)


def _build_list_context(**extra):
	context = {
		'aftersales': _list_queryset(),
		'filter_fields': FILTER_FIELDS,
		'status_options': AFTERSALE_STATUS,
		'issue_category_options': AFTERSALE_ISSUE_CATEGORY,
		'delivery_info_options': DELIVERY_INFO_OPTIONS,
	}
	context.update(extra)
	return context


def list(request):
	return render(request, 'aftersales/list.html', _build_list_context())


def create(request):
	error = ''
	default_order = None
	is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

	order_ref = (request.GET.get('order_ref') or '').strip()
	if order_ref:
		default_order = _get_order_by_ref(order_ref)

	if request.method == 'POST':
		order_ref = (request.POST.get('order_ref') or '').strip()
		issue = (request.POST.get('issue') or '').strip()
		result = (request.POST.get('result') or '').strip()
		status = (request.POST.get('status') or '').strip()
		remark = (request.POST.get('remark') or '').strip()
		issue_category = (request.POST.get('issue_category') or '').strip()
		delivery_info = (request.POST.get('delivery_info') or '').strip()
		domestic_tracking = (request.POST.get('domestic_tracking') or '').strip()
		product_optimization = (request.POST.get('product_optimization') or '').strip()

		order = _get_order_by_ref(order_ref)
		if not order:
			error = '订单号不存在'
		elif not issue:
			error = '问题不能为空'
		else:
			Aftersale.objects.create(
				order=order,
				issue=issue,
				result=result or None,
				status=status or None,
				remark=remark or None,
				issue_category=issue_category or None,
				delivery_info=delivery_info or None,
				domestic_tracking=domestic_tracking or None,
				product_optimization=product_optimization or None,
			)
			if is_ajax:
				return JsonResponse({'success': True})
			return redirect('aftersale_list')
		if is_ajax:
			return JsonResponse({'success': False, 'error': error}, status=400)

	return render(request, 'aftersales/list.html', _build_list_context(
		error=error,
		default_order=default_order,
	))


def detail_json(request, id):
	item = get_object_or_404(_list_queryset(), id=id)
	return JsonResponse({'success': True, 'aftersale': _serialize_aftersale(item)})


@csrf_exempt
def update(request, id):
	if request.method != 'POST':
		return JsonResponse({'success': False, 'error': '仅支持 POST 请求'}, status=405)

	item = get_object_or_404(_list_queryset(), id=id)
	order_ref = (request.POST.get('order_ref') or '').strip()
	issue = (request.POST.get('issue') or '').strip()
	result = (request.POST.get('result') or '').strip()
	status = (request.POST.get('status') or '').strip()
	remark = (request.POST.get('remark') or '').strip()
	issue_category = (request.POST.get('issue_category') or '').strip()
	delivery_info = (request.POST.get('delivery_info') or '').strip()
	domestic_tracking = (request.POST.get('domestic_tracking') or '').strip()
	product_optimization = (request.POST.get('product_optimization') or '').strip()

	order = _get_order_by_ref(order_ref)
	if not order:
		return JsonResponse({'success': False, 'error': '订单号不存在'}, status=400)
	if not issue:
		return JsonResponse({'success': False, 'error': '问题不能为空'}, status=400)

	item.order = order
	item.issue = issue
	item.result = result or None
	item.status = status or None
	item.remark = remark or None
	item.issue_category = issue_category or None
	item.delivery_info = delivery_info or None
	item.domestic_tracking = domestic_tracking or None
	item.product_optimization = product_optimization or None
	item.save()

	return JsonResponse({'success': True})

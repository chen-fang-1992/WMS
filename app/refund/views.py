from decimal import Decimal, InvalidOperation
import re

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from ..orders.models import Order
from .models import Refund
from .constants import (
	REFUND_STATUS,
	REFUND_STATUS_NEW,
	REFUND_STATUS_WIP,
	REFUND_STATUS_COMPLETED,
	REFUND_STATUS_CANCELLED,
	REFUND_ALLOWED_TRANSITIONS,
)


def _parse_decimal_value(value):
	if value is None:
		return None
	try:
		return Decimal(str(value).replace(',', '').strip())
	except (InvalidOperation, ValueError, TypeError):
		return None


def _generate_refund_no():
	prefix = timezone.localtime().strftime('RF%Y%m%d')
	last = Refund.objects.filter(refund_no__startswith=prefix).order_by('-refund_no').first()
	seq = 1
	if last and last.refund_no:
		match = re.search(r'-(\d+)$', last.refund_no)
		if match:
			seq = int(match.group(1)) + 1
	return f'{prefix}-{seq:04d}'


def list(request):
	refunds = Refund.objects.select_related('order').order_by('-created_at')

	return render(request, 'refund/list.html', {
		'refunds': refunds,
		'status_options': REFUND_STATUS,
	})


def create(request):
	error = ''
	default_order = None
	is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

	order_ref = (request.GET.get('order_ref') or '').strip()
	if order_ref:
		default_order = Order.objects.filter(reference=order_ref).first()

	if request.method == 'POST':
		order_ref = (request.POST.get('order_ref') or '').strip()
		amount_raw = (request.POST.get('amount') or '').strip()
		reason_detail = (request.POST.get('reason_detail') or '').strip()
		remark = (request.POST.get('remark') or '').strip()

		order = Order.objects.filter(reference=order_ref).first()
		amount = _parse_decimal_value(amount_raw)

		if not order:
			error = '订单号不存在'
		elif amount is None or amount <= 0:
			error = '金额必须大于 0'
		else:
			operator = request.user if getattr(request.user, 'is_authenticated', False) else None
			refund = Refund.objects.create(
				refund_no=_generate_refund_no(),
				order=order,
				status=REFUND_STATUS_NEW,
				amount=amount,
				reason_detail=reason_detail or None,
				remark=remark or None,
				created_by=operator,
				updated_by=operator,
			)
			if is_ajax:
				return JsonResponse({'success': True, 'id': refund.id, 'redirect_url': f'/refunds/detail/{refund.id}/'})
			return redirect('refund_detail', id=refund.id)
		if is_ajax:
			return JsonResponse({'success': False, 'error': error}, status=400)

	return render(request, 'refund/form.html', {'default_order': default_order, 'error': error})


def detail(request, id):
	refund = get_object_or_404(Refund.objects.select_related('order', 'created_by', 'updated_by'), id=id)
	return render(request, 'refund/detail.html', {
		'refund': refund,
		'status_options': REFUND_STATUS,
	})


def detail_json(request, id):
	refund = get_object_or_404(Refund.objects.select_related('order'), id=id)
	return JsonResponse({
		'success': True,
		'refund': {
			'id': refund.id,
			'refund_no': refund.refund_no,
			'order_ref': refund.order.reference,
			'status': refund.status,
			'amount': str(refund.amount),
			'reason_detail': refund.reason_detail or '',
			'remark': refund.remark or '',
			'cancel_reason': refund.cancel_reason or '',
			'updated_at': timezone.localtime(refund.updated_at).strftime('%Y-%m-%d %H:%M') if refund.updated_at else '',
		},
		'status_options': [{'value': v, 'label': l} for v, l in REFUND_STATUS],
	})


@csrf_exempt
def update(request, id):
	refund = get_object_or_404(Refund, id=id)
	if request.method != 'POST':
		return JsonResponse({'success': False, 'error': '仅支持 POST 请求'}, status=405)

	order_ref = (request.POST.get('order_ref') or '').strip()
	status = (request.POST.get('status') or '').strip()
	amount = _parse_decimal_value(request.POST.get('amount'))
	reason_detail = (request.POST.get('reason_detail') or '').strip()
	remark = (request.POST.get('remark') or '').strip()
	cancel_reason = (request.POST.get('cancel_reason') or '').strip()

	if not order_ref:
		return JsonResponse({'success': False, 'error': '订单号不能为空'}, status=400)
	order = Order.objects.filter(reference=order_ref).first()
	if not order:
		return JsonResponse({'success': False, 'error': '订单号不存在'}, status=400)

	if status not in dict(REFUND_STATUS):
		return JsonResponse({'success': False, 'error': '目标状态无效'}, status=400)

	if amount is None or amount <= 0:
		return JsonResponse({'success': False, 'error': '金额必须大于 0'}, status=400)

	if status != refund.status:
		if status not in REFUND_ALLOWED_TRANSITIONS.get(refund.status, []):
			return JsonResponse({'success': False, 'error': f'不允许从 {refund.status} 变更到 {status}'}, status=400)

	now = timezone.now()
	operator = request.user if getattr(request.user, 'is_authenticated', False) else None

	refund.order = order
	refund.status = status
	refund.amount = amount
	refund.reason_detail = reason_detail or None
	refund.remark = remark or None
	refund.updated_by = operator

	if status == REFUND_STATUS_COMPLETED:
		if not refund.completed_at:
			refund.completed_at = now
		refund.cancelled_at = None
		refund.cancel_reason = None
	elif status == REFUND_STATUS_CANCELLED:
		if not cancel_reason:
			return JsonResponse({'success': False, 'error': '状态为 Cancelled 时必须填写取消原因'}, status=400)
		refund.cancel_reason = cancel_reason
		if not refund.cancelled_at:
			refund.cancelled_at = now
		refund.completed_at = None
	else:
		refund.completed_at = None
		refund.cancelled_at = None
		refund.cancel_reason = None

	refund.save()
	return JsonResponse({'success': True})


@csrf_exempt
def update_status(request, id):
	refund = get_object_or_404(Refund, id=id)
	if request.method != 'POST':
		return JsonResponse({'success': False, 'error': '仅支持 POST 请求'}, status=405)

	target_status = (request.POST.get('status') or '').strip()
	cancel_reason = (request.POST.get('cancel_reason') or '').strip()
	remark = (request.POST.get('remark') or '').strip()

	if target_status not in dict(REFUND_STATUS):
		return JsonResponse({'success': False, 'error': '目标状态无效'}, status=400)

	if target_status not in REFUND_ALLOWED_TRANSITIONS.get(refund.status, []):
		return JsonResponse({'success': False, 'error': f'不允许从 {refund.status} 变更到 {target_status}'}, status=400)

	now = timezone.now()
	refund.status = target_status
	refund.remark = remark or refund.remark
	refund.updated_by = request.user if getattr(request.user, 'is_authenticated', False) else None

	if target_status == REFUND_STATUS_COMPLETED:
		refund.completed_at = now
	elif target_status == REFUND_STATUS_CANCELLED:
		if not cancel_reason:
			return JsonResponse({'success': False, 'error': '状态为 Cancelled 时必须填写取消原因'}, status=400)
		refund.cancel_reason = cancel_reason
		refund.cancelled_at = now

	refund.save()
	return JsonResponse({'success': True})


@csrf_exempt
def cancel(request, id):
	refund = get_object_or_404(Refund, id=id)
	if request.method != 'POST':
		return JsonResponse({'success': False, 'error': '仅支持 POST 请求'}, status=405)

	if refund.status not in [REFUND_STATUS_NEW, REFUND_STATUS_WIP]:
		return JsonResponse({'success': False, 'error': f'当前状态 {refund.status} 不允许取消'}, status=400)

	cancel_reason = (request.POST.get('cancel_reason') or '').strip()
	if not cancel_reason:
		return JsonResponse({'success': False, 'error': '取消原因不能为空'}, status=400)

	refund.status = REFUND_STATUS_CANCELLED
	refund.cancel_reason = cancel_reason
	refund.cancelled_at = timezone.now()
	refund.updated_by = request.user if getattr(request.user, 'is_authenticated', False) else None
	refund.save()
	return JsonResponse({'success': True})

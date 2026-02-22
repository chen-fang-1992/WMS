from django import template
from ..constants import ORDER_STATUS, ORDER_ROUTE_RECORD, ORDER_WOO_STATUS

register = template.Library()

@register.filter
def status_label(code):
	return dict(ORDER_STATUS).get(code, code)

@register.filter
def route_record_label(code):
	if not code:
		return ''
	return dict(ORDER_ROUTE_RECORD).get(code, code)

@register.filter
def woo_status_label(code):
	return dict(ORDER_WOO_STATUS).get(code, code)

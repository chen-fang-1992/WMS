from django import template
from ..constants import ORDER_STATUS, ORDER_ROUTE_RECORD

register = template.Library()

@register.filter
def status_label(code):
	return dict(ORDER_STATUS).get(code, code)

@register.filter
def route_record_label(code):
	return dict(ORDER_ROUTE_RECORD).get(code, code)

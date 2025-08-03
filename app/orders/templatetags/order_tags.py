from django import template
from ..constants import ORDER_STATUS

register = template.Library()

@register.filter
def status_label(code):
	return dict(ORDER_STATUS).get(code, code)

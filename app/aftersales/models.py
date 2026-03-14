from django.db import models

from ..orders.models import Order
from .constants import AFTERSALE_ISSUE_CATEGORY, AFTERSALE_STATUS


class Aftersale(models.Model):
	order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='aftersales')
	issue = models.TextField()
	result = models.CharField(max_length=200, null=True, blank=True)
	status = models.CharField(
		max_length=50,
		null=True,
		blank=True,
		choices=AFTERSALE_STATUS,
	)
	remark = models.TextField(null=True, blank=True)
	issue_category = models.CharField(
		max_length=100,
		null=True,
		blank=True,
		choices=AFTERSALE_ISSUE_CATEGORY,
	)
	delivery_info = models.CharField(max_length=100, null=True, blank=True)
	domestic_tracking = models.CharField(max_length=200, null=True, blank=True)
	product_optimization = models.TextField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		db_table = 'tms_aftersale'
		verbose_name = 'Aftersale'
		verbose_name_plural = 'Aftersales'
		ordering = ['-created_at', '-id']

	def __str__(self):
		return f'Aftersale #{self.id} ({self.order.reference})'

	def sku_summary(self):
		items = []
		for line in self.order.lines.all():
			sku = ''
			if line.product and line.product.sku:
				sku = line.product.sku.strip()
			elif line.raw_sku:
				sku = line.raw_sku.strip()
			if sku and sku not in items:
				items.append(sku)
		return ', '.join(items)

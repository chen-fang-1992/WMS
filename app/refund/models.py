from django.db import models
from django.conf import settings
from ..orders.models import Order
from .constants import REFUND_STATUS, REFUND_STATUS_NEW


class Refund(models.Model):
	refund_no = models.CharField(max_length=30, unique=True)
	order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='refunds')
	status = models.CharField(max_length=20, choices=REFUND_STATUS, default=REFUND_STATUS_NEW)
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	reason_detail = models.TextField(blank=True, null=True)
	remark = models.TextField(blank=True, null=True)
	assignee = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='assigned_refunds'
	)
	completed_at = models.DateTimeField(null=True, blank=True)
	cancelled_at = models.DateTimeField(null=True, blank=True)
	cancel_reason = models.TextField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_refunds'
	)
	updated_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='updated_refunds'
	)

	class Meta:
		db_table = 'tms_refund'
		verbose_name = 'Refund'
		verbose_name_plural = 'Refunds'

	def __str__(self):
		return f"{self.refund_no} ({self.order.reference})"

from django.db import models
from ..products.models import Product

class Inbound(models.Model):
	# 参考号
	reference = models.CharField(max_length=50, null=True, blank=True)

	# 仓库
	warehouse = models.CharField(max_length=50)

	# 日期
	date = models.CharField(max_length=50, null=True, blank=True)

	class Meta:
		db_table = 'tms_inbound'
		verbose_name = 'Inbound'
		verbose_name_plural = 'Inbounds'

	def __str__(self):
		return f"{self.reference}"

class InboundLine(models.Model):
	# 入库ID
	inbound = models.ForeignKey(Inbound, on_delete=models.CASCADE, related_name='lines')

	# 产品ID
	product = models.ForeignKey(Product, on_delete=models.CASCADE)

	# 数量
	quantity = models.PositiveIntegerField()

	class Meta:
		db_table = 'tms_inbound_line'
		verbose_name = 'InboundLine'
		verbose_name_plural = 'InboundLines'

	def __str__(self):
		return f"{self.product} x {self.quantity}"

from django.db import models
from ..products.models import Product

class Order(models.Model):
	# 参考号
	reference = models.CharField(max_length=50, null=True, blank=True)

	# 日期
	date = models.CharField(max_length=50, null=True, blank=True)

	# 联系人
	contact_name = models.CharField(max_length=100, null=True, blank=True)

	# 地址
	address = models.TextField(null=True, blank=True)

	# 路线记录
	route_record = models.TextField(null=True, blank=True)

	# 备注
	notes = models.TextField(null=True, blank=True)

	# 订单状态
	status = models.CharField(max_length=50, null=True, blank=True)

	class Meta:
		db_table = 'tms_order'
		verbose_name = 'Order'
		verbose_name_plural = 'Orders'

	def __str__(self):
		return f"{self.reference}"

class OrderLine(models.Model):
	# 订单ID
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='lines')

	# 产品ID
	product = models.ForeignKey(Product, on_delete=models.CASCADE)

	# 数量
	quantity = models.PositiveIntegerField()

	class Meta:
		db_table = 'tms_order_line'
		verbose_name = 'OrderLine'
		verbose_name_plural = 'OrderLines'

	def __str__(self):
		return f"{self.product} x {self.quantity}"

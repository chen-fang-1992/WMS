from django.db import models
from ..products.models import Product

class Order(models.Model):
	# 参考号
	reference = models.CharField(max_length=50, unique=True)

	# 日期
	date = models.DateTimeField(null=True, blank=True)

	# 联系人
	contact_name = models.CharField(max_length=100, null=True, blank=True)

	# 联系电话
	phone = models.CharField(max_length=20, null=True, blank=True)

	# 联系邮箱
	email = models.CharField(max_length=100, null=True, blank=True)

	# 地址
	address = models.CharField(max_length=300, null=True, blank=True)
	
	# suburb
	suburb = models.CharField(max_length=100, null=True, blank=True)

	# postcode
	postcode = models.CharField(max_length=20, null=True, blank=True)

	# state
	state = models.CharField(max_length=20, null=True, blank=True)

	# 路线记录
	route_record = models.TextField(null=True, blank=True)

	# 客户备注
	customer_notes = models.TextField(null=True, blank=True)

	# 备注
	notes = models.TextField(null=True, blank=True)

	# 订单状态
	status = models.CharField(max_length=50, null=True, blank=True)

	# 总价
	total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 运费
	shipping = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 来源
	source = models.CharField(max_length=100, null=True, blank=True)

	# 特殊费用
	special_fees = models.TextField(null=True, blank=True)
	
	# tracking number
	tracking_number = models.CharField(max_length=100, null=True, blank=True)

	# 其他元数据
	meta = models.JSONField(null=True, blank=True)

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
	product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)

	# 原始 SKU
	raw_sku = models.CharField(max_length=100, null=True, blank=True)

	# 数量
	quantity = models.PositiveIntegerField()

	class Meta:
		db_table = 'tms_order_line'
		verbose_name = 'OrderLine'
		verbose_name_plural = 'OrderLines'

	def __str__(self):
		if self.product:
			return f"{self.product} x {self.quantity}"
		return f"{self.raw_sku or '未知SKU'} x {self.quantity}"

	def display_name(self):
		if self.product:
			return self.product.name_cn or self.product.name_en or self.raw_sku or "未知SKU"
		return self.raw_sku or "未知SKU"

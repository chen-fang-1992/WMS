from django.db import models
from ..products.models import Product
from ..inbounds.models import InboundLine
from ..orders.models import OrderLine

class Stock(models.Model):
	# 产品ID
	product = models.OneToOneField(Product, on_delete=models.CASCADE)

	# 数量
	quantity = models.PositiveIntegerField()

	class Meta:
		db_table = 'tms_stock'
		verbose_name = 'Stock'
		verbose_name_plural = 'Stocks'

	def __str__(self):
		return f"{self.product.name_cn or self.product.name_en or self.product.sku} x {self.quantity}"
	
	@classmethod
	def recalculate_all(cls):
		# 初始化库存字典
		stock_data = {}

		# 加入入库数量（正数）
		for line in InboundLine.objects.select_related('product'):
			if line.product_id not in stock_data:
				stock_data[line.product_id] = 0
			stock_data[line.product_id] += line.quantity

		# 减去订单数量（负数）
		for line in OrderLine.objects.select_related('product'):
			if line.product_id not in stock_data:
				stock_data[line.product_id] = 0
			stock_data[line.product_id] -= line.quantity

		# 更新数据库
		for product_id, quantity in stock_data.items():
			if not product_id:
				continue
			product = Product.objects.filter(id=product_id).first()
			if not product:
				continue
			stock, _ = cls.objects.get_or_create(product=product, defaults={'quantity': 0})
			stock.quantity = max(quantity, 0)  # 避免负库存
			stock.save()

		# 可选：清除已删除产品的库存记录
		cls.objects.exclude(product_id__in=stock_data.keys()).delete()

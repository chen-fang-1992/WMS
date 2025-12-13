from django.db import models
from ..products.models import Product
from ..inbounds.models import InboundLine
from ..orders.models import OrderLine
from collections import defaultdict

class Stock(models.Model):
	# 产品ID
	product = models.ForeignKey(Product, on_delete=models.CASCADE)

	# 仓库
	warehouse = models.CharField(max_length=50)

	# 数量
	quantity = models.PositiveIntegerField()

	class Meta:
		db_table = 'tms_stock'
		verbose_name = 'Stock'
		verbose_name_plural = 'Stocks'
		unique_together = ('product', 'warehouse')

	def __str__(self):
		return f"{self.product.name_cn or self.product.name_en or self.product.sku} x {self.quantity}"

	@staticmethod
	def route_to_warehouse(route: str):
		if not route:
			return 'Sydney'

		route = route.upper()

		if 'BNE' in route:
			return 'Brisbane'
		if 'MEL' in route:
			return 'Melbourne'

		return 'Sydney'
	
	@classmethod
	def recalculate_all(cls):
		# 初始化库存字典
		stock_data = defaultdict(int)

		# 加入入库数量（正数）
		for line in InboundLine.objects.select_related('product', 'inbound'):
			product_id = line.product_id
			warehouse = line.inbound.warehouse

			if not product_id or not warehouse:
				continue

			key = (product_id, warehouse)
			stock_data[key] += line.quantity

		# 减去订单数量（负数）
		for line in OrderLine.objects.select_related('product', 'order'):
			product_id = line.product_id
			route = getattr(line.order, 'route', None)

			warehouse = cls.route_to_warehouse(route)

			if not product_id or not warehouse:
				continue

			key = (product_id, warehouse)
			stock_data[key] -= line.quantity

		# 写入 Stock
		seen_ids = []

		for (product_id, warehouse), quantity in stock_data.items():
			stock, _ = cls.objects.get_or_create(
				product_id=product_id,
				warehouse=warehouse,
				defaults={'quantity': 0}
			)
			stock.quantity = quantity
			stock.save()
			seen_ids.append(stock.id)

		# 可选：清除已删除产品的库存记录
		cls.objects.exclude(id__in=seen_ids).delete()

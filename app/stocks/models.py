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
	quantity_reserved = models.PositiveIntegerField(default=0)
	quantity_available = models.IntegerField(default=0)

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
		stock_data = defaultdict(lambda: {'quantity': 0, 'quantity_reserved': 0})

		# 加入入库数量（正数）
		for line in InboundLine.objects.select_related('product', 'inbound'):
			product_id = line.product_id
			warehouse = line.inbound.warehouse

			if not product_id or not warehouse:
				continue

			key = (product_id, warehouse)
			stock_data[key]['quantity'] += line.quantity

		# 减去订单数量（负数）
		for line in OrderLine.objects.select_related('product', 'order'):
			product_id = line.product_id
			route = getattr(line.order, 'route_record', None)

			warehouse = cls.route_to_warehouse(route)

			if not product_id or not warehouse:
				continue

			key = (product_id, warehouse)
			order_status = (getattr(line.order, 'status', '') or '').strip().lower()
			if order_status == 'completed':
				stock_data[key]['quantity'] -= line.quantity
			elif order_status not in {'cancelled', 'shipping', 'backorder'}:
				stock_data[key]['quantity_reserved'] += line.quantity

		# 写入 Stock
		seen_ids = []

		for (product_id, warehouse), values in stock_data.items():
			stock, _ = cls.objects.get_or_create(
				product_id=product_id,
				warehouse=warehouse,
				defaults={'quantity': 0, 'quantity_reserved': 0, 'quantity_available': 0}
			)
			stock.quantity = values['quantity']
			stock.quantity_reserved = values['quantity_reserved']
			stock.quantity_available = values['quantity'] - values['quantity_reserved']
			stock.save(update_fields=['quantity', 'quantity_reserved', 'quantity_available'])
			seen_ids.append(stock.id)

		# 可选：清除已删除产品的库存记录
		cls.objects.exclude(id__in=seen_ids).delete()

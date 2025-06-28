from django.db import models

class Product(models.Model):
	# 品种
	category = models.CharField(max_length=50, null=True, blank=True)

	# 厂家
	manufacturer = models.CharField(max_length=50, null=True, blank=True)

	# 产品英文名称
	name_en = models.CharField(max_length=200, null=True, blank=True)

	# 产品中文名称
	name_cn = models.CharField(max_length=200, null=True, blank=True)

	# 产品SKU
	sku = models.CharField(max_length=50, unique=True, null=True, blank=True)

	# 产品条码
	barcode = models.CharField(max_length=50, null=True, blank=True)

	# 产品图片
	image_url = models.URLField(max_length=255, null=True, blank=True)

	# 产品包装尺寸（长、宽、高）单位：厘米
	package_length = models.CharField(max_length=100, null=True, blank=True)
	package_width = models.CharField(max_length=100, null=True, blank=True)
	package_height = models.CharField(max_length=100, null=True, blank=True)

	# 运费体积（立方米）
	shipping_volume = models.CharField(max_length=100, null=True, blank=True)

	# 重量（千克）
	weight = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

	# 产品进价（人民币）
	cost_rmb = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 产品进价（澳币，按 4.5 汇率计算）
	cost_aud = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 海运成本（每立方 AU$161）
	sea_shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 实际成本 = 产品进价 + 海运成本
	total_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 2倍参考售价（= 实际成本 * 2）
	price_2x = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 2.5倍参考售价（= 实际成本 * 2.5）
	price_2_5x = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 3倍参考售价（= 实际成本 * 3）
	price_3x = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 实际售价
	actual_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 售价 * 0.75 （25% 折扣 + 税）
	discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	# 当前实际利润 = 实际售价 - 实际成本
	profit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

	class Meta:
		db_table = 'tms_product'
		verbose_name = 'Product'
		verbose_name_plural = 'Products'

	@classmethod
	def get_all_categories(cls):
		categories = cls.objects.values_list('category', flat=True).distinct().order_by('category')
		return [category if category is not None else "空" for category in categories]

	@classmethod
	def get_all_manufacturers(cls):
		manufacturers = cls.objects.values_list('manufacturer', flat=True).distinct().order_by('manufacturer')
		return [manufacturer if manufacturer is not None else "空" for manufacturer in manufacturers]

	def __str__(self):
		return f"{self.name_cn or self.name_en or self.sku}"

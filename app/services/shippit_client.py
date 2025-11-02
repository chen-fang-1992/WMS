import requests
from django.conf import settings
from app.orders.models import Order, OrderLine
from decimal import Decimal

SHIPPIT_API_URL = settings.SHIPPIT["API_URL"]
SHIPPIT_API_KEY = settings.SHIPPIT["API_KEY"]

def safe_dim(value, default):
	try:
		return float(value)
	except Exception:
		return default

def get_shipping_quote(order_id):
	order = Order.objects.get(id=order_id)
	lines = OrderLine.objects.filter(order=order)

	parcel_attributes = []

	for line in lines:
		product = line.product
		if not product:
			parcel_attributes.append({
				"qty": line.quantity,
				"weight": 1.0,
				"length": 10,
				"width": 10,
				"height": 10
			})
			continue

		if product.type == '成品(无BOM)' or product.type == '组件':
			# 成品默认尺寸和重量
			weight = safe_dim(product.weight, 1.0)
			length = safe_dim(product.package_length, 10)
			width  = safe_dim(product.package_width, 10)
			height = safe_dim(product.package_height, 10)

			parcel_attributes.append({
				"qty": line.quantity,
				"weight": round(weight, 3),
				"length": round(length, 1),
				"width": round(width, 1),
				"height": round(height, 1),
			})
		else:
			# 对于有BOM的成品，按组件计算
			bom_items = product.bom_items.select_related('component').all()
			for bom in bom_items:
				comp_product = bom.component
				comp_qty = bom.quantity * line.quantity

				weight = safe_dim(comp_product.weight, 1.0)
				length = safe_dim(comp_product.package_length, 10)
				width  = safe_dim(comp_product.package_width, 10)
				height = safe_dim(comp_product.package_height, 10)

				parcel_attributes.append({
					"qty": comp_qty,
					"weight": round(weight, 3),
					"length": round(length, 1),
					"width": round(width, 1),
					"height": round(height, 1),
				})

	print("📦 计算包裹属性:", parcel_attributes)

	payload = {
		"quote": {
			"dropoff_postcode": order.postcode or "2000",
			"dropoff_state": order.state or "NSW",
			"dropoff_suburb": order.suburb or "Sydney",
			"dropoff_country": "AU",
			"parcel_attributes": parcel_attributes,
			"return_all_quotes": True
		}
	}

	headers = {
		"Authorization": f"Bearer {SHIPPIT_API_KEY}",
		"Content-Type": "application/json"
	}

	resp = requests.post(f"{SHIPPIT_API_URL}/quotes", json=payload, headers=headers, timeout=30)
	resp.raise_for_status()
	data = resp.json()
	resp_list = data.get("response", [])

	available_quotes = []
	for item in resp_list:
		if not item.get("success"):
			continue
		for q in item.get("quotes", []):
			if q.get("price") <= 0:
				continue
			available_quotes.append({
				"courier": item.get("courier_type"),
				"service_level": item.get("service_level"),
				"price": Decimal(q.get("price")),
				"eta": q.get("estimated_transit_time")
			})

	if not available_quotes:
		print("⚠️ 没有可用报价:", data)
		return None

	# 排序取最低价
	available_quotes.sort(key=lambda x: x["price"])
	best_quote = available_quotes[0]

	result = {
		"best": best_quote,
		"all": available_quotes
	}

	print("✅ Shippit 最低报价:", best_quote)
	return result

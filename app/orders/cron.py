import re
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from app.services.woocommerce_client import get_wc_client
from app.orders.models import Order, OrderLine
from app.products.models import Product


def parse_wc_datetime(dt_str):
	dt = parse_datetime(dt_str)
	if dt and dt.tzinfo is None:
		return timezone.make_aware(dt)
	return dt

def clean_text(text: str) -> str:
	text = text.replace("(", "").replace(")", "")
	return text.strip().title()

def get_order_source(order):
	meta = {m['key']: m['value'] for m in order.get('meta_data', [])}
	source_type = meta.get('_wc_order_attribution_source_type', '')
	source = meta.get('_wc_order_attribution_utm_source', '')
	medium = meta.get('_wc_order_attribution_utm_medium', '')
	if source_type == 'utm':
		return clean_text(f"Source: {source}")
	elif medium != '':
		return clean_text(f"{medium}: {source}")
	elif source != '':
		return clean_text(f"{source}")
	else:
		return 'Unknown'

def sync_wc_orders():
	wc = get_wc_client()
	page = 1
	per_page = 100

	while True:
		orders = wc.get(
			"orders",
			params={"per_page": per_page, "page": page, "orderby": "date", "order": "asc"}
		).json()

		if not orders:
			break

		for order in orders:
			print(f"Processing order ID: {order['id']}")

			if Order.objects.filter(reference=order["id"]).exists():
				print(f"⏩ 已存在订单 WC#{order['id']}，跳过")
				continue

			source = get_order_source(order)

			obj = Order.objects.create(
				reference=order["id"],
				status="New",
				total=order["total"],
				contact_name=f"{order['billing']['first_name']} {order['billing']['last_name']}".strip(),
				phone=order["billing"].get("phone", ""),
				email=order["billing"].get("email", ""),
				address=f"{order['billing'].get('address_1', '')} {order['billing'].get('address_2', '')}".strip(),
				suburb=order["billing"].get("city", ""),
				postcode=order["billing"].get("postcode", ""),
				state=order["billing"].get("state", ""),
				customer_notes=order.get("customer_note", ""),
				date=parse_wc_datetime(order["date_created"]),
				source=source,
				meta=order,
			)

			for item in order.get("line_items", []):
				sku = item.get("sku")
				quantity = item.get("quantity", 0)

				if not sku:
					print(f"⚠️ 订单 {order['id']} 的某个商品缺少 SKU，跳过该行")
					continue

				products = Product.objects.filter(sku=sku)
				if products.exists():
					product = products.first()
					OrderLine.objects.create(
						order=obj,
						product=product,
						raw_sku=sku,
						quantity=quantity
					)
					print(f"  -> 添加行: {product.sku} x {quantity}")
				else:
					OrderLine.objects.create(
						order=obj,
						product=None,
						raw_sku=sku,
						quantity=quantity
					)
					print(f"❌ SKU {sku} 不存在，已保存为原始 SKU 行")

			print(f"✅ 新订单同步: WC#{obj.reference}")

		page += 1

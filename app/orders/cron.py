from datetime import timedelta
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from app.services.woocommerce_client import wc_get, wc_post, wc_put
from app.orders.models import Order, OrderLine
from app.products.models import Product
from app.stocks.models import Stock
from decimal import Decimal
import traceback
from django.conf import settings


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
	
def update_order_if_missing(order_data):
	try:
		obj = Order.objects.get(reference=order_data['id'])
	except Order.DoesNotExist:
		return False

	changed = False

	if not obj.source:
		new_source = get_order_source(order_data)
		obj.source = new_source
		changed = True

	if not obj.meta:
		obj.meta = order_data
		changed = True

	if not obj.woo_status or obj.woo_status != order_data.get('status', ''):
		obj.woo_status = order_data.get('status', '')
		changed = True

	if order_data.get('fee_lines'):
		special_fees = ''
		for item in order_data['fee_lines']:
			if item.get('total', '0.00') == '0.00':
				continue
			special_fees += f"{item.get('name', 'Fee')}: ${item.get('total', '0.00')}\n"
		special_fees = special_fees.strip()
		if obj.special_fees != special_fees:
			obj.special_fees = special_fees
			changed = True

	if order_data.get('status') == 'completed' and obj.status != 'Completed':
		obj.status = 'Completed'
		changed = True

	if order_data.get('status') == 'cancelled' and obj.status != 'Cancelled':
		obj.status = 'Cancelled'
		changed = True

	if changed:
		obj.save(update_fields=['source', 'meta', 'special_fees', 'status', 'woo_status'])
		print(f"🔄 已更新订单 WC#{obj.reference}: source/meta/special_fees/status/woo_status 补全")
	else:
		print(f"⏩ 已存在订单 WC#{obj.reference}，无需更新")

	return changed

def sync_wc_orders():
	page = 1
	per_page = 100
	since_date = (timezone.now() - timedelta(days=settings.WOOCOMMERCE["SYNC_ORDERS_SINCE"])).isoformat()

	while True:
		orders = wc_get(
			"orders",
			params={"per_page": per_page, "page": page, "orderby": "date", "order": "asc", "modified_after": since_date}
		).json()

		if not orders:
			break

		for order in orders:
			print(f"Processing order ID: {order['id']}")

			if Order.objects.filter(reference=order["id"]).exists():
				update_order_if_missing(order)
				continue

			source = get_order_source(order)

			obj = Order.objects.create(
				reference=order["id"],
				woo_status=order.get("status", ""),
				status="New",
				total=order["total"],
				shipping=order["shipping_total"],
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
				special_fees='',
				tracking_number='',
				delivery_date='1970-01-01',
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

			if order.get('fee_lines'):
				obj.special_fees = ''
				for item in order.get('fee_lines', []):
					if item.get('total', '0.00') == '0.00':
						continue
					obj.special_fees += f"{item.get('name', 'Fee')}: ${item.get('total', '0.00')}\n"
				obj.special_fees = obj.special_fees.strip()
				obj.save(update_fields=['special_fees'])

			print(f"✅ 新订单同步: WC#{obj.reference}")

		page += 1

	Stock.recalculate_all()

def push_order_to_wc(order_id):
	order = Order.objects.get(id=order_id)
	lines = OrderLine.objects.filter(order=order)

	# 基础订单结构
	data = {
		"status": "processing",
		"currency": "AUD",
		"payment_method": "",
		"payment_method_title": "",
		"set_paid": True,
		"billing": {
			"first_name": "",
			"last_name": "",
			"company": "",
			"address_1": order.address or "",
			"address_2": "",
			"city": order.suburb or "",
			"state": order.state or "",
			"postcode": order.postcode or "",
			"country": "AU",
			"email": order.email or "",
			"phone": order.phone or "",
		},
		"shipping": {
			"first_name": "",
			"last_name": "",
			"company": "",
			"address_1": order.address or "",
			"address_2": "",
			"city": order.suburb or "",
			"state": order.state or "",
			"postcode": order.postcode or "",
			"country": "AU",
			"phone": "",
		},
		"line_items": [],
		"shipping_lines": [],
		"fee_lines": [],
		"customer_note": order.customer_notes or "",
		"meta_data": [
			{"key": "tms_order_id", "value": order.id},
			{"key": "source_system", "value": "WMS"},
		],
	}

	# 拆分姓名
	if order.contact_name:
		parts = order.contact_name.strip().split(" ", 1)
		data["billing"]["first_name"] = parts[0]
		data["shipping"]["first_name"] = parts[0]
		if len(parts) > 1:
			data["billing"]["last_name"] = parts[1]
			data["shipping"]["last_name"] = parts[1]

	# 商品行
	for line in lines:
		item = {
			"quantity": line.quantity,
			"name": line.display_name_en(),
			"total": str(line.product.price if hasattr(line.product, "price") else 0),
		}

		if line.product and getattr(line.product, "meta", None) and "id" in line.product.meta:
			item["product_id"] = line.product.meta["id"]
		elif line.raw_sku:
			item["sku"] = line.raw_sku
		else:
			print(f"⚠️ 订单 {order.id} 中有商品缺 SKU，跳过该行")
			continue

		data["line_items"].append(item)

	# 运费
	if order.shipping and Decimal(order.shipping) > 0:
		data["shipping_lines"].append({
			"method_id": "flat_rate",
			"method_title": "Flat Rate",
			"total": str(order.shipping),
			"meta_data": [
				{"key": "Items", "value": ", ".join([l.display_name_en() for l in lines])}
			]
		})
	else:
		data["shipping_lines"].append({
			"method_id": "free_shipping",
			"method_title": "Free shipping",
			"total": "0.00",
			"meta_data": [
				{"key": "Items", "value": ", ".join([l.display_name_en() for l in lines])}
			]
		})

	# 特殊费用
	if order.special_fees:
		for fee in order.special_fees.split("\n"):
			if ":" in fee:
				name, total = fee.split(":", 1)
				data["fee_lines"].append({
					"name": name.strip(),
					"tax_class": "",
					"tax_status": "taxable",
					"total": total.replace("$", "").strip() or "0.00"
				})

	# 推送到 WooCommerce
	try:
		response = wc_post("orders", data).json()
		if "id" in response:
			order.reference = str(response["id"])
			order.meta = response
			order.save(update_fields=["reference", "meta"])
			print(f"✅ 已推送到 WooCommerce，WC#{response['id']}")
			return True
		else:
			print(f"⚠️ WooCommerce 返回异常: {response}")
	except Exception as e:
		print(f"❌ 推送失败: {e}\n{traceback.format_exc()}")

	return False

def sync_woo_order_completed(order):
	if not order.reference:
		print(f"❌ 订单 {order.id} 无 WooCommerce 参考号，无法同步完成状态")
		return False

	try:
		resp = wc_get(f"orders/{order.reference}")
		woo_order = resp.json()
	except Exception as e:
		print(f"❌ 获取 WooCommerce 订单失败: {e}\n{traceback.format_exc()}")
		return False

	current_status = woo_order.get("status", "")
	if current_status != "processing":
		print(f"⚠️ 订单 {order.id} 当前状态为 {current_status}，无法同步完成状态")
		return False

	try:
		resp = wc_put(
			f"orders/{order.reference}",
			json={"status": "completed"},
		)
		updated_order = resp.json()
		print(f"✅ 订单 {order.id} 已同步为完成状态，WC 状态: {updated_order.get('status', '')}")
	except Exception as e:
		print(f"❌ 同步完成状态失败: {e}\n{traceback.format_exc()}")
		return False

	return True

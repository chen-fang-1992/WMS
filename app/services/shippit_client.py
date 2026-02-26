import requests
from decimal import Decimal

from django.conf import settings

from app.orders.models import Order, OrderLine

SHIPPIT_API_URL = settings.SHIPPIT['API_URL']
SHIPPIT_API_KEY = settings.SHIPPIT['API_KEY']


def safe_dim(value, default):
    try:
        return float(value)
    except Exception:
        return default


def normalize_parcel_attributes(parcel_attributes):
    if not isinstance(parcel_attributes, list):
        return []

    normalized = []
    for item in parcel_attributes:
        if not isinstance(item, dict):
            continue
        try:
            qty = int(item.get('qty', 0))
            weight = float(item.get('weight', 0))
            length = float(item.get('length', 0))
            width = float(item.get('width', 0))
            height = float(item.get('height', 0))
        except Exception:
            continue

        if qty <= 0:
            continue

        normalized.append({
            'qty': qty,
            'weight': round(weight, 3),
            'length': round(length, 2),
            'width': round(width, 2),
            'height': round(height, 2),
        })

    return normalized


def build_default_parcel_attributes(order):
    lines = OrderLine.objects.filter(order=order).select_related('product')
    parcel_attributes = []

    for line in lines:
        product = line.product
        if not product:
            parcel_attributes.append({
                'qty': line.quantity,
                'weight': 1.0,
                'length': 10,
                'width': 10,
                'height': 10,
            })
            continue

        has_no_bom = product.bom_items.select_related('component').all().count() == 0
        is_simple = product.type in ['成品(无BOM)', '组件'] or has_no_bom

        if is_simple:
            weight = safe_dim(product.weight, 10)
            length = safe_dim(int(product.package_length) / 100, 1)
            width = safe_dim(int(product.package_width) / 100, 1)
            height = safe_dim(int(product.package_height) / 100, 1)

            parcel_attributes.append({
                'qty': line.quantity,
                'weight': round(weight, 3),
                'length': round(length, 2),
                'width': round(width, 2),
                'height': round(height, 2),
            })
            continue

        for bom in product.bom_items.select_related('component').all():
            comp_product = bom.component
            comp_qty = bom.quantity * line.quantity

            weight = safe_dim(comp_product.weight, 10)
            length = safe_dim(int(comp_product.package_length) / 100, 1)
            width = safe_dim(int(comp_product.package_width) / 100, 1)
            height = safe_dim(int(comp_product.package_height) / 100, 1)

            parcel_attributes.append({
                'qty': comp_qty,
                'weight': round(weight, 3),
                'length': round(length, 2),
                'width': round(width, 2),
                'height': round(height, 2),
            })

    return normalize_parcel_attributes(parcel_attributes)


def build_parcel_attributes(order):
    meta = order.meta or {}
    if isinstance(meta, dict):
        overridden = normalize_parcel_attributes(meta.get('parcel_attributes'))
        if overridden:
            return overridden

    return build_default_parcel_attributes(order)


def get_shipping_quote(order_id):
    order = Order.objects.get(id=order_id)
    parcel_attributes = build_parcel_attributes(order)

    print('?? parcel_attributes:', parcel_attributes)

    payload = {
        'quote': {
            'dropoff_postcode': order.postcode or '2000',
            'dropoff_state': order.state or 'NSW',
            'dropoff_suburb': order.suburb or 'Sydney',
            'dropoff_country': 'AU',
            'parcel_attributes': parcel_attributes,
            'return_all_quotes': True,
        }
    }

    headers = {
        'Authorization': f'Bearer {SHIPPIT_API_KEY}',
        'Content-Type': 'application/json',
    }

    resp = requests.post(f'{SHIPPIT_API_URL}/quotes', json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    resp_list = data.get('response', [])

    available_quotes = []
    for item in resp_list:
        if not item.get('success'):
            continue
        for q in item.get('quotes', []):
            if q.get('price') <= 0:
                continue
            available_quotes.append({
                'courier': item.get('courier_type'),
                'service_level': item.get('service_level'),
                'price': Decimal(q.get('price')),
                'eta': q.get('estimated_transit_time'),
            })

    if not available_quotes:
        print('?? no available quotes:', data)
        return None

    available_quotes.sort(key=lambda x: x['price'])
    best_quote = available_quotes[0]

    return {
        'best': best_quote,
        'all': available_quotes,
        'parcel_attributes': parcel_attributes,
    }

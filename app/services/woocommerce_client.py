from woocommerce import API
from django.conf import settings
import requests

def wc_get(endpoint, params=None):
	base = settings.WOOCOMMERCE["URL"].rstrip("/")
	url = f"{base}/wp-json/wc/v3/{endpoint.lstrip('/')}"

	params = params or {}

	resp = requests.get(
		url,
		params=params,
		auth=(
			settings.WOOCOMMERCE["CONSUMER_KEY"],
			settings.WOOCOMMERCE["CONSUMER_SECRET"],
		),
		timeout=30,
	)

	return resp

def wc_post(endpoint, params=None):
	base = settings.WOOCOMMERCE["URL"].rstrip("/")
	url = f"{base}/wp-json/wc/v3/{endpoint.lstrip('/')}"

	params = params or {}

	resp = requests.post(
		url,
		json=params,
		auth=(
			settings.WOOCOMMERCE["CONSUMER_KEY"],
			settings.WOOCOMMERCE["CONSUMER_SECRET"],
		),
		timeout=30,
	)

	return resp

def wc_put(endpoint, json=None):
	base = settings.WOOCOMMERCE["URL"].rstrip("/")
	url = f"{base}/wp-json/wc/v3/{endpoint.lstrip('/')}"

	json = json or {}

	resp = requests.put(
		url,
		json=json,
		auth=(
			settings.WOOCOMMERCE["CONSUMER_KEY"],
			settings.WOOCOMMERCE["CONSUMER_SECRET"],
		),
		timeout=30,
	)

	return resp

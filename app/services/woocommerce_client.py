from woocommerce import API
from django.conf import settings

def get_wc_client():
	return API(
		url=settings.WOOCOMMERCE["URL"],
		consumer_key=settings.WOOCOMMERCE["CONSUMER_KEY"],
		consumer_secret=settings.WOOCOMMERCE["CONSUMER_SECRET"],
		version=settings.WOOCOMMERCE["VERSION"],
		timeout=30
	)

from django.core.management.base import BaseCommand
from app.orders.cron import sync_wc_orders


class Command(BaseCommand):
	help = "Sync WooCommerce orders"

	def handle(self, *args, **options):
		try:
			sync_wc_orders()
			self.stdout.write(self.style.SUCCESS("WooCommerce orders synced successfully"))
		except Exception as e:
			self.stderr.write(self.style.ERROR(f"Error syncing orders: {e}"))

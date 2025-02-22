from django.shortcuts import render

# Create your views here.
def home(request):
	return render(request, 'home.html')

def customers(request):
	return render(request, 'customers.html')

def shipments(request):
	return render(request, 'shipments.html')

def invoices(request):
	return render(request, 'invoices.html')
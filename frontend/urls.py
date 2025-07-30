from django.urls import path
from django.shortcuts import redirect
from . import views

app_name = 'frontend'

def redirect_to_dashboard(request):
    """Redirige desde la raíz hacia el escritorio"""
    return redirect('frontend:dashboard')

urlpatterns = [
    # Redirección desde la raíz
    path('', redirect_to_dashboard, name='home'),
    
    # Login
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Escritorio
    path('escritorio/', views.dashboard, name='dashboard'),
    
    # Productos
    path('productos/', views.products_list, name='products_list'),
    path('productos/crear/', views.product_create, name='product_create'),
    path('productos/<int:pk>/', views.product_detail, name='product_detail'),
    path('productos/<int:pk>/editar/', views.product_edit, name='product_edit'),
    
    # Ventas
    path('ventas/', views.sales_list, name='sales_list'),
    path('ventas/crear/', views.sale_create, name='sale_create'),
    path('ventas/<int:pk>/', views.sale_detail, name='sale_detail'),
    
    # Stock
    path('stock/', views.stock_list, name='stock_list'),
    path('stock/movimientos/', views.stock_movements, name='stock_movements'),
    path('stock/<int:pk>/agregar/', views.add_stock, name='add_stock'),
    
    # Caja
    path('caja/', views.cashbox_list, name='cashbox_list'),
    path('caja/abrir/', views.open_cashbox, name='open_cashbox'),
    path('caja/<int:pk>/', views.cashbox_detail, name='cashbox_detail'),
    path('caja/<int:pk>/cerrar/', views.close_cashbox, name='close_cashbox'),
    path('caja/<int:pk>/movimiento/', views.add_cash_movement, name='add_cash_movement'),
    
    # Usuarios (solo admin)
    path('usuarios/', views.users_list, name='users_list'),
    path('usuarios/crear/', views.user_create, name='user_create'),
    path('usuarios/<int:pk>/', views.user_detail, name='user_detail'),
    path('usuarios/<int:pk>/editar/', views.user_edit, name='user_edit'),
    path('usuarios/<int:pk>/eliminar/', views.user_delete, name='user_delete'),
    
    # Reportes (solo admin)
    path('reportes/', views.reports, name='reports'),
    
    # Dashboard Financiero (solo admin)
    path('dashboard-financiero/', views.financial_dashboard, name='financial_dashboard'),
    
    # Proveedores (solo admin)
    path('proveedores/', views.suppliers_list, name='suppliers_list'),
    path('proveedores/crear/', views.supplier_create, name='supplier_create'),
    path('proveedores/<int:pk>/', views.supplier_detail, name='supplier_detail'),
    path('proveedores/<int:pk>/editar/', views.supplier_edit, name='supplier_edit'),
    path('proveedores/<int:pk>/eliminar/', views.supplier_delete, name='supplier_delete'),
    path('proveedores/<int:pk>/estado-cuenta/', views.supplier_account_status, name='supplier_account_status'),
    path('proveedores/<int:supplier_pk>/facturas/', views.supplier_invoices_list, name='supplier_invoices_list'),
    path('proveedores/<int:supplier_pk>/facturas/crear/', views.supplier_invoice_create, name='supplier_invoice_create'),
    path('proveedores/<int:supplier_pk>/facturas/<int:invoice_pk>/editar/', views.supplier_invoice_edit, name='supplier_invoice_edit'),
    path('proveedores/<int:supplier_pk>/facturas/<int:invoice_pk>/eliminar/', views.supplier_invoice_delete, name='supplier_invoice_delete'),
    path('proveedores/<int:supplier_pk>/pagos/crear/', views.supplier_payment_create, name='supplier_payment_create'),
    path('proveedores/<int:supplier_pk>/pagos/<int:payment_pk>/editar/', views.supplier_payment_edit, name='supplier_payment_edit'),
    path('proveedores/<int:supplier_pk>/pagos/<int:payment_pk>/eliminar/', views.supplier_payment_delete, name='supplier_payment_delete'),
    
    # Costos Fijos (solo admin)
    path('costos-fijos/', views.expenses_fixed_list, name='expenses_fixed_list'),
    path('costos-fijos/crear/', views.expense_fixed_create, name='expense_fixed_create'),
    path('costos-fijos/<int:pk>/', views.expense_fixed_detail_redirect, name='expense_fixed_detail'),
    path('costos-fijos/<int:pk>/estado-cuenta/', views.fixed_expense_account_status, name='fixed_expense_account_status'),
    path('costos-fijos/<int:expense_pk>/boletas/', views.expense_bills_list_redirect, name='expense_bills_list'),
    path('costos-fijos/<int:expense_pk>/boletas/crear/', views.expense_bill_create, name='expense_bill_create'),
    path('costos-fijos/<int:expense_pk>/boletas/<int:bill_pk>/editar/', views.expense_bill_edit, name='expense_bill_edit'),
    path('costos-fijos/<int:expense_pk>/boletas/<int:bill_pk>/eliminar/', views.expense_bill_delete, name='expense_bill_delete'),
    path('costos-fijos/<int:expense_pk>/pagos/crear/', views.expense_payment_create, name='expense_payment_create'),
    path('costos-fijos/<int:expense_pk>/pagos/<int:payment_pk>/editar/', views.expense_payment_edit, name='expense_payment_edit'),
    path('costos-fijos/boleta/<int:bill_id>/pagar/', views.expense_bill_pay, name='expense_bill_pay'),
    
    # Perfil
    path('perfil/', views.profile, name='profile'),
    
    # APIs
    path('api/buscar-productos/', views.api_search_products, name='api_search_products'),
    path('api/productos/<int:pk>/stock/', views.api_product_stock, name='api_product_stock'),
    path('api/productos/por-codigo/<str:barcode>/', views.api_product_by_barcode, name='api_product_by_barcode'),
] 
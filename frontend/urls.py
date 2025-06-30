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
    
    # Dashboard
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
    
    # Reportes (solo admin)
    path('reportes/', views.reports, name='reports'),
    
    # Perfil
    path('perfil/', views.profile, name='profile'),
    
    # APIs
    path('api/buscar-productos/', views.api_search_products, name='api_search_products'),
    path('api/productos/<int:pk>/stock/', views.api_product_stock, name='api_product_stock'),
    path('api/productos/por-codigo/<str:barcode>/', views.api_product_by_barcode, name='api_product_by_barcode'),
] 
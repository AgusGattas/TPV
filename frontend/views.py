from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q, F, Max
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json
from django.contrib.auth import authenticate, login, logout
from decimal import Decimal
import decimal
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.db import transaction
import os
from django.conf import settings
import pandas as pd

from products.models import Product, ProductImage
from sales.models import Sale, SaleItem
from stock.models import Stock, StockMovement
from cashbox.models import CashBox, CashMovement
from users.models import User
from suppliers.models import Supplier, SupplierInvoice, SupplierPayment
from expenses.models import ExpenseCategory, FixedExpense, MonthlyExpense, VariableExpense, ExpensePayment


@login_required
def dashboard(request):
    """Escritorio principal con estadísticas y resumen"""
    
    # Estadísticas generales
    total_products = Product.objects.filter(is_active=True).count()
    total_sales_today = Sale.objects.filter(
        created_at__date=timezone.now().date(),
        is_active=True
    ).count()
    
    # Ventas de hoy
    sales_today = Sale.objects.filter(
        created_at__date=timezone.now().date(),
        is_active=True
    )
    total_revenue_today = sales_today.aggregate(
        total=Sum('total_final')
    )['total'] or 0
    
    # Productos con stock bajo
    low_stock_products = Product.objects.filter(
        is_active=True,
        stock_info__current_quantity__lte=F('min_stock')
    ).count()
    
    # Productos sin stock
    out_of_stock_products = Product.objects.filter(
        is_active=True,
        stock_info__current_quantity=0
    ).count()
    
    # Caja actual
    current_cashbox = CashBox.objects.filter(closed_at__isnull=True).first()
    
    # Ventas recientes
    recent_sales = Sale.objects.filter(
        is_active=True
    ).select_related('user', 'cashbox').order_by('-created_at')[:10]
    
    # Movimientos de stock recientes
    recent_stock_movements = StockMovement.objects.select_related(
        'stock__product'
    ).order_by('-created_at')[:10]
    
    # Gráfico de ventas de los últimos 7 días
    sales_last_7_days = []
    for i in range(7):
        date = timezone.now().date() - timedelta(days=i)
        daily_sales = Sale.objects.filter(
            created_at__date=date,
            is_active=True
        ).aggregate(total=Sum('total_final'))['total'] or 0
        sales_last_7_days.append({
            'date': date.strftime('%d/%m'),
            'total': float(daily_sales)
        })
    sales_last_7_days.reverse()
    
    context = {
        'total_products': total_products,
        'total_sales_today': total_sales_today,
        'total_revenue_today': total_revenue_today,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'current_cashbox': current_cashbox,
        'recent_sales': recent_sales,
        'recent_stock_movements': recent_stock_movements,
        'sales_last_7_days': sales_last_7_days,
    }
    
    return render(request, 'frontend/dashboard.html', context)


@login_required
def products_list(request):
    """Lista de productos con búsqueda y filtros"""
    
    # Consulta base optimizada con select_related y prefetch_related
    products = Product.objects.filter(is_active=True).select_related('stock_info').prefetch_related('images')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(barcode__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Filtro por stock
    stock_filter = request.GET.get('stock_filter', '')
    if stock_filter == 'low':
        # Productos con stock bajo (menor o igual al mínimo)
        products = products.filter(
            stock_info__current_quantity__lte=F('min_stock'),
            stock_info__current_quantity__gt=0
        )
    elif stock_filter == 'out':
        # Productos sin stock
        products = products.filter(
            stock_info__current_quantity=0
        )
    
    # Ordenamiento
    order_by = request.GET.get('order_by', '-created_at')
    products = products.order_by(order_by)
    
    # Paginación - 20 productos por página
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'search': search,
        'stock_filter': stock_filter,
        'order_by': order_by,
        'page_obj': page_obj,
    }
    
    return render(request, 'frontend/products/list.html', context)


@login_required
def product_detail(request, pk):
    """Detalle de un producto"""
    
    product = get_object_or_404(Product, pk=pk, is_active=True)
    
    # Obtener el último precio de costo de los movimientos de stock
    stock = Stock.objects.filter(product=product).first()
    last_cost_price = None
    
    if stock:
        last_cost_price = StockMovement.objects.filter(
            stock=stock,
            type='ingreso'
        ).order_by('-created_at').values_list('cost_price', flat=True).first()
    
    # Si no hay movimientos previos, usar el precio de costo del producto
    if last_cost_price is None:
        last_cost_price = product.cost_price
    
    # Movimientos de stock del producto
    stock_movements = StockMovement.objects.filter(
        stock__product=product
    ).order_by('-created_at')[:20]
    
    # Ventas recientes del producto
    recent_sales = SaleItem.objects.filter(
        product=product
    ).select_related('sale').order_by('-sale__created_at')[:10]
    
    context = {
        'product': product,
        'last_cost_price': last_cost_price,
        'stock_movements': stock_movements,
        'recent_sales': recent_sales,
    }
    
    return render(request, 'frontend/products/detail.html', context)


@login_required
def product_create(request):
    """Crear nuevo producto"""
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario HTML
            name = request.POST.get('name')
            price = request.POST.get('price')
            cost_price = request.POST.get('cost_price', 0)
            min_stock = request.POST.get('min_stock', 0)
            description = request.POST.get('description', '')
            unit = request.POST.get('unit', 'unidad')
            initial_stock = request.POST.get('initial_stock', 0)
            barcode = request.POST.get('barcode', '').strip()  # Agregar código de barras
            
            # Validaciones básicas
            if not name or not price:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'El nombre y precio son obligatorios'
                    })
                messages.error(request, 'El nombre y precio son obligatorios')
                return render(request, 'frontend/products/create.html')
            
            # Crear el producto
            try:
                product = Product.objects.create(
                    name=name,
                    price=price,
                    cost_price=cost_price,
                    min_stock=min_stock,
                    description=description,
                    unit=unit,
                    barcode=barcode if barcode else None  # Solo usar el código si no está vacío
                )
            except ValueError as e:
                # Error de código de barras duplicado
                error_message = str(e)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': error_message
                    })
                messages.error(request, error_message)
                return render(request, 'frontend/products/create.html')
            
            # Crear registro de stock inicial
            if initial_stock and float(initial_stock) > 0:
                stock, created = Stock.objects.get_or_create(product=product)
                stock.add_stock(
                    quantity=int(initial_stock),
                    cost_price=Decimal(str(cost_price)) if cost_price else Decimal('0'),
                    reason="Stock inicial"
                )
            
            # Procesar imagen si se subió una
            if 'image' in request.FILES:
                image_file = request.FILES['image']
                ProductImage.objects.create(
                    product=product,
                    image=image_file
                )
            
            # Verificar si es una petición AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Producto "{product.name}" creado exitosamente',
                    'product_id': product.id,
                    'redirect_url': reverse('frontend:product_detail', kwargs={'pk': product.id})
                })
            
            messages.success(request, f'Producto "{product.name}" creado exitosamente')
            return redirect('frontend:product_detail', pk=product.id)
            
        except Exception as e:
            error_message = f'Error al crear el producto: {str(e)}'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            messages.error(request, error_message)
            return render(request, 'frontend/products/create.html')
    
    return render(request, 'frontend/products/create.html')


@login_required
def product_edit(request, pk):
    """Editar producto"""
    
    product = get_object_or_404(Product, pk=pk, is_active=True)
    
    # Obtener el último precio de costo de los movimientos de stock
    stock = Stock.objects.filter(product=product).first()
    last_cost_price = None
    
    if stock:
        last_cost_price = StockMovement.objects.filter(
            stock=stock,
            type='ingreso'
        ).order_by('-created_at').values_list('cost_price', flat=True).first()
    
    # Si no hay movimientos previos, usar el precio de costo del producto
    if last_cost_price is None:
        last_cost_price = product.cost_price
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario HTML
            name = request.POST.get('name')
            price = request.POST.get('price')
            cost_price = request.POST.get('cost_price', 0)
            min_stock = request.POST.get('min_stock', 0)
            description = request.POST.get('description', '')
            unit = request.POST.get('unit', 'unidad')
            barcode = request.POST.get('barcode', '')
            
            # Validaciones básicas
            if not name or not price:
                messages.error(request, 'El nombre y precio son obligatorios')
                return render(request, 'frontend/products/edit.html', {'product': product})
            
            # Guardar el precio de costo anterior para comparar
            old_cost_price = product.cost_price
            
            # Actualizar el producto
            product.name = name
            product.price = price
            product.cost_price = cost_price
            product.min_stock = min_stock
            product.description = description
            product.unit = unit
            product.barcode = barcode.strip() if barcode else None
            
            try:
                product.save()
            except ValueError as e:
                # Error de código de barras duplicado
                messages.error(request, str(e))
                return render(request, 'frontend/products/edit.html', {'product': product})
            
            # Si el precio de costo cambió, actualizar el último movimiento de stock
            if old_cost_price != product.cost_price:
                stock = Stock.objects.filter(product=product).first()
                if stock:
                    # Buscar el último movimiento de ingreso
                    last_movement = StockMovement.objects.filter(
                        stock=stock,
                        type='ingreso'
                    ).order_by('-created_at').first()
                    
                    if last_movement:
                        # Actualizar el precio de costo del último movimiento
                        last_movement.cost_price = product.cost_price
                        last_movement.save()
                        print(f"Actualizado último movimiento de stock para {product.name}: {old_cost_price} -> {product.cost_price}")
                    else:
                        # Si no hay movimientos, crear uno con el nuevo precio de costo
                        StockMovement.objects.create(
                            stock=stock,
                            type='ingreso',
                            quantity=0,
                            cost_price=product.cost_price,
                            reason="Actualización de precio de costo"
                        )
                        print(f"Creado nuevo movimiento de stock para {product.name} con precio: {product.cost_price}")
            
            # Procesar imagen si se subió una nueva
            if 'image' in request.FILES:
                image_file = request.FILES['image']
                # Eliminar imagen anterior si existe
                if product.images.exists():
                    product.images.all().delete()
                # Crear nueva imagen
                ProductImage.objects.create(
                    product=product,
                    image=image_file
                )
            
            messages.success(request, f'Producto "{product.name}" actualizado exitosamente')
            return redirect('frontend:product_detail', pk=product.id)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el producto: {str(e)}')
            return render(request, 'frontend/products/edit.html', {'product': product})
    
    # Asegurar que el producto tenga stock_info
    if not hasattr(product, 'stock_info') or product.stock_info is None:
        # Crear stock si no existe
        stock, created = Stock.objects.get_or_create(
            product=product,
            defaults={'current_quantity': 0, 'average_cost': 0}
        )
    
    context = {
        'product': product,
        'last_cost_price': last_cost_price,
    }
    
    return render(request, 'frontend/products/edit.html', context)


@login_required
def sales_list(request):
    """Lista de ventas"""
    
    sales = Sale.objects.filter(is_active=True).select_related('user', 'cashbox')
    
    # Filtros
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    payment_method = request.GET.get('payment_method', '')
    
    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    if payment_method:
        sales = sales.filter(payment_method=payment_method)
    
    # Ordenamiento
    order_by = request.GET.get('order_by', '-created_at')
    sales = sales.order_by(order_by)
    
    # Paginación
    paginator = Paginator(sales, 12)  # 12 ventas por página
    page_number = request.GET.get('page')
    sales = paginator.get_page(page_number)
    
    context = {
        'sales': sales,
        'date_from': date_from,
        'date_to': date_to,
        'payment_method': payment_method,
        'order_by': order_by,
    }
    
    return render(request, 'frontend/sales/list.html', context)


@login_required
def sale_detail(request, pk):
    """Detalle de una venta"""
    
    sale = get_object_or_404(Sale, pk=pk, is_active=True)
    
    # Información del arqueo de caja si la caja está cerrada
    cashbox_arqueo = None
    if sale.cashbox.closed_at:
        cashbox_arqueo = {
            'calculated_cash': sale.cashbox.calculated_cash,
            'counted_cash': sale.cashbox.counted_cash,
            'difference': sale.cashbox.difference,
            'cash_to_keep': sale.cashbox.cash_to_keep,
            'cash_to_withdraw': sale.cashbox.cash_to_withdraw,
            'closing_notes': getattr(sale.cashbox, 'closing_notes', ''),
            'closed_at': sale.cashbox.closed_at,
        }
    
    context = {
        'sale': sale,
        'cashbox_arqueo': cashbox_arqueo,
    }
    
    return render(request, 'frontend/sales/detail.html', context)


@login_required
def sale_delete(request, pk):
    """Eliminar una venta y revertir todos los cambios"""
    sale = get_object_or_404(Sale, pk=pk, is_active=True)
    
    # Verificar que el usuario tenga permisos para eliminar la venta
    # Solo el usuario que creó la venta o un admin puede eliminarla
    if not (sale.user == request.user or request.user.is_admin):
        messages.error(request, 'No tienes permisos para eliminar esta venta')
        return redirect('frontend:sales_list')
    
    # Verificar que la caja esté abierta
    if not sale.cashbox.is_open:
        messages.error(request, 'No se puede eliminar una venta de una caja cerrada')
        return redirect('frontend:sales_list')
    
    if request.method == 'POST':
        try:
            # Eliminar la venta y revertir todos los cambios
            sale.delete_sale()
            
            messages.success(
                request, 
                f'Venta #{sale.id} eliminada exitosamente. '
                f'Se ha revertido el stock y todos los cambios relacionados.'
            )
            return redirect('frontend:sales_list')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar la venta: {str(e)}')
            return redirect('frontend:sale_detail', pk=pk)
    
    # Mostrar confirmación
    context = {
        'sale': sale,
    }
    
    return render(request, 'frontend/sales/delete.html', context)


@login_required
def sale_create(request):
    """Crear nueva venta"""
    from decimal import Decimal
    
    # Verificar que haya una caja abierta por el usuario actual
    current_cashbox = CashBox.objects.filter(
        closed_at__isnull=True,
        user=request.user
    ).first()
    
    if not current_cashbox:
        # Verificar si hay una caja abierta por otro usuario
        other_user_cashbox = CashBox.objects.filter(closed_at__isnull=True).first()
        if other_user_cashbox:
            messages.error(request, f'Hay una caja abierta por {other_user_cashbox.user.get_full_name() or other_user_cashbox.user.username}. Solo el usuario que abrió la caja puede realizar ventas.')
        else:
            messages.error(request, 'No hay una caja abierta. Debes abrir una caja antes de realizar ventas.')
        return redirect('frontend:cashbox_list')
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Crear la venta
            sale = Sale.objects.create(
                user=request.user,
                cashbox=current_cashbox,
                payment_method=data['payment_method'],
                notes=data.get('notes', ''),
                sale_discount_percentage=Decimal(str(data.get('sale_discount_percentage', 0)))
            )
            
            # Si se envió un total_final específico, usarlo en lugar del calculado
            total_final_override = data.get('total_final')
            
            # Crear los items de la venta
            for item_data in data['items']:
                product = Product.objects.get(id=item_data['product_id'])
                
                # Verificar y obtener stock
                stock, created = Stock.objects.get_or_create(
                    product=product,
                    defaults={'current_quantity': 0}
                )
                
                # Verificar stock disponible
                if stock.current_quantity < item_data['quantity']:
                    raise ValueError(
                        f"Stock insuficiente para '{product.name}'. "
                        f"Disponible: {stock.current_quantity}, Solicitado: {item_data['quantity']}"
                    )
                
                # Convertir valores a Decimal para evitar errores de tipos
                unit_price = Decimal(str(item_data.get('unit_price', product.price)))
                discount_percentage = Decimal(str(item_data.get('discount_percentage', 0)))
                
                # Crear el item de venta
                sale_item = SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=item_data['quantity'],
                    unit_price=unit_price,
                    discount_percentage=discount_percentage
                )
                
                # Reducir stock
                stock.remove_stock(
                    quantity=item_data['quantity'],
                    reason=f"Venta #{sale.id}"
                )
            
            # Si se especificó un total_final, actualizarlo
            if total_final_override is not None:
                sale.total_final = Decimal(str(total_final_override))
                sale.save(update_fields=['total_final'])
            
            return JsonResponse({
                'success': True,
                'message': 'Venta creada exitosamente',
                'sale_id': sale.id,
                'ticket_number': sale.ticket_number
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    # Obtener productos para el formulario
    products = Product.objects.filter(
        is_active=True
    ).prefetch_related('images')
    
    context = {
        'current_cashbox': current_cashbox,
        'products': products,
    }
    
    return render(request, 'frontend/sales/create.html', context)


@login_required
def stock_list(request):
    """Lista de stock con movimientos"""
    
    # Consulta base optimizada
    stocks = Stock.objects.select_related('product').prefetch_related('product__images').all()
    
    # Filtros
    search = request.GET.get('search', '')
    if search:
        stocks = stocks.filter(
            Q(product__name__icontains=search) |
            Q(product__barcode__icontains=search)
        )
    
    stock_filter = request.GET.get('stock_filter', '')
    if stock_filter == 'low':
        stocks = stocks.filter(
            current_quantity__lte=F('product__min_stock'),
            current_quantity__gt=0
        )
    elif stock_filter == 'out':
        stocks = stocks.filter(current_quantity=0)
    
    # Ordenamiento
    order_by = request.GET.get('order_by', '-current_quantity')
    stocks = stocks.order_by(order_by)
    
    # Paginación - 20 stocks por página
    paginator = Paginator(stocks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Optimización: Obtener todos los últimos precios de costo en una sola consulta
    stock_ids = [stock.id for stock in page_obj]
    last_cost_prices = {}
    
    if stock_ids:
        # Obtener el último precio de costo para cada stock en una sola consulta
        latest_movements = StockMovement.objects.filter(
            stock_id__in=stock_ids,
            type='ingreso'
        ).values('stock_id').annotate(
            last_cost=Max('cost_price')
        )
        
        for movement in latest_movements:
            last_cost_prices[movement['stock_id']] = movement['last_cost']
    
    # Asignar los precios de costo a cada stock
    for stock in page_obj:
        stock.last_cost_price = last_cost_prices.get(stock.id, stock.product.cost_price)
    
    context = {
        'stocks': page_obj,
        'search': search,
        'stock_filter': stock_filter,
        'order_by': order_by,
        'page_obj': page_obj,
    }
    
    return render(request, 'frontend/stock/list.html', context)


@login_required
def stock_movements(request):
    """Movimientos de stock"""
    
    movements = StockMovement.objects.select_related(
        'stock__product', 'sale'
    ).all()
    
    # Filtros
    movement_type = request.GET.get('type', '')
    if movement_type:
        movements = movements.filter(type=movement_type)
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        movements = movements.filter(created_at__date__gte=date_from)
    if date_to:
        movements = movements.filter(created_at__date__lte=date_to)
    
    movements = movements.order_by('-created_at')
    
    # Paginación - 50 movimientos por página
    paginator = Paginator(movements, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'movements': page_obj,
        'movement_type': movement_type,
        'date_from': date_from,
        'date_to': date_to,
        'page_obj': page_obj,
    }
    
    return render(request, 'frontend/stock/movements.html', context)


@login_required
def add_stock(request, pk):
    """Agregar stock a un producto"""
    
    stock = get_object_or_404(Stock, pk=pk)
    
    # Obtener el último precio de costo de los movimientos de ingreso
    last_cost_price = StockMovement.objects.filter(
        stock=stock,
        type='ingreso'
    ).order_by('-created_at').values_list('cost_price', flat=True).first()
    
    # Si no hay movimientos previos, usar el precio de costo del producto
    if last_cost_price is None:
        last_cost_price = stock.product.cost_price
    
    context = {
        'stock': stock,
        'last_cost_price': last_cost_price,
    }
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            quantity = int(request.POST.get('quantity', 0))
            cost_price = Decimal(request.POST.get('cost_price', 0))
            reason = request.POST.get('reason', 'Compra')
            custom_reason = request.POST.get('custom_reason', '')
            
            if reason == 'Otro' and custom_reason:
                reason = custom_reason
            
            stock.add_stock(
                quantity=quantity,
                cost_price=cost_price,
                reason=reason
            )
            
            messages.success(request, 'Stock agregado exitosamente')
            return redirect('frontend:stock_list')
            
        except Exception as e:
            messages.error(request, f'Error al agregar stock: {str(e)}')
            return render(request, 'frontend/stock/add_stock.html', context)
    
    return render(request, 'frontend/stock/add_stock.html', context)


@login_required
def cashbox_list(request):
    """Lista de cajas"""
    
    cashboxes = CashBox.objects.select_related('user').all()
    
    context = {
        'cashboxes': cashboxes,
    }
    
    return render(request, 'frontend/cashbox/list.html', context)


@login_required
def cashbox_detail(request, pk):
    """Detalle de una caja"""
    
    cashbox = get_object_or_404(CashBox, pk=pk)
    
    # Movimientos de la caja
    movements = CashMovement.objects.filter(cashbox=cashbox).order_by('-created_at')
    
    # Ventas de la caja
    sales = Sale.objects.filter(cashbox=cashbox, is_active=True).order_by('-created_at')
    
    # Ventas por método de pago
    sales_by_payment = cashbox.sales_by_payment_method
    
    context = {
        'cashbox': cashbox,
        'movements': movements,
        'sales': sales,
        'sales_by_payment': sales_by_payment,
    }
    
    return render(request, 'frontend/cashbox/detail.html', context)


@login_required
def open_cashbox(request):
    """Abrir nueva caja"""
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Verificar que no haya cajas abiertas
            if CashBox.objects.filter(closed_at__isnull=True).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'Ya hay una caja abierta'
                }, status=400)
            
            cashbox = CashBox.objects.create(
                user=request.user,
                initial_cash=data['initial_cash']
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Caja abierta exitosamente',
                'cashbox_id': cashbox.id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    # Obtener sugerencia de efectivo inicial
    suggested_cash = CashBox.get_suggested_initial_cash()
    
    context = {
        'suggested_cash': suggested_cash,
    }
    
    return render(request, 'frontend/cashbox/open.html', context)


@login_required
def close_cashbox(request, pk):
    """Cerrar caja"""
    
    cashbox = get_object_or_404(CashBox, pk=pk)
    
    if not cashbox.is_open:
        messages.error(request, 'Esta caja ya está cerrada')
        return redirect('frontend:cashbox_detail', pk=pk)
    
    if request.method == 'POST':
        try:
            # Obtener y limpiar counted_cash
            counted_cash_str = request.POST.get('counted_cash', '0').strip()
            if not counted_cash_str:
                counted_cash_str = '0'
            counted_cash_str = counted_cash_str.replace(',', '.')
            counted_cash = Decimal(counted_cash_str)
            
            # Obtener y limpiar cash_to_keep
            cash_to_keep = None
            cash_to_keep_str = request.POST.get('cash_to_keep', '').strip()
            if cash_to_keep_str:
                cash_to_keep_str = cash_to_keep_str.replace(',', '.')
                cash_to_keep = Decimal(cash_to_keep_str)
            
            closing_notes = request.POST.get('closing_notes', '').strip()
            
            cashbox.close_cashbox(
                counted_cash=counted_cash,
                cash_to_keep=cash_to_keep,
                closing_notes=closing_notes
            )
            
            messages.success(request, 'Caja cerrada exitosamente')
            return redirect('frontend:cashbox_detail', pk=pk)
            
        except (ValueError, TypeError, decimal.ConversionSyntax) as e:
            messages.error(request, f'Error en el formato de los números: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error al cerrar la caja: {str(e)}')
    
    # Movimientos de la caja
    movements = CashMovement.objects.filter(cashbox=cashbox).order_by('-created_at')
    
    # Ventas de la caja
    sales = Sale.objects.filter(cashbox=cashbox, is_active=True).order_by('-created_at')
    
    # Ventas por método de pago
    sales_by_payment = cashbox.sales_by_payment_method
    
    context = {
        'cashbox': cashbox,
        'movements': movements,
        'sales': sales,
        'sales_by_payment': sales_by_payment,
    }
    
    return render(request, 'frontend/cashbox/close.html', context)


@login_required
def add_cash_movement(request, pk):
    """Agregar movimiento de caja"""
    
    cashbox = get_object_or_404(CashBox, pk=pk)
    
    if not cashbox.is_open:
        messages.error(request, 'No se pueden hacer movimientos en una caja cerrada')
        return redirect('frontend:cashbox_detail', pk=pk)
    
    if request.method == 'POST':
        try:
            movement_type = request.POST.get('type')
            amount = Decimal(request.POST.get('amount', 0))
            reason = request.POST.get('reason', '').strip()
            
            if not movement_type or not amount or not reason:
                messages.error(request, 'Todos los campos son obligatorios')
            else:
                CashMovement.objects.create(
                    cashbox=cashbox,
                    user=request.user,
                    type=movement_type,
                    amount=amount,
                    reason=reason
                )
                
                messages.success(request, 'Movimiento agregado exitosamente')
                return redirect('frontend:cashbox_detail', pk=pk)
            
        except Exception as e:
            messages.error(request, str(e))
    
    # Movimientos de la caja
    movements = CashMovement.objects.filter(cashbox=cashbox).order_by('-created_at')
    
    # Ventas de la caja
    sales = Sale.objects.filter(cashbox=cashbox, is_active=True).order_by('-created_at')
    
    context = {
        'cashbox': cashbox,
        'movements': movements,
        'sales': sales,
    }
    
    return render(request, 'frontend/cashbox/add_movement.html', context)


@login_required
def users_list(request):
    """Lista de usuarios (solo para administradores)"""
    
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    # Filtros
    search = request.GET.get('search', '')
    role_filter = request.GET.get('role_filter', '')
    order_by = request.GET.get('order_by', '-date_joined')
    
    # Query base
    users = User.objects.filter(is_active=True)
    
    # Aplicar filtros
    if search:
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(username__icontains=search) |
            Q(email__icontains=search)
        )
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Ordenamiento
    if order_by:
        users = users.order_by(order_by)
    
    # Paginación
    paginator = Paginator(users, 12)  # 12 usuarios por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'users': page_obj,
        'search': search,
        'role_filter': role_filter,
        'order_by': order_by,
    }
    
    return render(request, 'frontend/users/list.html', context)


@login_required
def user_create(request):
    """Crear nuevo usuario (solo para administradores)"""
    
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            username = request.POST.get('username')
            email = request.POST.get('email')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            role = request.POST.get('role', 'vendedor')
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            # Debug: mostrar los datos recibidos
            print(f"DEBUG - Datos recibidos:")
            print(f"Username: {username}")
            print(f"Email: {email}")
            print(f"First name: {first_name}")
            print(f"Last name: {last_name}")
            print(f"Role: {role}")
            print(f"Password1: {'*' * len(password1) if password1 else 'None'}")
            print(f"Password2: {'*' * len(password2) if password2 else 'None'}")
            
            # Validaciones básicas
            if not username or not email or not password1:
                messages.error(request, 'Username, email y contraseña son obligatorios')
                return render(request, 'frontend/users/create.html')
            
            if password1 != password2:
                messages.error(request, 'Las contraseñas no coinciden')
                return render(request, 'frontend/users/create.html')
            
            if len(password1) < 8:
                messages.error(request, 'La contraseña debe tener al menos 8 caracteres')
                return render(request, 'frontend/users/create.html')
            
            # Verificar si el username ya existe
            if User.objects.filter(username=username).exists():
                messages.error(request, 'El username ya está en uso')
                return render(request, 'frontend/users/create.html')
            
            # Verificar si el email ya existe
            if User.objects.filter(email=email).exists():
                messages.error(request, 'El email ya está registrado')
                return render(request, 'frontend/users/create.html')
            
            # Crear el usuario
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role=role
            )
            
            print(f"DEBUG - Usuario creado exitosamente: {user.username}")
            
            messages.success(request, f'Usuario "{user.username}" creado exitosamente')
            return redirect('frontend:users_list')
            
        except Exception as e:
            print(f"DEBUG - Error al crear usuario: {str(e)}")
            messages.error(request, f'Error al crear el usuario: {str(e)}')
            return render(request, 'frontend/users/create.html')
    
    return render(request, 'frontend/users/create.html')


@login_required
def user_detail(request, pk):
    """Detalle de un usuario (solo para administradores)"""
    
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    user = get_object_or_404(User, pk=pk, is_active=True)
    
    # Ventas realizadas por el usuario
    user_sales = Sale.objects.filter(
        user=user,
        is_active=True
    ).order_by('-created_at')[:10]
    
    # Estadísticas del usuario
    total_sales = Sale.objects.filter(user=user, is_active=True).count()
    total_revenue = Sale.objects.filter(
        user=user, 
        is_active=True
    ).aggregate(total=Sum('total_final'))['total'] or 0
    
    # Promedio por venta
    average_sale = float((total_revenue / total_sales) if total_sales > 0 else 0)
    
    # Última actividad
    last_sale = Sale.objects.filter(user=user, is_active=True).order_by('-created_at').first()
    
    context = {
        'user_detail': user,
        'user_sales': user_sales,
        'total_sales': total_sales,
        'total_revenue': float(total_revenue),
        'average_sale': average_sale,
        'last_sale': last_sale,
    }
    
    return render(request, 'frontend/users/detail.html', context)


@login_required
def user_edit(request, pk):
    """Editar usuario (administradores pueden editar cualquier usuario, usuarios pueden editar su propia cuenta)"""
    
    user = get_object_or_404(User, pk=pk, is_active=True)
    
    # Verificar permisos: solo administradores pueden editar otros usuarios
    if not request.user.is_admin and request.user != user:
        messages.error(request, 'No tienes permisos para editar otros usuarios')
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            username = request.POST.get('username')
            email = request.POST.get('email')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            role = request.POST.get('role', 'vendedor')
            is_active = request.POST.get('is_active') == 'on'
            
            # Campos de contraseña (opcionales)
            password1 = request.POST.get('password1', '')
            password2 = request.POST.get('password2', '')
            
            # Si el usuario está editando su propia cuenta, solo permitir ciertos campos
            is_self_edit = request.user == user
            
            # Validaciones básicas
            if not username or not email:
                messages.error(request, 'Username y email son obligatorios')
                return render(request, 'frontend/users/edit.html', {'user': user, 'is_self_edit': is_self_edit})
            
            # Verificar si el username ya existe (excluyendo el usuario actual)
            if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                messages.error(request, 'El username ya está en uso')
                return render(request, 'frontend/users/edit.html', {'user': user, 'is_self_edit': is_self_edit})
            
            # Verificar si el email ya existe (excluyendo el usuario actual)
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, 'El email ya está registrado')
                return render(request, 'frontend/users/edit.html', {'user': user, 'is_self_edit': is_self_edit})
            
            # Validar cambio de contraseña si se proporcionó
            if password1 or password2:
                if not password1 or not password2:
                    messages.error(request, 'Ambos campos de contraseña son obligatorios para cambiar la contraseña')
                    return render(request, 'frontend/users/edit.html', {'user': user, 'is_self_edit': is_self_edit})
                
                if password1 != password2:
                    messages.error(request, 'Las contraseñas no coinciden')
                    return render(request, 'frontend/users/edit.html', {'user': user, 'is_self_edit': is_self_edit})
                
                if len(password1) < 8:
                    messages.error(request, 'La contraseña debe tener al menos 8 caracteres')
                    return render(request, 'frontend/users/edit.html', {'user': user, 'is_self_edit': is_self_edit})
                
                # Cambiar la contraseña
                user.set_password(password1)
                password_changed = True
            else:
                password_changed = False
            
            # Actualizar el usuario
            user.username = username
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            
            # Solo administradores pueden cambiar rol y estado activo
            if not is_self_edit:
                user.role = role
                user.is_active = is_active
            
            user.save()
            
            if password_changed:
                messages.success(request, f'Usuario "{user.username}" actualizado exitosamente. La contraseña ha sido cambiada.')
            else:
                messages.success(request, f'Usuario "{user.username}" actualizado exitosamente')
            return redirect('frontend:users_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el usuario: {str(e)}')
            return render(request, 'frontend/users/edit.html', {'user': user})
    
    context = {
        'user': user,
        'is_self_edit': request.user == user,
    }
    
    return render(request, 'frontend/users/edit.html', context)


@login_required
def user_delete(request, pk):
    """Eliminar usuario (solo para administradores)"""
    
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    user = get_object_or_404(User, pk=pk, is_active=True)
    
    # No permitir eliminar el propio usuario
    if user == request.user:
        messages.error(request, 'No puedes eliminar tu propia cuenta')
        return redirect('frontend:users_list')
    
    if request.method == 'POST':
        try:
            # Verificar si el usuario tiene ventas asociadas
            sales_count = Sale.objects.filter(user=user, is_active=True).count()
            
            if sales_count > 0:
                # Si tiene ventas, solo desactivar
                user.is_active = False
                user.save()
                messages.success(request, f'Usuario "{user.username}" desactivado exitosamente (tiene {sales_count} ventas asociadas)')
            else:
                # Si no tiene ventas, eliminar completamente
                user.delete()
                messages.success(request, f'Usuario "{user.username}" eliminado exitosamente')
            
            return redirect('frontend:users_list')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar el usuario: {str(e)}')
            return redirect('frontend:users_list')
    
    # Mostrar confirmación
    sales_count = Sale.objects.filter(user=user, is_active=True).count()
    
    context = {
        'user': user,
        'sales_count': sales_count,
    }
    
    return render(request, 'frontend/users/delete.html', context)


@login_required
def reports(request):
    """Reportes (solo para administradores)"""
    
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    # Filtros de fecha
    date_from = request.GET.get('date_from', (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', timezone.now().strftime('%Y-%m-%d'))
    
    # Ventas por período (solo ventas activas)
    sales_period = Sale.objects.filter(
        created_at__date__range=[date_from, date_to],
        is_active=True
    )
    
    # 1. TOTAL VENTAS: Total de ventas realizadas en el período
    total_sales_count = sales_period.count()
    total_sales_revenue = sales_period.aggregate(total=Sum('total_final'))['total'] or 0
    
    # 2. TOTAL UTILIDAD: Ventas menos costos de productos vendidos
    # Calcular costo de mercadería vendida (CMV)
    sale_items = SaleItem.objects.filter(
        sale__created_at__date__range=[date_from, date_to],
        sale__is_active=True
    ).select_related('product')
    
    total_cmv = 0
    for item in sale_items:
        # Usar el costo del producto multiplicado por la cantidad vendida
        from decimal import Decimal
        product_cost = item.product.cost_price * Decimal(str(item.quantity))
        total_cmv += float(product_cost)
    
    # Calcular utilidad bruta
    total_utility = float(total_sales_revenue) - total_cmv
    
    # 3. TOTAL GASTOS: Suma de todos los egresos en el período
    from cashbox.models import CashMovement
    total_expenses = CashMovement.objects.filter(
        created_at__date__range=[date_from, date_to],
        type='egreso'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # 4. COSTO DE MERCADERÍA VENDIDA (CMV) y porcentaje
    cmv_percentage = float((Decimal(str(total_cmv)) / total_sales_revenue * 100) if total_sales_revenue > 0 else 0)
    
    # 5. RENTABILIDAD: Porcentaje de utilidad sobre ventas
    profitability_percentage = float((Decimal(str(total_utility)) / total_sales_revenue * 100) if total_sales_revenue > 0 else 0)
    
    # Ventas por método de pago
    sales_by_payment = sales_period.values('payment_method').annotate(
        count=Count('id'),
        total=Sum('total_final')
    )
    
    # Calcular porcentajes para métodos de pago
    for payment in sales_by_payment:
        payment['percentage'] = float((Decimal(str(payment['total'])) / total_sales_revenue * 100) if total_sales_revenue > 0 else 0)
        payment['total'] = float(payment['total'])
        payment['count'] = int(payment['count'])
    
    # Productos más vendidos
    top_products = SaleItem.objects.filter(
        sale__created_at__date__range=[date_from, date_to],
        sale__is_active=True
    ).values('product__name', 'product__barcode').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('subtotal')
    ).order_by('-total_quantity')[:10]
    
    # Calcular precio promedio por producto
    for product in top_products:
        product['average_price'] = float((Decimal(str(product['total_revenue'])) / product['total_quantity']) if product['total_quantity'] > 0 else 0)
        product['total_revenue'] = float(product['total_revenue'])
        product['total_quantity'] = int(product['total_quantity'])
    
    # Ventas por día en el período seleccionado
    sales_last_7_days = []
    from datetime import datetime
    start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    current_date = start_date
    while current_date <= end_date:
        daily_sales = Sale.objects.filter(
            created_at__date=current_date,
            is_active=True
        ).aggregate(total=Sum('total_final'))['total'] or 0
        sales_last_7_days.append({
            'date': current_date.strftime('%d/%m'),
            'total': float(daily_sales)
        })
        current_date += timedelta(days=1)
    
    context = {
        'date_from': date_from,
        'date_to': date_to,
        'total_sales_count': int(total_sales_count),
        'total_sales_revenue': float(total_sales_revenue),
        'total_utility': total_utility,
        'total_expenses': float(total_expenses),
        'total_cmv': total_cmv,
        'cmv_percentage': cmv_percentage,
        'profitability_percentage': profitability_percentage,
        'sales_by_payment': list(sales_by_payment),  # Convertir a lista para JSON
        'top_products': list(top_products),  # Convertir a lista para JSON
        'sales_last_7_days': sales_last_7_days,
    }
    
    return render(request, 'frontend/reports/index.html', context)


@login_required
def profile(request):
    """Perfil del usuario"""
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            user = request.user
            user.first_name = data.get('first_name', '')
            user.last_name = data.get('last_name', '')
            user.email = data.get('email', '')
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Perfil actualizado exitosamente'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return render(request, 'frontend/profile.html')


# APIs para AJAX
@login_required
def api_search_products(request):
    """API para buscar productos por código de barras o nombre"""
    
    search = request.GET.get('search', '')
    if not search:
        return JsonResponse({'products': []})
    
    products = Product.objects.filter(
        Q(name__icontains=search) | Q(barcode__icontains=search),
        is_active=True
    ).select_related('stock_info')[:10]
    
    products_data = []
    for product in products:
        products_data.append({
            'id': product.id,
            'name': product.name,
            'barcode': product.barcode,
            'price': float(product.price),
            'stock': product.current_stock,
            'unit': product.unit,
        })
    
    return JsonResponse({'products': products_data})


@login_required
def api_product_stock(request, pk):
    """API para obtener stock de un producto"""
    
    product = get_object_or_404(Product, pk=pk)
    
    return JsonResponse({
        'current_stock': product.current_stock,
        'min_stock': product.min_stock,
        'stock_status': product.stock_status,
    })


@login_required
def api_product_by_barcode(request, barcode):
    """API para buscar producto por código de barras"""
    
    try:
        product = Product.objects.get(barcode=barcode, is_active=True)
        return JsonResponse({
            'id': product.id,
            'name': product.name,
            'barcode': product.barcode,
            'price': float(product.price),
            'stock': product.current_stock,
            'unit': product.unit,
        })
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)


def login_view(request):
    """Vista de login para el frontend"""
    if request.user.is_authenticated:
        return redirect('frontend:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('frontend:dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'frontend/login.html')


def logout_view(request):
    """Vista de logout para el frontend"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente')
    return redirect('frontend:login') 

# =============================================================================
# VISTAS DE PROVEEDORES
# =============================================================================

@login_required
def suppliers_list(request):
    """Lista de proveedores"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    
    # Filtro por búsqueda
    search = request.GET.get('search')
    if search:
        suppliers = suppliers.filter(
            Q(name__icontains=search) | 
            Q(cuit__icontains=search) |
            Q(email__icontains=search)
        )
    
    # Filtro por estado de pago
    payment_status = request.GET.get('payment_status')
    if payment_status == 'up_to_date':
        suppliers = [supplier for supplier in suppliers if supplier.is_up_to_date]
    elif payment_status == 'overdue':
        suppliers = [supplier for supplier in suppliers if not supplier.is_up_to_date]
    
    # Paginación
    paginator = Paginator(suppliers, 20)
    page_number = request.GET.get('page')
    suppliers_page = paginator.get_page(page_number)
    
    context = {
        'suppliers': suppliers_page,
        'filters': {
            'search': search,
            'payment_status': payment_status,
        }
    }
    
    return render(request, 'frontend/suppliers/list.html', context)


@login_required
def supplier_detail(request, pk):
    """Detalle de un proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=pk, is_active=True)
    invoices = supplier.invoices.all().order_by('-invoice_date')
    
    # Estadísticas del proveedor
    total_invoices = invoices.count()
    total_amount = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    paid_amount = invoices.filter(is_paid=True).aggregate(total=Sum('total_amount'))['total'] or 0
    pending_amount = total_amount - paid_amount
    
    context = {
        'supplier': supplier,
        'invoices': invoices,
        'total_invoices': total_invoices,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'pending_amount': pending_amount,
    }
    
    return render(request, 'frontend/suppliers/detail.html', context)


@login_required
def supplier_invoices_list(request, supplier_pk):
    """Lista de facturas de un proveedor específico"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk)
    invoices = SupplierInvoice.objects.filter(supplier=supplier).order_by('-invoice_date')
    
    # Filtros
    payment_status = request.GET.get('payment_status')
    if payment_status:
        if payment_status == 'overdue':
            invoices = invoices.filter(is_overdue=True)
        else:
            invoices = invoices.filter(payment_status=payment_status)
    
    # Filtro por fechas
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        invoices = invoices.filter(invoice_date__gte=date_from)
    if date_to:
        invoices = invoices.filter(invoice_date__lte=date_to)
    
    # Paginación
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    invoices_page = paginator.get_page(page_number)
    
    context = {
        'supplier': supplier,
        'invoices': invoices_page,
        'filters': {
            'payment_status': payment_status,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'frontend/suppliers/supplier_invoices_list.html', context)


# =============================================================================
# VISTAS DE GASTOS
# =============================================================================




@login_required
def expenses_fixed_list(request):
    """Lista de gastos fijos"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    expenses = FixedExpense.objects.filter(is_active=True).select_related('category').order_by('name')
    
    # Filtro por búsqueda
    search = request.GET.get('search')
    if search:
        expenses = expenses.filter(name__icontains=search)
    
    # Filtro por estado de pago
    payment_status = request.GET.get('payment_status')
    if payment_status == 'up_to_date':
        expenses = [expense for expense in expenses if expense.is_up_to_date]
    elif payment_status == 'overdue':
        expenses = [expense for expense in expenses if not expense.is_up_to_date]
    
    # Paginación
    paginator = Paginator(expenses, 20)
    page_number = request.GET.get('page')
    expenses_page = paginator.get_page(page_number)
    
    context = {
        'expenses': expenses_page,
        'filters': {
            'search': search,
            'payment_status': payment_status,
        }
    }
    
    return render(request, 'frontend/expenses/fixed_list.html', context)








# =============================================================================
# VISTAS DE ESTADÍSTICAS MEJORADAS
# =============================================================================

@login_required
def financial_dashboard(request):
    """Dashboard financiero con estadísticas económicas y financieras"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    # Filtros de fecha
    date_from = request.GET.get('date_from', (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', timezone.now().strftime('%Y-%m-%d'))
    
    # ===== ESTADÍSTICAS ECONÓMICAS (como las actuales) =====
    
    # Ventas por período
    sales_period = Sale.objects.filter(
        created_at__date__range=[date_from, date_to],
        is_active=True
    )
    
    total_sales_count = sales_period.count()
    total_sales_revenue = sales_period.aggregate(total=Sum('total_final'))['total'] or 0
    
    # Costo de mercadería vendida (CMV)
    sale_items = SaleItem.objects.filter(
        sale__created_at__date__range=[date_from, date_to],
        sale__is_active=True
    ).select_related('product')
    
    total_cmv = 0
    for item in sale_items:
        from decimal import Decimal
        product_cost = item.product.cost_price * Decimal(str(item.quantity))
        total_cmv += float(product_cost)
    
    # Utilidad bruta
    total_utility = float(total_sales_revenue) - total_cmv
    
    # ===== ESTADÍSTICAS FINANCIERAS (nuevas) =====
    
    # Ingresos reales (efectivo que realmente entró)
    real_income = sales_period.aggregate(total=Sum('total_final'))['total'] or 0
    
    # Egresos reales (dinero que realmente salió)
    
    # Pagos a proveedores
    supplier_payments = SupplierPayment.objects.filter(
        payment_date__range=[date_from, date_to]
    )
    total_supplier_payments = supplier_payments.aggregate(total=Sum('amount'))['total'] or 0
    
    # Pagos de gastos fijos
    expense_payments = ExpensePayment.objects.filter(
        payment_date__range=[date_from, date_to]
    )
    total_expense_payments = expense_payments.aggregate(total=Sum('amount'))['total'] or 0
    
    # Gastos variables pagados
    variable_expenses = VariableExpense.objects.filter(
        expense_date__range=[date_from, date_to],
        payment_status='paid'
    )
    total_variable_expenses = variable_expenses.aggregate(total=Sum('amount'))['total'] or 0
    
    # Total egresos reales
    total_real_expenses = total_supplier_payments + total_expense_payments + total_variable_expenses
    
    # Saldo financiero real
    real_balance = real_income - total_real_expenses
    
    # ===== ESTADÍSTICAS ADICIONALES =====
    
    # Facturas pendientes de pago (aún no vencidas)
    pending_invoices = SupplierInvoice.objects.filter(
        is_paid=False,
        due_date__gte=timezone.now().date()  # Solo las que aún no vencieron
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Gastos fijos pendientes (aún no vencidos)
    pending_expenses = MonthlyExpense.objects.filter(
        is_paid=False,
        due_date__gte=timezone.now().date()  # Solo los que aún no vencieron
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Gastos vencidos (montos)
    overdue_expenses_amount = MonthlyExpense.objects.filter(
        due_date__lt=timezone.now().date(),
        is_paid=False
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    overdue_invoices_amount = SupplierInvoice.objects.filter(
        due_date__lt=timezone.now().date(),
        is_paid=False
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Cantidad de vencidos (para estadísticas adicionales)
    overdue_expenses_count = MonthlyExpense.objects.filter(
        due_date__lt=timezone.now().date(),
        is_paid=False
    ).count()
    
    overdue_invoices_count = SupplierInvoice.objects.filter(
        due_date__lt=timezone.now().date(),
        is_paid=False
    ).count()
    
    # Convertir a Decimal para evitar errores de tipos en el cálculo del porcentaje
    from decimal import Decimal
    total_cmv_decimal = Decimal(str(total_cmv))
    total_sales_revenue_decimal = Decimal(str(total_sales_revenue))
    
    context = {
        # Filtros
        'date_from': date_from,
        'date_to': date_to,
        
        # Económicas
        'total_sales_count': total_sales_count,
        'total_sales_revenue': total_sales_revenue,
        'total_cmv': total_cmv,
        'total_utility': total_utility,
        'cmv_percentage': (total_cmv_decimal / total_sales_revenue_decimal * 100) if total_sales_revenue_decimal > 0 else 0,
        
        # Financieras
        'real_income': real_income,
        'total_supplier_payments': total_supplier_payments,
        'total_expense_payments': total_expense_payments,
        'total_variable_expenses': total_variable_expenses,
        'total_real_expenses': total_real_expenses,
        'real_balance': real_balance,
        
        # Pendientes
        'pending_invoices': pending_invoices,
        'pending_expenses': pending_expenses,
        
        # Vencidos (montos)
        'overdue_invoices_amount': overdue_invoices_amount,
        'overdue_expenses_amount': overdue_expenses_amount,
        
        # Vencidos (cantidades)
        'overdue_expenses_count': overdue_expenses_count,
        'overdue_invoices_count': overdue_invoices_count,
    }
    
    return render(request, 'frontend/financial_dashboard.html', context) 

# =============================================================================
# VISTAS DE COSTOS FIJOS
# =============================================================================

@login_required
def expense_fixed_detail(request, pk):
    """Detalle de un costo fijo con sus boletas"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    expense = get_object_or_404(FixedExpense, pk=pk, is_active=True)
    bills = expense.monthly_expenses.all().order_by('-year', '-month')
    
    # Estadísticas del costo fijo
    total_bills = bills.count()
    total_amount = bills.aggregate(total=Sum('amount'))['total'] or 0
    paid_amount = bills.filter(is_paid=True).aggregate(total=Sum('amount'))['total'] or 0
    pending_amount = total_amount - paid_amount
    
    context = {
        'expense': expense,
        'bills': bills,
        'total_bills': total_bills,
        'total_amount': total_amount,
        'paid_amount': paid_amount,
        'pending_amount': pending_amount,
    }
    
    return render(request, 'frontend/expenses/fixed_detail.html', context)


@login_required
def expense_bills_list(request, expense_pk):
    """Lista de boletas de un costo fijo específico"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    expense = get_object_or_404(FixedExpense, pk=expense_pk, is_active=True)
    bills = expense.monthly_expenses.all().order_by('-year', '-month')
    
    # Filtros
    payment_status = request.GET.get('payment_status')
    if payment_status:
        if payment_status == 'overdue':
            bills = bills.filter(is_overdue=True)
        else:
            bills = bills.filter(payment_status=payment_status)
    
    # Filtro por año y mes
    year = request.GET.get('year')
    if year:
        bills = bills.filter(year=year)
    
    month = request.GET.get('month')
    if month:
        bills = bills.filter(month=month)
    
    # Filtro por fechas
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        bills = bills.filter(due_date__gte=date_from)
    if date_to:
        bills = bills.filter(due_date__lte=date_to)
    
    # Paginación
    paginator = Paginator(bills, 20)
    page_number = request.GET.get('page')
    bills_page = paginator.get_page(page_number)
    
    context = {
        'expense': expense,
        'bills': bills_page,
        'filters': {
            'payment_status': payment_status,
            'year': year,
            'month': month,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'frontend/expenses/expense_bills_list.html', context)


@login_required
def expense_fixed_create(request):
    """Crear nuevo costo fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    # Obtener categorías para el formulario
    categories = ExpenseCategory.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            name = request.POST.get('name')
            category_id = request.POST.get('category')
            amount = request.POST.get('amount')
            frequency = request.POST.get('frequency')
            due_day = request.POST.get('due_day')
            description = request.POST.get('description', '')
            
            # Validaciones básicas
            if not name or not category_id or not amount or not frequency or not due_day:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/expenses/create.html', {'categories': categories})
            
            # Validar que la categoría existe
            try:
                category = ExpenseCategory.objects.get(id=category_id, is_active=True)
            except ExpenseCategory.DoesNotExist:
                messages.error(request, 'La categoría seleccionada no es válida')
                return render(request, 'frontend/expenses/create.html', {'categories': categories})
            
            # Crear el costo fijo
            expense = FixedExpense.objects.create(
                name=name,
                category=category,
                amount=amount,
                frequency=frequency,
                due_day=due_day,
                description=description,
                is_active=True
            )
            
            messages.success(request, f'Costo fijo "{expense.name}" creado exitosamente')
            return redirect('frontend:expense_fixed_detail', pk=expense.pk)
            
        except Exception as e:
            messages.error(request, f'Error al crear el costo fijo: {str(e)}')
            return render(request, 'frontend/expenses/create.html', {'categories': categories})
    
    context = {
        'categories': categories,
    }
    
    return render(request, 'frontend/expenses/create.html', context)


@login_required
def expense_bill_create(request, expense_pk):
    """Crear nueva boleta para un costo fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    expense = get_object_or_404(FixedExpense, pk=expense_pk, is_active=True)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            year = request.POST.get('year')
            month = request.POST.get('month')
            amount = request.POST.get('amount')
            due_date = request.POST.get('due_date')
            description = request.POST.get('description', '')
            
            # Validaciones básicas
            if not year or not month or not amount or not due_date:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/expenses/bill_create.html', {'expense': expense})
            
            # Función para obtener el nombre del mes
            def get_month_name(month_num):
                months = {
                    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
                    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
                }
                return months.get(month_num, '')
            
            # Función para obtener el número de semana del mes
            def get_week_of_month(date):
                from datetime import datetime
                first_day = date.replace(day=1)
                first_weekday = first_day.weekday()
                days_since_first_weekday = (date.day - 1) + first_weekday
                return (days_since_first_weekday // 7) + 1
            
            # Validación según la frecuencia del gasto
            if expense.frequency == 'weekly':
                # Para gastos semanales: validar que no exista una boleta para la misma semana
                due_date_obj = datetime.strptime(due_date, '%Y-%m-%d').date()
                week_of_month = get_week_of_month(due_date_obj)
                
                # Buscar boletas existentes en el mismo mes y año
                existing_bills = MonthlyExpense.objects.filter(
                    fixed_expense=expense,
                    year=year,
                    month=month
                )
                
                # Verificar si ya existe una boleta para la misma semana
                for bill in existing_bills:
                    bill_week = get_week_of_month(bill.due_date)
                    if bill_week == week_of_month:
                        month_name = get_month_name(int(month))
                        messages.error(request, f'Ya existe una boleta para la semana {week_of_month} de {month_name} {year}')
                        return render(request, 'frontend/expenses/bill_create.html', {'expense': expense})
                        
            else:
                # Para otras frecuencias (mensual, trimestral, etc.): validar que no exista una boleta para ese mes/año
                existing_bill = MonthlyExpense.objects.filter(
                    fixed_expense=expense,
                    year=year,
                    month=month
                ).first()
                
                if existing_bill:
                    month_name = get_month_name(int(month))
                    messages.error(request, f'Ya existe una boleta para {month_name} {year}')
                    return render(request, 'frontend/expenses/bill_create.html', {'expense': expense})
            
            # Crear la boleta
            bill = MonthlyExpense.objects.create(
                fixed_expense=expense,
                year=year,
                month=month,
                amount=amount,
                due_date=due_date,
                notes=description,
                payment_status='pending'
            )
            
            month_name = get_month_name(int(month))
            messages.success(request, f'Boleta creada exitosamente para {month_name} {year}')
            return redirect('frontend:expense_bills_list', expense_pk=expense.pk)
            
        except Exception as e:
            messages.error(request, f'Error al crear la boleta: {str(e)}')
            return render(request, 'frontend/expenses/bill_create.html', {'expense': expense})
    
    context = {
        'expense': expense,
    }
    
    return render(request, 'frontend/expenses/bill_create.html', context)


@login_required
def expense_bill_pay(request, bill_id):
    """Marcar una boleta como pagada"""
    if not request.user.is_admin:
        return JsonResponse({
            'success': False,
            'message': 'No tienes permisos para realizar esta acción'
        })
    
    try:
        bill = get_object_or_404(MonthlyExpense, pk=bill_id)
        
        # Verificar que la boleta no esté ya pagada
        if bill.payment_status == 'paid':
            return JsonResponse({
                'success': False,
                'message': 'Esta boleta ya está marcada como pagada'
            })
        
        # Calcular el monto restante por pagar
        remaining_amount = bill.remaining_amount
        
        # Crear un registro de pago por el monto restante
        ExpensePayment.objects.create(
            monthly_expense=bill,
            amount=remaining_amount,
            payment_date=timezone.now().date(),
            payment_method='transfer',  # Por defecto transferencia
            reference=f'Pago automático - {bill.fixed_expense.name}',
            notes=f'Pago automático de boleta {bill.get_month_display()} {bill.year}'
        )
        
        # Actualizar el estado de la boleta
        bill.update_payment_status()
        bill.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Boleta marcada como pagada exitosamente. Se registró un pago de ${remaining_amount}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al procesar el pago: {str(e)}'
        })


@login_required
def supplier_create(request):
    """Crear nuevo proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            name = request.POST.get('name')
            cuit = request.POST.get('cuit', '')
            phone = request.POST.get('phone', '')
            email = request.POST.get('email', '')
            address = request.POST.get('address', '')
            notes = request.POST.get('notes', '')
            
            # Validaciones básicas
            if not name:
                messages.error(request, 'El nombre del proveedor es obligatorio')
                return render(request, 'frontend/suppliers/create.html')
            
            # Crear el proveedor
            supplier = Supplier.objects.create(
                name=name,
                cuit=cuit,
                phone=phone,
                email=email,
                address=address,
                notes=notes,
                is_active=True
            )
            
            messages.success(request, f'Proveedor "{supplier.name}" creado exitosamente')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al crear el proveedor: {str(e)}')
            return render(request, 'frontend/suppliers/create.html')
    
    return render(request, 'frontend/suppliers/create.html')


@login_required
def supplier_edit(request, pk):
    """Editar proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=pk, is_active=True)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            name = request.POST.get('name')
            cuit = request.POST.get('cuit', '')
            phone = request.POST.get('phone', '')
            email = request.POST.get('email', '')
            address = request.POST.get('address', '')
            notes = request.POST.get('notes', '')
            
            # Validaciones básicas
            if not name:
                messages.error(request, 'El nombre del proveedor es obligatorio')
                return render(request, 'frontend/suppliers/edit.html', {'supplier': supplier})
            
            # Actualizar el proveedor
            supplier.name = name
            supplier.cuit = cuit
            supplier.phone = phone
            supplier.email = email
            supplier.address = address
            supplier.notes = notes
            supplier.save()
            
            messages.success(request, f'Proveedor "{supplier.name}" actualizado exitosamente')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el proveedor: {str(e)}')
            return render(request, 'frontend/suppliers/edit.html', {'supplier': supplier})
    
    return render(request, 'frontend/suppliers/edit.html', {'supplier': supplier})


@login_required
def supplier_account_status(request, pk):
    """Estado de cuenta de un proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=pk, is_active=True)
    
    # Obtener todas las facturas del proveedor con sus pagos
    invoices = SupplierInvoice.objects.filter(supplier=supplier).order_by('invoice_date')
    
    # Calcular totales
    total_purchases = invoices.aggregate(total=Sum('total_amount'))['total'] or 0
    total_payments = sum(
        payment.amount 
        for invoice in invoices 
        for payment in invoice.payments.all()
    )
    balance = total_purchases - total_payments
    
    # Preparar datos para el template
    invoices_data = []
    for invoice in invoices:
        payments = invoice.payments.all().order_by('payment_date')
        invoices_data.append({
            'invoice': invoice,
            'payments': payments,
            'paid_amount': invoice.paid_amount,
            'remaining_amount': invoice.remaining_amount,
            'payment_status': invoice.payment_status
        })
    
    context = {
        'supplier': supplier,
        'invoices_data': invoices_data,
        'total_purchases': total_purchases,
        'total_payments': total_payments,
        'balance': balance,
        'issue_date': timezone.now().date(),
    }
    return render(request, 'frontend/suppliers/account_status.html', context)


@login_required
def supplier_invoice_create(request, supplier_pk):
    """Crear nueva factura para un proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk, is_active=True)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            invoice_number = request.POST.get('invoice_number')
            invoice_date = request.POST.get('invoice_date')
            due_date = request.POST.get('due_date')
            total_amount = request.POST.get('total_amount')
            description = request.POST.get('description', '')
            
            # Validaciones básicas
            if not invoice_number or not invoice_date or not due_date or not total_amount:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/suppliers/invoice_create.html', {'supplier': supplier})
            
            # Verificar que no exista una factura con el mismo número
            existing_invoice = SupplierInvoice.objects.filter(
                supplier=supplier,
                invoice_number=invoice_number
            ).first()
            
            if existing_invoice:
                messages.error(request, f'Ya existe una factura con el número {invoice_number}')
                return render(request, 'frontend/suppliers/invoice_create.html', {'supplier': supplier})
            
            # Crear la factura
            invoice = SupplierInvoice.objects.create(
                supplier=supplier,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                due_date=due_date,
                total_amount=total_amount,
                description=description,
                payment_status='pending'
            )
            
            messages.success(request, f'Factura {invoice.invoice_number} creada exitosamente')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al crear la factura: {str(e)}')
            return render(request, 'frontend/suppliers/invoice_create.html', {'supplier': supplier})
    
    return render(request, 'frontend/suppliers/invoice_create.html', {'supplier': supplier})


@login_required
def supplier_payment_create(request, supplier_pk):
    """Crear nuevo pago para un proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk, is_active=True)
    
    # Obtener facturas con monto pendiente (no solo las marcadas como no pagadas)
    pending_invoices = SupplierInvoice.objects.filter(
        supplier=supplier
    ).exclude(
        is_paid=True  # Excluir solo las completamente pagadas
    ).order_by('due_date')
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            invoice_id = request.POST.get('invoice')
            amount = request.POST.get('amount')
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method')
            reference = request.POST.get('reference', '')
            
            # Validaciones básicas
            if not invoice_id or not amount or not payment_date or not payment_method:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/suppliers/payment_create.html', {
                    'supplier': supplier,
                    'pending_invoices': pending_invoices
                })
            
            # Obtener la factura
            invoice = get_object_or_404(SupplierInvoice, pk=invoice_id, supplier=supplier)
            
            # Validar que la factura no esté completamente pagada
            if invoice.is_paid:
                messages.error(request, f'La factura {invoice.invoice_number} ya está completamente pagada')
                return render(request, 'frontend/suppliers/payment_create.html', {
                    'supplier': supplier,
                    'pending_invoices': pending_invoices
                })
            
            # Validar que el monto del pago no exceda el monto pendiente
            if float(amount) > float(invoice.remaining_amount):
                messages.error(request, f'El monto del pago (${amount}) no puede exceder el monto pendiente (${invoice.remaining_amount})')
                return render(request, 'frontend/suppliers/payment_create.html', {
                    'supplier': supplier,
                    'pending_invoices': pending_invoices
                })
            
            # Validar que el monto sea mayor a cero
            if float(amount) <= 0:
                messages.error(request, 'El monto del pago debe ser mayor a cero')
                return render(request, 'frontend/suppliers/payment_create.html', {
                    'supplier': supplier,
                    'pending_invoices': pending_invoices
                })
            
            # Crear el pago
            payment = SupplierPayment.objects.create(
                invoice=invoice,
                amount=amount,
                payment_date=payment_date,
                payment_method=payment_method,
                reference=reference
            )
            
            # Actualizar el estado de la factura
            invoice.update_payment_status()
            invoice.save()
            
            messages.success(request, f'Pago de ${amount} registrado exitosamente para la factura {invoice.invoice_number}')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al registrar el pago: {str(e)}')
            return render(request, 'frontend/suppliers/payment_create.html', {
                'supplier': supplier,
                'pending_invoices': pending_invoices
            })
    
    return render(request, 'frontend/suppliers/payment_create.html', {
        'supplier': supplier,
        'pending_invoices': pending_invoices
    })


@login_required
def supplier_delete(request, pk):
    """Eliminar proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=pk, is_active=True)
    
    if request.method == 'POST':
        try:
            # Verificar si tiene facturas asociadas
            invoices_count = supplier.invoices.count()
            if invoices_count > 0:
                messages.error(request, f'No se puede eliminar el proveedor porque tiene {invoices_count} factura(s) asociada(s)')
                return redirect('frontend:suppliers_list')
            
            # Eliminar el proveedor (soft delete)
            supplier.is_active = False
            supplier.save()
            
            messages.success(request, f'Proveedor "{supplier.name}" eliminado exitosamente')
            return redirect('frontend:suppliers_list')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar el proveedor: {str(e)}')
            return redirect('frontend:suppliers_list')
    
    # Si es GET, mostrar confirmación
    return render(request, 'frontend/suppliers/delete_confirm.html', {'supplier': supplier})


@login_required
def supplier_invoice_edit(request, supplier_pk, invoice_pk):
    """Editar factura de proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk, is_active=True)
    invoice = get_object_or_404(SupplierInvoice, pk=invoice_pk, supplier=supplier)
    
    # Convertir el monto a string para el template
    invoice.total_amount_str = str(invoice.total_amount)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            invoice_number = request.POST.get('invoice_number')
            invoice_date = request.POST.get('invoice_date')
            due_date = request.POST.get('due_date')
            total_amount = request.POST.get('total_amount')
            description = request.POST.get('description', '')
            
            # Validaciones básicas
            if not invoice_number or not invoice_date or not due_date or not total_amount:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/suppliers/invoice_edit.html', {
                    'supplier': supplier,
                    'invoice': invoice
                })
            
            # Verificar que no exista otra factura con el mismo número
            existing_invoice = SupplierInvoice.objects.filter(
                supplier=supplier,
                invoice_number=invoice_number
            ).exclude(pk=invoice_pk).first()
            
            if existing_invoice:
                messages.error(request, f'Ya existe una factura con el número {invoice_number}')
                return render(request, 'frontend/suppliers/invoice_edit.html', {
                    'supplier': supplier,
                    'invoice': invoice
                })
            
            # Actualizar la factura
            invoice.invoice_number = invoice_number
            invoice.invoice_date = invoice_date
            invoice.due_date = due_date
            invoice.total_amount = total_amount
            invoice.description = description
            invoice.save()
            
            messages.success(request, f'Factura {invoice.invoice_number} actualizada exitosamente')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar la factura: {str(e)}')
            return render(request, 'frontend/suppliers/invoice_edit.html', {
                'supplier': supplier,
                'invoice': invoice
            })
    
    return render(request, 'frontend/suppliers/invoice_edit.html', {
        'supplier': supplier,
        'invoice': invoice
    })


@login_required
def supplier_payment_edit(request, supplier_pk, payment_pk):
    """Editar pago de proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk, is_active=True)
    payment = get_object_or_404(SupplierPayment, pk=payment_pk, invoice__supplier=supplier)
    
    # Convertir el monto a string para el template
    payment.amount_str = str(payment.amount)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            invoice_id = request.POST.get('invoice')
            amount = request.POST.get('amount')
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method')
            reference = request.POST.get('reference', '')
            
            # Validaciones básicas
            if not invoice_id or not amount or not payment_date or not payment_method:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/suppliers/payment_edit.html', {
                    'supplier': supplier,
                    'payment': payment
                })
            
            # Obtener la factura
            invoice = get_object_or_404(SupplierInvoice, pk=invoice_id, supplier=supplier)
            
            # Actualizar el pago
            payment.invoice = invoice
            payment.amount = amount
            payment.payment_date = payment_date
            payment.payment_method = payment_method
            payment.reference = reference
            payment.save()
            
            # Actualizar el estado de la factura
            invoice.update_payment_status()
            invoice.save()
            
            messages.success(request, f'Pago actualizado exitosamente')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el pago: {str(e)}')
            return render(request, 'frontend/suppliers/payment_edit.html', {
                'supplier': supplier,
                'payment': payment
            })
    
    # Obtener facturas para el select
    invoices = SupplierInvoice.objects.filter(supplier=supplier).order_by('invoice_date')
    
    return render(request, 'frontend/suppliers/payment_edit.html', {
        'supplier': supplier,
        'payment': payment,
        'invoices': invoices
    })


@login_required
def supplier_invoice_delete(request, supplier_pk, invoice_pk):
    """Eliminar factura de proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk, is_active=True)
    invoice = get_object_or_404(SupplierInvoice, pk=invoice_pk, supplier=supplier)
    
    if request.method == 'POST':
        try:
            # Verificar si tiene pagos asociados
            payments_count = invoice.payments.count()
            if payments_count > 0:
                messages.error(request, f'No se puede eliminar la factura porque tiene {payments_count} pago(s) asociado(s)')
                return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
            # Eliminar la factura
            invoice.delete()
            
            messages.success(request, f'Factura {invoice.invoice_number} eliminada exitosamente')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al eliminar la factura: {str(e)}')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
    
    # Si es GET, mostrar confirmación
    return render(request, 'frontend/suppliers/invoice_delete_confirm.html', {
        'supplier': supplier,
        'invoice': invoice
    })


@login_required
def supplier_payment_delete(request, supplier_pk, payment_pk):
    """Eliminar pago de proveedor"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    supplier = get_object_or_404(Supplier, pk=supplier_pk, is_active=True)
    payment = get_object_or_404(SupplierPayment, pk=payment_pk, invoice__supplier=supplier)
    
    if request.method == 'POST':
        try:
            # Guardar referencia a la factura para actualizar su estado después
            invoice = payment.invoice
            
            # Eliminar el pago
            payment.delete()
            
            # Actualizar el estado de la factura
            invoice.update_payment_status()
            invoice.save()
            
            messages.success(request, f'Pago eliminado exitosamente')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
            
        except Exception as e:
            messages.error(request, f'Error al eliminar el pago: {str(e)}')
            return redirect('frontend:supplier_account_status', pk=supplier.pk)
    
    # Si es GET, mostrar confirmación
    return render(request, 'frontend/suppliers/payment_delete_confirm.html', {
        'supplier': supplier,
        'payment': payment
    })


@login_required
def fixed_expense_delete(request, pk):
    """Eliminar un gasto fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para realizar esta acción')
        return redirect('frontend:expense_fixed_list')
    
    fixed_expense = get_object_or_404(FixedExpense, pk=pk, is_active=True)
    
    if request.method == 'POST':
        try:
            from django.db import transaction
            
            with transaction.atomic():
                # Obtener información antes de eliminar para el mensaje
                bills_count = MonthlyExpense.objects.filter(fixed_expense=fixed_expense).count()
                payments_count = ExpensePayment.objects.filter(monthly_expense__fixed_expense=fixed_expense).count()
                expense_name = fixed_expense.name
                
                # Eliminar todos los pagos asociados primero
                ExpensePayment.objects.filter(monthly_expense__fixed_expense=fixed_expense).delete()
                
                # Eliminar todas las boletas asociadas
                MonthlyExpense.objects.filter(fixed_expense=fixed_expense).delete()
                
                # Finalmente eliminar el gasto fijo completamente
                fixed_expense.delete()
                
                # Mensaje de éxito con información de lo eliminado
                message = f'Gasto fijo "{expense_name}" eliminado completamente'
                if bills_count > 0 or payments_count > 0:
                    message += f' junto con {bills_count} boleta{"s" if bills_count != 1 else ""} y {payments_count} pago{"s" if payments_count != 1 else ""} asociado{"s" if (bills_count + payments_count) != 1 else ""}'
                message += '.'
                
                messages.success(request, message)
                return redirect('frontend:expenses_fixed_list')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar el gasto fijo: {str(e)}')
            return redirect('frontend:expenses_fixed_list')
    
    # Obtener información para mostrar en la confirmación
    bills_count = MonthlyExpense.objects.filter(fixed_expense=fixed_expense).count()
    payments_count = ExpensePayment.objects.filter(monthly_expense__fixed_expense=fixed_expense).count()
    
    context = {
        'fixed_expense': fixed_expense,
        'bills_count': bills_count,
        'payments_count': payments_count,
    }
    
    return render(request, 'frontend/expenses/fixed_delete.html', context)


@login_required
def fixed_expense_account_status(request, pk):
    """Estado de cuenta de un gasto fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    fixed_expense = get_object_or_404(FixedExpense, pk=pk, is_active=True)
    
    # Obtener parámetros de filtrado
    from datetime import datetime
    current_date = datetime.now()
    selected_year = request.GET.get('year', current_date.year)
    selected_month = request.GET.get('month', '')  # Cambiado de current_date.month a ''
    
    try:
        selected_year = int(selected_year)
        selected_month = int(selected_month) if selected_month else None
    except (ValueError, TypeError):
        selected_year = current_date.year
        selected_month = None
    
    # Obtener todas las boletas mensuales del gasto fijo
    monthly_expenses = MonthlyExpense.objects.filter(
        fixed_expense=fixed_expense
    ).order_by('-year', '-month')
    
    # Filtrar por año y mes si se especifica
    if selected_year and selected_month:
        monthly_expenses = monthly_expenses.filter(year=selected_year, month=selected_month)
    elif selected_year:
        monthly_expenses = monthly_expenses.filter(year=selected_year)
    # Si no se especifica mes, mostrar todos los meses del año seleccionado
    
    # Calcular totales
    total_amount = sum(expense.amount for expense in monthly_expenses)
    total_paid = sum(expense.paid_amount for expense in monthly_expenses)
    balance = total_amount - total_paid
    
    # Preparar datos para el template
    expenses_data = []
    for expense in monthly_expenses:
        payments = expense.payments.all().order_by('payment_date')
        expenses_data.append({
            'expense': expense,
            'payments': payments,
            'paid_amount': expense.paid_amount,
            'remaining_amount': expense.remaining_amount,
            'payment_status': expense.payment_status
        })
    
    # Generar años disponibles (desde 2020 hasta el año actual + 1)
    years = list(range(2020, current_date.year + 2))
    months = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    context = {
        'fixed_expense': fixed_expense,
        'expenses_data': expenses_data,
        'total_amount': total_amount,
        'total_paid': total_paid,
        'balance': balance,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'years': years,
        'months': months,
        'current_date': current_date,
        'issue_date': timezone.now().date(),
    }
    return render(request, 'frontend/expenses/account_status.html', context)


@login_required
def expense_payment_create(request, expense_pk):
    """Crear nuevo pago para un gasto fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    fixed_expense = get_object_or_404(FixedExpense, pk=expense_pk, is_active=True)
    
    # Definir variables de fecha actual fuera del bloque POST
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            amount = request.POST.get('amount')
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method')
            reference = request.POST.get('reference', '')
            
            # Validaciones básicas
            if not amount or not payment_date or not payment_method:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                # Buscar el período más apropiado para mostrar en el template
                current_date = datetime.now()
                
                # Buscar primero las boletas vencidas (prioridad máxima)
                next_pending_expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    is_paid=False,
                    due_date__lt=current_date.date()
                ).order_by('due_date').first()
                
                # Si no hay boletas vencidas, buscar el período actual
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        year=current_year,
                        month=current_month,
                        is_paid=False
                    ).first()
                
                # Si no hay período actual con pendiente, buscar el más próximo
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        is_paid=False
                    ).order_by('year', 'month').first()
                
                return render(request, 'frontend/expenses/payment_create.html', {
                    'fixed_expense': fixed_expense,
                    'pending_info': {
                        'current_month': current_month,
                        'current_year': current_year,
                        'next_pending_expense': next_pending_expense
                    }
                })
            
            # Validar que el monto sea mayor a cero
            if float(amount) <= 0:
                messages.error(request, 'El monto del pago debe ser mayor a cero')
                # Buscar el período más apropiado para mostrar en el template
                current_date = datetime.now()
                
                # Buscar primero las boletas vencidas (prioridad máxima)
                next_pending_expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    is_paid=False,
                    due_date__lt=current_date.date()
                ).order_by('due_date').first()
                
                # Si no hay boletas vencidas, buscar el período actual
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        year=current_year,
                        month=current_month,
                        is_paid=False
                    ).first()
                
                # Si no hay período actual con pendiente, buscar el más próximo
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        is_paid=False
                    ).order_by('year', 'month').first()
                
                return render(request, 'frontend/expenses/payment_create.html', {
                    'fixed_expense': fixed_expense,
                    'pending_info': {
                        'current_month': current_month,
                        'current_year': current_year,
                        'next_pending_expense': next_pending_expense
                    }
                })
            
            # Buscar el período más apropiado para asignar el pago
            # Priorizar las boletas vencidas, luego el período actual, luego el más próximo
            current_date = datetime.now()
            current_year = current_date.year
            current_month = current_date.month
            
            # Buscar primero las boletas vencidas (prioridad máxima)
            expense = MonthlyExpense.objects.filter(
                fixed_expense=fixed_expense,
                is_paid=False,
                due_date__lt=current_date.date()
            ).order_by('due_date').first()
            
            # Si no hay boletas vencidas, buscar el período actual
            if not expense:
                expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    year=current_year,
                    month=current_month,
                    is_paid=False
                ).first()
            
            # Si no hay período actual con pendiente, buscar el más próximo
            if not expense:
                expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    is_paid=False
                ).order_by('year', 'month').first()
            
            # Si no hay ningún período con pendiente, mostrar error
            if not expense:
                messages.error(request, 'No hay períodos pendientes de pago para este gasto fijo')
                # Buscar el período más apropiado para mostrar en el template
                current_date = datetime.now()
                
                # Buscar primero las boletas vencidas (prioridad máxima)
                next_pending_expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    is_paid=False,
                    due_date__lt=current_date.date()
                ).order_by('due_date').first()
                
                # Si no hay boletas vencidas, buscar el período actual
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        year=current_year,
                        month=current_month,
                        is_paid=False
                    ).first()
                
                # Si no hay período actual con pendiente, buscar el más próximo
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        is_paid=False
                    ).order_by('year', 'month').first()
                
                return render(request, 'frontend/expenses/payment_create.html', {
                    'fixed_expense': fixed_expense,
                    'pending_info': {
                        'current_month': current_month,
                        'current_year': current_year,
                        'next_pending_expense': next_pending_expense
                    }
                })
            
            # Verificar que el período tenga monto pendiente
            if expense.remaining_amount <= 0:
                messages.error(request, f'El período {expense.get_month_display()} {expense.year} ya está completamente pagado')
                # Buscar el período más apropiado para mostrar en el template
                current_date = datetime.now()
                
                # Buscar primero las boletas vencidas (prioridad máxima)
                next_pending_expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    is_paid=False,
                    due_date__lt=current_date.date()
                ).order_by('due_date').first()
                
                # Si no hay boletas vencidas, buscar el período actual
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        year=current_year,
                        month=current_month,
                        is_paid=False
                    ).first()
                
                # Si no hay período actual con pendiente, buscar el más próximo
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        is_paid=False
                    ).order_by('year', 'month').first()
                
                return render(request, 'frontend/expenses/payment_create.html', {
                    'fixed_expense': fixed_expense,
                    'pending_info': {
                        'current_month': current_month,
                        'current_year': current_year,
                        'next_pending_expense': next_pending_expense
                    }
                })
            
            # Validar que el monto del pago no exceda el monto pendiente
            if float(amount) > float(expense.remaining_amount):
                messages.error(request, f'El monto del pago (${amount}) no puede exceder el monto pendiente (${expense.remaining_amount}) del período {expense.get_month_display()} {expense.year}')
                # Buscar el período más apropiado para mostrar en el template
                current_date = datetime.now()
                
                # Buscar primero las boletas vencidas (prioridad máxima)
                next_pending_expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    is_paid=False,
                    due_date__lt=current_date.date()
                ).order_by('due_date').first()
                
                # Si no hay boletas vencidas, buscar el período actual
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        year=current_year,
                        month=current_month,
                        is_paid=False
                    ).first()
                
                # Si no hay período actual con pendiente, buscar el más próximo
                if not next_pending_expense:
                    next_pending_expense = MonthlyExpense.objects.filter(
                        fixed_expense=fixed_expense,
                        is_paid=False
                    ).order_by('year', 'month').first()
                
                return render(request, 'frontend/expenses/payment_create.html', {
                    'fixed_expense': fixed_expense,
                    'pending_info': {
                        'current_month': current_month,
                        'current_year': current_year,
                        'next_pending_expense': next_pending_expense
                    }
                })
            
            # Crear el pago
            payment = ExpensePayment.objects.create(
                monthly_expense=expense,
                amount=amount,
                payment_date=payment_date,
                payment_method=payment_method,
                reference=reference
            )
            
            # Actualizar el estado de la boleta
            expense.update_payment_status()
            expense.save()
            
            messages.success(request, f'Pago de ${amount} registrado exitosamente para {expense.get_month_display()} {expense.year}')
            return redirect('frontend:fixed_expense_account_status', pk=fixed_expense.pk)
            
        except Exception as e:
            messages.error(request, f'Error al registrar el pago: {str(e)}')
            # Buscar el período más apropiado para mostrar en el template
            current_date = datetime.now()
            
            # Buscar primero las boletas vencidas (prioridad máxima)
            next_pending_expense = MonthlyExpense.objects.filter(
                fixed_expense=fixed_expense,
                is_paid=False,
                due_date__lt=current_date.date()
            ).order_by('due_date').first()
            
            # Si no hay boletas vencidas, buscar el período actual
            if not next_pending_expense:
                next_pending_expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    year=current_year,
                    month=current_month,
                    is_paid=False
                ).first()
            
            # Si no hay período actual con pendiente, buscar el más próximo
            if not next_pending_expense:
                next_pending_expense = MonthlyExpense.objects.filter(
                    fixed_expense=fixed_expense,
                    is_paid=False
                ).order_by('year', 'month').first()
            
            return render(request, 'frontend/expenses/payment_create.html', {
                'fixed_expense': fixed_expense,
                'pending_info': {
                    'current_month': current_month,
                    'current_year': current_year,
                    'next_pending_expense': next_pending_expense
                }
            })
    
    # Buscar el período más apropiado para mostrar en el template
    # Priorizar las boletas vencidas, luego el período actual, luego el más próximo
    current_date = datetime.now()
    
    # Buscar primero las boletas vencidas (prioridad máxima)
    next_pending_expense = MonthlyExpense.objects.filter(
        fixed_expense=fixed_expense,
        is_paid=False,
        due_date__lt=current_date.date()
    ).order_by('due_date').first()
    
    # Si no hay boletas vencidas, buscar el período actual
    if not next_pending_expense:
        next_pending_expense = MonthlyExpense.objects.filter(
            fixed_expense=fixed_expense,
            year=current_year,
            month=current_month,
            is_paid=False
        ).first()
    
    # Si no hay período actual con pendiente, buscar el más próximo
    if not next_pending_expense:
        next_pending_expense = MonthlyExpense.objects.filter(
            fixed_expense=fixed_expense,
            is_paid=False
        ).order_by('year', 'month').first()
    
    return render(request, 'frontend/expenses/payment_create.html', {
        'fixed_expense': fixed_expense,
        'pending_info': {
            'current_month': current_month,
            'current_year': current_year,
            'next_pending_expense': next_pending_expense
        }
    })


@login_required
def expense_payment_edit(request, expense_pk, payment_pk):
    """Editar pago de gasto fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    fixed_expense = get_object_or_404(FixedExpense, pk=expense_pk, is_active=True)
    payment = get_object_or_404(ExpensePayment, pk=payment_pk, monthly_expense__fixed_expense=fixed_expense)
    
    # Convertir el monto a string para el template
    payment.amount_str = str(payment.amount)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            expense_id = request.POST.get('expense')
            amount = request.POST.get('amount')
            payment_date = request.POST.get('payment_date')
            payment_method = request.POST.get('payment_method')
            reference = request.POST.get('reference', '')
            
            # Validaciones básicas
            if not expense_id or not amount or not payment_date or not payment_method:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/expenses/payment_edit.html', {
                    'fixed_expense': fixed_expense,
                    'payment': payment
                })
            
            # Obtener la boleta
            expense = get_object_or_404(MonthlyExpense, pk=expense_id, fixed_expense=fixed_expense)
            
            # Actualizar el pago
            payment.monthly_expense = expense
            payment.amount = amount
            payment.payment_date = payment_date
            payment.payment_method = payment_method
            payment.reference = reference
            payment.save()
            
            # Actualizar el estado de la boleta
            expense.update_payment_status()
            expense.save()
            
            messages.success(request, f'Pago actualizado exitosamente')
            return redirect('frontend:fixed_expense_account_status', pk=fixed_expense.pk)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar el pago: {str(e)}')
            return render(request, 'frontend/expenses/payment_edit.html', {
                'fixed_expense': fixed_expense,
                'payment': payment
            })
    
    # Obtener boletas para el select
    expenses = MonthlyExpense.objects.filter(fixed_expense=fixed_expense).order_by('-year', '-month')
    
    return render(request, 'frontend/expenses/payment_edit.html', {
        'fixed_expense': fixed_expense,
        'payment': payment,
        'expenses': expenses
    })


@login_required
def expense_bill_edit(request, expense_pk, bill_pk):
    """Editar boleta de gasto fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    fixed_expense = get_object_or_404(FixedExpense, pk=expense_pk, is_active=True)
    bill = get_object_or_404(MonthlyExpense, pk=bill_pk, fixed_expense=fixed_expense)
    
    # Convertir el monto a string para el template
    bill.amount_str = str(bill.amount)
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            year = request.POST.get('year')
            month = request.POST.get('month')
            amount = request.POST.get('amount')
            due_date = request.POST.get('due_date')
            notes = request.POST.get('notes', '')
            
            # Validaciones básicas
            if not year or not month or not amount or not due_date:
                messages.error(request, 'Todos los campos obligatorios deben estar completos')
                return render(request, 'frontend/expenses/bill_edit.html', {
                    'fixed_expense': fixed_expense,
                    'bill': bill
                })
            
            # Verificar que no exista otra boleta para el mismo mes/año
            existing_bill = MonthlyExpense.objects.filter(
                fixed_expense=fixed_expense,
                year=year,
                month=month
            ).exclude(pk=bill.pk).first()
            
            if existing_bill:
                messages.error(request, f'Ya existe una boleta para {existing_bill.get_month_display()} {existing_bill.year}')
                return render(request, 'frontend/expenses/bill_edit.html', {
                    'fixed_expense': fixed_expense,
                    'bill': bill
                })
            
            # Actualizar la boleta
            bill.year = year
            bill.month = month
            bill.amount = amount
            bill.due_date = due_date
            bill.notes = notes
            bill.save()
            
            # Actualizar el estado de pago
            bill.update_payment_status()
            bill.save()
            
            messages.success(request, f'Boleta actualizada exitosamente')
            return redirect('frontend:fixed_expense_account_status', pk=fixed_expense.pk)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar la boleta: {str(e)}')
            return render(request, 'frontend/expenses/bill_edit.html', {
                'fixed_expense': fixed_expense,
                'bill': bill
            })
    
    # Generar años disponibles
    current_year = datetime.now().year
    years = list(range(2020, current_year + 2))
    months = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    return render(request, 'frontend/expenses/bill_edit.html', {
        'fixed_expense': fixed_expense,
        'bill': bill,
        'years': years,
        'months': months
    })


@login_required
def expense_fixed_detail_redirect(request, pk):
    """Redirigir al estado de cuenta"""
    return redirect('frontend:fixed_expense_account_status', pk=pk)


@login_required
def expense_bills_list_redirect(request, expense_pk):
    """Redirigir al estado de cuenta"""
    return redirect('frontend:fixed_expense_account_status', pk=expense_pk)


@login_required
def expense_bill_delete(request, expense_pk, bill_pk):
    """Eliminar una boleta de gasto fijo"""
    if not request.user.is_admin:
        messages.error(request, 'No tienes permisos para acceder a esta sección')
        return redirect('dashboard')
    
    fixed_expense = get_object_or_404(FixedExpense, pk=expense_pk, is_active=True)
    bill = get_object_or_404(MonthlyExpense, pk=bill_pk, fixed_expense=fixed_expense)
    
    if request.method == 'POST':
        try:
            # Verificar si tiene pagos asociados
            if bill.payments.exists():
                # Eliminar pagos asociados primero
                bill.payments.all().delete()
            
            # Eliminar la boleta
            bill.delete()
            
            messages.success(request, f'Boleta de {bill.get_month_display()} {bill.year} eliminada exitosamente')
            return redirect('frontend:fixed_expense_account_status', pk=fixed_expense.pk)
            
        except Exception as e:
            messages.error(request, f'Error al eliminar la boleta: {str(e)}')
            return redirect('frontend:expense_bill_edit', expense_pk=fixed_expense.pk, bill_pk=bill.pk)
    
    # Si no es POST, mostrar confirmación
    context = {
        'fixed_expense': fixed_expense,
        'bill': bill,
        'has_payments': bill.payments.exists(),
        'payments_count': bill.payments.count(),
    }
    return render(request, 'frontend/expenses/bill_delete_confirm.html', context)


def import_products_from_excel(request):
    """Vista para importar productos desde Excel"""
    if request.method == 'POST':
        try:
            # Verificar si se subió un archivo
            if 'excel_file' not in request.FILES:
                messages.error(request, 'Por favor selecciona un archivo Excel.')
                return redirect('frontend:products_list')
            
            excel_file = request.FILES['excel_file']
            
            # Verificar extensión del archivo
            if not excel_file.name.endswith(('.xlsx', '.xls')):
                messages.error(request, 'Por favor sube un archivo Excel (.xlsx o .xls)')
                return redirect('frontend:products_list')
            
            # Leer el archivo Excel
            df = pd.read_excel(excel_file)
            
            # Verificar columnas requeridas
            required_columns = ['Articulo', 'Costo', 'Precio Venta', 'Codigo']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                messages.error(request, f'Faltan las siguientes columnas en el Excel: {", ".join(missing_columns)}')
                return redirect('frontend:products_list')
            
            # Contadores para el reporte
            created_count = 0
            updated_count = 0
            errors = []
            
            # Procesar cada fila
            for index, row in df.iterrows():
                try:
                    # Obtener datos de la fila
                    name = str(row['Articulo']).strip()
                    
                    # Validación mínima: solo necesitamos el nombre
                    if not name or name == 'nan':
                        errors.append(f'Fila {index + 2}: Nombre del producto vacío')
                        continue
                    
                    # Obtener otros datos con valores por defecto
                    try:
                        cost_price = Decimal(str(row['Costo'])) if pd.notna(row['Costo']) else Decimal('0')
                    except:
                        cost_price = Decimal('0')
                    
                    try:
                        sale_price = Decimal(str(row['Precio Venta'])) if pd.notna(row['Precio Venta']) else Decimal('0')
                    except:
                        sale_price = Decimal('0')
                    
                    try:
                        barcode = str(row['Codigo']).strip() if pd.notna(row['Codigo']) else ''
                    except:
                        barcode = ''
                    
                    # Si no hay código de barras, generar uno automáticamente
                    if not barcode:
                        # Crear producto sin código de barras (se generará automáticamente)
                        product = Product.objects.create(
                            name=name,
                            cost_price=cost_price,
                            price=sale_price,
                            is_active=True
                        )
                        created_count += 1
                        print(f"✅ Creado: {name} (sin código de barras)")
                    else:
                        # Buscar producto existente por código de barras
                        product, created = Product.objects.get_or_create(
                            barcode=barcode,
                            defaults={
                                'name': name,
                                'cost_price': cost_price,
                                'price': sale_price,
                                'is_active': True
                            }
                        )
                        
                        if created:
                            created_count += 1
                            print(f"✅ Creado: {name}")
                        else:
                            # Actualizar producto existente
                            product.name = name
                            product.cost_price = cost_price
                            product.price = sale_price
                            product.is_active = True
                            product.save()
                            updated_count += 1
                            print(f"🔄 Actualizado: {name}")
                        
                except Exception as e:
                    errors.append(f'Fila {index + 2}: Error - {str(e)}')
                    continue
            
            # Mostrar resultados
            if created_count > 0 or updated_count > 0:
                success_msg = f'Importación completada: {created_count} productos creados, {updated_count} productos actualizados.'
                if errors:
                    success_msg += f' Errores: {len(errors)}'
                messages.success(request, success_msg)
            
            if errors:
                for error in errors[:10]:  # Mostrar solo los primeros 10 errores
                    messages.warning(request, error)
                if len(errors) > 10:
                    messages.warning(request, f'... y {len(errors) - 10} errores más.')
            
            return redirect('frontend:products_list')
            
        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            return redirect('frontend:products_list')
    
    # GET request - mostrar formulario de importación
    return render(request, 'frontend/products/import_products.html')


def product_delete(request, pk):
    """Vista para eliminar un producto"""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        try:
            # Soft delete - marcar como inactivo en lugar de eliminar físicamente
            product.is_active = False
            product.save()
            messages.success(request, f'Producto "{product.name}" eliminado exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar el producto: {str(e)}')
        
        return redirect('frontend:products_list')
    
    # GET request - mostrar confirmación
    context = {
        'product': product
    }
    return render(request, 'frontend/products/delete_confirm.html', context)
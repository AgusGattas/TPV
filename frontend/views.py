from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta
import json
from django.contrib.auth import authenticate, login, logout
from decimal import Decimal

from products.models import Product, ProductImage
from sales.models import Sale, SaleItem
from stock.models import Stock, StockMovement
from cashbox.models import CashBox, CashMovement
from users.models import User


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
    
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    
    # Búsqueda
    search = request.GET.get('search', '')
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(barcode__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Ordenamiento
    order_by = request.GET.get('order_by', '-created_at')
    products = products.order_by(order_by)
    
    context = {
        'products': products,
        'search': search,
        'stock_filter': '',
        'order_by': order_by,
    }
    
    return render(request, 'frontend/products/list.html', context)


@login_required
def product_detail(request, pk):
    """Detalle de un producto"""
    
    product = get_object_or_404(Product, pk=pk, is_active=True)
    
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
            product = Product.objects.create(
                name=name,
                price=price,
                cost_price=cost_price,
                min_stock=min_stock,
                description=description,
                unit=unit
            )
            
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
            
            # Actualizar el producto
            product.name = name
            product.price = price
            product.cost_price = cost_price
            product.min_stock = min_stock
            product.description = description
            product.unit = unit
            product.barcode = barcode
            product.save()
            
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
    
    context = {
        'product': product,
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
def sale_create(request):
    """Crear nueva venta"""
    
    # Verificar que haya una caja abierta
    current_cashbox = CashBox.objects.filter(closed_at__isnull=True).first()
    if not current_cashbox:
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
                notes=data.get('notes', '')
            )
            
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
                
                # Crear el item de venta
                sale_item = SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    quantity=item_data['quantity'],
                    unit_price=item_data.get('unit_price', product.price),
                    discount_percentage=item_data.get('discount_percentage', 0)
                )
                
                # Reducir stock
                stock.remove_stock(
                    quantity=item_data['quantity'],
                    reason=f"Venta #{sale.id}"
                )
            
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
    
    stocks = Stock.objects.select_related('product').all()
    
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
    
    context = {
        'stocks': stocks,
        'search': search,
        'stock_filter': stock_filter,
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
    
    context = {
        'movements': movements,
        'movement_type': movement_type,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'frontend/stock/movements.html', context)


@login_required
def add_stock(request, pk):
    """Agregar stock a un producto"""
    
    stock = get_object_or_404(Stock, pk=pk)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            stock.add_stock(
                quantity=data['quantity'],
                cost_price=data['cost_price'],
                reason=data.get('reason', 'Compra')
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Stock agregado exitosamente',
                'new_quantity': stock.current_quantity
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    # Obtener el último precio de costo de los movimientos de ingreso
    last_cost_price = StockMovement.objects.filter(
        stock=stock,
        type='ingreso'
    ).order_by('-created_at').values_list('cost_price', flat=True).first()
    
    # Si no hay movimientos previos, usar el costo promedio actual
    if last_cost_price is None:
        last_cost_price = stock.average_cost
    
    context = {
        'stock': stock,
        'last_cost_price': last_cost_price,
    }
    
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
    
    context = {
        'cashbox': cashbox,
        'movements': movements,
        'sales': sales,
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
            counted_cash = Decimal(request.POST.get('counted_cash', 0))
            cash_to_keep = request.POST.get('cash_to_keep')
            if cash_to_keep:
                cash_to_keep = Decimal(cash_to_keep)
            
            closing_notes = request.POST.get('closing_notes', '').strip()
            
            cashbox.close_cashbox(
                counted_cash=counted_cash,
                cash_to_keep=cash_to_keep,
                closing_notes=closing_notes
            )
            
            messages.success(request, 'Caja cerrada exitosamente')
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
        product_cost = item.product.cost_price * item.quantity
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
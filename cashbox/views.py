from rest_framework.mixins import (
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework import filters as rest_filters
from django_filters import rest_framework as filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers
from django.db.models import Sum, Count
from cashbox.models import CashBox, CashMovement
from rest_framework.permissions import AllowAny
from cashbox.serializer import (
    CashBoxSerializer, 
    CashBoxCreateSerializer, 
    CashBoxCloseSerializer,
    CashMovementSerializer,
    CashMovementCreateSerializer
)
from cashbox.filters import CashBoxFilter, CashMovementFilter
from django_base.base_utils.base_viewsets import BaseGenericViewSet
from users.models import User

# Create your views here.

class CashBoxViewSet(
    BaseGenericViewSet,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
):
    filter_backends = (
        filters.DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    )

    # filterset_class = CashBoxFilter

    search_fields = (
        "id",
        "user__email",
    )

    ordering = ("-opened_at",)

    ordering_fields = ("id", "opened_at", "closed_at", "initial_cash")

    serializers = {
        "list": CashBoxSerializer,
        "retrieve": CashBoxSerializer,
        "create": CashBoxCreateSerializer,
        "update": CashBoxCloseSerializer,
        "partial_update": CashBoxCloseSerializer,
        "close": CashBoxCloseSerializer,
        "default": CashBoxSerializer,
    }

    permissions = {
        "list": [AllowAny],
        "retrieve": [AllowAny],
        "create": [AllowAny],
        "update": [AllowAny],
        "partial_update": [AllowAny],
        "close": [AllowAny],
        "default": [AllowAny],
    }

    def get_queryset(self):
        return (
            CashBox.objects.select_related("user")
            .prefetch_related("movements", "sales")
            .all()
            .order_by("-opened_at")
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Cerrar una caja"""
        cashbox = self.get_object()
        serializer = self.get_serializer(cashbox, data=request.data)
        
        if serializer.is_valid():
            try:
                cashbox.close_cashbox(
                    counted_cash=serializer.validated_data['counted_cash'],
                    cash_to_keep=serializer.validated_data.get('cash_to_keep')
                )
                return Response({"message": "Caja cerrada exitosamente"}, status=status.HTTP_200_OK)
            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Obtener resumen de la caja"""
        cashbox = self.get_object()
        return Response(cashbox.get_summary())

    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """Listar movimientos de la caja"""
        cashbox = self.get_object()
        movements = cashbox.movements.all()
        serializer = CashMovementSerializer(movements, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def sales(self, request, pk=None):
        """Listar ventas de la caja"""
        cashbox = self.get_object()
        sales = cashbox.sales.filter(is_active=True)
        from sales.serializer import SaleSerializer
        serializer = SaleSerializer(sales, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def open_cashboxes(self, request):
        """Listar cajas abiertas"""
        cashboxes = self.get_queryset().filter(closed_at__isnull=True)
        serializer = self.get_serializer(cashboxes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def closed_cashboxes(self, request):
        """Listar cajas cerradas"""
        cashboxes = self.get_queryset().filter(closed_at__isnull=False)
        serializer = self.get_serializer(cashboxes, many=True)
        return Response(serializer.data)


class CashMovementViewSet(
    BaseGenericViewSet,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
):
    filter_backends = (
        filters.DjangoFilterBackend,
        rest_filters.SearchFilter,
        rest_filters.OrderingFilter,
    )

    filterset_class = CashMovementFilter

    search_fields = (
        "reason",
        "cashbox__id",
    )

    ordering = ("-created_at",)

    ordering_fields = ("id", "amount", "type", "created_at")

    serializers = {
        "list": CashMovementSerializer,
        "retrieve": CashMovementSerializer,
        "create": CashMovementCreateSerializer,
        "update": CashMovementSerializer,
        "partial_update": CashMovementSerializer,
        "default": CashMovementSerializer,
    }

    permissions = {
        "list": [AllowAny],
        "retrieve": [AllowAny],
        "create": [AllowAny],
        "update": [AllowAny],
        "partial_update": [AllowAny],
        "default": [AllowAny],
    }

    def get_queryset(self):
        return (
            CashMovement.objects.select_related("cashbox", "user")
            .all()
            .order_by("-created_at")
        )

    def perform_create(self, serializer):
        # Asignar el usuario actual si está autenticado, sino usar un usuario por defecto
        if self.request.user.is_authenticated:
            serializer.save(user=self.request.user)
        else:
            # Usar el primer usuario disponible o crear uno por defecto
            try:
                default_user = User.objects.first()
                if not default_user:
                    # Crear un usuario por defecto si no existe ninguno
                    default_user = User.objects.create_user(
                        email="vendedor@default.com",
                        password="default123",
                        first_name="Vendedor",
                        last_name="Default",
                        role="vendedor"
                    )
                serializer.save(user=default_user)
            except Exception as e:
                raise serializers.ValidationError(f"No se pudo asignar un usuario: {str(e)}")

    @action(detail=False, methods=['get'])
    def by_cashbox(self, request, cashbox_id=None):
        """Movimientos por caja"""
        movements = self.get_queryset().filter(cashbox_id=cashbox_id)
        serializer = self.get_serializer(movements, many=True)
        return Response(serializer.data)

 
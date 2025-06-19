from rest_framework.routers import DefaultRouter
from sales.views import SaleViewSet, SaleItemViewSet

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sales")
router.register("sale-items", SaleItemViewSet, basename="sale-items")

urlpatterns = [] 
from rest_framework.routers import DefaultRouter
from stock.views import StockViewSet, StockMovementViewSet

router = DefaultRouter()
router.register("stock", StockViewSet, basename="stock")
router.register("stock-movements", StockMovementViewSet, basename="stock-movements")

urlpatterns = [] 
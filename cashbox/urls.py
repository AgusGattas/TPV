from rest_framework.routers import DefaultRouter
from cashbox.views import CashBoxViewSet, CashMovementViewSet

router = DefaultRouter()
router.register("cashbox", CashBoxViewSet, basename="cashbox")
router.register("cash-movements", CashMovementViewSet, basename="cash-movements")

urlpatterns = [] 
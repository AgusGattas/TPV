from drf_yasg import openapi
from drf_yasg.views import get_schema_view

from rest_framework.routers import DefaultRouter

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static

from users.urls import router as users_router
from products.urls import router as products_router
from sales.urls import router as sales_router
from cashbox.urls import router as cashbox_router
from stock.urls import router as stock_router

from platform_configurations.urls import router as platform_configurations_router

from django_global_places.urls import router as django_global_places_router


schema_view = get_schema_view(
    openapi.Info(
        title="Base project API",
        default_version="v1",
        description="Base project documentation",
        contact=openapi.Contact(email="contact@linkchar.com"),
    ),
    public=True,
)

base_router = DefaultRouter()
base_router.registry.extend(users_router.registry)
base_router.registry.extend(platform_configurations_router.registry)
base_router.registry.extend(django_global_places_router.registry)
base_router.registry.extend(products_router.registry)
base_router.registry.extend(sales_router.registry)
base_router.registry.extend(cashbox_router.registry)
base_router.registry.extend(stock_router.registry)



# fmt: off
#<-------------- Django + libraries urls -------------->
urlpatterns = [
    path("admin/", admin.site.urls),
    path("__debug__/", include("debug_toolbar.urls")),
]

# <-------------- Swagger urls -------------->
urlpatterns += [
    re_path(r"^swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    re_path(r"^swagger/$", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    re_path(r"^redoc/$", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]

#<-------------- Our apps includes -------------->
urlpatterns += [
    path("api/users/", include("users.urls")),
    path("api/auth/", include("auth.urls")),
]

#<-------------- Our base router -------------->
urlpatterns += [path("api/", include(base_router.urls)),]

#<-------------- Frontend URLs -------------->
urlpatterns += [path("", include("frontend.urls")),]

#<-------------- Authentication URLs -------------->
urlpatterns += [
    path("login/", include("auth.urls")),
]

# fmt: on

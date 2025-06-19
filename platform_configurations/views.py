from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework import status
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework import mixins

from platform_configurations import models


class SystemStatusSerializer(serializers.Serializer):
    is_operational = serializers.BooleanField()


class SytemStatusViewSet(GenericViewSet, mixins.ListModelMixin):
    """Viewset for system status. If the system is not operational,
    the system will return a 503 status code in every endpoint instead of this."""
    
    serializer_class = SystemStatusSerializer

    def get_queryset(self):
        queryset = models.SystemStatus.objects.all().first()
        return queryset

    @action(detail=False, methods=["get"], url_path="is-system-up")
    def system_status(self, request):
        system_status = self.get_queryset()

        return Response(
            {
                "is_operational": system_status.get_status().is_operational,
            },
            status=status.HTTP_200_OK,
        )

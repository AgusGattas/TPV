from dj_rest_auth.views import PasswordChangeView

from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework import serializers

from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings

from django_base.base_utils.base_viewsets import BaseGenericViewSet
from users.models import User, TokenRecovery
from django_base.base_utils.utils import get_random_string, email_template_sender


class PasswordRecoverySendMailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordRecoveryCheckTokenSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()


class PasswordRecoveryConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    password = serializers.CharField()


class PasswordRecoveryViewSet(BaseGenericViewSet):
    queryset = User.objects.all()
    
    serializers = {
        "recovery_send_mail": PasswordRecoverySendMailSerializer,
        "recovery_check_token": PasswordRecoveryCheckTokenSerializer,
        "recovery_confirm": PasswordRecoveryConfirmSerializer,
        "default": PasswordRecoverySendMailSerializer,
    }
    
    permissions = {
        "recovery_send_mail": [AllowAny],
        "recovery_check_token": [AllowAny],
        "recovery_confirm": [AllowAny],
        "default": [AllowAny],
    }

    def get_validated_token(self, email, token):
        token_recovery = TokenRecovery.objects.get(user__email=email, token=token)
        if (
            token_recovery.created_at + settings.PASSWORD_RECOVERY_TOKEN_EXPIRE_AT
            < timezone.now()
        ):
            raise ValidationError(_("Token expired"))
        return token_recovery

    def get_user(self, email):
        user = User.objects.get(email=email)
        return user

    @action(
        detail=False,
        methods=["post"],
        url_path="",
        url_name="password_recovery_email_send",
    )
    def recovery_send_mail(self, request):
        request_type = (
            request.data.get("request_type", "reset")
            if settings.PASSWORD_CHANGE_BY_EMAIL
            else "reset"
        )

        try:
            user = self.get_user(request.data.get("email"))

            recovery_token = get_random_string(settings.PASSWORD_RECOVERY_TOKEN_LENGTH)

            if TokenRecovery.objects.filter(user=user).exists():
                token_recovery = TokenRecovery.objects.get(user=user)
                token_recovery.delete()

            TokenRecovery.objects.create(user=user, token=recovery_token)

            email_subject = _("Password Reset for %(app_name)s") % {
                "app_name": settings.APP_NAME
            }

            context = {
                "FRONT_URL": settings.FRONT_URL,
                "recovery_token": recovery_token,
                "APP_NAME": settings.APP_NAME,
                "REQUEST_TYPE": request_type,
                "PASSWORD_RECOVERY_TOKEN_TYPE": settings.PASSWORD_RECOVERY_TOKEN_TYPE,
                "EMAIL": user.email,
            }

            email_template_sender(
                email_subject,
                "registration/password_recovery_email.html",
                context,
                user.email,
            )
        except Exception as e:
            print(e)
            pass

        return Response(_("Email sent"), status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="check-token",
        url_name="password_recovery_check_token",
    )
    def recovery_check_token(self, request):
        try:
            self.get_validated_token(
                request.data.get("email"), request.data.get("token")
            )
        except ValidationError as e:
            return Response(str(e.message), status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(_("Token is invalid"), status=status.HTTP_400_BAD_REQUEST)

        return Response(_("Token is valid"), status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="confirm",
        url_name="password_recovery_confirm",
    )
    def recovery_confirm(self, request):
        try:
            password = request.data.get("password", "")
            user = self.get_user(request.data.get("email"))
            token_recovery = self.get_validated_token(
                request.data.get("email"), request.data.get("token")
            )
            validate_password(password, user=user)
        except ValidationError as e:
            if hasattr(e, "message"):
                return Response(str(e.message), status=status.HTTP_400_BAD_REQUEST)
            return Response(e, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(_("Token is invalid"), status=status.HTTP_400_BAD_REQUEST)

        user.set_password(password)
        user.save()
        token_recovery.delete()
        return Response(_("Password reset successful"), status=status.HTTP_200_OK)


class PasswordChangeViewModify(PasswordChangeView):
    def post(self, request, *args, **kwargs):
        if not settings.PASSWORD_CHANGE_BY_EMAIL:
            return Response(
                _("Only password change by email is allowed"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not "old_password" in request.data:
            return Response(
                _("old_password is required"), status=status.HTTP_400_BAD_REQUEST
            )
        old_password = request.data["old_password"]
        if not request.user.check_password(old_password):
            return Response(
                _("Old password is incorrect"), status=status.HTTP_400_BAD_REQUEST
            )
        if old_password == request.data["new_password"]:
            return Response(
                _("New password must be different from old password"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = request.data.copy()
        data["new_password1"] = data["new_password"]
        data["new_password2"] = data["new_password"]
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # TODO Add is register complete permission??
        # request.user.is_register_completed = True
        # request.user.save()

        return Response(_("New password has been saved."), status=status.HTTP_200_OK)

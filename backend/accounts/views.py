from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from core.audit import log
from core.permissions import IsAdmin
from .models import Notification
from .serializers import (LoginSerializer, NotificationSerializer,
                          UserCreateSerializer, UserSerializer, UserUpdateSerializer)


class LoginView(APIView):
    """POST /api/auth/login/ - returns access/refresh tokens plus user info."""
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            log(action='LOGIN_FAILED', entity='User',
                username=request.data.get('username', ''))
            raise
        user = serializer.user
        log(user=user, action='LOGIN', entity='User', entity_id=user.pk, entity_repr=user.username)
        return Response(serializer.validated_data)


class RefreshTokenView(TokenRefreshView):
    """POST /api/auth/refresh/ - standard SimpleJWT refresh."""


class MeView(APIView):
    """GET /api/auth/me/ - current user profile."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    """Admin management of users: /api/users/"""
    permission_classes = (IsAdmin,)
    filterset_fields = ('role', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering_fields = ('username', 'date_joined')

    def get_queryset(self):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.all().order_by('username')

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UserUpdateSerializer
        return UserSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """In-app notifications: /api/notifications/"""
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)
        unread = self.request.query_params.get('unread')
        if unread is not None and unread.lower() in ('1', 'true', 'yes'):
            qs = qs.filter(is_read=False)
        return qs

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response({'detail': 'Marked as read'})

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        updated = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'detail': f'{updated} notifications marked as read'})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'count': count})

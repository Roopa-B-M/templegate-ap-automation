from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Notification, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'last_login')
    list_filter = ('role', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (('Role', {'fields': ('role', 'phone')}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (('Role', {'fields': ('role',)}),)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read')
    readonly_fields = [f.name for f in Notification._meta.fields]

# terrasat/admin.py

from django import forms
from django.contrib import admin

from .models import AllWardsMathare, MaintenanceTask, PhoneUser
from .views import SMS_CONFIRMATION, _send_confirmation_sms, set_task_status


class PhoneUserAdminForm(forms.ModelForm):
    """
    Replaces the free-text ward_name field with a dropdown of real ward
    names pulled from all_wards_mathare, so admins can't typo a ward
    that doesn't exist. ward_fid is auto-filled from the selection on
    save rather than entered manually.
    """
    ward_name = forms.ChoiceField(choices=[], required=False)

    class Meta:
        model = PhoneUser
        fields = ("phone_number", "ward_name", "language")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ward_names = (
            AllWardsMathare.objects
            .exclude(name__isnull=True)
            .exclude(name__exact="")
            .values_list("name", flat=True)
            .distinct()
            .order_by("name")
        )
        self.fields["ward_name"].choices = [("", "— none —")] + [(w, w) for w in ward_names]


@admin.register(PhoneUser)
class PhoneUserAdmin(admin.ModelAdmin):
    form = PhoneUserAdminForm
    list_display = ("phone_number", "ward_name", "language", "registered_at")
    list_filter = ("ward_name", "language")
    search_fields = ("phone_number", "ward_name")
    readonly_fields = ("registered_at",)

    def save_model(self, request, obj, form, change):
        # Auto-fill ward_fid from the chosen ward name, same lookup
        # pattern used in the USSD flow.
        if obj.ward_name:
            matching_row = AllWardsMathare.objects.filter(name__iexact=obj.ward_name).first()
            obj.ward_fid = matching_row.fid if matching_row else None
        else:
            obj.ward_fid = None

        super().save_model(request, obj, form, change)

        # Send confirmation SMS after the record is actually saved.
        # Same helper the USSD flow uses — wrapped in try/except there,
        # so a failed SMS never blocks the admin save itself.
        if obj.ward_name:
            lang = obj.language if obj.language in SMS_CONFIRMATION else "en"
            _send_confirmation_sms(
                obj.phone_number,
                SMS_CONFIRMATION[lang].format(ward=obj.ward_name),
            )


@admin.register(MaintenanceTask)
class MaintenanceTaskAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "status", "ward_name", "reported_by_phone", "created_at")
    list_filter = ("status", "category", "ward_name")
    search_fields = ("ward_name", "reported_by_phone", "description")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_verified", "mark_in_progress", "mark_resolved", "mark_rejected"]

    def _bulk_set_status(self, request, queryset, new_status):
        # set_task_status is the SAME function the staff dashboard uses
        # (views.py) — keeping this in one place means admin and
        # dashboard can never send conflicting notifications or drift
        # out of sync on what counts as "resolved".
        for task in queryset:
            set_task_status(task, new_status)
        self.message_user(request, f"{queryset.count()} task(s) updated to '{new_status}'.")

    def mark_verified(self, request, queryset):
        self._bulk_set_status(request, queryset, "verified")
    mark_verified.short_description = "Mark selected as Verified"

    def mark_in_progress(self, request, queryset):
        self._bulk_set_status(request, queryset, "in_progress")
    mark_in_progress.short_description = "Mark selected as In progress"

    def mark_resolved(self, request, queryset):
        # Only status change that texts the original reporter — closes
        # the loop so residents see reports actually lead somewhere,
        # which matters for a bottom-up reporting channel to keep working.
        self._bulk_set_status(request, queryset, "resolved")
    mark_resolved.short_description = "Mark selected as Resolved (notifies reporter via SMS)"

    def mark_rejected(self, request, queryset):
        self._bulk_set_status(request, queryset, "rejected")
    mark_rejected.short_description = "Mark selected as Rejected"
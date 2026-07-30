# terrasat/urls.py

from django.urls import path

from . import views

urlpatterns = [
    # ... any existing TerraSat urls you already have go here too ...

    path("", views.mathare_map, name="mathare_map"),
    path("api/layers/mathare-floods/", views.mathare_flood_geojson, name="mathare_flood_geojson"),
    path("api/wards/<int:fid>/detail/", views.ward_detail, name="ward_detail"),

    path("ussd/register/", views.ussd_register, name="ussd_register"),
    path("ussd/register", views.ussd_register, name="ussd_register_no_slash"),

    path("high-risk/", views.high_risk_dashboard, name="high_risk_dashboard"),
    path("high-risk/clear-cache/", views.high_risk_clear_cache, name="high_risk_clear_cache"),
    path("high-risk/public/", views.high_risk_public_summary, name="high_risk_public_summary"),
    path("high-risk/review/", views.high_risk_review, name="high_risk_review"),
    path("high-risk/send-alerts/", views.high_risk_send_alerts, name="high_risk_send_alerts"),

    path("tasks/", views.task_dashboard, name="task_dashboard"),
    path("tasks/public-summary/", views.task_public_summary, name="task_public_summary"),
    path("tasks/list/", views.task_list, name="task_list"),
    path("tasks/<int:task_id>/update-status/", views.task_update_status, name="task_update_status"),
]
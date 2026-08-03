from django.test import SimpleTestCase
from django.urls import reverse


class PublicDashboardAccessTests(SimpleTestCase):
    def test_high_risk_dashboard_is_public(self):
        response = self.client.get(reverse("high_risk_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_task_dashboard_is_public(self):
        response = self.client.get(reverse("task_dashboard"))
        self.assertEqual(response.status_code, 200)

from django.test import TestCase


class LandingPageTests(TestCase):
    def test_signed_out_visitor_sees_the_landing_page(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rabbit Herd")
        self.assertContains(response, "private record keeper")

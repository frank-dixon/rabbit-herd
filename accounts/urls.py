from django.urls import path

from . import views


def moved(name):
    """Old /accounts/... address: a permanent 308 redirect (keeps POST and the query string)."""
    from django.http import HttpResponseRedirect
    from django.urls import reverse

    class Moved(HttpResponseRedirect):
        status_code = 308

    def view(request):
        qs = request.META.get("QUERY_STRING")
        return Moved(reverse(name) + (f"?{qs}" if qs else ""))
    return view


# The sign-in pages live at /login/, /signup/ and /logout/ (rabbit_herd/urls.py).
auth_urlpatterns = [
    path("login/", views.EmailLoginView.as_view(), name="login"),
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("start/", views.start, name="start"),
    path("start/demo/", views.start_demo, name="start_demo"),
]

urlpatterns = [
    path("login/", moved("login")),
    path("logout/", moved("logout")),
    path("signup/", moved("signup")),
    path("signup/done/", views.signup_done, name="signup_done"),
    path("confirm/<uidb64>/<token>/", views.confirm_email, name="confirm_email"),
    path("guest/", views.continue_as_guest, name="guest"),
    path("passkey/offer/skip/", views.passkey_offer_skip, name="passkey_offer_skip"),
    path(
        "password/change/",
        views.AppPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password/change/done/",
        views.AppPasswordChangeDoneView.as_view(),
        name="password_change_done",
    ),
    path(
        "password/reset/",
        views.AppPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        views.AppPasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        views.AppPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        views.AppPasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path(
        "passkey/register/options/",
        views.passkey_register_options,
        name="passkey_register_options",
    ),
    path(
        "passkey/register/verify/",
        views.passkey_register_verify,
        name="passkey_register_verify",
    ),
    path(
        "passkey/login/options/",
        views.passkey_login_options,
        name="passkey_login_options",
    ),
    path(
        "passkey/login/verify/",
        views.passkey_login_verify,
        name="passkey_login_verify",
    ),
]

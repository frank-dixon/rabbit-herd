from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.EmailLoginView.as_view(), name="login"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("signup/", views.SignupView.as_view(), name="signup"),
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

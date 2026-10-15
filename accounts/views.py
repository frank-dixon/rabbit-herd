import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import PasswordResetForm
from django.template import loader
from django.contrib.auth.views import (
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.views.generic import FormView

from .emails import (
    resend_confirmation_email,
    send_account_mail,
    send_confirmation_email,
)
from .forms import EmailAuthenticationForm, SignupForm
from .models import User
from .passkeys import (
    PasskeyError,
    authentication_options,
    read_json,
    registration_options,
    verify_authentication,
    verify_registration,
)
from .redirects import is_safe_next, safe_next_url
from .tokens import email_confirmation_token


class EmailLoginView(FormView):
    template_name = "accounts/login.html"
    form_class = EmailAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("index")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate = self.request.GET.get("next", "")
        context["next"] = candidate if is_safe_next(self.request, candidate) else ""
        return context

    def form_valid(self, form):
        login(self.request, form.get_user())
        return redirect(safe_next_url(self.request, "index"))


class SignupView(FormView):
    template_name = "accounts/signup.html"
    form_class = SignupForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("index")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        existing = form.existing_user
        if existing is None:
            user = form.save()
            user.guide_step = "today"
            user.show_samples = True
            user.save(update_fields=["guide_step", "show_samples"])
            from rabbits.samples import add_samples
            add_samples(user, "today")  # rabbits + pairings + litters + tasks
            send_confirmation_email(self.request, user)
        elif not existing.email_confirmed and not existing.is_guest:
            # Re-send the link, but keep the account's original password, so
            # a stranger cannot set the password on someone else's account.
            resend_confirmation_email(self.request, existing)
        return redirect("signup_done")


class AppLogoutView(LogoutView):
    next_page = "index"


class AppPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("password_change_done")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["old_password"].label = "Current password"
        form.fields["new_password2"].label = "Confirm new password"
        return form

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_guest:
            messages.error(request, "Guest sessions don't have a password. Create an account to set one.")
            return redirect("index")
        return super().dispatch(request, *args, **kwargs)


class AppPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


class ConfirmedPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)
        send_account_mail(subject, body, to_email)

    def get_users(self, email):
        users = User.objects.filter(
            email__iexact=email,
            is_active=True,
            email_confirmed=True,
            is_guest=False,
        )
        return (user for user in users if user.has_usable_password())


class AppPasswordResetView(PasswordResetView):
    form_class = ConfirmedPasswordResetForm
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def form_valid(self, form):
        self.extra_email_context = {**(self.extra_email_context or {}), "app_name": settings.APP_NAME}
        host = settings.APP_HOSTNAME
        if host:
            self.extra_email_context = {
                **(self.extra_email_context or {}),
                "domain": host,
                "protocol": "https",
            }
        return super().form_valid(form)


class AppPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class AppPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["new_password2"].label = "Confirm new password"
        return form


class AppPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


def signup_done(request):
    return render(request, "accounts/signup_done.html")


def confirm_email(request, uidb64, token):
    user = None
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, TypeError, ValueError, OverflowError):
        user = None
    if user is None or user.is_guest or not email_confirmation_token.check_token(user, token):
        return render(request, "accounts/confirm_invalid.html", status=400)
    user.is_active = True
    user.email_confirmed = True
    user.email_confirmed_at = timezone.now()
    user.save(update_fields=["is_active", "email_confirmed", "email_confirmed_at"])
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("index")


@require_POST
def continue_as_guest(request):
    if request.user.is_authenticated:
        return redirect("index")
    suffix = uuid.uuid4().hex
    user = User.objects.create_user(
        email=f"guest-{suffix}@guest.invalid",
        password=None,
        is_guest=True,
        is_active=True,
        email_confirmed=True,
        email_confirmed_at=timezone.now(),
        guide_step="today",
        show_samples=True,
    )
    from rabbits.samples import add_samples
    add_samples(user, "today")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("index")


@require_POST
def passkey_register_options(request):
    try:
        options = registration_options(request, read_json(request))
    except PasskeyError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    return JsonResponse(options)


@require_POST
def passkey_register_verify(request):
    try:
        payload = read_json(request)
        credential = payload.get("credential")
        if not isinstance(credential, dict):
            raise PasskeyError("The passkey response was incomplete.")
        user, created = verify_registration(request, credential)
    except PasskeyError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    if created:
        send_confirmation_email(request, user)
        return JsonResponse({"redirect": reverse("signup_done")})
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"redirect": safe_next_url(request, "index", payload.get("next"))})


@require_POST
def passkey_login_options(request):
    try:
        read_json(request)
        options = authentication_options(request)
    except PasskeyError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    return JsonResponse(options)


@require_POST
def passkey_login_verify(request):
    try:
        payload = read_json(request)
        credential = payload.get("credential")
        if not isinstance(credential, dict):
            raise PasskeyError("The passkey response was incomplete.")
        user = verify_authentication(request, credential)
    except PasskeyError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"redirect": safe_next_url(request, "index", payload.get("next"))})

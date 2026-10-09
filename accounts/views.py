from django.contrib.auth import login
from django.contrib.auth.views import LogoutView
from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.views.generic import FormView

from .forms import EmailAuthenticationForm, SignupForm
from .passkeys import (
    PasskeyError,
    authentication_options,
    read_json,
    registration_options,
    verify_authentication,
    verify_registration,
)
from .redirects import is_safe_next, safe_next_url


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
        user = form.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("index")


class AppLogoutView(LogoutView):
    next_page = "index"


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
        user, _created = verify_registration(request, credential)
    except PasskeyError as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
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

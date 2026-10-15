import secrets
import uuid

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

from pages.theme_data import THEMES as THEME_DATA


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        user = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_confirmed", True)
        extra_fields.setdefault("email_confirmed_at", timezone.now())
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    webauthn_user_handle = models.BinaryField(max_length=64, editable=False)
    is_guest = models.BooleanField(default=False)
    email_confirmed = models.BooleanField(default=False)
    email_confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    # Appearance, chosen in Settings and applied server-side on <html>.
    THEMES = [(key, label) for key, label, *_ in THEME_DATA]
    DENSITIES = [("roomy", "Roomy"), ("compact", "Compact")]
    ui_theme = models.CharField(max_length=8, choices=THEMES, default="light")
    ui_density = models.CharField(max_length=8, choices=DENSITIES, default="roomy")
    # The app icon next to the name in the app shell (pages.marks).
    MARKS = [("s1", "S1"), ("g2", "G2")]
    ui_mark = models.CharField(max_length=4, choices=MARKS, default="s1")
    # The Rabbits page layout, remembered per account.
    LIST_VIEWS = [("grid", "Grid"), ("list", "List")]
    ui_list_view = models.CharField(max_length=8, choices=LIST_VIEWS, default="grid")
    # The Weights page: Table or Chart (split list + growth chart), remembered per account.
    WEIGHTS_VIEWS = [("table", "Table"), ("chart", "Chart")]
    ui_weights_view = models.CharField(max_length=8, choices=WEIGHTS_VIEWS, default="table")
    WEIGHTS_RANGES = [("3m", "3 mo"), ("12m", "12 mo"), ("all", "All")]
    ui_weights_range = models.CharField(max_length=4, choices=WEIGHTS_RANGES, default="12m")
    # Grid or List on the other index pages (programs, pairings, shows, health): {page: view}.
    ui_views = models.JSONField(default=dict, blank=True)
    # Phone bottom bar: destination keys in order (pages.nav.DESTINATIONS). Empty means the default.
    tab_bar = models.JSONField(default=list, blank=True)
    # The side menu's order: destination keys, main section then Records. Empty = default.
    side_menu = models.JSONField(default=list, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if not self.username:
            self.username = uuid.uuid4().hex
        if not self.webauthn_user_handle:
            self.webauthn_user_handle = secrets.token_bytes(32)
        super().save(*args, **kwargs)


class PasskeyCredential(models.Model):
    user = models.ForeignKey(
        User,
        related_name="passkeys",
        on_delete=models.CASCADE,
    )
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Passkey for {self.user.email}"

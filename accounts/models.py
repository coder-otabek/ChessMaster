from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import random, string


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(blank=True, max_length=300)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    favorite_opening = models.CharField(max_length=100, blank=True)
    play_style = models.CharField(max_length=50, blank=True,
        choices=[('aggressive','Hujumkor'),('defensive','Mudofaachi'),
                 ('positional','Pozitsion'),('tactical','Taktik')])
    rating = models.IntegerField(default=1200)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    games_played = models.IntegerField(default=0)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-rating']

    def __str__(self):
        return f"{self.user.username} ({self.rating})"

    @property
    def win_rate(self):
        if self.games_played == 0:
            return 0.0
        return round(self.wins / self.games_played * 100, 1)

    @property
    def rank(self):
        return Profile.objects.filter(rating__gt=self.rating).count() + 1

    @property
    def title(self):
        r = self.rating
        if r >= 2400: return "Grandmaster"
        if r >= 2200: return "Master"
        if r >= 2000: return "Expert"
        if r >= 1800: return "Advanced"
        return "Intermediate"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f"OTP for {self.email}"

    @staticmethod
    def generate_otp():
        return ''.join(random.choices(string.digits, k=6))


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


class EmailVerificationOTP(models.Model):
    """Ro'yxatdan o'tishda email tasdiqlash uchun OTP."""
    email      = models.EmailField()
    otp        = models.CharField(max_length=6)
    form_data  = models.JSONField()          # vaqtincha forma ma'lumotlari
    created_at = models.DateTimeField(auto_now_add=True)
    is_used    = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"RegOTP for {self.email}"

    @staticmethod
    def generate_otp():
        return ''.join(random.choices(string.digits, k=6))

    @property
    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() - self.created_at > timedelta(minutes=15)

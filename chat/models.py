from django.db import models
from django.contrib.auth.models import User


class Message(models.Model):
    sender    = models.ForeignKey(User, related_name='sent_messages',     on_delete=models.CASCADE)
    receiver  = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content   = models.TextField(max_length=1000)
    is_read   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} → {self.receiver}: {self.content[:30]}"

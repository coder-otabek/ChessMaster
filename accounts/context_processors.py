from chat.models import Message


def unread_messages(request):
    """Barcha sahifalarda o'qilmagan xabarlar sonini beradi."""
    if request.user.is_authenticated:
        try:
            count = Message.objects.filter(
                receiver=request.user, is_read=False
            ).count()
            return {'unread_messages_count': count}
        except Exception:
            pass
    return {'unread_messages_count': 0}
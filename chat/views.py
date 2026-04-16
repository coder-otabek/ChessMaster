from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import timedelta
from .models import Message
from accounts.models import Profile


def get_online_players(exclude_user):
    """So'nggi 5 daqiqa ichida faol bo'lgan o'yinchilar."""
    cutoff = timezone.now() - timedelta(minutes=5)
    return Profile.objects.filter(
        Q(is_online=True) | Q(last_seen__gte=cutoff)
    ).exclude(user=exclude_user).select_related('user').order_by('-rating')[:20]


def build_conversations(me):
    """Foydalanuvchining barcha suhbatlari."""
    partner_ids_qs = Message.objects.filter(
        Q(sender=me) | Q(receiver=me)
    ).values_list('sender', 'receiver')
    ids = set()
    for s, r in partner_ids_qs:
        ids.add(s); ids.add(r)
    ids.discard(me.id)

    cutoff = timezone.now() - timedelta(minutes=5)
    conversations = []
    for uid in ids:
        try:
            partner = User.objects.select_related('profile').get(pk=uid)
            last = Message.objects.filter(
                Q(sender=me, receiver=partner) | Q(sender=partner, receiver=me)
            ).order_by('-created_at').first()
            unread = Message.objects.filter(
                sender=partner, receiver=me, is_read=False
            ).count()
            p_profile = getattr(partner, 'profile', None)
            is_online = (
                getattr(p_profile, 'is_online', False) or
                (p_profile and p_profile.last_seen and p_profile.last_seen >= cutoff)
            ) if p_profile else False
            conversations.append({
                'partner':        partner,
                'last_message':   last.content[:50] if last else '',
                'last_time':      last.created_at if last else None,
                'unread_count':   unread,
                'partner_online': is_online,
            })
        except User.DoesNotExist:
            pass
    conversations.sort(key=lambda x: x['last_time'] or timezone.now().replace(year=2000), reverse=True)
    return conversations


@login_required
def chat_list(request):
    conversations  = build_conversations(request.user)
    online_players = get_online_players(request.user)
    total_unread   = Message.objects.filter(receiver=request.user, is_read=False).count()
    return render(request, 'chess/chat.html', {
        'conversations':  conversations,
        'online_players': online_players,
        'active_partner': None,
        'chat_messages':  [],
        'total_unread':   total_unread,
    })


@login_required
def chat_with(request, username):
    me      = request.user
    partner = get_object_or_404(User, username=username)

    msgs = Message.objects.filter(
        Q(sender=me, receiver=partner) | Q(sender=partner, receiver=me)
    ).order_by('created_at')[:100]

    Message.objects.filter(
        sender=partner, receiver=me, is_read=False
    ).update(is_read=True)

    conversations  = build_conversations(me)
    online_players = get_online_players(me)
    total_unread   = Message.objects.filter(receiver=me, is_read=False).count()

    return render(request, 'chess/chat.html', {
        'conversations':  conversations,
        'online_players': online_players,
        'active_partner': partner,
        'chat_messages':  msgs,
        'total_unread':   total_unread,
    })


@login_required
@require_POST
def mark_read(request, username):
    """Berilgan foydalanuvchidan kelgan xabarlarni o'qilgan deb belgilash."""
    partner = get_object_or_404(User, username=username)
    Message.objects.filter(
        sender=partner, receiver=request.user, is_read=False
    ).update(is_read=True)
    # Jami o'qilmagan xabarlar soni (boshqa suhbatlardan ham)
    total_unread = Message.objects.filter(
        receiver=request.user, is_read=False
    ).count()
    return JsonResponse({'ok': True, 'unread': total_unread})


@login_required
def unread_count(request):
    """Jami o'qilmagan xabarlar soni."""
    count = Message.objects.filter(
        receiver=request.user, is_read=False
    ).count()
    return JsonResponse({'count': count})
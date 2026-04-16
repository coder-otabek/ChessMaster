import json
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Game, MatchmakingQueue, ChallengeInvite, INITIAL_BOARD
from accounts.models import Profile


# ─── Bosh sahifa ──────────────────────────────────────────────────────────
def home_view(request):
    if request.user.is_authenticated:
        return redirect('find_opponent')
    top_players = Profile.objects.select_related('user').order_by('-rating')[:5]
    return render(request, 'chess/home.html', {'top_players': top_players})


# ─── Reyting jadvali ──────────────────────────────────────────────────────
def leaderboard_view(request):
    players = Profile.objects.select_related('user').order_by('-rating')
    return render(request, 'chess/leaderboard.html', {
        'players': players,
        'top3': list(players[:3]),
        'total_players': players.count(),
    })


# ─── Raqib topish lobby ───────────────────────────────────────────────────
@login_required
def find_opponent_view(request):
    from django.utils import timezone
    from datetime import timedelta
    active_games = []
    for g in Game.objects.filter(
        Q(white_player=request.user) | Q(black_player=request.user),
        status='active'
    )[:3]:
        opp = g.black_player if g.white_player == request.user else g.white_player
        active_games.append({'id': g.id, 'opponent': opp, 'time_info': g.time_control})

    cutoff = timezone.now() - timedelta(seconds=15)
    online_players = Profile.objects.filter(
        last_seen__gte=cutoff
    ).exclude(user=request.user).select_related('user').order_by('-rating')[:20]

    # Kelgan taklif bormi?
    pending_invite = ChallengeInvite.objects.filter(
        receiver=request.user, status='pending'
    ).select_related('sender').first()

    return render(request, 'chess/find_opponent.html', {
        'active_games':   active_games,
        'online_players': online_players,
        'pending_invite': pending_invite,
    })


@login_required
def online_players_api(request):
    """Online o'yinchilar ro'yxatini JSON formatda qaytaradi."""
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(seconds=15)
    players = Profile.objects.filter(
        last_seen__gte=cutoff
    ).exclude(user=request.user).select_related('user').order_by('-rating')[:20]

    data = []
    for p in players:
        data.append({
            'username':    p.user.username,
            'rating':      p.rating,
            'avatar_url':  p.avatar.url if p.avatar else None,
            'profile_url': f'/profile/{p.user.username}/',
        })
    return JsonResponse({'players': data})


# ─── Navbat (matchmaking) ─────────────────────────────────────────────────
@login_required
@require_POST
def queue_join(request):
    data     = json.loads(request.body)
    tc_min   = data.get('minutes', 5)
    tc_inc   = data.get('increment', 0)
    tc       = f"{tc_min}+{tc_inc}"

    MatchmakingQueue.objects.filter(user=request.user).delete()
    rating = request.user.profile.rating

    opp_q = MatchmakingQueue.objects.filter(
        time_control=tc,
        rating__gte=rating - 200,
        rating__lte=rating + 200,
    ).exclude(user=request.user).order_by('joined_at').first()

    if opp_q:
        opponent = opp_q.user
        opp_q.delete()

        # Tasodifiy rang taqsimlash
        if random.random() < 0.5:
            white, black = request.user, opponent
        else:
            white, black = opponent, request.user

        game = Game.objects.create(
            white_player=white, black_player=black,
            time_control=tc, status='active',
            white_time_remaining=tc_min * 60,
            black_time_remaining=tc_min * 60,
            white_rating_before=white.profile.rating,
            black_rating_before=black.profile.rating,
        )
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        async_to_sync(get_channel_layer().group_send)(
            f"queue_{opponent.id}",
            {'type': 'game_found', 'game_id': game.id}
        )
        return JsonResponse({'game_id': game.id})
    else:
        MatchmakingQueue.objects.create(user=request.user, time_control=tc, rating=rating)
        return JsonResponse({'game_id': None, 'in_queue': True})


@login_required
def queue_status(request):
    if MatchmakingQueue.objects.filter(user=request.user).exists():
        return JsonResponse({'in_queue': True, 'game_id': None})
    game = Game.objects.filter(
        Q(white_player=request.user) | Q(black_player=request.user), status='active'
    ).order_by('-created_at').first()
    return JsonResponse({'in_queue': False, 'game_id': game.id if game else None})


@login_required
@require_POST
def queue_leave(request):
    MatchmakingQueue.objects.filter(user=request.user).delete()
    return JsonResponse({'ok': True})


# ─── Chaqiruv taklifi ─────────────────────────────────────────────────────
@login_required
def check_invite(request):
    """WS ishlamasa polling orqali kelgan taklifni tekshirish."""
    invite = ChallengeInvite.objects.filter(
        receiver=request.user, status='pending'
    ).select_related('sender').order_by('-created_at').first()
    if invite:
        return JsonResponse({
            'invite_id':    invite.id,
            'from_user':    invite.sender.username,
            'time_control': invite.time_control,
        })
    return JsonResponse({'invite_id': None})


@login_required
def check_active_game(request):
    """WS orqali game_found o'tkazib yuborilgan bo'lsa, polling fallback uchun.
    Foydalanuvchi hali kirmagan aktiv o'yini borligini tekshiradi."""
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(seconds=30)
    game = Game.objects.filter(
        Q(white_player=request.user) | Q(black_player=request.user),
        status='active',
        created_at__gte=cutoff,
    ).order_by('-created_at').first()
    if game:
        opp = game.black_player if game.white_player == request.user else game.white_player
        return JsonResponse({
            'game_id':      game.id,
            'opponent':     opp.username,
            'time_control': game.time_control,
        })
    return JsonResponse({'game_id': None})


@login_required
def challenge_status(request, invite_id):
    """Yuborilgan taklifning joriy holatini qaytaradi (polling uchun)."""
    invite = get_object_or_404(ChallengeInvite, pk=invite_id, sender=request.user)
    data = {'status': invite.status, 'game_id': None}
    if invite.game_id:
        data['game_id'] = invite.game_id
    return JsonResponse(data)


@login_required
@csrf_exempt
def challenge_player(request, username):
    """Raqibni o'yinga chaqirish — faqat fetch/AJAX so'rovlarini qabul qiladi."""
    # Agar to'g'ridan-to'g'ri brauzerdan kirilsa — o'yin topish sahifasiga qaytarish
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Accept', '').startswith('application/json') or
        'json' in request.headers.get('Accept', '') or
        request.headers.get('Content-Type', '').startswith('application/json')
    )
    # fetch() so'rovlari Accept: */* yuboradi, lekin Sec-Fetch-Mode: cors bo'ladi
    sec_fetch_mode = request.headers.get('Sec-Fetch-Mode', '')
    sec_fetch_dest = request.headers.get('Sec-Fetch-Dest', '')
    is_fetch = sec_fetch_mode in ('cors', 'no-cors') or sec_fetch_dest == 'empty'

    if not is_ajax and not is_fetch:
        # Brauzerdan to'g'ridan-to'g'ri kirish — sahifaga yo'naltirish
        messages.info(request, f"{username} ni chaqirish uchun quyidagi tugmani ishlating.")
        return redirect('find_opponent')

    receiver = get_object_or_404(User, username=username)
    if receiver == request.user:
        return JsonResponse({'ok': False, 'error': "O'zingizni chaqirib bo'lmaydi."})

    tc = request.GET.get('tc', '5+0')

    # Eski pending takliflarni bekor qilish
    ChallengeInvite.objects.filter(
        sender=request.user, receiver=receiver, status='pending'
    ).update(status='cancelled')

    invite = ChallengeInvite.objects.create(
        sender=request.user, receiver=receiver, time_control=tc
    )

    # WebSocket orqali xabardor qilish
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        async_to_sync(get_channel_layer().group_send)(
            f"queue_{receiver.id}",
            {
                'type':         'challenge_invite',
                'invite_id':    invite.id,
                'from_user':    request.user.username,
                'time_control': tc,
            }
        )
    except Exception:
        pass

    return JsonResponse({'ok': True, 'invite_id': invite.id})


@login_required
def challenge_respond(request, invite_id):
    """Taklifni qabul qilish yoki rad etish."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    try:
        return _challenge_respond_inner(request, invite_id)
    except Exception as e:
        import traceback
        return JsonResponse({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}, status=500)


def _challenge_respond_inner(request, invite_id):
    from django.http import Http404
    try:
        invite = ChallengeInvite.objects.get(
            pk=invite_id, receiver=request.user, status='pending'
        )
    except ChallengeInvite.DoesNotExist:
        # Allaqachon qabul qilingan yoki bekor qilingan
        existing = ChallengeInvite.objects.filter(pk=invite_id).first()
        if existing and existing.game_id:
            return JsonResponse({'ok': True, 'accepted': True, 'game_id': existing.game_id})
        return JsonResponse({'ok': False, 'error': 'Taklif topilmadi'}, status=404)

    try:
        data   = json.loads(request.body)
    except Exception:
        data = {}
    accept = data.get('accept', False)

    if not accept:
        invite.status = 'declined'
        invite.save(update_fields=['status'])
        # Jo'natuvchiga xabardor qil
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            async_to_sync(get_channel_layer().group_send)(
                f"queue_{invite.sender.id}",
                {'type': 'invite_response', 'accepted': False, 'game_id': None,
                 'from_user': request.user.username}
            )
        except Exception:
            pass
        return JsonResponse({'ok': True, 'accepted': False})

    # Qabul qilindi — tasodifiy rang taqsimlash
    try:
        tc_min = int(invite.time_control.split('+')[0])
    except (ValueError, IndexError):
        tc_min = 5  # default 5 daqiqa
    if random.random() < 0.5:
        white, black = invite.sender, invite.receiver
    else:
        white, black = invite.receiver, invite.sender

    game = Game.objects.create(
        white_player=white, black_player=black,
        time_control=invite.time_control, status='active',
        white_time_remaining=tc_min * 60,
        black_time_remaining=tc_min * 60,
        white_rating_before=white.profile.rating,
        black_rating_before=black.profile.rating,
    )
    invite.status = 'accepted'
    invite.game   = game
    invite.save(update_fields=['status', 'game'])

    # Ikkalasiga ham o'yin topildi xabari — WebSocket orqali
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        cl = get_channel_layer()
        for uid in [invite.sender.id, invite.receiver.id]:
            async_to_sync(cl.group_send)(
                f"queue_{uid}",
                {'type': 'game_found', 'game_id': game.id}
            )
    except Exception:
        pass

    return JsonResponse({'ok': True, 'accepted': True, 'game_id': game.id})


@login_required
@require_POST
@csrf_exempt
def challenge_cancel(request, invite_id):
    """Jo'natuvchi taklifni bekor qiladi."""
    invite = get_object_or_404(ChallengeInvite, pk=invite_id, sender=request.user, status='pending')
    invite.status = 'cancelled'
    invite.save(update_fields=['status'])
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        async_to_sync(get_channel_layer().group_send)(
            f"queue_{invite.receiver.id}",
            {'type': 'invite_response', 'accepted': False, 'game_id': None,
             'from_user': request.user.username}
        )
    except Exception:
        pass
    return JsonResponse({'ok': True})


# ─── O'yin sahifasi ───────────────────────────────────────────────────────
@login_required
def game_view(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    if (request.user != game.white_player and
            request.user != game.black_player and
            not request.user.is_staff):
        messages.error(request, "Bu o'yinga kirish huquqingiz yo'q.")
        return redirect('find_opponent')
    return render(request, 'chess/game.html', {'game': game, 'watch_mode': False})


# ─── Qonuniy harakatlar ───────────────────────────────────────────────────
@login_required
def game_legal_moves(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    if game.status != 'active':
        return JsonResponse({'legal_moves': {}, 'turn': game.current_turn})
    from chess.chess_engine import legal_moves as lm
    board    = game.board_state
    ep_sq    = game.ep_square or None
    castling = game.castling_rights
    color    = game.current_turn
    lm_map   = {}
    for s, p in board.items():
        if p and p[0] == color:
            ml = lm(board, s, color, ep_sq, castling)
            if ml:
                lm_map[s] = ml
    return JsonResponse({
        'legal_moves': lm_map,
        'turn': color,
        'in_check': __import__('chess.chess_engine', fromlist=['is_in_check']).is_in_check(board, color),
    })


# ─── Harakatni qabul qilish (REST fallback) ───────────────────────────────
@login_required
@require_POST
def game_move(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    if game.status != 'active':
        return JsonResponse({'success': False, 'error': "O'yin tugagan."})
    data    = json.loads(request.body)
    from_sq = data.get('from')
    to_sq   = data.get('to')
    from chess.chess_engine import legal_moves as lm, apply_move
    board    = game.board_state
    ep_sq    = game.ep_square or None
    castling = game.castling_rights
    color    = game.current_turn
    if to_sq not in lm(board, from_sq, color, ep_sq, castling):
        return JsonResponse({'success': False, 'error': "Noto'g'ri harakat."})
    new_board, new_ep, new_castling = apply_move(board, from_sq, to_sq, ep_sq, castling)
    moves = game.moves
    moves.append(f"{from_sq}-{to_sq}")
    game.board_json    = json.dumps(new_board)
    game.moves_json    = json.dumps(moves)
    game.current_turn  = 'b' if color == 'w' else 'w'
    game.ep_square     = new_ep or ''
    game.castling_json = json.dumps(new_castling)
    game.save(update_fields=['board_json','moves_json','current_turn','ep_square','castling_json','updated_at'])
    return JsonResponse({'success': True, 'board': new_board, 'turn': game.current_turn,
                         'moves': moves, 'white_time': game.white_time_remaining,
                         'black_time': game.black_time_remaining})


# ─── Taslim bo'lish ───────────────────────────────────────────────────────
@login_required
@require_POST
def game_resign(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    if game.status == 'active':
        if request.user == game.white_player:
            game.status = 'black_wins'
            game.calculate_rating_change('black')
        else:
            game.status = 'white_wins'
            game.calculate_rating_change('white')
        game.apply_result()
        # WebSocket orqali raqibga real-time xabardor qil
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            async_to_sync(get_channel_layer().group_send)(
                f"chess_{game_id}",
                {
                    'type': 'chess_move',
                    'board': game.board_state, 'turn': game.current_turn,
                    'moves': game.moves, 'from_sq': None, 'to_sq': None,
                    'legal_moves': {}, 'in_check': False, 'check_sq': '',
                    'white_time': game.white_time_remaining,
                    'black_time': game.black_time_remaining,
                    'game_over': True, 'result': game.status,
                    'white_change': game.white_rating_change,
                    'black_change': game.black_rating_change,
                }
            )
        except Exception:
            pass
        messages.info(request, "Taslim bo'ldingiz.")
    return redirect('find_opponent')


# ─── Durang taklifi ───────────────────────────────────────────────────────
@login_required
@require_POST
def game_draw_offer(request, game_id):
    game = get_object_or_404(Game, pk=game_id)
    if game.status == 'active':
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        async_to_sync(get_channel_layer().group_send)(
            f"chess_{game_id}",
            {'type': 'draw_offer', 'from': request.user.username}
        )
    return JsonResponse({'ok': True})


# ─── O'yinni tark etish (abandon) ────────────────────────────────────────
@login_required
@csrf_exempt
def game_abandon(request, game_id):
    """O'yinchi o'yinni tark etdi — yutqizgan hisoblanadi."""
    game = get_object_or_404(Game, pk=game_id)
    if game.status == 'active':
        if request.user == game.white_player:
            game.status = 'black_wins'
            game.calculate_rating_change('black')
        elif request.user == game.black_player:
            game.status = 'white_wins'
            game.calculate_rating_change('white')
        else:
            return JsonResponse({'ok': False})
        game.apply_result()
        # WebSocket orqali raqibga xabardor qil
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            async_to_sync(get_channel_layer().group_send)(
                f"chess_{game_id}",
                {
                    'type': 'chess_move',
                    'board': game.board_state, 'turn': game.current_turn,
                    'moves': game.moves, 'from_sq': None, 'to_sq': None,
                    'legal_moves': {}, 'in_check': False, 'check_sq': '',
                    'white_time': game.white_time_remaining,
                    'black_time': game.black_time_remaining,
                    'game_over': True, 'result': game.status,
                    'white_change': game.white_rating_change,
                    'black_change': game.black_rating_change,
                }
            )
        except Exception:
            pass
    return JsonResponse({'ok': True})
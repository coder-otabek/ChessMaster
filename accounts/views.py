from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta

from .forms import (RegisterForm, LoginForm, PasswordResetRequestForm,
                    OTPVerifyForm, SetNewPasswordForm, ProfileEditForm,
                    AdminAddUserForm, AdminEditUserForm, AdminResetPasswordForm)
from .models import Profile, PasswordResetOTP, EmailVerificationOTP


def is_staff(user):
    return user.is_active and (user.is_staff or user.is_superuser)


# ─── Ro'yxatdan o'tish ────────────────────────────────────────────────────
def register_view(request):
    if request.user.is_authenticated:
        return redirect('find_opponent')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # Foydalanuvchini hali saqlamaymiz — avval email tasdiqlansin
        data = form.cleaned_data
        email = data['email']

        # Eski tasdiqlanmagan OTPlarni o'chiramiz
        EmailVerificationOTP.objects.filter(email=email).delete()
        otp_code = EmailVerificationOTP.generate_otp()
        EmailVerificationOTP.objects.create(
            email=email,
            otp=otp_code,
            form_data={
                'username':   data['username'],
                'email':      email,
                'first_name': data['first_name'],
                'last_name':  data['last_name'],
                'password':   form.cleaned_data['password1'],
            }
        )
        # Email yuborish
        try:
            send_mail(
                subject="ChessMaster UZ — Email tasdiqlash kodi",
                message=(
                    f"Salom {data['first_name']},\n\n"
                    f"Ro'yxatdan o'tishni tasdiqlash uchun kod: {otp_code}\n\n"
                    f"Kod 15 daqiqa amal qiladi.\n"
                    f"Agar siz ro'yxatdan o'tmagan bo'lsangiz, bu xabarni e'tiborsiz qoldiring.\n\n"
                    f"ChessMaster UZ"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            messages.error(request, f"Email yuborishda xato: {str(e)}")
            return render(request, 'registration/register.html', {'form': form})

        request.session['reg_email'] = email
        messages.success(request, f"{email} manziliga tasdiqlash kodi yuborildi.")
        return redirect('register_verify')
    return render(request, 'registration/register.html', {'form': form})


def register_verify_view(request):
    """Ro'yxatdan o'tishda email OTP tasdiqlash."""
    email = request.session.get('reg_email')
    if not email:
        return redirect('register')
    form = OTPVerifyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        otp_input = form.cleaned_data['otp']
        try:
            otp_obj = EmailVerificationOTP.objects.filter(
                email=email, otp=otp_input, is_used=False
            ).latest('created_at')
            if otp_obj.is_expired:
                messages.error(request, "Kod muddati o'tgan. Qayta ro'yxatdan o'ting.")
                return redirect('register')
            # Foydalanuvchini yaratamiz
            d = otp_obj.form_data
            user = User(
                username=d['username'],
                email=d['email'],
                first_name=d['first_name'],
                last_name=d['last_name'],
                is_active=True,
            )
            user.set_password(d['password'])
            user.save()
            otp_obj.is_used = True
            otp_obj.save()
            login(request, user)
            request.session.pop('reg_email', None)
            messages.success(request, f"Xush kelibsiz, {user.username}!")
            # Xush kelibsiz emaili
            try:
                send_mail(
                    subject="ChessMaster UZ — Muvaffaqiyatli ro'yxatdan o'tdingiz!",
                    message=(
                        f"Assalomu alaykum, {user.first_name or user.username}!\n\n"
                        f"Siz ChessMaster UZ saytiga muvaffaqiyatli ro'yxatdan o'tdingiz.\n"
                        f"Foydalanuvchi nomingiz: {user.username}\n\n"
                        f"Endi saytga kirib o'yinchilar bilan musobaqa o'tkazishingiz mumkin.\n\n"
                        f"ChessMaster UZ jamoasi"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            return redirect('find_opponent')
        except EmailVerificationOTP.DoesNotExist:
            form.add_error('otp', "Noto'g'ri kod.")
    return render(request, 'registration/register_verify.html', {'form': form, 'email': email})


def register_resend_view(request):
    """Ro'yxatdan o'tish OTPsini qayta yuborish."""
    if request.method != 'POST':
        return JsonResponse({'ok': False})
    email = request.session.get('reg_email')
    if not email:
        return JsonResponse({'ok': False, 'error': 'Sessiya topilmadi'})
    try:
        otp_obj = EmailVerificationOTP.objects.filter(email=email, is_used=False).latest('created_at')
    except EmailVerificationOTP.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'OTP topilmadi'})
    # Yangi OTP
    EmailVerificationOTP.objects.filter(email=email).delete()
    otp_code = EmailVerificationOTP.generate_otp()
    EmailVerificationOTP.objects.create(
        email=email, otp=otp_code, form_data=otp_obj.form_data
    )
    try:
        send_mail(
            subject="ChessMaster UZ — Yangi tasdiqlash kodi",
            message=(
                f"Yangi tasdiqlash kodi: {otp_code}\n\n"
                f"Kod 15 daqiqa amal qiladi.\n\nChessMaster UZ"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


# ─── Kirish ───────────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('find_opponent')
    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        # Rolga qarab yo'naltirish
        if user.is_superuser:
            return redirect('superuser_users')
        elif user.is_staff:
            return redirect('admin_dashboard')
        else:
            return redirect('find_opponent')
    return render(request, 'registration/login.html', {'form': form})


# ─── Chiqish ──────────────────────────────────────────────────────────────
def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Parolni tiklash — email yuborish ─────────────────────────────────────
def password_reset_request(request):
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "Bu email bilan foydalanuvchi topilmadi.")
            return render(request, 'registration/password_reset.html', {'form': form})
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email=email).order_by('date_joined').first()

        # Eski OTPlarni o'chirish
        PasswordResetOTP.objects.filter(user=user).delete()
        otp_code = PasswordResetOTP.generate_otp()
        PasswordResetOTP.objects.create(user=user, email=email, otp=otp_code)

        # Email yuborish
        try:
            send_mail(
                subject="ChessMaster UZ — Parolni tiklash kodi",
                message=(
                    f"Salom {user.username},\n\n"
                    f"Parolni tiklash kodi: {otp_code}\n\n"
                    f"Kod 15 daqiqa amal qiladi.\n"
                    f"Agar siz so'rov qilmagan bo'lsangiz, bu xabarni e'tiborsiz qoldiring.\n\n"
                    f"ChessMaster UZ"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception as e:
            messages.error(request, f"Email yuborishda xato: {str(e)}")
            return render(request, 'registration/password_reset.html', {'form': form})

        messages.success(request, f"{email} manziliga kod yuborildi.")
        request.session['reset_email'] = email
        return redirect('password_reset_verify')
    return render(request, 'registration/password_reset.html', {'form': form})


# ─── OTP tasdiqlash ───────────────────────────────────────────────────────
def password_reset_verify(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('password_reset')
    form = OTPVerifyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        otp_input = form.cleaned_data['otp']
        try:
            otp_obj = PasswordResetOTP.objects.filter(
                email=email, otp=otp_input, is_used=False
            ).latest('created_at')
            from django.utils import timezone
            from datetime import timedelta
            if timezone.now() - otp_obj.created_at > timedelta(minutes=15):
                messages.error(request, "Kod muddati o'tgan. Qayta so'rang.")
                return redirect('password_reset')
            otp_obj.is_used = True
            otp_obj.save()
            request.session['reset_verified'] = True
            request.session['reset_user_id'] = otp_obj.user.id
            return redirect('password_reset_confirm')
        except PasswordResetOTP.DoesNotExist:
            form.add_error('otp', "Noto'g'ri kod.")
    return render(request, 'registration/password_reset_verify.html', {'form': form, 'email': email})


def password_reset_resend(request):
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Faqat POST'})
    email = request.session.get('reset_email')
    if not email:
        return JsonResponse({'ok': False, 'error': 'Sessiya topilmadi'})
    try:
        try:
            user = User.objects.get(email=email)
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email=email).order_by('date_joined').first()
        PasswordResetOTP.objects.filter(user=user).delete()
        otp_code = PasswordResetOTP.generate_otp()
        PasswordResetOTP.objects.create(user=user, email=email, otp=otp_code)
        send_mail(
            "ChessMaster UZ — Parolni tiklash kodi",
            f"Salom {user.username},\n\nYangi tasdiqlash kodi: {otp_code}\n\nKod 15 daqiqa amal qiladi.\n\nChessMaster UZ",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)})


# ─── Yangi parol o'rnatish ────────────────────────────────────────────────
def password_reset_confirm(request):
    if not request.session.get('reset_verified'):
        return redirect('password_reset')
    form = SetNewPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user_id = request.session.get('reset_user_id')
        user = get_object_or_404(User, pk=user_id)
        user.set_password(form.cleaned_data['new_password1'])
        user.save()
        del request.session['reset_verified']
        del request.session['reset_email']
        del request.session['reset_user_id']
        messages.success(request, "Parol muvaffaqiyatli yangilandi. Kiring.")
        return redirect('login')
    return render(request, 'registration/password_reset_confirm.html', {'form': form})


# ─── Parol o'zgartirish (kirgan holda) ────────────────────────────────────
@login_required
def password_change_view(request):
    if request.method == 'POST':
        old = request.POST.get('old_password')
        new1 = request.POST.get('new_password1')
        new2 = request.POST.get('new_password2')
        if not request.user.check_password(old):
            messages.error(request, "Eski parol noto'g'ri.")
        elif new1 != new2:
            messages.error(request, "Yangi parollar mos kelmadi.")
        elif len(new1) < 8:
            messages.error(request, "Parol kamida 8 ta belgidan iborat bo'lishi kerak.")
        else:
            request.user.set_password(new1)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Parol muvaffaqiyatli yangilandi.")
            return redirect('profile', username=request.user.username)
    return render(request, 'registration/password_change.html')


# ─── Profil ───────────────────────────────────────────────────────────────
@login_required
def profile_view(request, username):
    profile_user = get_object_or_404(
        User.objects.select_related('profile'), username=username
    )
    from chess.models import Game
    recent_games = []
    for g in Game.objects.filter(
        Q(white_player=profile_user) | Q(black_player=profile_user),
        status__in=['white_wins','black_wins','draw']
    ).order_by('-created_at')[:10]:
        if g.white_player == profile_user:
            opponent = g.black_player
            result = 'win' if g.status == 'white_wins' else ('loss' if g.status == 'black_wins' else 'draw')
            rc = g.white_rating_change
            opp_r = g.black_rating_before
        else:
            opponent = g.white_player
            result = 'win' if g.status == 'black_wins' else ('loss' if g.status == 'white_wins' else 'draw')
            rc = g.black_rating_change
            opp_r = g.white_rating_before
        recent_games.append({
            'game': g, 'opponent': opponent, 'result': result,
            'rating_change': rc, 'opponent_rating': opp_r,
            'created_at': g.created_at, 'id': g.id
        })
    return render(request, 'registration/profile.html', {
        'profile_user': profile_user,
        'recent_games': recent_games,
    })


# ─── Profil tahrirlash ────────────────────────────────────────────────────
@login_required
def profile_edit_view(request):
    form = ProfileEditForm(request.user, request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        u = request.user
        u.first_name = d['first_name']
        u.last_name  = d['last_name']
        u.username   = d['username']
        u.email      = d['email']
        u.save()
        p = u.profile
        p.bio              = d['bio']
        p.country          = d['country']
        p.city             = d['city']
        p.favorite_opening = d['favorite_opening']
        p.play_style       = d['play_style']
        if d.get('avatar'):
            p.avatar = d['avatar']
        p.save()
        messages.success(request, "Profil yangilandi.")
        return redirect('profile', username=u.username)
    return render(request, 'registration/profile_edit.html', {'form': form})


# ─── O'yin tarixi ─────────────────────────────────────────────────────────
@login_required
def game_history_view(request):
    from chess.models import Game
    games_qs = Game.objects.filter(
        Q(white_player=request.user) | Q(black_player=request.user),
        status__in=['white_wins','black_wins','draw']
    ).order_by('-created_at')
    paginator = Paginator(games_qs, 20)
    page = request.GET.get('page', 1)
    games_page = paginator.get_page(page)
    return render(request, 'chess/game_history.html', {'games': games_page})


# ═══════════════════════════════════════════════════════════
# ADMIN VIEWS
# ═══════════════════════════════════════════════════════════

@login_required
@user_passes_test(is_staff)
def admin_dashboard(request):
    from chess.models import Game
    from django.utils import timezone
    from datetime import timedelta
    today = timezone.now().date()
    stats = {
        'total_users': User.objects.count(),
        'new_users_today': User.objects.filter(date_joined__date=today).count(),
        'total_games': Game.objects.count(),
        'games_today': Game.objects.filter(created_at__date=today).count(),
        'active_games': Game.objects.filter(status='active').count(),
        'online_users': Profile.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=15)).count(),
    }
    recent_games = Game.objects.select_related(
        'white_player','black_player',
        'white_player__profile','black_player__profile'
    ).order_by('-created_at')[:10]
    top_players = User.objects.select_related('profile').order_by('-profile__rating')[:10]
    return render(request, 'admin_panel/dashboard.html', {
        'stats': stats,
        'recent_games': recent_games,
        'top_players': top_players,
    })


@login_required
@user_passes_test(is_staff)
def admin_players(request):
    qs = User.objects.select_related('profile').all()
    q = request.GET.get('q','')
    if q:
        qs = qs.filter(Q(username__icontains=q)|Q(email__icontains=q)|
                       Q(first_name__icontains=q)|Q(last_name__icontains=q))
    role = request.GET.get('role','')
    if role == 'superuser': qs = qs.filter(is_superuser=True)
    elif role == 'admin': qs = qs.filter(is_staff=True, is_superuser=False)
    elif role == 'user': qs = qs.filter(is_staff=False, is_superuser=False)
    status = request.GET.get('status','')
    if status == 'active': qs = qs.filter(is_active=True)
    elif status == 'inactive': qs = qs.filter(is_active=False)
    sort = request.GET.get('sort','-profile__rating')
    qs = qs.order_by(sort)
    paginator = Paginator(qs, 25)
    players = paginator.get_page(request.GET.get('page',1))
    return render(request, 'admin_panel/players.html', {'players': players})


@login_required
@user_passes_test(is_staff)
def admin_edit_player(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    form = AdminEditUserForm(target_user, request.POST or None, initial={
        'first_name': target_user.first_name,
        'last_name': target_user.last_name,
        'username': target_user.username,
        'email': target_user.email,
        'rating': target_user.profile.rating,
        'wins': target_user.profile.wins,
        'losses': target_user.profile.losses,
        'is_staff': target_user.is_staff,
        'is_active': target_user.is_active,
    })
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        target_user.first_name = d['first_name']
        target_user.last_name  = d['last_name']
        target_user.username   = d['username']
        target_user.email      = d['email']
        if request.user.is_superuser:
            target_user.is_staff  = d['is_staff']
            target_user.is_active = d['is_active']
        target_user.save()
        p = target_user.profile
        p.rating = d['rating']
        p.wins   = d['wins']
        p.losses = d['losses']
        p.save()
        messages.success(request, f"{target_user.username} yangilandi.")
        return redirect('admin_players')
    return render(request, 'admin_panel/edit_player.html', {
        'form': form, 'target_user': target_user
    })


@login_required
@user_passes_test(is_staff)
def admin_reset_player_password(request, user_id):
    target_user = get_object_or_404(User, pk=user_id)
    form = AdminResetPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        target_user.set_password(form.cleaned_data['new_password'])
        target_user.save()
        messages.success(request, f"{target_user.username} paroli yangilandi.")
        return redirect('admin_edit_player', user_id=user_id)
    return render(request, 'admin_panel/reset_password.html', {
        'form': form, 'target_user': target_user
    })


@login_required
@user_passes_test(is_staff)
def admin_toggle_active(request, user_id):
    if request.method == 'POST':
        target_user = get_object_or_404(User, pk=user_id)
        if not target_user.is_superuser:
            target_user.is_active = not target_user.is_active
            target_user.save()
            state = "faollashtirildi" if target_user.is_active else "bloklandi"
            messages.success(request, f"{target_user.username} {state}.")
    return redirect('admin_players')


@login_required
@user_passes_test(is_staff)
def admin_games(request):
    from chess.models import Game
    qs = Game.objects.select_related(
        'white_player','black_player',
        'white_player__profile','black_player__profile'
    ).order_by('-created_at')
    q = request.GET.get('q','')
    if q:
        qs = qs.filter(Q(white_player__username__icontains=q)|Q(black_player__username__icontains=q))
    paginator = Paginator(qs, 25)
    games = paginator.get_page(request.GET.get('page',1))
    return render(request, 'admin_panel/games.html', {'games': games})


@login_required
@user_passes_test(is_staff)
def admin_create_game(request):
    from chess.models import Game
    players = User.objects.filter(is_active=True).select_related('profile').order_by('username')
    if request.method == 'POST':
        white_id = request.POST.get('white_player', '').strip()
        black_id = request.POST.get('black_player', '').strip()
        tc = request.POST.get('time_control', '5+0')

        if not white_id or not black_id:
            messages.error(request, "Ikkala o'yinchini ham tanlang.")
            return render(request, 'admin_panel/create_game.html', {'players': players})

        if white_id == black_id:
            messages.error(request, "Bir xil o'yinchi ikki tomondan o'ynay olmaydi.")
            return render(request, 'admin_panel/create_game.html', {'players': players})

        white = get_object_or_404(User, pk=white_id)
        black = get_object_or_404(User, pk=black_id)

        # Agar o'yinchilardan biri aktiv o'yinda bo'lsa — admin majburan yakunlaydi
        for player in [white, black]:
            old_games = Game.objects.filter(
                status='active'
            ).filter(Q(white_player=player) | Q(black_player=player))
            for og in old_games:
                # Eski o'yinni abandon qilamiz
                if og.white_player == player:
                    og.status = 'black_wins'
                else:
                    og.status = 'white_wins'
                og.save(update_fields=['status'])

        try:
            mins = int(tc.split('+')[0])
        except (ValueError, IndexError):
            mins = 5

        game = Game.objects.create(
            white_player=white,
            black_player=black,
            time_control=tc,
            status='active',
            white_time_remaining=mins * 60,
            black_time_remaining=mins * 60,
            white_rating_before=white.profile.rating,
            black_rating_before=black.profile.rating,
        )
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            async def _notify_both():
                cl = get_channel_layer()
                for player, opp in [(white, black), (black, white)]:
                    await cl.group_send(
                        f"queue_{player.id}",
                        {
                            'type':         'game_found',
                            'game_id':      game.id,
                            'admin_start':  True,
                            'opponent':     opp.username,
                            'time_control': tc,
                        }
                    )

            async_to_sync(_notify_both)()
        except Exception:
            pass
        messages.success(request, f"✅ O'yin #{game.id} yaratildi: {white.username} vs {black.username}")
        return redirect('admin_watch_game', game_id=game.id)

    return render(request, 'admin_panel/create_game.html', {'players': players})


@login_required
@user_passes_test(is_staff)
def admin_live_games(request):
    from chess.models import Game
    active_games = Game.objects.filter(status='active').select_related(
        'white_player','black_player',
        'white_player__profile','black_player__profile'
    )
    return render(request, 'admin_panel/live_games.html', {'active_games': active_games})


@login_required
@user_passes_test(is_staff)
def admin_watch_game(request, game_id):
    from chess.models import Game
    game = get_object_or_404(Game, pk=game_id)
    return render(request, 'chess/game.html', {'game': game, 'watch_mode': True})


# ─── Excel / CSV export ───────────────────────────────────────────────────
@login_required
@user_passes_test(is_staff)
def admin_ratings_page(request):
    players = Profile.objects.select_related('user').order_by('-rating')
    return render(request, 'admin_panel/ratings_export.html', {'players': players})


@login_required
@user_passes_test(is_staff)
def admin_export_excel(request):
    if request.method != 'POST':
        return redirect('admin_ratings')
    from chess.views_export import build_excel_response
    return build_excel_response(request)


@login_required
@user_passes_test(is_staff)
def admin_export_csv(request):
    from chess.views_export import build_csv_response
    return build_csv_response(request)


# ═══════════════════════════════════════════════════════════
# SUPERUSER VIEWS
# ═══════════════════════════════════════════════════════════

def is_superuser(user):
    return user.is_active and user.is_superuser


@login_required
@user_passes_test(is_superuser)
def superuser_users(request):
    qs = User.objects.select_related('profile').all()
    q = request.GET.get('q','')
    if q:
        qs = qs.filter(Q(username__icontains=q)|Q(email__icontains=q)|
                       Q(first_name__icontains=q)|Q(last_name__icontains=q))
    role = request.GET.get('role','')
    if role == 'superuser': qs = qs.filter(is_superuser=True)
    elif role == 'admin': qs = qs.filter(is_staff=True, is_superuser=False)
    elif role == 'user': qs = qs.filter(is_staff=False)
    status = request.GET.get('status','')
    if status == 'active': qs = qs.filter(is_active=True)
    elif status == 'inactive': qs = qs.filter(is_active=False)
    qs = qs.order_by('-profile__rating')
    paginator = Paginator(qs, 25)
    users = paginator.get_page(request.GET.get('page',1))
    return render(request, 'superuser/users.html', {'users': users})


@login_required
@user_passes_test(is_superuser)
def superuser_add_user(request):
    form = AdminAddUserForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        role = request.POST.get('role','user')
        user.is_active = 'is_active' in request.POST
        if role == 'superuser':
            user.is_superuser = True
            user.is_staff = True
        elif role == 'admin':
            user.is_staff = True
            user.is_superuser = False
        else:
            user.is_staff = False
            user.is_superuser = False
        user.save()
        try:
            initial_rating = int(request.POST.get('initial_rating', 1200))
            user.profile.rating = initial_rating
            user.profile.save()
        except Exception:
            pass
        messages.success(request, f"{user.username} qo'shildi.")
        return redirect('superuser_users')
    return render(request, 'superuser/add_user.html', {'form': form})


@login_required
@user_passes_test(is_superuser)
def superuser_delete_user(request, user_id):
    if request.method == 'POST':
        target = get_object_or_404(User, pk=user_id)
        if not target.is_superuser:
            uname = target.username
            target.delete()
            messages.success(request, f"{uname} o'chirildi.")
        else:
            messages.error(request, "Superuserni o'chirib bo'lmaydi.")
    return redirect('superuser_users')


@login_required
@user_passes_test(is_superuser)
def superuser_settings(request):
    return render(request, 'superuser/settings.html')


# ─── Live status endpoint ────────────────────────────────────────────────
from django.views.decorators.http import require_GET

@login_required
@require_GET
def live_status(request):
    """Real-time ma'lumotlar: online o'yinchilar, o'qilmagan xabarlar."""
    from chat.models import Message
    # O'zining last_seen ni yangilaymiz — polling = aktiv (is_online ga tayanmaymiz)
    Profile.objects.filter(user=request.user).update(
        last_seen=timezone.now()
    )
    # 15 soniya ichida aktiv bo'lgan — online hisoblanadi
    cutoff = timezone.now() - timedelta(seconds=15)
    online = list(Profile.objects.filter(
        last_seen__gte=cutoff
    ).values_list('user__username', flat=True))
    unread = Message.objects.filter(receiver=request.user, is_read=False).count()
    return JsonResponse({'online': online, 'unread': unread})


# ─── Admin: o'yinni majburan yakunlash ───────────────────────────────────
@login_required
@user_passes_test(is_staff)
def admin_force_end_game(request, game_id):
    from chess.models import Game
    if request.method == 'POST':
        game = get_object_or_404(Game, pk=game_id, status='active')
        game.status = 'draw'
        game.save(update_fields=['status'])
        # WebSocket orqali o'yinchilarga xabardor qil
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
                    'game_over': True, 'result': 'draw',
                    'white_change': 0, 'black_change': 0,
                }
            )
        except Exception:
            pass
        messages.success(request, f"O'yin #{game_id} yakunlandi.")
    return redirect('admin_live_games')
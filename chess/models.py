import json
from django.db import models
from django.contrib.auth.models import User


INITIAL_BOARD = {
    'a8':'bR','b8':'bN','c8':'bB','d8':'bQ','e8':'bK','f8':'bB','g8':'bN','h8':'bR',
    'a7':'bP','b7':'bP','c7':'bP','d7':'bP','e7':'bP','f7':'bP','g7':'bP','h7':'bP',
    'a2':'wP','b2':'wP','c2':'wP','d2':'wP','e2':'wP','f2':'wP','g2':'wP','h2':'wP',
    'a1':'wR','b1':'wN','c1':'wB','d1':'wQ','e1':'wK','f1':'wB','g1':'wN','h1':'wR',
}


class Game(models.Model):
    STATUS_CHOICES = [
        ('waiting','Kutilmoqda'),
        ('active','Aktiv'),
        ('white_wins','Oq g\'alaba'),
        ('black_wins','Qora g\'alaba'),
        ('draw','Durang'),
        ('aborted','Bekor qilindi'),
    ]
    TIME_CHOICES = [
        ('1+0','1+0 Bullet'),('2+1','2+1 Bullet'),
        ('3+2','3+2 Blitz'),('5+0','5+0 Blitz'),
        ('10+0','10+0 Rapid'),('15+10','15+10 Rapid'),
    ]

    white_player = models.ForeignKey(User, related_name='white_games', on_delete=models.CASCADE)
    black_player = models.ForeignKey(User, related_name='black_games', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    time_control = models.CharField(max_length=10, choices=TIME_CHOICES, default='5+0')

    board_json    = models.TextField(default=json.dumps(INITIAL_BOARD))
    moves_json    = models.TextField(default='[]')
    current_turn  = models.CharField(max_length=1, default='w')
    ep_square     = models.CharField(max_length=3, default='', blank=True)
    castling_json = models.TextField(
        default=json.dumps({'wK': True, 'wQ': True, 'bK': True, 'bQ': True})
    )

    white_time_remaining = models.IntegerField(default=300)
    black_time_remaining = models.IntegerField(default=300)

    white_rating_before  = models.IntegerField(default=1200)
    black_rating_before  = models.IntegerField(default=1200)
    white_rating_change  = models.IntegerField(default=0)
    black_rating_change  = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ended_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"#{self.id} {self.white_player} vs {self.black_player} [{self.status}]"

    @property
    def board_state(self):
        return json.loads(self.board_json)

    @property
    def moves(self):
        return json.loads(self.moves_json)

    @property
    def castling_rights(self):
        try:
            return json.loads(self.castling_json)
        except Exception:
            return {'wK': True, 'wQ': True, 'bK': True, 'bQ': True}

    @property
    def time_control_minutes(self):
        return int(self.time_control.split('+')[0])

    @property
    def time_control_increment(self):
        return int(self.time_control.split('+')[1])

    @property
    def move_count(self):
        return len(self.moves)

    def calculate_rating_change(self, winner):
        """ELO reyting hisoblash"""
        K = 32
        wr = self.white_rating_before
        br = self.black_rating_before
        expected_w = 1 / (1 + 10 ** ((br - wr) / 400))
        expected_b = 1 - expected_w
        if winner == 'white':
            score_w, score_b = 1, 0
        elif winner == 'black':
            score_w, score_b = 0, 1
        else:
            score_w, score_b = 0.5, 0.5
        self.white_rating_change = round(K * (score_w - expected_w))
        self.black_rating_change = round(K * (score_b - expected_b))

    def apply_result(self):
        """Natijani profilga qo'llash — faqat o'zgargan ustunlarni saqlaydi."""
        from django.utils import timezone
        wp = self.white_player.profile
        bp = self.black_player.profile
        wp.rating      = max(100, wp.rating + self.white_rating_change)
        bp.rating      = max(100, bp.rating + self.black_rating_change)
        wp.games_played += 1
        bp.games_played += 1
        if self.status == 'white_wins':
            wp.wins   += 1; bp.losses += 1
        elif self.status == 'black_wins':
            bp.wins   += 1; wp.losses += 1
        else:
            wp.draws  += 1; bp.draws  += 1
        wp.save(update_fields=['rating', 'games_played', 'wins', 'losses', 'draws'])
        bp.save(update_fields=['rating', 'games_played', 'wins', 'losses', 'draws'])
        self.ended_at = timezone.now()
        self.save(update_fields=[
            'status', 'ended_at',
            'white_rating_change', 'black_rating_change',
        ])


class MatchmakingQueue(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    time_control = models.CharField(max_length=10, default='5+0')
    rating = models.IntegerField(default=1200)
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} waiting [{self.time_control}]"


class ChallengeInvite(models.Model):
    """Chaqiruv taklifi — tasdiqlashni kutib turadi."""
    STATUS_CHOICES = [
        ('pending',   'Kutilmoqda'),
        ('accepted',  'Qabul qilindi'),
        ('declined',  'Rad etildi'),
        ('cancelled', 'Bekor qilindi'),
    ]
    sender       = models.ForeignKey(User, related_name='sent_invites',     on_delete=models.CASCADE)
    receiver     = models.ForeignKey(User, related_name='received_invites', on_delete=models.CASCADE)
    time_control = models.CharField(max_length=10, default='5+0')
    status       = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    game         = models.ForeignKey(Game, null=True, blank=True, on_delete=models.SET_NULL)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender} -> {self.receiver} [{self.status}]"
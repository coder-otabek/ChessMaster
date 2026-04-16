import json
import random
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChessConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        self.room    = f"chess_{self.game_id}"
        self.user    = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()
        await self.set_online(True)

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)
        await self.set_online(False)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return
        t = data.get('type')

        if t == 'move':
            result = await self.process_move(data.get('from'), data.get('to'), data.get('promo'))
            if result:
                await self.channel_layer.group_send(self.room, {'type': 'chess_move', **result})

        elif t == 'chat':
            msg = str(data.get('message', ''))[:200].strip()
            if msg:
                await self.channel_layer.group_send(self.room, {
                    'type': 'chat_message',
                    'username': self.user.username,
                    'message': msg,
                })

        elif t == 'draw_offer':
            await self.channel_layer.group_send(self.room, {
                'type': 'draw_offer', 'from': self.user.username,
            })

        elif t == 'draw_accept':
            await self.end_game('draw')

        elif t == 'resign':
            await self.end_game('resign')

        elif t == 'abandon':
            # O'yindan chiqayotgan o'yinchi — yutqizgan hisoblanadi
            await self.end_game('resign')

    # ── Group handlers ────────────────────────────────────────────────────

    async def chess_move(self, event):
        await self.send(text_data=json.dumps({
            'type':         'move',
            'board':        event['board'],
            'turn':         event['turn'],
            'moves':        event['moves'],
            'white_time':   event['white_time'],
            'black_time':   event['black_time'],
            'from_sq':      event.get('from_sq'),
            'to_sq':        event.get('to_sq'),
            'legal_moves':  event.get('legal_moves', {}),
            'in_check':     event.get('in_check', False),
            'check_sq':     event.get('check_sq', ''),
            'game_over':    event.get('game_over', False),
            'result':       event.get('result', ''),
            'white_change': event.get('white_change', 0),
            'black_change': event.get('black_change', 0),
        }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat', 'username': event['username'], 'message': event['message'],
        }))

    async def draw_offer(self, event):
        await self.send(text_data=json.dumps({'type': 'draw_offer', 'from': event['from']}))

    async def game_found(self, event):
        await self.send(text_data=json.dumps({'type': 'game_found', 'game_id': event['game_id']}))

    # ── DB helpers ────────────────────────────────────────────────────────

    @database_sync_to_async
    def set_online(self, status):
        try:
            from datetime import timedelta
            p = self.user.profile
            p.last_seen = timezone.now() if status else timezone.now() - timedelta(minutes=10)
            p.save(update_fields=['last_seen'])
        except Exception:
            pass

    @database_sync_to_async
    def process_move(self, from_sq, to_sq, promo=None):
        from chess.models import Game
        from chess.chess_engine import (
            legal_moves, apply_move, game_status, is_in_check, opponent
        )
        import json as js

        try:
            game = Game.objects.select_for_update().get(pk=self.game_id)
        except Exception:
            return None

        if game.status != 'active':
            return None

        u        = self.user
        is_white = (u == game.white_player)
        my_color = 'w' if is_white else 'b'

        if game.current_turn != my_color:
            return None

        board    = game.board_state
        ep_sq    = game.ep_square or None
        castling = game.castling_rights

        allowed = legal_moves(board, from_sq, my_color, ep_sq, castling)
        if to_sq not in allowed:
            return None

        new_board, new_ep, new_castling = apply_move(board, from_sq, to_sq, ep_sq, castling)

        # Piyoda targ'ibi — server tomonida ham qo'llanadi
        piece = board[from_sq]
        ptype = piece[1]
        tc, tr = 'abcdefgh'.index(to_sq[0]), int(to_sq[1])
        if ptype == 'P' and (tr == 8 or tr == 1):
            pmap = {'Q': 'Q', 'R': 'R', 'B': 'B', 'N': 'N'}
            chosen = pmap.get(promo, 'Q')
            new_board[to_sq] = my_color + chosen

        # SAN notation
        capture = bool(board.get(to_sq)) or (ptype == 'P' and ep_sq == to_sq)
        if ptype == 'K' and abs('abcdefgh'.index(from_sq[0]) - tc) == 2:
            san = 'O-O' if to_sq[0] == 'g' else 'O-O-O'
        else:
            san  = (ptype if ptype != 'P' else '')
            san += (from_sq[0] if ptype == 'P' and capture else '')
            san += ('x' if capture else '')
            san += to_sq
            if ptype == 'P' and (tr == 8 or tr == 1):
                san += '=' + (promo or 'Q')

        moves_list = game.moves
        moves_list.append(san)

        next_turn  = opponent(my_color)
        status     = game_status(new_board, next_turn, new_ep, new_castling)
        in_check   = is_in_check(new_board, next_turn)
        check_sq   = ''
        if in_check:
            san += '+'
            moves_list[-1] = san
            for s, p in new_board.items():
                if p == next_turn + 'K':
                    check_sq = s; break

        game_over = False
        result    = ''
        wc = bc   = 0

        if status == 'checkmate':
            moves_list[-1] = moves_list[-1].rstrip('+') + '#'
            result    = 'white_wins' if my_color == 'w' else 'black_wins'
            game.status = result
            game.calculate_rating_change('white' if my_color == 'w' else 'black')
            game_over = True
            wc, bc = game.white_rating_change, game.black_rating_change
        elif status == 'stalemate':
            result = 'draw'
            game.status = 'draw'
            game.calculate_rating_change('draw')
            game_over = True
            wc, bc = game.white_rating_change, game.black_rating_change

        game.board_json    = js.dumps(new_board)
        game.moves_json    = js.dumps(moves_list)
        game.current_turn  = next_turn if not game_over else game.current_turn
        game.ep_square     = new_ep or ''
        game.castling_json = js.dumps(new_castling)
        game.save(update_fields=[
            'board_json', 'moves_json', 'current_turn',
            'ep_square', 'castling_json', 'updated_at',
        ])

        if game_over:
            game.apply_result()

        # Keyingi navbat uchun qonuniy harakatlar
        from chess.chess_engine import legal_moves as lm
        lm_map = {}
        if not game_over:
            for s, p in new_board.items():
                if p and p[0] == next_turn:
                    ml = lm(new_board, s, next_turn, new_ep, new_castling)
                    if ml:
                        lm_map[s] = ml

        return {
            'board': new_board, 'turn': next_turn if not game_over else game.current_turn,
            'moves': moves_list, 'from_sq': from_sq, 'to_sq': to_sq,
            'legal_moves': lm_map, 'in_check': in_check, 'check_sq': check_sq,
            'white_time': game.white_time_remaining, 'black_time': game.black_time_remaining,
            'game_over': game_over, 'result': result, 'white_change': wc, 'black_change': bc,
        }

    @database_sync_to_async
    def end_game(self, reason):
        from chess.models import Game
        try:
            game = Game.objects.get(pk=self.game_id)
            if game.status != 'active':
                return
            if reason == 'draw':
                game.status = 'draw'
                game.calculate_rating_change('draw')
            elif reason == 'resign':
                if self.user == game.white_player:
                    game.status = 'black_wins'
                    game.calculate_rating_change('black')
                else:
                    game.status = 'white_wins'
                    game.calculate_rating_change('white')
            game.apply_result()
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            async_to_sync(get_channel_layer().group_send)(self.room, {
                'type': 'chess_move',
                'board': game.board_state, 'turn': game.current_turn,
                'moves': game.moves, 'from_sq': None, 'to_sq': None,
                'legal_moves': {}, 'in_check': False, 'check_sq': '',
                'white_time': game.white_time_remaining,
                'black_time': game.black_time_remaining,
                'game_over': True, 'result': game.status,
                'white_change': game.white_rating_change,
                'black_change': game.black_rating_change,
            })
        except Exception:
            pass


class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close(); return
        self.room = f"queue_{self.user.id}"
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def game_found(self, event):
        await self.send(text_data=json.dumps({
            'type':        'game_found',
            'game_id':     event['game_id'],
            'admin_start': event.get('admin_start', False),
            'opponent':    event.get('opponent', ''),
            'time_control':event.get('time_control', ''),
        }))

    async def challenge_invite(self, event):
        await self.send(text_data=json.dumps({
            'type':         'challenge_invite',
            'invite_id':    event['invite_id'],
            'from_user':    event['from_user'],
            'time_control': event['time_control'],
        }))

    async def invite_response(self, event):
        await self.send(text_data=json.dumps({
            'type':     'invite_response',
            'accepted': event['accepted'],
            'game_id':  event.get('game_id'),
            'from_user': event.get('from_user'),
        }))
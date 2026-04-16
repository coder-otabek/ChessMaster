import json
from datetime import timedelta
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        self.partner_username = self.scope['url_route']['kwargs']['username']
        users = sorted([self.user.username, self.partner_username])
        self.room = f"chat_{'_'.join(users)}"
        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()
        await self.set_online(True)

        count = await self.mark_partner_messages_read()
        if count > 0:
            await self.channel_layer.group_send(self.room, {
                'type':   'read_receipt',
                'reader': self.user.username,
            })

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)
        await self.set_online(False)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return

        if data.get('type') == 'seen':
            count = await self.mark_partner_messages_read()
            if count > 0:
                await self.channel_layer.group_send(self.room, {
                    'type':   'read_receipt',
                    'reader': self.user.username,
                })
            return

        msg = data.get('message', '').strip()[:1000]
        if not msg:
            return
        saved = await self.save_message(msg)
        await self.channel_layer.group_send(self.room, {
            'type':     'chat_message',
            'username': self.user.username,
            'message':  msg,
            'msg_id':   saved,
        })
        await self.channel_layer.group_send(
            f"notify_{self.partner_username}",
            {
                'type':      'new_message',
                'from_user': self.user.username,
                'message':   msg[:60],
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type':     'chat',
            'username': event['username'],
            'message':  event['message'],
            'msg_id':   event.get('msg_id'),
        }))
        if event['username'] != self.user.username:
            import asyncio
            await asyncio.sleep(0.1)
            count = await self.mark_partner_messages_read()
            if count > 0:
                await self.channel_layer.group_send(self.room, {
                    'type':   'read_receipt',
                    'reader': self.user.username,
                })

    async def read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type':   'read_receipt',
            'reader': event['reader'],
        }))

    @database_sync_to_async
    def mark_partner_messages_read(self):
        from django.contrib.auth.models import User
        from chat.models import Message
        try:
            partner = User.objects.get(username=self.partner_username)
            count = Message.objects.filter(
                sender=partner, receiver=self.user, is_read=False
            ).count()
            if count:
                Message.objects.filter(
                    sender=partner, receiver=self.user, is_read=False
                ).update(is_read=True)
            return count
        except Exception:
            return 0

    @database_sync_to_async
    def set_online(self, status):
        try:
            p = self.user.profile
            p.last_seen = timezone.now() if status else timezone.now() - timedelta(minutes=10)
            p.save(update_fields=['last_seen'])
        except Exception:
            pass

    @database_sync_to_async
    def save_message(self, content):
        from django.contrib.auth.models import User
        from chat.models import Message
        try:
            partner = User.objects.get(username=self.partner_username)
            msg = Message.objects.create(
                sender=self.user,
                receiver=partner,
                content=content
            )
            return msg.id
        except Exception:
            return None


class NotifyConsumer(AsyncWebsocketConsumer):
    # Global group — barcha online foydalanuvchilar
    ONLINE_GROUP = 'online_users'

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        self.room = f"notify_{self.user.username}"
        await self.channel_layer.group_add(self.room, self.channel_name)
        # Global online group ga qo'shilish
        await self.channel_layer.group_add(self.ONLINE_GROUP, self.channel_name)
        await self.accept()
        await self.set_online(True)
        # Barcha online foydalanuvchilarga: men online bo'ldim
        await self.channel_layer.group_send(self.ONLINE_GROUP, {
            'type':     'user_status',
            'username': self.user.username,
            'online':   True,
        })

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.room, self.channel_name)
        await self.channel_layer.group_discard(self.ONLINE_GROUP, self.channel_name)
        await self.set_online(False)
        # Barcha online foydalanuvchilarga: men offline bo'ldim
        await self.channel_layer.group_send(self.ONLINE_GROUP, {
            'type':     'user_status',
            'username': self.user.username,
            'online':   False,
        })

    async def new_message(self, event):
        count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type':      'new_message',
            'from_user': event['from_user'],
            'message':   event['message'],
            'unread':    count,
        }))

    async def user_status(self, event):
        """Foydalanuvchi online/offline bo'lganda barcha online userlarga yuboriladi."""
        await self.send(text_data=json.dumps({
            'type':     'user_status',
            'username': event['username'],
            'online':   event['online'],
        }))

    @database_sync_to_async
    def set_online(self, status):
        try:
            p = self.user.profile
            p.last_seen = timezone.now() if status else timezone.now() - timedelta(minutes=10)
            p.save(update_fields=['last_seen'])
        except Exception:
            pass

    @database_sync_to_async
    def get_unread_count(self):
        from chat.models import Message
        try:
            return Message.objects.filter(
                receiver=self.user, is_read=False
            ).count()
        except Exception:
            return 0
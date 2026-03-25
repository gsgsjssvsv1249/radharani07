import asyncio
import os
import json
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import UserStatusOnline, UserStatusOffline

# Credentials (set these as environment variables in hosting service)
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))  # your Telegram numeric ID

DATA_FILE = 'user_status.json'
SESSION_FILE = 'bot_session'
IST = timezone(timedelta(hours=5, minutes=30))

class TelegramStatusMonitor:
    def __init__(self, client):
        self.client = client
        self.monitored_users = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                self.monitored_users = json.load(f)

    def save_data(self):
        with open(DATA_FILE, 'w') as f:
            json.dump(self.monitored_users, f, indent=2)

    async def add_user(self, username_or_id):
        entity = await self.client.get_entity(username_or_id)
        user_id = entity.id
        self.monitored_users[str(user_id)] = {
            'username': entity.username or '',
            'first_name': entity.first_name or '',
            'status_history': []
        }
        self.save_data()
        await self.client.send_message(OWNER_ID, f"✅ Added {entity.first_name or 'User'} (@{entity.username or user_id}) to monitoring")

    async def get_user_status(self, user_id):
        full_user = await self.client(GetFullUserRequest(user_id))
        user = full_user.users[0]
        status = user.status
        if isinstance(status, UserStatusOnline):
            return {'online': True, 'status_type': 'online'}
        elif isinstance(status, UserStatusOffline):
            return {
                'online': False,
                'status_type': 'offline',
                'was_online': status.was_online.astimezone(IST).isoformat() if status.was_online else None
            }
        else:
            return {'online': False, 'status_type': str(type(status))}

    async def check_all_users(self):
        for user_id_str, user_data in self.monitored_users.items():
            user_id = int(user_id_str)
            status = await self.get_user_status(user_id)
            if status:
                last_status = user_data.get('current_status', {})
                if status['online'] and not last_status.get('online', False):
                    await self.client.send_message(OWNER_ID, f"🟢 {user_data['first_name']} IS NOW ONLINE!")
                    user_data['online_start'] = datetime.now(IST).isoformat()
                elif not status['online'] and last_status.get('online', False):
                    offline_time = datetime.now(IST)
                    duration_str = None
                    if 'online_start' in user_data:
                        online_start = datetime.fromisoformat(user_data['online_start'])
                        duration = offline_time - online_start
                        hours, remainder = divmod(duration.seconds, 3600)
                        minutes, _ = divmod(remainder, 60)
                        duration_str = f"{hours}h {minutes}m"
                    msg = f"🔴 {user_data['first_name']} WENT OFFLINE"
                    if duration_str:
                        msg += f"\n   📊 Was online for: {duration_str}"
                    await self.client.send_message(OWNER_ID, msg)
                    user_data.pop('online_start', None)
                user_data['current_status'] = status
                self.save_data()

    async def background_monitor(self, check_interval=30):
        while True:
            await self.check_all_users()
            await asyncio.sleep(check_interval)

async def main():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    monitor = TelegramStatusMonitor(client)
    asyncio.create_task(monitor.background_monitor(check_interval=30))
    await client.send_message(OWNER_ID, "🚀 Bot started. Monitoring users 24/7.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())

"""
python manage.py ai_cleanup                 # purge deleted chats + chats idle > 365 days
python manage.py ai_cleanup --days 180
python manage.py ai_cleanup --usage-days 365  # also drop AIUsage rows older than this

Run weekly from cron. Deleted chats are removed for good; idle chats too.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from TaxBuddyApp.models import AIConversation, AIUsage


class Command(BaseCommand):
    help = "Delete removed / old TaxBuddy Umair AI chats"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=365, help="delete chats idle longer than this")
        parser.add_argument("--usage-days", type=int, default=0, help="also delete AIUsage older than this (0 = keep)")

    def handle(self, *args, **o):
        cutoff = timezone.now() - timedelta(days=o["days"])
        n1, _ = AIConversation.objects.filter(is_deleted=True).delete()
        n2, _ = AIConversation.objects.filter(updated__lt=cutoff).delete()
        msg = f"Removed deleted chats ({n1} rows) and idle chats ({n2} rows)."
        if o["usage_days"]:
            n3, _ = AIUsage.objects.filter(created__lt=timezone.now() - timedelta(days=o["usage_days"])).delete()
            msg += f" Removed {n3} usage rows."
        self.stdout.write(msg)

"""
python manage.py ai_usage            # last 7 days
python manage.py ai_usage --days 30

Daily TaxBuddy Umair AI usage: answers, errors, tokens, cost, average speed, top tools.
"""
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from TaxBuddyApp.models import AIUsage


class Command(BaseCommand):
    help = "Show TaxBuddy Umair AI usage and cost per day"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    def handle(self, *args, **opts):
        since = timezone.now() - timedelta(days=opts["days"])
        qs = AIUsage.objects.filter(created__gte=since)
        rows = (qs.annotate(day=TruncDate("created")).values("day")
                  .annotate(n=Count("id"), err=Count("id", filter=~Q(status="ok")),
                            inp=Sum("input_tokens"), out=Sum("output_tokens"),
                            cr=Sum("cache_read_tokens"), cw=Sum("cache_write_tokens"),
                            usd=Sum("cost_usd"), ms=Avg("latency_ms"))
                  .order_by("day"))
        self.stdout.write(f"{'Day':<12}{'Answers':>8}{'Errors':>8}{'Input':>10}{'Output':>9}"
                          f"{'CacheRd':>10}{'USD':>10}{'Avg s':>7}")
        for r in rows:
            self.stdout.write(f"{str(r['day']):<12}{r['n']:>8}{r['err']:>8}{r['inp'] or 0:>10}"
                              f"{r['out'] or 0:>9}{r['cr'] or 0:>10}{float(r['usd'] or 0):>10.4f}"
                              f"{(r['ms'] or 0) / 1000:>7.1f}")
        tot = qs.aggregate(n=Count("id"), usd=Sum("cost_usd"))
        self.stdout.write(f"\nTotal: {tot['n']} answers, ${float(tot['usd'] or 0):.4f}")
        tools = Counter(t for s in qs.values_list("tools", flat=True) for t in s.split(",") if t)
        if tools:
            self.stdout.write("Top tools: " + ", ".join(f"{k} ({v})" for k, v in tools.most_common(8)))
        if not float(tot["usd"] or 0) and tot["n"]:
            self.stdout.write("Cost is 0: set AI_PRICE_INPUT_PER_MTOK / AI_PRICE_OUTPUT_PER_MTOK in .env")

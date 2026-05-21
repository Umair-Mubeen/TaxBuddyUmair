# ══════════════════════════════════════════════════════════════
# 1. models.py — Add this model
# ══════════════════════════════════════════════════════════════

class ATLRecord(models.Model):
    ntn         = models.CharField(max_length=20, db_index=True)
    name        = models.CharField(max_length=300, blank=True)
    business_name = models.CharField(max_length=300, blank=True)
    tax_year    = models.CharField(max_length=10, default='2025')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ntn']
        verbose_name = 'ATL Record'
        indexes = [
            models.Index(fields=['ntn']),
        ]

    def __str__(self):
        return f"{self.ntn} — {self.name}"

    @property
    def is_cnic(self):
        """NTN with 13 digits = individual CNIC"""
        return len(str(self.ntn).replace('-', '')) == 13

    @property
    def display_name(self):
        return self.business_name or self.name or 'N/A'


# ══════════════════════════════════════════════════════════════
# 2. management/commands/update_atl.py
#    Path: TaxBuddyApp/management/commands/update_atl.py
#    Run: python manage.py update_atl
# ══════════════════════════════════════════════════════════════

import requests
import openpyxl
from io import BytesIO
from django.core.management.base import BaseCommand
from TaxBuddyApp.models import ATLRecord
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Download and update ATL from FBR'

    def handle(self, *args, **kwargs):
        self.stdout.write('Downloading ATL from FBR...')

        ATL_URL = 'https://www.fbr.gov.pk/download-atl/132041'

        try:
            response = requests.get(
                ATL_URL,
                timeout=120,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            response.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Download failed: {e}'))
            return

        try:
            wb = openpyxl.load_workbook(BytesIO(response.content), read_only=True)
            ws = wb.active
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Excel parse failed: {e}'))
            return

        self.stdout.write('Clearing old records...')
        ATLRecord.objects.all().delete()

        batch = []
        count = 0

        for row in ws.iter_rows(min_row=2, values_only=True):
            # Columns: S#, NTN, Name, Business Name
            if not row or not row[1]:
                continue

            ntn           = str(row[1]).strip().replace('-', '').replace(' ', '')
            name          = str(row[2] or '').strip()
            business_name = str(row[3] or '').strip()

            if not ntn or ntn in ('None', 'NTN', ''):
                continue

            batch.append(ATLRecord(
                ntn=ntn,
                name=name,
                business_name=business_name,
                tax_year='2025',
            ))
            count += 1

            # Bulk insert every 5000 records
            if len(batch) >= 5000:
                ATLRecord.objects.bulk_create(batch, ignore_conflicts=True)
                batch = []
                self.stdout.write(f'  Imported {count} records...')

        # Insert remaining
        if batch:
            ATLRecord.objects.bulk_create(batch, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f'✓ ATL updated successfully — {count} records imported'
        ))


# ══════════════════════════════════════════════════════════════
# 3. views.py — Add this view
# ══════════════════════════════════════════════════════════════

from django.db.models import Q

def atl_check_view(request):
    """Render ATL check page"""
    return render(request, 'atl-check.html', {
        'atl_total': ATLRecord.objects.count(),
        'atl_updated': ATLRecord.objects.order_by('-updated_at').first(),
    })


def atl_search_api(request):
    """AJAX API — search ATL by CNIC or NTN"""
    from django.http import JsonResponse

    query = request.GET.get('q', '').strip().replace('-', '').replace(' ', '')

    if not query:
        return JsonResponse({'found': False, 'error': 'Please enter CNIC or NTN'})

    if len(query) < 7:
        return JsonResponse({'found': False, 'error': 'Enter at least 7 digits'})

    # Search DB
    record = ATLRecord.objects.filter(ntn__icontains=query).first()

    if record:
        return JsonResponse({
            'found': True,
            'status': 'Active Filer ✅',
            'ntn': record.ntn,
            'name': record.display_name,
            'tax_year': record.tax_year,
            'message': f'{record.display_name} is an Active Filer on FBR ATL {record.tax_year}',
        })
    else:
        return JsonResponse({
            'found': False,
            'status': 'Not Found ❌',
            'message': f'No record found for {query} in ATL. This person may be a Non-Filer or the ATL may not be updated yet.',
        })

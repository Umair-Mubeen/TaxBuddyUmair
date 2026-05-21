import os
import time
import glob
import openpyxl
from io import BytesIO
from django.core.management.base import BaseCommand
from TaxBuddyApp.models import ATLRecord


class Command(BaseCommand):
    help = 'Auto-download and import ATL from FBR website'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to local ATL file (skip download)',
        )

    def handle(self, *args, **kwargs):
        file_path = kwargs.get('file')

        # ── Option 1: Local file provided ────────────────────
        if file_path:
            self.stdout.write(f'📂 Loading: {file_path}')
            with open(file_path, 'rb') as f:
                data = f.read()
            self.import_data(data)
            return

        # ── Option 2: Auto download via Selenium ─────────────
        self.stdout.write('🌐 Starting auto-download from FBR...')

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
        except ImportError:
            self.stdout.write(self.style.ERROR(
                '✗ Selenium not installed.\n'
                'Run: pip install selenium\n'
                'Also install ChromeDriver: pip install webdriver-manager'
            ))
            return

        # Download folder
        download_dir = os.path.join(os.path.expanduser('~'), 'atl_downloads')
        os.makedirs(download_dir, exist_ok=True)

        # Chrome options
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_experimental_option('prefs', {
            'download.default_directory': download_dir,
            'download.prompt_for_download': False,
            'download.directory_upgrade': True,
            'safebrowsing.enabled': True,
        })

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ ChromeDriver error: {e}'))
            return

        try:
            self.stdout.write('📄 Opening FBR ATL page...')
            driver.get('https://www.fbr.gov.pk/download-atl/132041')
            time.sleep(3)

            # Click the ATL download link
            wait = WebDriverWait(driver, 15)
            try:
                # Find the "Active Taxpayer List (Income Tax)" link
                link = wait.until(EC.element_to_be_clickable(
                    (By.PARTIAL_LINK_TEXT, 'Active Taxpayer List (Income Tax)')
                ))
                self.stdout.write('✓ Found ATL download link')
                link.click()
                self.stdout.write('⏳ Downloading... (waiting 30 seconds)')
                time.sleep(30)

            except Exception as e:
                # Try direct URL from status bar
                self.stdout.write(f'  Link click failed: {e}')
                self.stdout.write('  Trying direct URL...')
                driver.get('https://www.fbr.gov.pk/Downloads/?id=3901&Type=Docs')
                time.sleep(30)

        finally:
            driver.quit()

        # Find downloaded file
        files = sorted(
            glob.glob(os.path.join(download_dir, '*.*')),
            key=os.path.getmtime,
            reverse=True
        )

        if not files:
            self.stdout.write(self.style.ERROR(
                f'✗ No file downloaded in {download_dir}\n'
                f'Manual option:\n'
                f'  1. Download ATL from fbr.gov.pk/download-atl/132041\n'
                f'  2. Run: python manage.py update_atl --file /path/to/atl.xlsx'
            ))
            return

        latest = files[0]
        self.stdout.write(f'✓ File found: {latest}')

        with open(latest, 'rb') as f:
            data = f.read()

        self.import_data(data)

        # Cleanup
        os.remove(latest)

    def import_data(self, data):
        """Parse Excel/XLS/CSV and import to DB"""
        self.stdout.write('📊 Parsing file...')
        rows = []

        # Try XLSX
        try:
            wb = openpyxl.load_workbook(BytesIO(data), read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            self.stdout.write('✓ XLSX format')
        except Exception:
            pass

        # Try XLS
        if not rows:
            try:
                import xlrd
                wb = xlrd.open_workbook(file_contents=data)
                ws = wb.sheet_by_index(0)
                rows = [ws.row_values(i) for i in range(1, ws.nrows)]
                self.stdout.write('✓ XLS format')
            except Exception:
                pass

        # Try CSV
        if not rows:
            try:
                import csv, io
                text = data.decode('utf-8', errors='ignore')
                reader = csv.reader(io.StringIO(text))
                rows = list(reader)[1:]
                self.stdout.write('✓ CSV format')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Cannot parse: {e}'))
                return

        if not rows:
            self.stdout.write(self.style.ERROR('✗ No data found in file'))
            return

        self.stdout.write(f'📋 Total rows: {len(rows):,}')
        self.stdout.write('🗑️  Clearing old records...')
        ATLRecord.objects.all().delete()

        batch = []
        count = 0
        skipped = 0

        for row in rows:
            if not row or not row[1]:
                skipped += 1
                continue

            ntn           = str(row[1]).strip().replace('-', '').replace(' ', '')
            name          = str(row[2] or '').strip() if len(row) > 2 else ''
            business_name = str(row[3] or '').strip() if len(row) > 3 else ''

            if not ntn or ntn.lower() in ('none', 'ntn', ''):
                skipped += 1
                continue

            batch.append(ATLRecord(
                ntn=ntn,
                name=name,
                business_name=business_name,
                tax_year='2025',
            ))
            count += 1

            if len(batch) >= 5000:
                ATLRecord.objects.bulk_create(batch, ignore_conflicts=True)
                batch = []
                self.stdout.write(f'  ↳ Imported {count:,} records...')

        if batch:
            ATLRecord.objects.bulk_create(batch, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ ATL updated!\n'
            f'   Imported : {count:,}\n'
            f'   Skipped  : {skipped:,}'
        ))
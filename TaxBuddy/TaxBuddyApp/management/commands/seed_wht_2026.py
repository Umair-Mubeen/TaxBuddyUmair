# ══════════════════════════════════════════════════════════════
# SEED COMMAND — TaxBuddyApp/management/commands/seed_wht_2026.py
#
# Populates the EXISTING WithholdingTaxRate model (model #284, the one
# your rate-card page + homepage cards + admin already use) with all
# verified TY2026-27 rates.
#
# Setup (one-time):
#   mkdir -p TaxBuddyApp/management/commands
#   touch TaxBuddyApp/management/__init__.py
#   touch TaxBuddyApp/management/commands/__init__.py
#   # place this file at: TaxBuddyApp/management/commands/seed_wht_2026.py
#
# Run:
#   python manage.py seed_wht_2026
#   # (idempotent — safe to re-run; updates existing 2026-2027 rows by section+description)
#
# NOTE:
#   • section is stored as "Section 236C" so homepage cards
#     (section__iexact='Section 236C') match.
#   • late_filer_rate left blank (abolished for 2026-2027).
#   • 2025-2026 rows are NOT touched — history preserved.
#   • All rates verified against KPMG TY2027 card + Income Tax
#     Ordinance (amended to 30 June 2026). 154A flagged [VERIFY].
# ══════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand
from TaxBuddyApp.models import WithholdingTaxRate

YEAR = '2026-2027'

# (category, section, description, filer, non_filer, who_deducts, threshold)
ROWS = [
    # ---------- PROPERTY ----------
    ('property', 'Section 236C', 'Sale / transfer of immovable property', '2.75%', '11.5%', 'Registrar / transferring authority', 'On gross consideration'),
    ('property', 'Section 236K', 'Purchase of immovable property (FMV up to Rs 50M)', '1.25%', '10.5%', 'Registrar / transferring authority', 'FMV up to Rs 50 million'),
    ('property', 'Section 236K', 'Purchase of immovable property (FMV Rs 50M–100M)', '1.25%', '14.5%', 'Registrar / transferring authority', 'FMV Rs 50M–100M'),
    ('property', 'Section 236K', 'Purchase of immovable property (FMV above Rs 100M)', '1.25%', '18.5%', 'Registrar / transferring authority', 'FMV above Rs 100 million'),

    # ---------- BANKING ----------
    ('banking', 'Section 151', 'Profit on bank deposits & savings accounts', '20%', '40%', 'Bank', 'Final tax; Normal Tax Regime if profit exceeds Rs 5M'),
    ('banking', 'Section 151', 'National Savings & Post Office schemes', '15%', '30%', 'National Savings / Post Office', 'Final tax; Normal Tax Regime if profit exceeds Rs 5M'),
    ('banking', 'Section 151', 'Government securities (individual)', '15%', '30%', 'Paying agent', 'Final tax; Normal Tax Regime if profit exceeds Rs 5M'),
    ('banking', 'Section 151', 'Government securities (company / AOP)', '20%', '40%', 'Paying agent', 'Adjustable for company'),
    ('banking', 'Section 151(1A)', 'Sukuk return — company', '25%', '50%', 'SPV / company', 'Final tax'),
    ('banking', 'Section 151(1A)', 'Sukuk return — individual/AOP (return over Rs 1M)', '12.5%', '25%', 'SPV / company', 'Final tax'),
    ('banking', 'Section 151(1A)', 'Sukuk return — individual/AOP (return under Rs 1M)', '10%', '20%', 'SPV / company', 'Final tax'),
    ('banking', 'Section 151A', 'Capital gain on debt securities', '20%', '40%', 'Custodian', 'On the gain'),
    ('banking', 'Section 151B', 'Life insurance / takaful payout (within 1 year)', '15%', '30%', 'Insurance company', '1–4 yrs: 10% / 20%'),
    ('banking', 'Section 231AB', 'Cash withdrawal from bank', '0%', '0.8%', 'Bank', 'Exceeding Rs 50,000 per day'),
    ('banking', 'Section 236Y', 'Foreign card payments (debit/credit/prepaid)', '0.5%', '1%', 'Bank', 'International card transactions'),

    # ---------- DIVIDENDS ----------
    ('other', 'Section 150', 'Dividend — general (most companies)', '15%', '30%', 'Payer of dividend', 'Final tax'),
    ('other', 'Section 150', 'Dividend — Independent Power Producers (pass-through)', '7.5%', '15%', 'Payer of dividend', 'Final tax'),
    ('other', 'Section 150', 'Dividend — company with no tax payable (exemption/losses/credit)', '25%', '50%', 'Payer of dividend', 'Final tax'),
    ('other', 'Section 150', 'Dividend — Real Estate Investment Trust (REIT)', '15%', '30%', 'Payer of dividend', 'Final tax'),

    # ---------- SALARY ----------
    ('salary', 'Section 149', 'Salary — tax deducted by employer', 'Per salary slab (0%–35%)', 'Same slab (no non-filer surcharge)', 'Employer', 'Annual tax spread over 12 months'),

    # ---------- PROPERTY RENT (155) ----------
    ('other', 'Section 155', 'Property rent — up to Rs 300,000', '0%', '—', 'Tenant / prescribed person', 'Annual rent'),
    ('other', 'Section 155', 'Property rent — Rs 300,000–600,000', '5%', '—', 'Tenant / prescribed person', 'Of amount over 300,000'),
    ('other', 'Section 155', 'Property rent — Rs 600,000–2,000,000', 'Rs 15,000 + 10%', '—', 'Tenant / prescribed person', 'Of amount over 600,000'),
    ('other', 'Section 155', 'Property rent — above Rs 2,000,000', 'Rs 155,000 + 25%', '—', 'Tenant / prescribed person', 'Of amount over 2,000,000'),
    ('other', 'Section 155', 'Property rent — company', '15%', '30%', 'Tenant / prescribed person', 'On annual rent, flat'),

    # ---------- CONTRACTS / SERVICES (153) ----------
    ('business', 'Section 153(1)(a)', 'Sale of rice / cotton seed / edible oil', '1.5%', '3%', 'Prescribed person', 'Minimum / adjustable'),
    ('business', 'Section 153', 'Distributors of cigarettes', '2.5%', '5%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153', 'Distributors — pharmaceutical products', '1%', '2%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153', 'FMCG distributors/dealers/wholesalers (on ATL)', '0.25%', '—', 'Prescribed person', 'Minimum tax (if on ATL)'),
    ('business', 'Section 153', 'Sale of gold, silver & articles thereof', '1%', '2%', 'Prescribed person', 'Adjustable'),
    ('business', 'Section 153(1)(a)', 'Other goods — company (excl. toll mfg)', '5%', '10%', 'Prescribed person', 'Minimum for mfr/listed'),
    ('business', 'Section 153(1)(a)', 'Other goods — company (toll manufacturing)', '9%', '18%', 'Prescribed person', 'Minimum for mfr/listed'),
    ('business', 'Section 153(1)(a)', 'Other goods — other taxpayers (excl. toll mfg)', '5.5%', '11%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(a)', 'Other goods — other taxpayers (toll mfg)', '11%', '22%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'Transport / freight forwarding / air cargo / courier', '4%', '8%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'Manpower/hotel/security/software/tracking/advertising/warehousing services', '7%', '14%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'Engineering/inspection/testing/oilfield/telecom/travel/REIT-mgmt services', '7%', '14%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'IT & IT-enabled services (as defined in s.2)', '4%', '8%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'Oil tanker contractor services', '2%', '4%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'Independent professionals (lawyers/accountants/engineers)', '15%', '30% (individual) / N/A for AOP', 'Prescribed person', 'Minimum for individual'),
    ('business', 'Section 153(1)(b)', 'Companies operating terminal / port operating services', '12%', '24%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'Other services — company', '14%', '28%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(b)', 'Electronic/print media advertisement services', '1.5%', '3%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(c)', 'Execution of contract — company', '7.5%', '15%', 'Prescribed person', 'Minimum (adjustable for listed)'),
    ('business', 'Section 153(1)(c)', 'Execution of contract — other taxpayers', '8%', '16%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(1)(c)', 'Execution of contract — sportsperson', '15%', '30%', 'Prescribed person', 'Minimum tax'),
    ('business', 'Section 153(2A)', 'E-commerce (digital/banking payment)', '1%', '2%', 'Payment intermediary', 'Adjustable / final'),
    ('business', 'Section 153', 'Export house — services for rendering of certain services', '1%', '2%', 'Prescribed person', 'Minimum tax'),

    # ---------- IMPORTS / EXPORTS ----------
    ('advance', 'Section 148', 'Import — goods in Part I, Twelfth Schedule', '1%', '2%', 'Customs', 'Minimum (varies for industrial own-use)'),
    ('advance', 'Section 148', 'Import — goods in Part II, Twelfth Schedule', '2%', '4%', 'Customs', 'Minimum (varies for industrial own-use)'),
    ('advance', 'Section 154', 'Export of goods (on realization of proceeds)', '1.25%', '1.25%', 'Authorized dealer (bank)', 'Minimum tax'),
    ('advance', 'Section 154', 'Sale of goods to an exporter (inland back-to-back)', '1.25%', '1.25%', 'Banking company', 'Minimum tax'),
    ('advance', 'Section 154A', 'Export of IT / IT-enabled services (foreign remittance) [VERIFY]', '0.25%', '0.25%', 'Authorized dealer (bank)', 'Final (reduced rate, conditions)'),
    ('advance', 'Section 152(2A)', 'Payments to PE of non-resident — sale of goods (company)', '5%', '10%', 'Payer', 'Minimum, subject to conditions'),

    # ---------- VEHICLES: 234 token ----------
    ('advance', 'Section 234', 'Motor vehicle token — up to 1,000 CC', 'Rs 800', 'Rs 10,000', 'Excise & taxation', 'Annual, by engine capacity'),
    ('advance', 'Section 234', 'Motor vehicle token — 1,001–1,199 CC', 'Rs 1,500', 'Rs 18,000', 'Excise & taxation', 'Annual, by engine capacity'),
    ('advance', 'Section 234', 'Motor vehicle token — 1,200–1,299 CC', 'Rs 1,750', 'Rs 20,000', 'Excise & taxation', 'Annual, by engine capacity'),
    ('advance', 'Section 234', 'Motor vehicle token — 1,300–1,499 CC', 'Rs 2,500', 'Rs 30,000', 'Excise & taxation', 'Annual, by engine capacity'),
    ('advance', 'Section 234', 'Motor vehicle token — 1,500–1,599 CC', 'Rs 3,750', 'Rs 45,000', 'Excise & taxation', 'Annual, by engine capacity'),
    ('advance', 'Section 234', 'Motor vehicle token — 1,600–1,999 CC', 'Rs 4,500', 'Rs 60,000', 'Excise & taxation', 'Annual, by engine capacity'),
    ('advance', 'Section 234', 'Motor vehicle token — above 2,000 CC', 'Rs 10,000', 'Rs 120,000', 'Excise & taxation', 'Annual, by engine capacity'),

    # ---------- VEHICLES: 231B registration (% of value) ----------
    ('advance', 'Section 231B', 'Vehicle registration — up to 850 CC', '0.5%', '1.5%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — 851–1,000 CC', '1%', '3%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — 1,001–1,300 CC', '1.5%', '4.5%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — 1,301–1,600 CC', '2%', '6%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — 1,601–1,800 CC', '3%', '9%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — 1,801–2,000 CC', '5%', '15%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — 2,001–2,500 CC', '7%', '21%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — 2,501–3,000 CC', '9%', '27%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle registration — above 3,000 CC', '12%', '36%', 'Registration authority', '% of vehicle value'),
    ('advance', 'Section 231B', 'Vehicle leasing to a non-ATL person', '4%', '4%', 'Leasing co / bank / NBFC', 'On lease amount'),

    # ---------- UTILITIES: 235 electricity, 236 phone ----------
    ('advance', 'Section 235', 'Electricity bill — up to Rs 500', 'Nil', 'Nil', 'Electricity supplier', 'Commercial / industrial'),
    ('advance', 'Section 235', 'Electricity bill — Rs 500–20,000', '10%', '10%', 'Electricity supplier', 'Of the bill amount'),
    ('advance', 'Section 235', 'Electricity bill — above Rs 20,000 (commercial)', 'Rs 1,950 + 12%', 'Rs 1,950 + 12%', 'Electricity supplier', 'Of amount over Rs 20,000'),
    ('advance', 'Section 235', 'Electricity bill — above Rs 20,000 (industrial)', 'Rs 1,950 + 5%', 'Rs 1,950 + 5%', 'Electricity supplier', 'Of amount over Rs 20,000'),
    ('advance', 'Section 235', 'Electricity — domestic (non-ATL), bill over Rs 25,000', '—', '7.5%', 'Electricity supplier', 'Only if not on ATL'),
    ('advance', 'Section 236', 'Telephone bill over Rs 1,000', '10%', '10%', 'Telephone company', 'On amount over Rs 1,000'),
    ('advance', 'Section 236', 'Internet / prepaid card / units', '15%', '15%', 'ISP / card issuer', 'On the amount'),
    ('advance', 'Section 236', 'Internet/prepaid — non-filer (u/s 114B)', '—', '75%', 'ISP / card issuer', 'For persons in FBR general order'),
    ('advance', 'Section 236', 'Mobile phone / prepaid card / units', '15%', '15%', 'Mobile operator', 'On the amount'),

    # ---------- OTHER ----------
    ('other', 'Section 236CB', 'Functions & gatherings', '10%', '10%', 'Function/event arranger', 'On total bill'),
    ('other', 'Section 156', 'Prize bond winnings', '15%', '30%', 'Payer', 'On gross winning'),
    ('other', 'Section 156A', 'Petroleum products — commission to petrol pump operators', '12%', '24%', 'Oil marketing company', 'Final tax'),
    ('other', 'Section 233', 'Brokerage & commission — advertising agents', '10%', '20%', 'The principal', 'Minimum tax'),
    ('other', 'Section 233', 'Brokerage & commission — life insurance agent (comm. < Rs 0.5M/yr)', '8%', '16%', 'The principal', 'Minimum tax'),
    ('other', 'Section 233', 'Brokerage & commission — others', '12%', '24%', 'The principal', 'Minimum tax'),
    ('other', 'Section 236A', 'Sale by auction (goods/property)', '10%', '20%', 'Auction authority', 'On auction value'),
    ('other', 'Section 236A', 'Auction of immovable property', '5%', '10%', 'Auction authority', 'On auction value'),
    ('other', 'Section 236G', 'Sales to distributors — fertilizer', '0.7%', '1.4%', 'Manufacturer / commercial importer', 'On sales amount'),
    ('other', 'Section 236G', 'Sales to distributors — other than fertilizer', '0.1%', '2%', 'Manufacturer / commercial importer', 'On sales amount'),
    ('other', 'Section 236H', 'Sales to retailers', '0.5%', '2.5%', 'Manufacturer / distributor', 'On sales amount'),
    ('other', 'Section 236H', 'Sales to wholesalers', '0.5%', '1%', 'Manufacturer / distributor', 'On sales amount'),
    ('other', 'Section 231C', 'Foreign domestic workers — visa issuance/renewal', 'Rs 200,000', 'Rs 400,000', 'Visa-issuing authority', 'Per visa (agency/sponsor)'),
    ('other', 'Section 236Z', 'Bonus shares issued (value)', '10%', '10%', 'Company issuing bonus shares', 'Final tax'),
]


class Command(BaseCommand):
    help = 'Seed verified TY2026-27 withholding tax rates into WithholdingTaxRate'

    def handle(self, *args, **opts):
        created, updated = 0, 0
        for i, (cat, sec, desc, filer, nonf, deducts, thr) in enumerate(ROWS):
            obj, was_created = WithholdingTaxRate.objects.update_or_create(
                tax_year=YEAR,
                section=sec,
                description=desc,
                defaults=dict(
                    category=cat,
                    filer_rate=filer,
                    late_filer_rate='',       # abolished for 2026-2027
                    non_filer_rate=nonf,
                    who_deducts=deducts,
                    threshold=thr,
                    order=i,
                    is_active=True,
                ),
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'WHT {YEAR}: {created} created, {updated} updated, {len(ROWS)} total.'
        ))

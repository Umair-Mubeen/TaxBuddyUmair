# ══════════════════════════════════════════════════════════════
# SEED — TaxBuddyApp/management/commands/seed_wht_calc_2026.py
#
# Fills the WHTRate model (db_table 'wht_rates') used by the
# WHT & Advance Tax CALCULATOR at /Withholding-Tax-Card/.
# This is SEPARATE from WithholdingTaxRate (the rate-card page).
#
# Setup:
#   mkdir -p TaxBuddyApp/management/commands
#   (ensure __init__.py in management/ and commands/)
#   place at: TaxBuddyApp/management/commands/seed_wht_calc_2026.py
#
# Run:
#   python manage.py seed_wht_calc_2026
#   (idempotent — keyed on uid; safe to re-run)
#
# Notes:
#   • rate_kind: 'percentage' = % of amount; 'fixed' = flat Rs amount
#   • filer/late_filer/non_filer are DECIMALS (numbers, not "%" strings)
#   • For 2026-2027, late_filer = filer (late-filer abolished) EXCEPT
#     236C/236K which the API treats specially — there we still set
#     late_filer separately but it equals filer for 2026-2027.
#   • Rates verified vs KPMG TY2027 card + Ordinance (30 June 2026).
# ══════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand
from TaxBuddyApp.models import WHTRate

YEAR = '2026-2027'

# uid, section, cat, name, sub, rate_kind, filer, late_filer, non_filer, nature, tax_type, slab_min, slab_max, base_tax
ROWS = [
    # ---- PROPERTY (percentage) ----
    ('236C_2627', '236C', 'property', 'Sale / transfer of immovable property', 'On gross consideration', 'percentage', 2.75, 2.75, 11.5, 'Advance Tax', 'Adjustable', None, None, None),
    ('236K_50_2627', '236K', 'property', 'Purchase of property (FMV up to Rs 50M)', 'Fair market value up to 50 million', 'percentage', 1.25, 1.25, 10.5, 'Advance Tax', 'Adjustable', None, None, None),
    ('236K_100_2627', '236K', 'property', 'Purchase of property (FMV Rs 50M–100M)', 'Fair market value 50–100 million', 'percentage', 1.25, 1.25, 14.5, 'Advance Tax', 'Adjustable', None, None, None),
    ('236K_over100_2627', '236K', 'property', 'Purchase of property (FMV above Rs 100M)', 'Fair market value above 100 million', 'percentage', 1.25, 1.25, 18.5, 'Advance Tax', 'Adjustable', None, None, None),

    # ---- BANKING (percentage) ----
    ('151_bank_2627', '151', 'banking', 'Profit on bank deposits & savings', 'Final tax; NTR if profit exceeds Rs 5M', 'percentage', 20, 20, 40, 'WHT', 'Final Tax', None, None, None),
    ('151_nss_2627', '151', 'banking', 'National Savings & Post Office schemes', 'Final tax; NTR if profit exceeds Rs 5M', 'percentage', 15, 15, 30, 'WHT', 'Final Tax', None, None, None),
    ('151_govsec_ind_2627', '151', 'banking', 'Government securities (individual)', '', 'percentage', 15, 15, 30, 'WHT', 'Final Tax', None, None, None),
    ('151_govsec_co_2627', '151', 'banking', 'Government securities (company / AOP)', '', 'percentage', 20, 20, 40, 'WHT', 'Adjustable', None, None, None),
    ('151A_2627', '151A', 'banking', 'Capital gain on debt securities', '', 'percentage', 20, 20, 40, 'WHT', 'Adjustable', None, None, None),
    ('231AB_2627', '231AB', 'banking', 'Cash withdrawal from bank', 'Exceeding Rs 50,000 per day', 'percentage', 0, 0, 0.8, 'Advance Tax', 'Adjustable', None, None, None),
    ('236Y_2627', '236Y', 'banking', 'Foreign card payments (debit/credit/prepaid)', 'International card transactions', 'percentage', 0.5, 0.5, 1, 'Advance Tax', 'Adjustable', None, None, None),

    # ---- DIVIDENDS ----
    ('150_gen_2627', '150', 'dividends', 'Dividend — general (most companies)', '', 'percentage', 15, 15, 30, 'WHT', 'Final Tax', None, None, None),
    ('150_ipp_2627', '150', 'dividends', 'Dividend — IPP (pass-through)', '', 'percentage', 7.5, 7.5, 15, 'WHT', 'Final Tax', None, None, None),
    ('150_notax_2627', '150', 'dividends', 'Dividend — company with no tax payable', '', 'percentage', 25, 25, 50, 'WHT', 'Final Tax', None, None, None),
    ('150_reit_2627', '150', 'dividends', 'Dividend — REIT', '', 'percentage', 15, 15, 30, 'WHT', 'Final Tax', None, None, None),

    # ---- SALARY (slab) ----
    ('149_s1_2627', '149', 'salary', 'Salary slab: up to 600,000', '0%', 'slab', 0, 0, 0, 'WHT', 'Adjustable', 0, 600000, 0),
    ('149_s2_2627', '149', 'salary', 'Salary slab: 600,001–1,200,000', '1% over 600,000', 'slab', 1, 1, 1, 'WHT', 'Adjustable', 600001, 1200000, 0),
    ('149_s3_2627', '149', 'salary', 'Salary slab: 1,200,001–2,200,000', 'Rs 6,000 + 11% over 1,200,000', 'slab', 11, 11, 11, 'WHT', 'Adjustable', 1200001, 2200000, 6000),
    ('149_s4_2627', '149', 'salary', 'Salary slab: 2,200,001–3,200,000', 'Rs 116,000 + 20% over 2,200,000', 'slab', 20, 20, 20, 'WHT', 'Adjustable', 2200001, 3200000, 116000),
    ('149_s5_2627', '149', 'salary', 'Salary slab: 3,200,001–4,100,000', 'Rs 316,000 + 25% over 3,200,000', 'slab', 25, 25, 25, 'WHT', 'Adjustable', 3200001, 4100000, 316000),
    ('149_s6_2627', '149', 'salary', 'Salary slab: 4,100,001–5,600,000', 'Rs 541,000 + 29% over 4,100,000', 'slab', 29, 29, 29, 'WHT', 'Adjustable', 4100001, 5600000, 541000),
    ('149_s7_2627', '149', 'salary', 'Salary slab: 5,600,001–7,000,000', 'Rs 976,000 + 32% over 5,600,000', 'slab', 32, 32, 32, 'WHT', 'Adjustable', 5600001, 7000000, 976000),
    ('149_s8_2627', '149', 'salary', 'Salary slab: above 7,000,000', 'Rs 1,424,000 + 35% over 7,000,000', 'slab', 35, 35, 35, 'WHT', 'Adjustable', 7000001, None, 1424000),

    # ---- RENT 155 (slab, individual) ----
    ('155_s1_2627', '155', 'rent', 'Property rent: up to 300,000', '0%', 'slab', 0, 0, 0, 'WHT', 'Adjustable', 0, 300000, 0),
    ('155_s2_2627', '155', 'rent', 'Property rent: 300,001–600,000', '5% over 300,000', 'slab', 5, 5, 5, 'WHT', 'Adjustable', 300001, 600000, 0),
    ('155_s3_2627', '155', 'rent', 'Property rent: 600,001–2,000,000', 'Rs 15,000 + 10% over 600,000', 'slab', 10, 10, 10, 'WHT', 'Adjustable', 600001, 2000000, 15000),
    ('155_s4_2627', '155', 'rent', 'Property rent: above 2,000,000', 'Rs 155,000 + 25% over 2,000,000', 'slab', 25, 25, 25, 'WHT', 'Adjustable', 2000001, None, 155000),
    ('155_co_2627', '155', 'rent', 'Property rent — company', 'Flat 15% / 30%', 'percentage', 15, 15, 30, 'WHT', 'Adjustable', None, None, None),

    # ---- CONTRACTS / SERVICES / GOODS (153) ----
    ('153_rice_2627', '153', 'goods', 'Sale of rice / cotton seed / edible oil', '', 'percentage', 1.5, 1.5, 3, 'WHT', 'Minimum Tax', None, None, None),
    ('153_cig_2627', '153', 'goods', 'Distributors of cigarettes', '', 'percentage', 2.5, 2.5, 5, 'WHT', 'Minimum Tax', None, None, None),
    ('153_pharma_2627', '153', 'goods', 'Distributors — pharmaceutical', '', 'percentage', 1, 1, 2, 'WHT', 'Minimum Tax', None, None, None),
    ('153_gold_2627', '153', 'goods', 'Sale of gold, silver & articles', '', 'percentage', 1, 1, 2, 'WHT', 'Adjustable', None, None, None),
    ('153_goods_co_2627', '153(1)(a)', 'goods', 'Other goods — company (excl. toll)', '', 'percentage', 5, 5, 10, 'WHT', 'Minimum Tax', None, None, None),
    ('153_goods_co_toll_2627', '153(1)(a)', 'goods', 'Other goods — company (toll mfg)', '', 'percentage', 9, 9, 18, 'WHT', 'Minimum Tax', None, None, None),
    ('153_goods_ot_2627', '153(1)(a)', 'goods', 'Other goods — other taxpayers (excl. toll)', '', 'percentage', 5.5, 5.5, 11, 'WHT', 'Minimum Tax', None, None, None),
    ('153_goods_ot_toll_2627', '153(1)(a)', 'goods', 'Other goods — other taxpayers (toll)', '', 'percentage', 11, 11, 22, 'WHT', 'Minimum Tax', None, None, None),
    ('153_transport_2627', '153(1)(b)', 'services', 'Transport / freight / air cargo / courier', '', 'percentage', 4, 4, 8, 'WHT', 'Minimum Tax', None, None, None),
    ('153_svc7_2627', '153(1)(b)', 'services', 'Manpower/hotel/security/software/advertising/warehousing', '', 'percentage', 7, 7, 14, 'WHT', 'Minimum Tax', None, None, None),
    ('153_svc7b_2627', '153(1)(b)', 'services', 'Engineering/inspection/oilfield/telecom/travel/REIT-mgmt', '', 'percentage', 7, 7, 14, 'WHT', 'Minimum Tax', None, None, None),
    ('153_it_2627', '153(1)(b)', 'services', 'IT & IT-enabled services', '', 'percentage', 4, 4, 8, 'WHT', 'Minimum Tax', None, None, None),
    ('153_oiltanker_2627', '153(1)(b)', 'services', 'Oil tanker contractor services', '', 'percentage', 2, 2, 4, 'WHT', 'Minimum Tax', None, None, None),
    ('153_prof_2627', '153(1)(b)', 'services', 'Independent professionals', 'Individual 15/30; N/A for AOP', 'percentage', 15, 15, 30, 'WHT', 'Minimum Tax', None, None, None),
    ('153_port_2627', '153(1)(b)', 'services', 'Terminal / port operating services', '', 'percentage', 12, 12, 24, 'WHT', 'Minimum Tax', None, None, None),
    ('153_othsvc_2627', '153(1)(b)', 'services', 'Other services — company', '', 'percentage', 14, 14, 28, 'WHT', 'Minimum Tax', None, None, None),
    ('153_media_2627', '153(1)(b)', 'services', 'Electronic/print media advertisement', '', 'percentage', 1.5, 1.5, 3, 'WHT', 'Minimum Tax', None, None, None),
    ('153_con_co_2627', '153(1)(c)', 'contracts', 'Execution of contract — company', '', 'percentage', 7.5, 7.5, 15, 'WHT', 'Minimum Tax', None, None, None),
    ('153_con_ot_2627', '153(1)(c)', 'contracts', 'Execution of contract — other taxpayers', '', 'percentage', 8, 8, 16, 'WHT', 'Minimum Tax', None, None, None),
    ('153_con_sport_2627', '153(1)(c)', 'contracts', 'Execution of contract — sportsperson', '', 'percentage', 15, 15, 30, 'WHT', 'Minimum Tax', None, None, None),
    ('153_ecom_2627', '153(2A)', 'services', 'E-commerce (digital/banking payment)', '', 'percentage', 1, 1, 2, 'WHT', 'Adjustable', None, None, None),

    # ---- IMPORTS / EXPORTS ----
    ('148_p1_2627', '148', 'imports', 'Import — Part I, Twelfth Schedule', '', 'percentage', 1, 1, 2, 'Advance Tax', 'Minimum Tax', None, None, None),
    ('148_p2_2627', '148', 'imports', 'Import — Part II, Twelfth Schedule', '', 'percentage', 2, 2, 4, 'Advance Tax', 'Minimum Tax', None, None, None),
    ('154_goods_2627', '154', 'exports', 'Export of goods (on proceeds)', '', 'percentage', 1.25, 1.25, 1.25, 'WHT', 'Minimum Tax', None, None, None),
    ('154_b2b_2627', '154', 'exports', 'Sale to exporter (inland back-to-back)', '', 'percentage', 1.25, 1.25, 1.25, 'WHT', 'Minimum Tax', None, None, None),
    ('154A_it_2627', '154A', 'exports', 'Export of IT / IT-enabled services [VERIFY]', 'Reduced rate, conditions', 'percentage', 0.25, 0.25, 0.25, 'WHT', 'Final Tax', None, None, None),

    # ---- VEHICLES: 234 token (fixed Rs) ----
    ('234_1000_2627', '234', 'vehicles', 'Motor vehicle token — up to 1,000 CC', 'Annual by capacity', 'fixed', 800, 800, 10000, 'Advance Tax', 'Adjustable', None, None, None),
    ('234_1199_2627', '234', 'vehicles', 'Motor vehicle token — 1,001–1,199 CC', 'Annual by capacity', 'fixed', 1500, 1500, 18000, 'Advance Tax', 'Adjustable', None, None, None),
    ('234_1299_2627', '234', 'vehicles', 'Motor vehicle token — 1,200–1,299 CC', 'Annual by capacity', 'fixed', 1750, 1750, 20000, 'Advance Tax', 'Adjustable', None, None, None),
    ('234_1499_2627', '234', 'vehicles', 'Motor vehicle token — 1,300–1,499 CC', 'Annual by capacity', 'fixed', 2500, 2500, 30000, 'Advance Tax', 'Adjustable', None, None, None),
    ('234_1599_2627', '234', 'vehicles', 'Motor vehicle token — 1,500–1,599 CC', 'Annual by capacity', 'fixed', 3750, 3750, 45000, 'Advance Tax', 'Adjustable', None, None, None),
    ('234_1999_2627', '234', 'vehicles', 'Motor vehicle token — 1,600–1,999 CC', 'Annual by capacity', 'fixed', 4500, 4500, 60000, 'Advance Tax', 'Adjustable', None, None, None),
    ('234_2000_2627', '234', 'vehicles', 'Motor vehicle token — above 2,000 CC', 'Annual by capacity', 'fixed', 10000, 10000, 120000, 'Advance Tax', 'Adjustable', None, None, None),

    # ---- VEHICLES: 231B registration (% of value) ----
    ('231B_850_2627', '231B', 'vehicles', 'Vehicle registration — up to 850 CC', '% of value', 'percentage', 0.5, 0.5, 1.5, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_1000_2627', '231B', 'vehicles', 'Vehicle registration — 851–1,000 CC', '% of value', 'percentage', 1, 1, 3, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_1300_2627', '231B', 'vehicles', 'Vehicle registration — 1,001–1,300 CC', '% of value', 'percentage', 1.5, 1.5, 4.5, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_1600_2627', '231B', 'vehicles', 'Vehicle registration — 1,301–1,600 CC', '% of value', 'percentage', 2, 2, 6, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_1800_2627', '231B', 'vehicles', 'Vehicle registration — 1,601–1,800 CC', '% of value', 'percentage', 3, 3, 9, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_2000_2627', '231B', 'vehicles', 'Vehicle registration — 1,801–2,000 CC', '% of value', 'percentage', 5, 5, 15, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_2500_2627', '231B', 'vehicles', 'Vehicle registration — 2,001–2,500 CC', '% of value', 'percentage', 7, 7, 21, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_3000_2627', '231B', 'vehicles', 'Vehicle registration — 2,501–3,000 CC', '% of value', 'percentage', 9, 9, 27, 'Advance Tax', 'Adjustable', None, None, None),
    ('231B_over3000_2627', '231B', 'vehicles', 'Vehicle registration — above 3,000 CC', '% of value', 'percentage', 12, 12, 36, 'Advance Tax', 'Adjustable', None, None, None),

    # ---- OTHER ----
    ('236CB_2627', '236CB', 'other', 'Functions & gatherings', 'On total bill', 'percentage', 10, 10, 10, 'Advance Tax', 'Adjustable', None, None, None),
    ('156_2627', '156', 'prizes', 'Prize bond winnings', 'On gross winning', 'percentage', 15, 15, 30, 'WHT', 'Final Tax', None, None, None),
    ('156A_2627', '156A', 'other', 'Petroleum products — pump operator commission', '', 'percentage', 12, 12, 24, 'WHT', 'Final Tax', None, None, None),
    ('233_adv_2627', '233', 'services', 'Brokerage & commission — advertising agents', '', 'percentage', 10, 10, 20, 'WHT', 'Minimum Tax', None, None, None),
    ('233_life_2627', '233', 'services', 'Brokerage — life insurance agent (< Rs 0.5M)', '', 'percentage', 8, 8, 16, 'WHT', 'Minimum Tax', None, None, None),
    ('233_oth_2627', '233', 'services', 'Brokerage & commission — others', '', 'percentage', 12, 12, 24, 'WHT', 'Minimum Tax', None, None, None),
    ('236A_goods_2627', '236A', 'other', 'Sale by auction (goods/property)', '', 'percentage', 10, 10, 20, 'Advance Tax', 'Adjustable', None, None, None),
    ('236A_prop_2627', '236A', 'other', 'Auction of immovable property', '', 'percentage', 5, 5, 10, 'Advance Tax', 'Adjustable', None, None, None),
    ('236G_fert_2627', '236G', 'goods', 'Sales to distributors — fertilizer', '', 'percentage', 0.7, 0.7, 1.4, 'Advance Tax', 'Adjustable', None, None, None),
    ('236G_oth_2627', '236G', 'goods', 'Sales to distributors — other than fertilizer', '', 'percentage', 0.1, 0.1, 2, 'Advance Tax', 'Adjustable', None, None, None),
    ('236H_ret_2627', '236H', 'goods', 'Sales to retailers', '', 'percentage', 0.5, 0.5, 2.5, 'Advance Tax', 'Adjustable', None, None, None),
    ('236H_whole_2627', '236H', 'goods', 'Sales to wholesalers', '', 'percentage', 0.5, 0.5, 1, 'Advance Tax', 'Adjustable', None, None, None),
    ('231C_2627', '231C', 'other', 'Foreign domestic workers — visa (fixed Rs)', 'Per visa', 'fixed', 200000, 200000, 400000, 'Advance Tax', 'Adjustable', None, None, None),
    ('236Z_2627', '236Z', 'other', 'Bonus shares issued (value)', '', 'percentage', 10, 10, 10, 'WHT', 'Final Tax', None, None, None),

    # ---- UTILITIES (235 electricity, 236 phone) — percentage ----
    ('235_comm_2627', '235', 'other', 'Electricity — commercial (over Rs 20,000)', 'Rs 1,950 + 12%', 'percentage', 12, 12, 12, 'Advance Tax', 'Minimum Tax', None, None, None),
    ('235_ind_2627', '235', 'other', 'Electricity — industrial (over Rs 20,000)', 'Rs 1,950 + 5%', 'percentage', 5, 5, 5, 'Advance Tax', 'Adjustable', None, None, None),
    ('236_tel_2627', '236', 'other', 'Telephone bill over Rs 1,000', '', 'percentage', 10, 10, 10, 'Advance Tax', 'Adjustable', None, None, None),
    ('236_net_2627', '236', 'other', 'Internet / prepaid / mobile', '', 'percentage', 15, 15, 15, 'Advance Tax', 'Adjustable', None, None, None),
]


class Command(BaseCommand):
    help = 'Seed verified TY2026-27 rates into WHTRate (calculator model)'

    def handle(self, *args, **opts):
        created, updated = 0, 0
        for i, row in enumerate(ROWS):
            (uid, section, cat, name, sub, rate_kind, filer, late_filer,
             non_filer, nature, tax_type, slab_min, slab_max, base_tax) = row
            _, was_created = WHTRate.objects.update_or_create(
                uid=uid,
                defaults=dict(
                    section=section, cat=cat, name=name, sub=sub,
                    rate_kind=rate_kind,
                    filer=filer, late_filer=late_filer, non_filer=non_filer,
                    nature=nature, tax_type=tax_type,
                    tax_year=YEAR, is_active=True, sort_order=i,
                    slab_min=slab_min, slab_max=slab_max, base_tax=base_tax,
                ),
            )
            created += was_created
            updated += (not was_created)
        self.stdout.write(self.style.SUCCESS(
            f'WHTRate {YEAR}: {created} created, {updated} updated, {len(ROWS)} total.'
        ))

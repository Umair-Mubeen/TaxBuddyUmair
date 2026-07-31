# ══════════════════════════════════════════════════════════════
# SEED — TaxBuddyApp/management/commands/seed_glossary.py
#
# Fills the GlossaryTerm model used by the public Tax Glossary at
# /glossary/ (glossary_list + glossary_detail).
#
# Setup:
#   place at: TaxBuddyApp/management/commands/seed_glossary.py
#   (ensure __init__.py exists in management/ and commands/)
#
# Run:
#   python manage.py seed_glossary
#   (idempotent — keyed on slug; safe to re-run. Existing terms are
#    updated, new ones created. Nothing else is touched.)
#
# Notes:
#   • slug is auto-generated from the term (slugify).
#   • These are educational definitions — plain-English tax terms.
#   • Adjust wording anytime from Django admin; re-running won't wipe
#     your manual edits' term/slug, but WILL overwrite the fields
#     below on matched slugs, so edit here if you want changes to stick.
# ══════════════════════════════════════════════════════════════

from django.core.management.base import BaseCommand
from django.utils.text import slugify
from TaxBuddyApp.models import GlossaryTerm

# term, short_meaning, explanation, legal_definition, section_ref, example
TERMS = [
    (
        "ATL (Active Taxpayers List)",
        "FBR's public list of people who filed their return on time — being on it means lower withholding tax rates.",
        "The Active Taxpayers List is published by FBR and updated regularly. If your name is on it, banks, registrars and other withholding agents deduct tax from you at the normal (lower) rate. If you're not on it, you're treated as a non-filer and pay higher rates on most transactions — often double.",
        "Maintained under section 181A of the Income Tax Ordinance, 2001.",
        "Section 181A",
        "A filer buying property pays 1.25% under 236K; a non-filer pays up to 18.5% on the same purchase.",
    ),
    (
        "Non-Filer",
        "A person not on the Active Taxpayers List — faces higher, often double, withholding tax rates.",
        "A non-filer is anyone who hasn't filed their income tax return (or filed late and isn't on the ATL). To discourage staying outside the tax net, the law charges non-filers increased withholding rates on many transactions — property, banking, vehicles and more.",
        "Increased rates set out in the Tenth Schedule to the Income Tax Ordinance, 2001.",
        "Tenth Schedule",
        "A non-filer withdrawing cash over Rs 50,000/day pays 0.8% under 231AB; a filer pays 0%.",
    ),
    (
        "NTN (National Tax Number)",
        "Your unique tax registration number with FBR, used for all filings and tax matters.",
        "The NTN identifies you in FBR's system. For individuals it's usually your CNIC; businesses get a separate number. You need it to file returns, register for sales tax, and appear on the ATL.",
        "Registration under section 181 of the Income Tax Ordinance, 2001.",
        "Section 181",
        "",
    ),
    (
        "Withholding Tax (WHT)",
        "Tax deducted at source by a payer (bank, employer, buyer) and deposited with FBR on your behalf.",
        "Instead of waiting for you to pay, the law makes the person paying you (or collecting from you) deduct tax up front and deposit it with FBR. It may be adjustable against your final liability, or final in itself, depending on the section.",
        "Various withholding provisions, sections 148 to 236 of the Income Tax Ordinance, 2001.",
        "Sections 148–236",
        "Your employer deducts tax from your salary each month under section 149 — that's withholding tax.",
    ),
    (
        "Advance Tax",
        "Tax collected in advance on certain transactions (vehicle, property, utilities), usually adjustable against your final liability.",
        "Advance tax is collected at the time of a transaction — buying a car, purchasing property, paying a phone bill — before your final tax is worked out. Most advance tax is adjustable: you subtract it from what you owe when you file.",
        "Sections 147 and 231–236 of the Income Tax Ordinance, 2001.",
        "Sections 147, 231–236",
        "",
    ),
    (
        "Final Tax Regime (FTR)",
        "Income where the tax deducted is full and final — not taxed again at slab rates.",
        "Under FTR, once the specified tax is deducted, that income is settled — you don't add it to your normal income or pay slab rates on it. Common examples include export proceeds and certain prize/dividend income, subject to conditions.",
        "Final tax treatment under section 169 of the Income Tax Ordinance, 2001.",
        "Section 169",
        "IT export income under 154A (0.25% PSEB) is final tax — not taxed again at slab rates, subject to conditions.",
    ),
    (
        "Normal Tax Regime (NTR)",
        "Income taxed at standard slab rates after expenses and deductions — not final.",
        "Under NTR, income is added up, allowable expenses and deductions are subtracted, and tax is charged at the progressive slab rates. This is the default treatment for salary and business income that isn't under a final regime.",
        "",
        "",
        "A freelancer with a Pakistani client is taxed under NTR (slab rates), not the 154A export regime.",
    ),
    (
        "Minimum Tax",
        "A floor tax on turnover that applies even if you have little or no profit.",
        "Minimum tax makes sure businesses contribute something even in a loss or low-profit year. It's charged on turnover at a set percentage; if your normal tax is lower than the minimum, you pay the minimum.",
        "Section 113 of the Income Tax Ordinance, 2001.",
        "Section 113",
        "",
    ),
    (
        "Super Tax",
        "An additional tax on high-income persons and companies above set income thresholds.",
        "Super tax is charged on top of normal tax once income crosses specified thresholds. It's aimed at higher earners and large companies, with rates rising in bands.",
        "Section 4C of the Income Tax Ordinance, 2001.",
        "Section 4C",
        "",
    ),
    (
        "Filer",
        "A person on the Active Taxpayers List (filed their return) — gets the lower withholding rates.",
        "A filer is someone who has filed their income tax return and appears on the ATL. Filing brings you into the tax net and unlocks the normal (lower) withholding rates across property, banking, vehicles and more.",
        "Linked to the ATL under section 181A of the Income Tax Ordinance, 2001.",
        "Section 181A",
        "",
    ),
    (
        "FMV (Fair Market Value)",
        "The value FBR uses for property — often notified valuation tables — to compute 236C/236K tax.",
        "For property transactions, tax is calculated on the fair market value, which FBR notifies through valuation tables for each area. The higher the FMV, the higher the advance tax on purchase or sale.",
        "Concept under section 68 of the Income Tax Ordinance, 2001.",
        "Section 68",
        "If FBR values a plot at Rs 10M and a filer buys it, 236K at 1.25% = Rs 125,000.",
    ),
    (
        "Input Tax",
        "Sales tax you paid on your purchases, which you can adjust against the sales tax you collect.",
        "When a registered business buys taxable goods or services, the sales tax it pays is input tax. It can be set off against output tax, so you effectively pay tax only on your value addition.",
        "Section 7 of the Sales Tax Act, 1990.",
        "Sales Tax Act 1990, s.7",
        "",
    ),
    (
        "Output Tax",
        "The sales tax you charge your customers on your taxable supplies.",
        "Output tax is the sales tax a registered person adds to the price of goods or services sold. You collect it from customers, subtract your input tax, and pay the difference to FBR.",
        "Defined in the Sales Tax Act, 1990.",
        "Sales Tax Act 1990",
        "",
    ),
    (
        "Further Tax",
        "Extra sales tax charged when you supply to an unregistered person.",
        "To push buyers to register, the law adds a further tax on supplies made to people who aren't sales-tax registered. It's charged on top of the normal sales tax rate.",
        "Section 3(1A) of the Sales Tax Act, 1990.",
        "Sales Tax Act 1990, s.3(1A)",
        "",
    ),
    (
        "Tax Year",
        "The 12-month period for income tax — in Pakistan, 1 July to 30 June.",
        "Pakistan's tax year runs from 1 July to 30 June and is named after the year in which it ends. Some businesses use a special tax year with FBR's approval.",
        "Section 74 of the Income Tax Ordinance, 2001.",
        "Section 74",
        "Tax Year 2026 covers income earned from 1 July 2025 to 30 June 2026.",
    ),
    (
        "Tax Credit",
        "An amount subtracted directly from the tax you owe (not from income).",
        "A tax credit reduces your actual tax bill rupee-for-rupee, unlike a deduction which reduces taxable income. Common credits include those for charitable donations and approved pension contributions.",
        "Sections 61 to 65 of the Income Tax Ordinance, 2001.",
        "Sections 61–65",
        "",
    ),
    (
        "Wealth Statement",
        "A statement of your assets, liabilities and expenses filed alongside your return.",
        "The wealth statement shows what you own, what you owe, and how your wealth changed over the year. FBR uses it to check that your declared income supports your lifestyle and asset growth.",
        "Section 116 of the Income Tax Ordinance, 2001.",
        "Section 116",
        "",
    ),
    (
        "Return of Income",
        "The annual income tax return filed with FBR declaring your income and tax.",
        "The return of income is the yearly filing where you declare all income, claim deductions and credits, and report the tax due or refundable. Filing it on time gets you onto the ATL.",
        "Section 114 of the Income Tax Ordinance, 2001.",
        "Section 114",
        "",
    ),
    (
        "PSEB",
        "Pakistan Software Export Board — registration gives IT exporters the reduced 0.25% rate under 154A.",
        "PSEB is the government body for the IT and software export sector. Registering with PSEB lets IT and IT-enabled service exporters access the reduced 0.25% final tax rate on export proceeds, instead of 1%.",
        "Relevant to the reduced rate under section 154A.",
        "Section 154A",
        "A PSEB-registered freelancer pays 0.25% on export income; without it, 1%.",
    ),
    (
        "PRC / ePRC",
        "Proceeds Realization Certificate — bank proof that foreign export income was received legally.",
        "The PRC (now often issued electronically as ePRC) is a certificate from your bank confirming that export proceeds were realized through proper banking channels under the correct purpose code. It's key proof for claiming export tax treatment.",
        "",
        "",
        "An IT exporter keeps a PRC for each foreign remittance as proof for the 154A regime.",
    ),
    (
        "Section 154A",
        "Reduced final tax on export of IT and IT-enabled services — 0.25% for PSEB-registered, 1% for others.",
        "Section 154A gives exporters of IT and IT-enabled services a low final-tax rate on proceeds received through banking channels: 0.25% if PSEB-registered, otherwise 1%. It's treated as final tax, subject to conditions.",
        "Section 154A of the Income Tax Ordinance, 2001.",
        "Section 154A",
        "A Fiverr freelancer receiving foreign payments through a Pakistani bank is taxed under 154A, subject to conditions.",
    ),
    (
        "Section 7E",
        "Tax on deemed income from certain immovable properties.",
        "Section 7E treats certain properties as producing a deemed income and taxes it, aimed at high-value idle real estate. Exemptions and thresholds apply, and rules have changed over time.",
        "Section 7E of the Income Tax Ordinance, 2001.",
        "Section 7E",
        "",
    ),
    (
        "SRO (Statutory Regulatory Order)",
        "A legal notification FBR issues to change tax rules, rates or procedures.",
        "An SRO is how FBR makes or amends rules under powers given by tax laws — adjusting rates, granting exemptions, or setting procedures. SROs can change your tax position between budgets, so they're worth tracking.",
        "Issued under powers in the Income Tax Ordinance 2001, Sales Tax Act 1990 and other laws.",
        "",
        "SRO 1413(I)/2025 revised the mandatory e-invoicing timeline for sales-tax registered persons.",
    ),
    (
        "Adjustable Tax",
        "Tax deducted that you can adjust against your final liability — the opposite of final tax.",
        "Adjustable tax isn't the end of the story: you subtract it from your total tax when you file, and if too much was deducted you get a refund. Most advance tax is adjustable.",
        "",
        "",
        "Advance tax on your electricity bill is adjustable — you claim it back against your yearly tax.",
    ),
    (
        "Taxable Income",
        "Total income minus allowable deductions, on which your tax is calculated.",
        "Taxable income is what's left after subtracting allowable deductions and exemptions from your total income. Slab rates (or applicable rates) are then applied to it to work out the tax.",
        "Section 9 of the Income Tax Ordinance, 2001.",
        "Section 9",
        "",
    ),
]


class Command(BaseCommand):
    help = 'Seed the Pakistan Tax Glossary (GlossaryTerm model) with core terms'

    def handle(self, *args, **opts):
        created, updated = 0, 0
        for term, short_meaning, explanation, legal_def, section_ref, example in TERMS:
            slug = slugify(term.split('(')[0].strip())  # clean slug, drops "(...)"
            _, was_created = GlossaryTerm.objects.update_or_create(
                slug=slug,
                defaults=dict(
                    term=term,
                    short_meaning=short_meaning,
                    explanation=explanation,
                    legal_definition=legal_def,
                    section_ref=section_ref,
                    example=example,
                    is_active=True,
                ),
            )
            created += was_created
            updated += (not was_created)
        self.stdout.write(self.style.SUCCESS(
            f'Glossary: {created} created, {updated} updated, {len(TERMS)} total.'
        ))

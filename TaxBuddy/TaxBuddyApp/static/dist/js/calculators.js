/* ============================================================
   TaxBuddy Umair — Calculators JavaScript
   Handles: live formatting, year validation, result scrolling
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  // ── FORMAT INCOME INPUT WITH COMMAS ON DISPLAY ───────────
  const incomeInput = document.getElementById('income_amount') ||
                      document.querySelector('[name="income_amount"]');

  if (incomeInput) {
    incomeInput.addEventListener('input', () => {
      // Only allow numbers
      incomeInput.value = incomeInput.value.replace(/[^0-9]/g, '');
      updateLivePreview();
    });
  }

  // ── LIVE PREVIEW LABEL ─────────────────────────────────────
  function updateLivePreview() {
    const input     = document.querySelector('[name="income_amount"]');
    const typeRadio = document.querySelector('[name="income_type"]:checked');
    const preview   = document.getElementById('live-preview');

    if (!input || !preview) return;

    const val  = parseFloat(input.value) || 0;
    const type = typeRadio ? typeRadio.value : 'Yearly';
    const annual = type === 'Monthly' ? val * 12 : val;

    if (annual > 0) {
      preview.textContent = `Annual income: PKR ${Math.round(annual).toLocaleString('en-PK')}`;
      preview.style.display = 'block';
    } else {
      preview.style.display = 'none';
    }
  }

  // Update preview on radio change
  document.querySelectorAll('[name="income_type"]').forEach(r => {
    r.addEventListener('change', updateLivePreview);
  });

  // ── YEAR VALIDATION: prevent same year selected ───────────
  const year1 = document.querySelector('[name="tax_year_1"]');
  const year2 = document.querySelector('[name="tax_year_2"]');

  function validateYears() {
    if (!year1 || !year2) return;
    const submit = document.querySelector('.calc-submit');
    const warn   = document.getElementById('year-warn');

    if (year1.value && year2.value && year1.value === year2.value) {
      if (warn) {
        warn.textContent = '⚠️ Please select two different tax years for comparison.';
        warn.style.display = 'block';
      }
      if (submit) submit.disabled = true;
    } else {
      if (warn) warn.style.display = 'none';
      if (submit) submit.disabled = false;
    }
  }

  if (year1) year1.addEventListener('change', validateYears);
  if (year2) year2.addEventListener('change', validateYears);

  // ── SCROLL TO RESULTS ON PAGE LOAD (if results present) ──
  const resultEl = document.querySelector('.calc-result');
  if (resultEl) {
    // Small delay to let page render
    setTimeout(() => {
      resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
  }

  // ── DEDUCTION TOTALS (Property Calculator) ───────────────
  const deductionInputs = document.querySelectorAll('.deduction-grid input[type="number"]');
  if (deductionInputs.length) {
    const totalDisplay = document.getElementById('deduction-total');
    function updateDeductionTotal() {
      let total = 0;
      deductionInputs.forEach(inp => total += parseFloat(inp.value) || 0);
      if (totalDisplay) {
        totalDisplay.textContent = `Total Deductions: PKR ${Math.round(total).toLocaleString('en-PK')}`;
      }
    }
    deductionInputs.forEach(inp => inp.addEventListener('input', updateDeductionTotal));
  }

  // ── FORM SUBMIT: show loading state ───────────────────────
  const calcForms = document.querySelectorAll('form');
  calcForms.forEach(form => {
    form.addEventListener('submit', (e) => {
      const btn = form.querySelector('.calc-submit');
      if (btn && !btn.disabled) {
        btn.textContent = '⏳ Calculating…';
        btn.style.opacity = '0.8';
      }
    });
  });

});

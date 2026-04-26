/* ============================================================
   TaxBuddy Umair — MCQ / Quiz JavaScript
   Features: Score tracking, sessionStorage persistence,
             keyboard navigation, smooth UX
   ============================================================ */

// ── STATE ────────────────────────────────────────────────────
const MCQ_STORAGE_KEY = 'taxbuddy_mcq_score';

let mcqState = loadState();

// ── LOAD / SAVE STATE ─────────────────────────────────────────
function loadState() {
  try {
    const saved = sessionStorage.getItem(MCQ_STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      return {
        answered: parsed.answered || 0,
        correct:  parsed.correct  || 0,
        wrong:    parsed.wrong    || 0,
        total:    0, // recounted on page load
      };
    }
  } catch(e) {}
  return { answered: 0, correct: 0, wrong: 0, total: 0 };
}

function saveState() {
  try {
    sessionStorage.setItem(MCQ_STORAGE_KEY, JSON.stringify({
      answered: mcqState.answered,
      correct:  mcqState.correct,
      wrong:    mcqState.wrong,
    }));
  } catch(e) {}
}

function resetState() {
  mcqState = { answered: 0, correct: 0, wrong: 0, total: 0 };
  try { sessionStorage.removeItem(MCQ_STORAGE_KEY); } catch(e) {}
  mcqState.total = document.querySelectorAll('.mcq-card').length;
  updateScorePanel();
}

// ── INIT ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  mcqState.total = document.querySelectorAll('.mcq-card').length;
  updateScorePanel();

  // Keyboard support: Enter / Space to select focused option
  document.querySelectorAll('.mcq-option').forEach(opt => {
    opt.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        selectMCQOption(opt);
      }
    });
  });

  // Reset button (if present)
  const resetBtn = document.getElementById('mcq-reset-btn');
  if (resetBtn) resetBtn.addEventListener('click', resetState);

  // Show reset button if there's a saved score
  if (mcqState.answered > 0) {
    const btn = document.getElementById('mcq-reset-btn');
    if (btn) btn.style.display = 'inline-flex';
  }
});


// ── SELECT OPTION ─────────────────────────────────────────────
/**
 * Called when user clicks an MCQ option.
 * @param {HTMLElement} el - The clicked .mcq-option element
 */
function selectMCQOption(el) {
  const parentOptions = el.closest('.mcq-options');
  // Already answered this question?
  if (parentOptions.querySelector('.selected-correct, .selected-wrong')) return;

  const isCorrect = el.dataset.correct === 'true';
  const expId     = el.dataset.exp;

  // Disable all options in this question
  parentOptions.querySelectorAll('.mcq-option').forEach(opt => {
    opt.classList.add('disabled');
    opt.setAttribute('tabindex', '-1');
    // Always highlight the correct answer in green
    if (opt.dataset.correct === 'true') {
      opt.classList.add('selected-correct');
    }
  });

  // Mark selected option right/wrong
  if (isCorrect) {
    el.classList.add('selected-correct');
  } else {
    el.classList.add('selected-wrong');
  }

  // Show explanation
  const exp = document.getElementById(expId);
  if (exp) {
    exp.classList.add('show');
    if (!isCorrect) exp.classList.add('wrong-exp');
    // Smooth scroll to explanation on mobile
    if (window.innerWidth < 768) {
      setTimeout(() => {
        exp.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 150);
    }
  }

  // Update state
  mcqState.answered++;
  if (isCorrect) mcqState.correct++;
  else           mcqState.wrong++;

  saveState(); // persist across pagination
  updateScorePanel();

  // Show reset button once user has answered ≥1
  const resetBtn = document.getElementById('mcq-reset-btn');
  if (resetBtn) resetBtn.style.display = 'inline-flex';
}


// ── UPDATE SCORE PANEL ────────────────────────────────────────
function updateScorePanel() {
  const answeredEl = document.getElementById('score-answered');
  const correctEl  = document.getElementById('score-correct');
  const wrongEl    = document.getElementById('score-wrong');
  const pctEl      = document.getElementById('score-pct');

  if (answeredEl) answeredEl.textContent = `${mcqState.answered} / ${mcqState.total}`;
  if (correctEl)  correctEl.textContent  = mcqState.correct;
  if (wrongEl)    wrongEl.textContent    = mcqState.wrong;

  if (pctEl) {
    if (mcqState.answered === 0) {
      pctEl.textContent = '—';
      pctEl.style.color = '';
    } else {
      const pct = Math.round((mcqState.correct / mcqState.answered) * 100);
      pctEl.textContent = `${pct}%`;
      // Colour code: green ≥70%, amber 50-69%, red <50%
      pctEl.style.color = pct >= 70
        ? 'var(--green)'
        : pct >= 50
        ? 'var(--gold)'
        : 'var(--red)';
    }
  }

  // Show running motivation message
  updateMotivation();
}


// ── MOTIVATION MESSAGE ────────────────────────────────────────
function updateMotivation() {
  const msgEl = document.getElementById('mcq-motivation');
  if (!msgEl || mcqState.answered === 0) return;

  const pct = Math.round((mcqState.correct / mcqState.answered) * 100);
  let msg = '';

  if (mcqState.answered < 3)       msg = '🎯 Keep going!';
  else if (pct === 100)             msg = '🏆 Perfect score! Excellent!';
  else if (pct >= 80)               msg = '🌟 Great work! You\'re well prepared.';
  else if (pct >= 60)               msg = '📚 Good effort. Review the explanations.';
  else                              msg = '💪 Keep practising — you\'ll improve!';

  msgEl.textContent = msg;
  msgEl.style.display = 'block';
}

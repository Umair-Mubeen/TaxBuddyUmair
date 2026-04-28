/* ============================================================
   TaxBuddy Umair — MCQ / Quiz JavaScript
   Drives: score panel, progress bar, status dots,
           explanation reveal, sessionStorage persistence,
           motivation bar, reset
   ============================================================ */

// ── STATE ─────────────────────────────────────────────────────
const MCQ_KEY = 'taxbuddy_mcq_score';
let totalOnPage = 0;

let state = loadState();

function loadState() {
  try {
    const raw = sessionStorage.getItem(MCQ_KEY);
    if (raw) {
      const p = JSON.parse(raw);
      return { answered: p.answered || 0, correct: p.correct || 0, wrong: p.wrong || 0 };
    }
  } catch(e) {}
  return { answered: 0, correct: 0, wrong: 0 };
}

function saveState() {
  try { sessionStorage.setItem(MCQ_KEY, JSON.stringify(state)); } catch(e) {}
}

function resetState() {
  state = { answered: 0, correct: 0, wrong: 0 };
  try { sessionStorage.removeItem(MCQ_KEY); } catch(e) {}
  updateAllUI();
  // Hide motivation bar
  const bar = document.getElementById('mcq-motivation-bar');
  if (bar) bar.classList.remove('show');
  const resetBtn = document.getElementById('mcq-reset-btn');
  if (resetBtn) resetBtn.style.display = 'none';
}

// ── INIT ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  totalOnPage = document.querySelectorAll('.mcq-card').length;
  updateAllUI();

  // Keyboard: Enter / Space on focused option
  document.querySelectorAll('.mcq-option').forEach(opt => {
    opt.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        selectMCQOption(opt);
      }
    });
  });

  // Show reset btn if there's a previous score
  if (state.answered > 0) {
    const bar = document.getElementById('mcq-motivation-bar');
    if (bar) bar.classList.add('show');
  }
});

// ── SELECT OPTION ─────────────────────────────────────────────
function selectMCQOption(el) {
  const parentOpts = el.closest('.mcq-options');
  // Already answered?
  if (parentOpts.querySelector('.selected-correct, .selected-wrong')) return;

  const isCorrect = el.dataset.correct === 'true';
  const expId     = el.dataset.exp;
  const qPk       = el.dataset.qpk;

  // Mark all options disabled, highlight correct answer
  parentOpts.querySelectorAll('.mcq-option').forEach(opt => {
    opt.classList.add('disabled');
    opt.setAttribute('tabindex', '-1');
    if (opt.dataset.correct === 'true' && opt !== el) {
      opt.classList.add('correct-highlight');
    }
  });

  // Mark selected option
  el.classList.add(isCorrect ? 'selected-correct' : 'selected-wrong');

  // Show explanation
  const exp      = document.getElementById(expId);
  const expInner = document.getElementById(`exp-inner-${qPk}`);
  const expHeader= document.getElementById(`exp-header-${qPk}`);
  const expIcon  = document.getElementById(`exp-icon-${qPk}`);
  const expTitle = document.getElementById(`exp-title-${qPk}`);

  if (exp) {
    exp.classList.add('show');
    if (!isCorrect && expInner)  expInner.classList.add('wrong-bg');
    if (!isCorrect && expHeader) expHeader.classList.add('wrong');
    if (expIcon)  expIcon.textContent  = isCorrect ? '✅' : '❌';
    if (expTitle) expTitle.textContent = isCorrect ? 'Correct Answer!' : 'Incorrect — See Explanation';
    // Scroll explanation into view on mobile
    if (window.innerWidth < 768) {
      setTimeout(() => exp.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 200);
    }
  }

  // Update status dot on card header
  const dot = document.getElementById(`dot-${qPk}`);
  if (dot) dot.classList.add(isCorrect ? 'correct' : 'wrong');

  // Style card border
  const card = document.getElementById(`mcq-card-${qPk}`);
  if (card) card.classList.add(isCorrect ? 'answered' : 'answered-wrong');

  // Update state
  state.answered++;
  if (isCorrect) state.correct++;
  else           state.wrong++;

  saveState();
  updateAllUI();
}

// ── UPDATE ALL UI ELEMENTS ────────────────────────────────────
function updateAllUI() {
  updateScorePanel();
  updateProgressBar();
  updateMotivationBar();
}

function updateScorePanel() {
  const answeredEl = document.getElementById('score-answered');
  const correctEl  = document.getElementById('score-correct');
  const wrongEl    = document.getElementById('score-wrong');
  const pctEl      = document.getElementById('score-pct');

  if (answeredEl) {
    answeredEl.innerHTML = `${state.answered}<span style="font-size:13px;color:var(--text-light);font-weight:400;"> / ${totalOnPage}</span>`;
  }
  if (correctEl) correctEl.textContent = state.correct;
  if (wrongEl)   wrongEl.textContent   = state.wrong;

  if (pctEl) {
    if (state.answered === 0) {
      pctEl.textContent = '—';
      pctEl.style.color = '';
    } else {
      const pct = Math.round((state.correct / state.answered) * 100);
      pctEl.textContent = `${pct}%`;
      pctEl.style.color = pct >= 70 ? 'var(--green)' : pct >= 50 ? 'var(--gold)' : 'var(--red)';
    }
  }
}

function updateProgressBar() {
  const bar     = document.getElementById('progress-bar');
  const pctText = document.getElementById('progress-pct-text');
  if (!bar) return;

  const pct = totalOnPage > 0 ? Math.round((state.answered / totalOnPage) * 100) : 0;
  bar.style.width = pct + '%';
  if (pctText) pctText.textContent = pct + '% complete';

  // Change bar colour at 100%
  if (pct === 100) {
    bar.style.background = 'linear-gradient(90deg, var(--green), #4ee8b0)';
  }
}

function updateMotivationBar() {
  const bar    = document.getElementById('mcq-motivation-bar');
  const msgEl  = document.getElementById('mcq-motivation');
  const resetBtn = document.getElementById('mcq-reset-btn');
  if (!bar || !msgEl) return;

  if (state.answered === 0) return;

  const pct = Math.round((state.correct / state.answered) * 100);
  let msg = '';

  if (state.answered < 3)  msg = '🎯 Keep going!';
  else if (pct === 100)    msg = '🏆 Perfect! Outstanding knowledge!';
  else if (pct >= 80)      msg = '🌟 Excellent! You\'re well prepared.';
  else if (pct >= 60)      msg = '📚 Good effort! Review the explanations.';
  else if (pct >= 40)      msg = '💪 Keep practising — you\'ll improve!';
  else                     msg = '📖 Focus on the ITO 2001 references.';

  msgEl.textContent = msg;
  bar.classList.add('show');
  if (resetBtn) resetBtn.style.display = 'flex';
}

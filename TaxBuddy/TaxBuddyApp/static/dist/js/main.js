/* ============================================================
   TaxBuddy Umair — Main Site JavaScript
   Features: Mobile Nav, FAQ, Back-to-Top, WA Tracking,
             Smooth Scroll, Lazy Load, TOC Highlight
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  // ══════════════════════════════════════════════════════════
  // MOBILE NAV — FULLY FIXED
  // ══════════════════════════════════════════════════════════
  const hamburger = document.getElementById('nav-hamburger');
  const mobileNav = document.getElementById('mobile-nav');

  function closeMobileNav() {
    if (!mobileNav) return;
    mobileNav.classList.remove('open');
    if (hamburger) {
      hamburger.classList.remove('open');
      hamburger.setAttribute('aria-expanded', 'false');
    }
    document.body.style.overflow = '';
  }

  if (hamburger && mobileNav) {
    hamburger.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = mobileNav.classList.toggle('open');
      hamburger.classList.toggle('open', isOpen);
      hamburger.setAttribute('aria-expanded', String(isOpen));
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });

    document.addEventListener('click', (e) => {
      if (!hamburger.contains(e.target) && !mobileNav.contains(e.target)) {
        closeMobileNav();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeMobileNav();
    });

    mobileNav.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => closeMobileNav());
    });
  }

  // ── MOBILE SUB-MENUS ─────────────────────────────────────
  document.querySelectorAll('.mobile-nav-toggle').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const sub = document.getElementById(btn.dataset.target);
      if (!sub) return;
      const isOpen = sub.classList.toggle('open');
      btn.setAttribute('aria-expanded', String(isOpen));
      const arrow = btn.querySelector('.mob-arrow');
      if (arrow) arrow.style.transform = isOpen ? 'rotate(180deg)' : '';
    });
  });

  // ══════════════════════════════════════════════════════════
  // ACTIVE NAV LINK
  // ══════════════════════════════════════════════════════════
  const currentPath = window.location.pathname.replace(/\/$/, '');
  document.querySelectorAll('.nav-links a, .mobile-nav a').forEach(a => {
    const href = (a.getAttribute('href') || '').replace(/\/$/, '');
    if (href && href === currentPath) a.classList.add('active');
  });

  // ══════════════════════════════════════════════════════════
  // DESKTOP DROPDOWN — keyboard accessible
  // ══════════════════════════════════════════════════════════
  document.querySelectorAll('.has-dropdown > a').forEach(trigger => {
    trigger.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const dd = trigger.nextElementSibling;
        if (!dd) return;
        const visible = dd.style.display === 'block';
        dd.style.display = visible ? '' : 'block';
        trigger.setAttribute('aria-expanded', String(!visible));
      }
    });
  });

  // ══════════════════════════════════════════════════════════
  // FAQ ACCORDION
  // ══════════════════════════════════════════════════════════
  document.querySelectorAll('.faq-question').forEach(btn => {
    btn.addEventListener('click', () => {
      const answer = btn.nextElementSibling;
      const isOpen = answer.classList.contains('open');
      document.querySelectorAll('.faq-answer').forEach(a => a.classList.remove('open'));
      document.querySelectorAll('.faq-question').forEach(q => {
        q.classList.remove('open');
        q.setAttribute('aria-expanded', 'false');
      });
      if (!isOpen) {
        answer.classList.add('open');
        btn.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
      }
    });
    btn.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); btn.click(); }
    });
  });

  // ══════════════════════════════════════════════════════════
  // SMOOTH SCROLL — respects sticky nav height
  // ══════════════════════════════════════════════════════════
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const target = document.querySelector(a.getAttribute('href'));
      if (target) {
        e.preventDefault();
        const navH = document.querySelector('nav')?.offsetHeight || 70;
        window.scrollTo({
          top: target.getBoundingClientRect().top + window.scrollY - navH - 12,
          behavior: 'smooth'
        });
      }
    });
  });

  // ══════════════════════════════════════════════════════════
  // BACK TO TOP BUTTON
  // ══════════════════════════════════════════════════════════
  const backToTop = document.getElementById('back-to-top');
  if (backToTop) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 400) {
        backToTop.style.display = 'flex';
        backToTop.style.alignItems = 'center';
        backToTop.style.justifyContent = 'center';
        backToTop.style.opacity = '1';
      } else {
        backToTop.style.display = 'none';
      }
    }, { passive: true });

    backToTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // ══════════════════════════════════════════════════════════
  // WHATSAPP CLICK TRACKING (Google Analytics)
  // ══════════════════════════════════════════════════════════
  document.querySelectorAll('a[href*="wa.me"], .wa-float').forEach(btn => {
    btn.addEventListener('click', () => {
      // Track in GA4 if available
      if (typeof gtag !== 'undefined') {
        gtag('event', 'whatsapp_click', {
          event_category: 'contact',
          event_label: window.location.pathname,
        });
      }
      // Track in GA Universal if available
      if (typeof ga !== 'undefined') {
        ga('send', 'event', 'Contact', 'WhatsApp Click', window.location.pathname);
      }
    });
  });

  // ══════════════════════════════════════════════════════════
  // AUTO-DISMISS DJANGO MESSAGES after 5s
  // ══════════════════════════════════════════════════════════
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
      alert.style.transition = 'opacity .5s';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 5000);
  });

  // ══════════════════════════════════════════════════════════
  // GUIDE TOC — HIGHLIGHT ON SCROLL
  // ══════════════════════════════════════════════════════════
  const tocLinks = document.querySelectorAll('.guide-toc a');
  if (tocLinks.length) {
    const sections = document.querySelectorAll('.article-content h2[id]');
    if (sections.length) {
      const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            tocLinks.forEach(l => l.classList.remove('active'));
            const link = document.querySelector(`.guide-toc a[href="#${entry.target.id}"]`);
            if (link) link.classList.add('active');
          }
        });
      }, { rootMargin: '-80px 0px -60% 0px' });
      sections.forEach(s => observer.observe(s));
    }
  }

  // ══════════════════════════════════════════════════════════
  // RESPONSIVE TABLE WRAPPER
  // ══════════════════════════════════════════════════════════
  document.querySelectorAll('.article-content table').forEach(table => {
    if (!table.parentElement.classList.contains('table-scroll')) {
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'overflow-x:auto;-webkit-overflow-scrolling:touch;margin:20px 0;border-radius:8px;';
      wrapper.classList.add('table-scroll');
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    }
  });

  // ══════════════════════════════════════════════════════════
  // NATIVE LAZY LOADING FALLBACK (older browsers)
  // ══════════════════════════════════════════════════════════
  if ('loading' in HTMLImageElement.prototype) {
    // Browser supports native lazy loading — nothing to do
  } else {
    // Fallback: IntersectionObserver for older browsers
    const lazyImages = document.querySelectorAll('img[loading="lazy"]');
    if ('IntersectionObserver' in window) {
      const imgObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            if (img.dataset.src) img.src = img.dataset.src;
            imgObserver.unobserve(img);
          }
        });
      });
      lazyImages.forEach(img => imgObserver.observe(img));
    }
  }

  // ══════════════════════════════════════════════════════════
  // NUMBER-ONLY INPUTS
  // ══════════════════════════════════════════════════════════
  document.addEventListener('input', e => {
    if (e.target.classList.contains('number-only')) {
      e.target.value = e.target.value.replace(/[^0-9]/g, '');
    }
  });

  // ══════════════════════════════════════════════════════════
  // SEARCH BAR (if present on page)
  // ══════════════════════════════════════════════════════════
  const searchInput = document.getElementById('site-search');
  if (searchInput) {
    searchInput.addEventListener('keydown', e => {
      if (e.key === 'Enter' && searchInput.value.trim()) {
        window.location.href = `/blog/?q=${encodeURIComponent(searchInput.value.trim())}`;
      }
    });
  }

});

// ── UTILITY: Format PKR ─────────────────────────────────────
function formatPKR(n) {
  return 'PKR ' + (isNaN(n) ? 0 : Math.round(n)).toLocaleString('en-PK');
}

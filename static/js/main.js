/**
 * main.js — Shared Frontend JavaScript
 * ======================================
 * Global utilities available on every page:
 *   - showToast(message, type)
 *   - Sidebar hamburger toggle
 *   - Health-dot polling
 */

// ── Toast Notification System ────────────────────────────────────────────────

/**
 * Display a toast notification.
 * @param {string} message  - Text to display
 * @param {'success'|'error'|'info'} type - Visual style
 * @param {number} duration - Auto-dismiss after ms (default 4000)
 */
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = { success: '✅', error: '❌', info: 'ℹ️' };

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.setAttribute('role', 'alert');
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || ''}</span>
    <span class="toast-msg">${escapeHtml(message)}</span>
    <button class="toast-close" aria-label="Close notification">×</button>
  `;

  const dismiss = () => {
    toast.classList.add('hide');
    toast.addEventListener('animationend', () => toast.remove(), { once: true });
  };

  toast.querySelector('.toast-close').addEventListener('click', dismiss);
  container.appendChild(toast);

  if (duration > 0) setTimeout(dismiss, duration);
  return toast;
}

// ── Sidebar hamburger toggle ─────────────────────────────────────────────────
(function initSidebar() {
  const hamburger = document.getElementById('hamburger');
  const sidebar   = document.getElementById('sidebar');
  const main      = document.getElementById('main-content');
  if (!hamburger || !sidebar) return;

  hamburger.addEventListener('click', () => {
    const isOpen = sidebar.classList.toggle('open');
    hamburger.setAttribute('aria-expanded', isOpen);
  });

  // Close sidebar when clicking outside on mobile
  main && main.addEventListener('click', () => {
    if (window.innerWidth <= 768) sidebar.classList.remove('open');
  });
})();

// ── Health dot polling ───────────────────────────────────────────────────────
(function initHealthDot() {
  const dot = document.getElementById('health-dot');
  if (!dot) return;

  async function checkHealth() {
    try {
      const res  = await fetch('/api/health', { cache: 'no-store' });
      const json = await res.json();
      dot.className = json.status === 'healthy' ? 'status-dot dot-green' : 'status-dot dot-red';
      dot.title     = json.status === 'healthy' ? 'System Healthy' : 'System Degraded';
    } catch {
      dot.className = 'status-dot dot-red';
      dot.title     = 'Cannot reach server';
    }
  }

  checkHealth();
  setInterval(checkHealth, 60_000);  // re-check every 60 s
})();

// ── Utility: HTML escape ─────────────────────────────────────────────────────
function escapeHtml(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(str));
  return d.innerHTML;
}

// ── Utility: Format ISO timestamp to local string ────────────────────────────
function formatTs(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleString();
  } catch {
    return isoStr;
  }
}

// ── Expose globally ──────────────────────────────────────────────────────────
window.showToast  = showToast;
window.formatTs   = formatTs;
window.escapeHtml = escapeHtml;

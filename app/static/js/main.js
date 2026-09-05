function toggleProfileMenu() {
  const menu = document.getElementById('profile-menu');
  if (menu) menu.classList.toggle('hidden');
}

document.addEventListener('click', function (e) {
  const menu = document.getElementById('profile-menu');
  const btn = document.getElementById('profile-menu-btn');
  if (!menu || !btn) return;
  if (!menu.contains(e.target) && !btn.contains(e.target)) {
    menu.classList.add('hidden');
  }
});

// Job status dropdown (used on Job Workspaces + Job Overview)
function closeAllStatusDropdowns(except) {
  document.querySelectorAll('[data-status-dropdown]').forEach(function (root) {
    if (root.id === except) return;
    var panel = root.querySelector('[data-dd-panel]');
    var chevron = root.querySelector('[data-dd-chevron]');
    if (panel) panel.classList.add('hidden');
    if (chevron) chevron.style.transform = '';
    var btn = root.querySelector('button[aria-expanded]');
    if (btn) btn.setAttribute('aria-expanded', 'false');
  });
}

function toggleStatusDropdown(id) {
  var root = document.getElementById(id);
  if (!root) return;
  var panel = root.querySelector('[data-dd-panel]');
  var chevron = root.querySelector('[data-dd-chevron]');
  var btn = root.querySelector('button[aria-expanded]');
  var willOpen = panel.classList.contains('hidden');
  closeAllStatusDropdowns(id);
  panel.classList.toggle('hidden', !willOpen);
  if (chevron) chevron.style.transform = willOpen ? 'rotate(180deg)' : '';
  if (btn) btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
}

document.addEventListener('click', function (e) {
  if (!e.target.closest('[data-status-dropdown]')) {
    closeAllStatusDropdowns(null);
  }
});

document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') closeAllStatusDropdowns(null);
});

// Auto-dismiss toasts after 4s, with a quick fade+slide out
document.querySelectorAll('.toast').forEach(function (toast, i) {
  toast.style.transition = 'opacity .25s ease, transform .25s ease';
  setTimeout(function () {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(20px)';
    setTimeout(function () { toast.remove(); }, 250);
  }, 4000 + i * 300);
});

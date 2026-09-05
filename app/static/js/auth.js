function setMode(mode) {
  const bg = document.getElementById('tab-bg');
  const loginTab = document.getElementById('tab-login');
  const signupTab = document.getElementById('tab-signup');
  const loginForm = document.getElementById('form-login');
  const signupForm = document.getElementById('form-signup');
  if (mode === 'login') {
    if (bg) bg.style.transform = 'translateX(0)';
    if (loginTab) { loginTab.classList.add('text-ink'); loginTab.classList.remove('text-slate-400'); }
    if (signupTab) { signupTab.classList.add('text-slate-400'); signupTab.classList.remove('text-ink'); }
    if (loginForm) loginForm.classList.remove('hidden');
    if (signupForm) signupForm.classList.add('hidden');
  } else {
    if (bg) bg.style.transform = 'translateX(100%)';
    if (signupTab) { signupTab.classList.add('text-ink'); signupTab.classList.remove('text-slate-400'); }
    if (loginTab) { loginTab.classList.add('text-slate-400'); loginTab.classList.remove('text-ink'); }
    if (signupForm) signupForm.classList.remove('hidden');
    if (loginForm) loginForm.classList.add('hidden');
  }
}

document.addEventListener('DOMContentLoaded', function () {
  const authTabs = document.getElementById('auth-tabs');
  if (authTabs && authTabs.dataset.initialMode === 'signup') {
    setMode('signup');
  }
});

document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = el('msg');
  msg.className = 'msg';
  msg.textContent = 'Signing in...';
  const btn = e.target.querySelector('button');
  btn.disabled = true;
  try {
    const data = await api('/api/login', {
      method: 'POST',
      body: JSON.stringify({ email: el('email').value.trim(), password: el('password').value }),
    });
    const links = { student: 'student.html', admin: 'admin.html', counselor: 'counselor.html' };
    location.href = '/' + (links[data.role] || 'login.html');
  } catch (err) {
    msg.className = 'msg error';
    msg.textContent = err.message;
    btn.disabled = false;
  }
});

(async () => {
  try {
    const me = await api('/api/me');
    const links = { student: 'student.html', admin: 'admin.html', counselor: 'counselor.html' };
    if (me.user) location.href = '/' + links[me.user.role];
  } catch (e) { /* not logged in */ }
})();
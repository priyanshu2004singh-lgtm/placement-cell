async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    ...opts,
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-json */ }
  if (!res.ok) {
    const msg = (data && data.error) ? data.error : ('Request failed (' + res.status + ')');
    throw new Error(msg);
  }
  return data;
}

function el(id) { return document.getElementById(id); }

function badge(status) {
  const safe = String(status).toLowerCase();
  return `<span class="badge ${safe}">${status}</span>`;
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

async function logout() {
  await api('/api/logout', { method: 'POST' });
  location.href = '/login.html';
}

async function guard(allowedRoles) {
  let me;
  try { me = await api('/api/me'); }
  catch (e) { location.href = '/login.html'; return null; }
  const map = { student: 'student.html', admin: 'admin.html', counselor: 'counselor.html' };
  if (!allowedRoles.includes(me.user.role)) {
    location.href = '/' + (map[me.user.role] || 'login.html');
    return null;
  }
  document.title = 'Placement Cell - ' + me.user.name;
  const who = el('who');
  if (who) who.textContent = me.user.name + ' (' + me.user.role + ')';
  return me;
}

function toast(msg, ok = true) {
  const box = el('msgBox');
  if (!box) { alert(msg); return; }
  box.textContent = msg;
  box.className = 'msg ' + (ok ? 'ok' : 'error');
  setTimeout(() => { if (box) box.textContent = ''; }, 5000);
}
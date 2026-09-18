el('logoutBtn').addEventListener('click', logout);

document.querySelectorAll('#tabs button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('#tabs button').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.section').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    el(b.dataset.tab).classList.add('active');
  });
});

async function loadDashboard() {
  const data = await api('/api/sessions');
  const sessions = data.sessions;
  const booked = sessions.filter(s => s.status === 'booked').length;
  const completed = sessions.filter(s => s.status === 'completed').length;
  const short = await api('/api/shortlist');
  const placed = new Set(short.shortlists.filter(x => x.status === 'selected').map(x => x.student_name)).size;
  el('statsCards').innerHTML = [
    { num: booked, lbl: 'Upcoming Sessions' },
    { num: completed, lbl: 'Completed Sessions' },
    { num: placed, lbl: 'Students Placed' },
    { num: sessions.length, lbl: 'Total Sessions' },
  ].map(s => `<div class="card"><div class="num">${s.num}</div><div class="lbl">${s.lbl}</div></div>`).join('');
}

async function loadSessions() {
  const data = await api('/api/sessions');
  const body = el('sessionsBody');
  if (!data.sessions.length) { body.innerHTML = '<tr><td colspan="6" class="empty">No sessions assigned yet.</td></tr>'; return; }
  body.innerHTML = data.sessions.map(s => `
    <tr>
      <td>${esc(s.student_name)}</td><td>${esc(s.rollno)}</td>
      <td>${esc(s.slot_time)}</td><td>${badge(s.status)}</td>
      <td class="muted">${esc(s.feedback || '-')}</td>
      <td>${s.status === 'booked'
        ? `<button class="btn small green" onclick="completeSession(${s.id})">Complete</button>`
        : ''}</td>
    </tr>`).join('');
}

async function completeSession(id) {
  const feedback = prompt('Feedback for the student (optional):');
  if (feedback === null) return;
  try {
    await api(`/api/sessions/${id}/complete`, { method: 'POST', body: JSON.stringify({ feedback }) });
    toast('Session marked completed');
    refresh();
  } catch (err) { toast(err.message, false); }
}

async function loadShortlist() {
  const data = await api('/api/shortlist');
  const body = el('shortlistBody');
  if (!data.shortlists.length) { body.innerHTML = '<tr><td colspan="7" class="empty">No shortlists yet.</td></tr>'; return; }
  body.innerHTML = data.shortlists.map(x => `
    <tr><td>${esc(x.company)}</td><td>${esc(x.role_title)}</td>
        <td>${esc(x.student_name)}</td><td>${esc(x.rollno)}</td>
        <td>${esc(x.branch)}</td><td>${Number(x.cgpa).toFixed(2)}</td>
        <td>${badge(x.status)}</td></tr>`).join('');
}

async function refresh() {
  await Promise.all([loadDashboard(), loadSessions(), loadShortlist()]);
}

(async () => {
  await guard(['counselor']);
  await refresh();
})();
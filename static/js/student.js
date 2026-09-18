let profile = null;

el('logoutBtn').addEventListener('click', logout);

document.querySelectorAll('#tabs button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('#tabs button').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.section').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    el(b.dataset.tab).classList.add('active');
  });
});

el('saveProfile').addEventListener('click', async () => {
  try {
    await api('/api/student/profile', {
      method: 'PUT',
      body: JSON.stringify({
        cgpa: parseFloat(el('pCgpa').value),
        backlogs: parseInt(el('pBacklogs').value || '0', 10),
        skills: el('pSkills').value.trim(),
        phone: el('pPhone').value.trim(),
        resume_url: el('pResume').value.trim(),
      }),
    });
    toast('Profile updated');
    loadProfile();
  } catch (err) { toast(err.message, false); }
});

el('bookSession').addEventListener('click', async () => {
  const counselor_id = el('counselorSelect').value;
  const slot_time = el('slotTime').value;
  if (!counselor_id || !slot_time) { toast('Pick a counselor and a slot time', false); return; }
  try {
    await api('/api/sessions/book', {
      method: 'POST',
      body: JSON.stringify({ counselor_id: parseInt(counselor_id, 10), slot_time }),
    });
    toast('Session booked');
    loadSessions();
  } catch (err) { toast(err.message, false); }
});

async function loadProfile() {
  const me = await api('/api/me');
  profile = me.profile;
  const stats = [
    { num: profile.cgpa.toFixed(2), lbl: 'CGPA' },
    { num: badge(profile.status), lbl: 'Placement Status' },
    { num: profile.backlogs, lbl: 'Backlogs' },
    { num: profile.academic_year, lbl: 'Year' },
    { num: profile.branch, lbl: 'Branch' },
  ];
  el('statsCards').innerHTML = stats.map(s =>
    `<div class="card"><div class="num">${s.num}</div><div class="lbl">${s.lbl}</div></div>`).join('');
  el('pCgpa').value = profile.cgpa;
  el('pBacklogs').value = profile.backlogs;
  el('pSkills').value = profile.skills || '';
  el('pPhone').value = profile.phone || '';
  el('pResume').value = profile.resume_url || '';
  return me;
}

async function loadDrives() {
  const data = await api('/api/drives');
  const body = el('drivesBody');
  if (!data.drives.length) { body.innerHTML = '<tr><td colspan="8" class="empty">No open drives match your profile right now.</td></tr>'; return; }
  body.innerHTML = data.drives.map(d => `
    <tr>
      <td>${esc(d.company)}</td>
      <td>${esc(d.role_title)}</td>
      <td>&#8377; ${Number(d.package).toFixed(2)} LPA</td>
      <td>
        <div class="chips">
          <span class="chip">CGPA &#8805; ${Number(d.min_cgpa).toFixed(2)}</span>
          <span class="chip">Year ${d.academic_year}</span>
          <span class="chip">Backlogs &#8804; ${d.max_backlogs}</span>
        </div>
      </td>
      <td class="muted">${esc(d.apply_deadline.replace(' ', '<br>'))}</td>
      <td>${esc(d.drive_date)}</td>
      <td class="muted">${esc(d.venue || '-')}</td>
      <td>
        ${d.applied
          ? '<button class="btn small" disabled>Applied</button>'
          : `<button class="btn small primary" onclick="applyTo(${d.drive_id}, this)">Apply</button>`}
      </td>
    </tr>`).join('');
}

async function applyTo(driveId, btn) {
  btn.disabled = true;
  btn.textContent = 'Applying...';
  try {
    await api(`/api/drives/${driveId}/apply`, { method: 'POST' });
    toast('Applied successfully!');
    loadDrives();
    loadApplications();
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Apply';
    toast(err.message, false);
  }
}

async function loadApplications() {
  const data = await api('/api/student/applications');
  const body = el('appsBody');
  if (!data.applications.length) {
    body.innerHTML = '<tr><td colspan="6" class="empty">You have not applied to any drive yet.</td></tr>';
    return;
  }
  body.innerHTML = data.applications.map(a => `
    <tr>
      <td>${esc(a.company)}</td>
      <td>${esc(a.role_title)}</td>
      <td>&#8377; ${Number(a.package_lpa).toFixed(2)} LPA</td>
      <td class="muted">${esc(a.applied_at)}</td>
      <td>${badge(a.drive_status)}</td>
      <td>${badge(a.application_status)}</td>
    </tr>`).join('');
}

async function loadCounselors() {
  const data = await api('/api/counselors');
  el('counselorSelect').innerHTML =
    '<option value="">-- Select counselor --</option>' +
    data.counselors.map(c => `<option value="${c.id}">${esc(c.name)} (${esc(c.specialization || 'General')})</option>`).join('');
}

async function loadSessions() {
  const data = await api('/api/sessions');
  const body = el('sessionsBody');
  if (!data.sessions.length) { body.innerHTML = '<tr><td colspan="5" class="empty">No counselling sessions yet.</td></tr>'; return; }
  body.innerHTML = data.sessions.map(s => `
    <tr>
      <td>${esc(s.counselor_name)}</td>
      <td>${esc(s.slot_time)}</td>
      <td>${badge(s.status)}</td>
      <td class="muted">${esc(s.feedback || '-')}</td>
      <td>
        ${s.status === 'booked'
          ? `<button class="btn small red" onclick="cancelSession(${s.id})">Cancel</button>`
          : ''}
      </td>
    </tr>`).join('');
}

async function cancelSession(id) {
  if (!confirm('Cancel this session?')) return;
  try { await api(`/api/sessions/${id}/cancel`, { method: 'POST' }); toast('Session cancelled'); loadSessions(); }
  catch (err) { toast(err.message, false); }
}

(async () => {
  await guard(['student']);
  await loadProfile();
  await Promise.all([loadDrives(), loadApplications(), loadCounselors(), loadSessions()]);
})();
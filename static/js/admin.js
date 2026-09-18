let drives = [];
let currentDriveId = null;
let currentDriveInfo = null;

el('logoutBtn').addEventListener('click', logout);

document.querySelectorAll('#tabs button').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('#tabs button').forEach(x => x.classList.remove('active'));
    document.querySelectorAll('.section').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    el(b.dataset.tab).classList.add('active');
  });
});

/* ---------------- Dashboard ---------------- */
async function loadDashboard() {
  const d = await api('/api/dashboard');
  const stats = d.stats;
  el('statsCards').innerHTML = [
    { num: stats.total_students, lbl: 'Total Students' },
    { num: stats.placed_students, lbl: 'Placed' },
    { num: stats.total_companies, lbl: 'Companies' },
    { num: stats.open_drives, lbl: 'Open Drives' },
    { num: stats.total_applications, lbl: 'Applications' },
    { num: stats.pending_sessions, lbl: 'Pending Counselling' },
  ].map(s => `<div class="card"><div class="num">${s.num}</div><div class="lbl">${s.lbl}</div></div>`).join('');

  el('reportBody').innerHTML = d.report.map(r => `
    <tr><td>${esc(r.company)}</td><td>${esc(r.role_title)}</td>
        <td>${r.applied_count}</td><td>${r.selected_count}</td></tr>`).join('')
    || '<tr><td colspan="4" class="empty">No data</td></tr>';

  el('recentBody').innerHTML = d.recent.map(r => `
    <tr><td>${esc(r.student)}</td><td>${esc(r.branch)}</td><td>${esc(r.company)}</td>
        <td>${esc(r.role_title)}</td><td>${badge(r.status)}</td><td class="muted">${esc(r.applied_at)}</td></tr>`).join('')
    || '<tr><td colspan="6" class="empty">No recent activity</td></tr>';
}

/* ---------------- Companies ---------------- */
el('addCompany').addEventListener('click', async () => {
  try {
    await api('/api/companies', { method: 'POST', body: JSON.stringify({
      name: el('cName').value.trim(), sector: el('cSector').value.trim(),
      website: el('cWeb').value.trim(), contact_email: el('cEmail').value.trim() }) });
    toast('Company added');
    ['cName', 'cSector', 'cWeb', 'cEmail'].forEach(i => el(i).value = '');
    refresh();
  } catch (err) { toast(err.message, false); }
});

async function loadCompanies() {
  const d = await api('/api/companies');
  el('companiesBody').innerHTML = d.companies.map(c => `
    <tr><td>${esc(c.name)}</td><td>${esc(c.sector || '-')}</td>
        <td>${c.website ? `<a href="${esc(c.website)}" target="_blank">${esc(c.website)}</a>` : '-'}</td>
        <td>${esc(c.contact_email || '-')}</td>
        <td><button class="btn small red" onclick="delCompany(${c.id})">Delete</button></td></tr>`).join('')
    || '<tr><td colspan="5" class="empty">No companies yet.</td></tr>';
}

async function delCompany(id) {
  if (!confirm('Delete this company and all its roles/drives?')) return;
  try { await api(`/api/companies/${id}`, { method: 'DELETE' }); toast('Deleted'); loadCompanies(); }
  catch (err) { toast(err.message, false); }
}

/* ---------------- Roles ---------------- */
el('addRole').addEventListener('click', async () => {
  const branches = [...document.querySelectorAll('#rBranches input:checked')].map(x => x.value);
  if (!el('rCompany').value || !el('rTitle').value.trim()) { toast('Company and title are required', false); return; }
  if (!branches.length) { toast('Select at least one branch', false); return; }
  try {
    await api('/api/roles', { method: 'POST', body: JSON.stringify({
      company_id: parseInt(el('rCompany').value, 10),
      title: el('rTitle').value.trim(),
      package_lpa: parseFloat(el('rPackage').value),
      vacancies: parseInt(el('rVacancies').value || '1', 10),
      description: el('rDesc').value.trim(),
      min_cgpa: parseFloat(el('rMinCgpa').value || '0'),
      max_backlogs: parseInt(el('rMaxBack').value || '0', 10),
      academic_year: el('rYear').value,
      branches,
      skills: el('rSkills').value.split(',').map(s => s.trim()).filter(Boolean),
    }) });
    toast('Role added');
    ['rTitle', 'rPackage', 'rSkills', 'rDesc'].forEach(i => el(i).value = '');
    el('rVacancies').value = '5'; el('rMinCgpa').value = ''; el('rMaxBack').value = '0';
    refresh();
  } catch (err) { toast(err.message, false); }
});

async function loadRoles() {
  const d = await api('/api/roles');
  el('rolesBody').innerHTML = d.roles.map(r => `
    <tr><td>${esc(r.company)}</td><td>${esc(r.title)}</td>
        <td>&#8377; ${Number(r.package_lpa).toFixed(2)}</td>
        <td>${Number(r.min_cgpa).toFixed(2)}</td><td>${r.academic_year}</td>
        <td><div class="chips">${(r.branches || '').split(',').map(b => `<span class="chip">${b}</span>`).join('')}</div></td>
        <td class="muted">${esc(r.skills || '-')}</td>
        <td><button class="btn small red" onclick="delRole(${r.id})">Delete</button></td></tr>`).join('')
    || '<tr><td colspan="8" class="empty">No roles yet.</td></tr>';
}

async function delRole(id) {
  if (!confirm('Delete this role (cascades to drives/applications)?')) return;
  try { await api(`/api/roles/${id}`, { method: 'DELETE' }); toast('Role deleted'); refresh(); }
  catch (err) { toast(err.message, false); }
}

/* ---------------- Drives ---------------- */
async function loadDrives() {
  drives = (await api('/api/drives')).drives;
  el('drivesBody').innerHTML = drives.map(d => `
    <tr><td><strong>${esc(d.company)}</strong> &#8212; ${esc(d.role_title)}</td>
        <td class="muted">${esc(d.apply_deadline)}</td><td>${esc(d.drive_date)}</td>
        <td class="muted">${esc(d.venue || '-')}</td>
        <td>${badge(d.status)}</td>
        <td>${d.applied_count}</td><td>${d.shortlisted_count}</td>
        <td>
          <button class="btn small ${d.status === 'open' ? 'amber' : 'primary'}"
                  onclick="toggleDriveStatus(${d.id})">${d.status === 'open' ? 'Close' : 'Reopen'}</button>
          <button class="btn small" onclick="openManager(${d.id})">Applicants</button>
          <button class="btn small red" onclick="delDrive(${d.id})">Delete</button>
        </td></tr>`).join('')
    || '<tr><td colspan="8" class="empty">No drives scheduled.</td></tr>';

  el('dRole').innerHTML = '<option value="">-- role --</option>' +
    (await api('/api/roles')).roles.map(r =>
      `<option value="${r.id}">${esc(r.company)} - ${esc(r.title)}</option>`).join('');
}

el('addDrive').addEventListener('click', async () => {
  const role_id = el('dRole').value;
  const apply_deadline = el('dDeadline').value;
  const drive_date = el('dDate').value;
  if (!role_id || !apply_deadline || !drive_date) { toast('Role, apply-by and drive date required', false); return; }
  try {
    await api('/api/drives', { method: 'POST', body: JSON.stringify({
      role_id: parseInt(role_id, 10), apply_deadline, drive_date,
      venue: el('dVenue').value.trim() }) });
    toast('Drive scheduled');
    refresh();
  } catch (err) { toast(err.message, false); }
});

async function toggleDriveStatus(id) {
  const d = drives.find(x => x.id === id);
  const status = d.status === 'open' ? 'closed' : 'open';
  try {
    await api(`/api/drives/${id}`, { method: 'PUT', body: JSON.stringify({ status }) });
    toast('Drive ' + status);
    refresh();
  } catch (err) { toast(err.message, false); }
}

async function delDrive(id) {
  if (!confirm('Delete this drive permanently?')) return;
  try { await api(`/api/drives/${id}`, { method: 'DELETE' }); toast('Drive deleted'); refresh(); }
  catch (err) { toast(err.message, false); }
}

/* ---------------- Applications / results ---------------- */
function openManager(id) {
  const tab = document.querySelector('[data-tab="tab-applications"]');
  document.querySelectorAll('#tabs button').forEach(x => x.classList.remove('active'));
  document.querySelectorAll('.section').forEach(x => x.classList.remove('active'));
  tab.classList.add('active');
  document.querySelector(`#tabs button[data-tab="tab-applications"]`).classList.add('active');
  el('selDrive').value = id;
  loadApplicants();
}

async function loadDriveOptions() {
  const d = await api('/api/drives');
  el('selDrive').innerHTML = d.drives.map(x =>
    `<option value="${x.id}">#${x.id} ${esc(x.company)} - ${esc(x.role_title)}</option>`).join('');
  el('sMinCgpa').value = '';
  el('applicantsBody').innerHTML = '';
  el('driveInfo').innerHTML = '';
}

el('loadDrive').addEventListener('click', loadApplicants);

async function loadApplicants() {
  currentDriveId = parseInt(el('selDrive').value || '0', 10);
  if (!currentDriveId) { toast('Select a drive first', false); return; }
  const [detail, data] = await Promise.all([
    api(`/api/drives/${currentDriveId}`),
    api(`/api/drives/${currentDriveId}/applications`),
  ]);
  currentDriveInfo = detail.drive;
  const d = currentDriveInfo;
  el('driveInfo').innerHTML =
    `<div class="chips">
       <span class="chip"><strong>${esc(d.company)} - ${esc(d.title)}</strong></span>
       <span class="chip">Package &#8377;${Number(d.package_lpa).toFixed(2)} LPA</span>
       <span class="chip">Vacancies: ${d.vacancies}</span>
       <span class="chip">Status: ${badge(d.drive_status)}</span>
     </div>`;
  const selected = data.applications.filter(a => a.status === 'selected').length;
  const filled = selected >= d.vacancies;
  el('vacancyNote').textContent = `Vacancies: ${d.vacancies} — filled: ${selected}${filled ? ' (FULL)' : ''}`;

  const tbody = el('applicantsBody');
  if (!data.applications.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">No applications for this drive yet.</td></tr>';
    return;
  }
  tbody.innerHTML = data.applications.map(a => `
    <tr>
      <td>${esc(a.rollno)}</td><td>${esc(a.name)}</td><td>${esc(a.branch)}</td>
      <td>${Number(a.cgpa).toFixed(2)}</td><td>${a.backlogs}</td>
      <td>${badge(a.status)}</td>
      <td>
        ${a.status === 'applied'
          ? `<button class="btn small primary" onclick="setResult(${a.student_id},'shortlist',this)">Shortlist</button>`
          : ''}
        ${(a.status === 'shortlisted' || a.status === 'applied') && !filled && d.drive_status === 'completed'
          ? `<button class="btn small green" onclick="setResult(${a.student_id},'selected',this)">Select</button>`
          : ''}
        ${(a.status === 'shortlisted' || a.status === 'applied') && d.drive_status === 'completed'
          ? `<button class="btn small red" onclick="setResult(${a.student_id},'rejected',this)">Reject</button>`
          : ''}
        ${d.drive_status === 'completed'
          ? `<span class="chip" style="background:#f1f5f9;color:#64748b;">drive completed</span>`
          : ''}
      </td>
    </tr>`).join('');
}

el('doShortlist').addEventListener('click', async () => {
  if (!currentDriveId) { toast('Load a drive first', false); return; }
  const min_cgpa = parseFloat(el('sMinCgpa').value || '0');
  try {
    await api(`/api/drives/${currentDriveId}/shortlist`, { method: 'POST', body: JSON.stringify({ min_cgpa }) });
    toast('Shortlist updated (trigger + procedure applied)');
    loadApplicants();
  } catch (err) { toast(err.message, false); }
});

async function setResult(studentId, status, btn) {
  if (status === 'selected' && !confirm('Confirm selection? This marks the student as PLACED.')) return;
  if (status === 'rejected' && !confirm('Reject this student?')) return;
  if (status === 'shortlist' && !confirm('Shortlist this student?')) return;
  btn.disabled = true;
  try {
    await api(`/api/drives/${currentDriveId}/results`, { method: 'POST', body: JSON.stringify({ student_id: studentId, status }) });
    toast(`Result recorded: ${status}`);
    loadApplicants();
  } catch (err) { toast(err.message, false); btn.disabled = false; }
}

async function refresh() {
  await Promise.all([loadDashboard(), loadCompanies(), loadRoles(), loadDrives(), loadDriveOptions()]);
}

(async () => {
  await guard(['admin']);
  await refresh();
})();
document.getElementById('regForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const msg = el('msg');
  const btn = e.target.querySelector('button');
  btn.disabled = true;
  msg.textContent = 'Creating account...';
  try {
    await api('/api/register', {
      method: 'POST',
      body: JSON.stringify({
        name: el('name').value.trim(),
        email: el('email').value.trim(),
        password: el('password').value,
        rollno: el('rollno').value.trim(),
        branch: el('branch').value,
        academic_year: el('academic_year').value,
        cgpa: parseFloat(el('cgpa').value),
        backlogs: parseInt(el('backlogs').value || '0', 10),
        skills: el('skills').value.trim(),
        phone: el('phone').value.trim(),
      }),
    });
    msg.className = 'msg ok';
    msg.textContent = 'Account created! Redirecting to login...';
    setTimeout(() => location.href = '/login.html', 900);
  } catch (err) {
    msg.className = 'msg error';
    msg.textContent = err.message;
    btn.disabled = false;
  }
});
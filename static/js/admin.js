// Admin Dashboard Interactivity

document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    loadRegistrations();
    loadUsers();
    loadCourses();
    loadSettings();
    initAdminChat();

    // Event listeners
    document.getElementById('statusFilter')?.addEventListener('change', loadRegistrations);
    document.getElementById('searchInput')?.addEventListener('input', debounce(loadRegistrations, 300));
    document.getElementById('newCourseBtn')?.addEventListener('click', openCourseModal);
    document.getElementById('courseForm')?.addEventListener('submit', handleSaveCourse);
    document.getElementById('settingsForm')?.addEventListener('submit', handleSaveSettings);
    document.getElementById('khqrFileInput')?.addEventListener('change', handleKhqrUpload);
    document.getElementById('registrationForm')?.addEventListener('submit', handleSaveRegistration);
    document.getElementById('newUserBtn')?.addEventListener('click', openUserModal);
    document.getElementById('userForm')?.addEventListener('submit', handleSaveUser);
    document.getElementById('userSearchInput')?.addEventListener('input', debounce(loadUsers, 300));
    document.getElementById('courseFileInput')?.addEventListener('change', handleCourseImageUpload);
});

function debounce(func, timeout = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => { func.apply(this, args); }, timeout);
    };
}

async function loadDashboardStats() {
    try {
        const res = await fetch('/api/v1/admin/stats');
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById('statTotalReg').innerText = data.total_registrations;
        document.getElementById('statPaidReg').innerText = data.paid_registrations;
        document.getElementById('statPendingReg').innerText = data.pending_registrations;
        document.getElementById('statRevenueUsd').innerText = `$${data.revenue.usd}`;
        document.getElementById('statRevenueKhr').innerText = `${data.revenue.khr.toLocaleString()} KHR`;
    } catch (e) {
        console.error("Failed to load stats:", e);
    }
}

async function loadRegistrations() {
    const status = document.getElementById('statusFilter')?.value || 'ALL';
    const search = document.getElementById('searchInput')?.value || '';

    try {
        const res = await fetch(`/api/v1/admin/registrations?status_filter=${status}&search=${encodeURIComponent(search)}`);
        if (!res.ok) return;

        const data = await res.json();
        const tbody = document.getElementById('registrationsTbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        if (data.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#94a3b8; padding:2rem;">ពុំមានទិន្នន័យចុះឈ្មោះទេ (No registrations found)</td></tr>`;
            return;
        }

        const statusBadges = {
            PAID: `<span class="status-badge status-paid">✓ PAID</span>`,
            SUBMITTED: `<span class="status-badge status-submitted">🧾 SUBMITTED</span>`,
            REJECTED: `<span class="status-badge status-rejected">✕ REJECTED</span>`,
            PENDING: `<span class="status-badge status-pending"><span class="pulse-dot"></span> PENDING</span>`
        };

        data.forEach(r => {
            const tr = document.createElement('tr');
            const statusBadge = statusBadges[r.status] || statusBadges.PENDING;

            // Opens the receipt full size so Admin can check the slip before approving.
            const receiptCell = r.receipt_image_url
                ? `<button onclick="openReceiptModal(${r.id})" class="btn btn-outline btn-sm">🧾 មើល (View)</button>`
                : `<span style="color:#64748b; font-size:0.8rem;">—</span>`;

            let actionBtnsHtml = '';
            if (r.status === 'PAID' && r.invite_link) {
                const codeChip = r.access_code
                    ? `<div style="display:inline-flex; align-items:center; gap:0.2rem; font-size:0.78rem; color:${r.code_used ? '#64748b' : '#10b981'}; background:rgba(16,185,129,0.1); padding:0.2rem 0.5rem; border-radius:6px; border:1px solid rgba(16,185,129,0.2);">
                         🔑 <code style="letter-spacing:0.1em; font-weight:bold;">${escapeHtml(r.access_code)}</code>
                         ${r.code_used ? '(ប្រើរួច)' : `<button onclick="copyAccessCode('${escapeHtml(r.access_code)}')" class="btn btn-outline btn-sm" style="padding:0.15rem 0.4rem;" title="Copy Code">📋</button>`}
                       </div>`
                    : '';
                actionBtnsHtml = `<a href="${r.invite_link}" target="_blank" class="btn btn-outline btn-sm">🔗 View Link</a>${codeChip}`;
            } else if (r.status === 'SUBMITTED') {
                actionBtnsHtml = `
                    <button onclick="openReceiptModal(${r.id})" class="btn btn-primary btn-sm">🔍 ពិនិត្យ (Review)</button>
                    <button onclick="rejectRegistration(${r.id})" class="btn btn-outline btn-sm" style="color:#ef4444; border-color:rgba(239,68,68,0.3);">✕ Reject</button>
                `;
            } else {
                actionBtnsHtml = `<button onclick="approveRegistration(${r.id})" class="btn btn-primary btn-sm">✓ Accept</button>`;
            }

            actionBtnsHtml += `
                <button onclick="editRegistration(${r.id})" class="btn btn-outline btn-sm">✏️ Edit</button>
                <button onclick="deleteRegistration(${r.id}, '${r.invoice_id}')" class="btn btn-outline btn-sm" style="color:#ef4444; border-color:rgba(239,68,68,0.3);">🗑️ Delete</button>
            `;

            const actionCell = `<div style="display:flex; align-items:center; gap:0.4rem; flex-wrap:nowrap;">${actionBtnsHtml}</div>`;

            tr.innerHTML = `
                <td style="white-space:nowrap;"><code>${r.invoice_id}</code></td>
                <td><strong>${escapeHtml(r.student_name)}</strong></td>
                <td style="white-space:nowrap;">${escapeHtml(r.phone_number)}</td>
                <td style="white-space:nowrap;">@${escapeHtml(r.telegram_username.replace('@', ''))}</td>
                <td style="min-width:180px;">${escapeHtml(r.course_title)}</td>
                <td style="white-space:nowrap;"><strong>${r.amount} ${r.currency}</strong></td>
                <td>${receiptCell}</td>
                <td style="white-space:nowrap;">${statusBadge}</td>
                <td>${actionCell}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed loading registrations:", e);
    }
}

async function copyAccessCode(code) {
    try {
        await navigator.clipboard.writeText(code);
        alert(`បានចម្លងលេខកូដ! (Code copied)\n\n${code}\n\nសូមផ្ញើទៅសិស្សតាម Telegram។`);
    } catch (e) {
        prompt('សូមចម្លងលេខកូដនេះផ្ញើទៅសិស្ស (Copy this code):', code);
    }
}

async function approveRegistration(regId) {
    // Warn when approving a student who has not sent any proof of payment yet.
    try {
        const detail = await (await fetch(`/api/v1/admin/registrations/${regId}`)).json();
        if (!detail.receipt_image_url &&
            !confirm("⚠️ សិស្សនេះមិនទាន់ Upload វិក័យបត្រទេ!\nតើអ្នកនៅតែចង់អនុម័តឬ?\n\n(This student has NOT uploaded a receipt. Approve anyway?)")) return;
    } catch (e) {
        console.error(e);
    }

    if (!confirm("តើអ្នកពិតជាចង់អនុម័តការបង់ប្រាក់នេះមែនទេ? Link ក្រុមនឹងផ្ញើទៅសិស្សភ្លាមៗ។ (Accept this payment and unlock the group link?)")) return;

    try {
        const res = await fetch(`/api/v1/admin/registrations/${regId}/approve`, { method: 'POST' });
        if (res.ok) {
            closeReceiptModal();
            // Surface the code straight away: if the student already closed the
            // app, this is the only way they can reach the group link.
            let codeNote = '';
            try {
                const detail = await (await fetch(`/api/v1/admin/registrations/${regId}`)).json();
                const list = await (await fetch('/api/v1/admin/registrations?status_filter=ALL&search=')).json();
                const row = list.find(x => x.id === regId);
                if (row && row.access_code) {
                    codeNote = `\n\n🔑 លេខកូដសម្រាប់សិស្ស: ${row.access_code}\nផ្ញើលេខនេះទៅសិស្សបើគាត់បិទកម្មវិធីរួច។`;
                }
            } catch (e) { console.error(e); }

            alert(`អនុម័តជោគជ័យ! Telegram Link ត្រូវបានបង្កើត។ (Accepted successfully!)${codeNote}`);
            loadDashboardStats();
            loadRegistrations();
        } else {
            alert("Approve failed");
        }
    } catch (e) {
        console.error(e);
    }
}

async function rejectRegistration(regId) {
    if (!confirm("តើអ្នកពិតជាចង់បដិសេធវិក័យបត្រនេះមែនទេ? សិស្សនឹងត្រូវ Upload ម្តងទៀត។ (Reject this receipt?)")) return;

    try {
        const res = await fetch(`/api/v1/admin/registrations/${regId}/reject`, { method: 'POST' });
        if (res.ok) {
            closeReceiptModal();
            loadDashboardStats();
            loadRegistrations();
        } else {
            alert("Reject failed");
        }
    } catch (e) {
        console.error(e);
    }
}

// ---------- User accounts (created by Admin only) ----------

async function loadUsers() {
    const search = document.getElementById('userSearchInput')?.value || '';
    try {
        const res = await fetch(`/api/v1/admin/users?search=${encodeURIComponent(search)}`);
        if (!res.ok) return;

        const users = await res.json();
        const tbody = document.getElementById('usersTbody');
        if (!tbody) return;

        tbody.innerHTML = '';
        if (users.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:2rem;">ពុំមានគណនីទេ (No accounts found)</td></tr>`;
            return;
        }

        users.forEach(u => {
            const roleBadge = u.role === 'ADMIN'
                ? `<span class="status-badge status-paid">🛡️ ADMIN</span>`
                : `<span class="status-badge status-submitted">🎓 STUDENT</span>`;
            const activeBadge = u.is_active
                ? `<span class="status-badge status-paid">✓ Active</span>`
                : `<span class="status-badge status-rejected">✕ Disabled</span>`;

            // Hidden until clicked, so the password is not on show over someone's shoulder.
            const pwCell = u.password_plain
                ? `<span id="pw-${u.id}" data-pw="${escapeHtml(u.password_plain)}" data-shown="0"
                         style="font-family:monospace; letter-spacing:0.1em;">••••••••</span>
                   <button onclick="togglePassword(${u.id})" class="btn btn-outline btn-sm" style="margin-left:0.4rem;">👁️</button>
                   <button onclick="copyPassword(${u.id})" class="btn btn-outline btn-sm">📋</button>`
                : `<span style="color:#64748b; font-size:0.8rem;">— (មិនអាចអានបាន)</span>`;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="white-space:nowrap;"><code>${u.id}</code></td>
                <td><strong>${escapeHtml(u.username)}</strong></td>
                <td style="white-space:nowrap;">${pwCell}</td>
                <td>${escapeHtml(u.full_name || '—')}</td>
                <td style="white-space:nowrap;">${roleBadge}</td>
                <td style="white-space:nowrap;">${activeBadge}</td>
                <td>
                    <div style="display:flex; align-items:center; gap:0.4rem; flex-wrap:nowrap;">
                        <button onclick="editUser(${u.id})" class="btn btn-outline btn-sm">✏️ Edit</button>
                        <button onclick="deleteUser(${u.id}, '${escapeHtml(u.username)}')" class="btn btn-outline btn-sm" style="color:#ef4444; border-color:rgba(239,68,68,0.3);">🗑️ Delete</button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error('Failed loading users:', e);
    }
}

function togglePassword(userId) {
    const el = document.getElementById(`pw-${userId}`);
    if (!el) return;
    const shown = el.getAttribute('data-shown') === '1';
    el.textContent = shown ? '••••••••' : el.getAttribute('data-pw');
    el.setAttribute('data-shown', shown ? '0' : '1');
}

async function copyPassword(userId) {
    const el = document.getElementById(`pw-${userId}`);
    if (!el) return;
    const pw = el.getAttribute('data-pw');
    try {
        await navigator.clipboard.writeText(pw);
        alert(`បានចម្លងលេខសម្ងាត់ហើយ! (Password copied)\n\n${pw}`);
    } catch (e) {
        // clipboard needs HTTPS or localhost; show it so Admin can copy by hand.
        prompt('សូមចម្លងលេខសម្ងាត់នេះ (Copy this password):', pw);
    }
}

function generatePassword() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789';
    const bytes = new Uint32Array(12);
    crypto.getRandomValues(bytes);
    document.getElementById('userPasswordInput').value =
        Array.from(bytes, b => chars[b % chars.length]).join('');
}

function openUserModal() {
    document.getElementById('userModalTitle').innerText = 'បង្កើតគណនីថ្មី (New User)';
    document.getElementById('userIdInput').value = '';
    document.getElementById('userUsernameInput').value = '';
    document.getElementById('userFullNameInput').value = '';
    document.getElementById('userPhoneInput').value = '';
    document.getElementById('userTelegramInput').value = '';
    document.getElementById('userRoleInput').value = 'STUDENT';
    document.getElementById('userActiveInput').value = 'true';
    document.getElementById('userPasswordHint').innerText = '*';
    document.getElementById('userPasswordNote').innerText =
        'សូមចម្លងលេខសម្ងាត់នេះផ្ញើទៅសិស្ស — វាមិនអាចមើលឃើញវិញបានទេក្រោយរក្សាទុក។';
    generatePassword();
    document.getElementById('userModal').classList.add('active');
}

async function editUser(userId) {
    try {
        const res = await fetch(`/api/v1/admin/users/${userId}`);
        if (!res.ok) return alert('រកមិនឃើញគណនីនេះទេ (User not found)');
        const u = await res.json();

        document.getElementById('userModalTitle').innerText = `កែប្រែគណនី: ${u.username}`;
        document.getElementById('userIdInput').value = u.id;
        document.getElementById('userUsernameInput').value = u.username;
        document.getElementById('userPasswordInput').value = '';
        document.getElementById('userFullNameInput').value = u.full_name || '';
        document.getElementById('userPhoneInput').value = u.phone_number || '';
        document.getElementById('userTelegramInput').value = u.telegram_username || '';
        document.getElementById('userRoleInput').value = u.role;
        document.getElementById('userActiveInput').value = String(u.is_active);
        document.getElementById('userPasswordHint').innerText = '(ទុកទទេ = មិនប្តូរ)';
        document.getElementById('userPasswordNote').innerText =
            'ទុកឲ្យទទេបើមិនចង់ប្តូរលេខសម្ងាត់។ បំពេញថ្មីដើម្បី Reset ជូនសិស្ស។';

        document.getElementById('userModal').classList.add('active');
    } catch (e) {
        console.error(e);
    }
}

async function handleSaveUser(e) {
    e.preventDefault();
    const id = document.getElementById('userIdInput').value;
    const password = document.getElementById('userPasswordInput').value;

    if (!id && !password) return alert('ត្រូវការលេខសម្ងាត់សម្រាប់គណនីថ្មី (A password is required for a new account)');

    const payload = {
        username: document.getElementById('userUsernameInput').value.trim(),
        full_name: document.getElementById('userFullNameInput').value.trim(),
        phone_number: document.getElementById('userPhoneInput').value.trim(),
        telegram_username: document.getElementById('userTelegramInput').value.trim(),
        role: document.getElementById('userRoleInput').value
    };
    if (password) payload.password = password;
    if (id) payload.is_active = document.getElementById('userActiveInput').value === 'true';

    try {
        const res = await fetch(id ? `/api/v1/admin/users/${id}` : '/api/v1/admin/users', {
            method: id ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
            document.getElementById('userModal').classList.remove('active');
            // Shown once: the plain password is never retrievable after this.
            alert(password
                ? `${data.message}\n\nUsername: ${payload.username}\nPassword: ${password}\n\nសូមចម្លងផ្ញើទៅសិស្ស!`
                : data.message);
            loadUsers();
        } else {
            alert(`Failed: ${data.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
        alert('Connection error while saving the account.');
    }
}

async function deleteUser(userId, username) {
    if (!confirm(`តើអ្នកពិតជាចង់លុបគណនី "${username}" មែនទេ?\n\n(Delete this account? Their paid registrations are kept.)`)) return;

    try {
        const res = await fetch(`/api/v1/admin/users/${userId}`, { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            loadUsers();
        } else {
            alert(`Delete failed: ${data.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
    }
}

// ---------- Receipt review ----------

async function openReceiptModal(regId) {
    try {
        const res = await fetch(`/api/v1/admin/registrations/${regId}`);
        if (!res.ok) return alert('រកមិនឃើញការចុះឈ្មោះនេះទេ (Registration not found)');
        const r = await res.json();

        document.getElementById('receiptModalInvoice').innerText = r.invoice_id;
        document.getElementById('receiptModalStudent').innerText = `${r.student_name} · ${r.phone_number} · @${(r.telegram_username || '').replace('@', '')}`;
        document.getElementById('receiptModalAmount').innerText = `${r.amount} ${r.currency}`;

        const img = document.getElementById('receiptModalImg');
        const empty = document.getElementById('receiptModalEmpty');
        if (r.receipt_image_url) {
            img.src = r.receipt_image_url + '?t=' + Date.now();
            img.style.display = 'block';
            empty.style.display = 'none';
        } else {
            img.style.display = 'none';
            empty.style.display = 'block';
        }

        // Approve/reject straight from the preview, so the slip is always seen first.
        document.getElementById('receiptAcceptBtn').onclick = () => approveRegistration(regId);
        document.getElementById('receiptRejectBtn').onclick = () => rejectRegistration(regId);
        document.getElementById('receiptAcceptBtn').style.display = r.status === 'PAID' ? 'none' : 'inline-flex';
        document.getElementById('receiptRejectBtn').style.display = r.status === 'PAID' ? 'none' : 'inline-flex';

        document.getElementById('receiptModal').classList.add('active');
    } catch (e) {
        console.error(e);
    }
}

function closeReceiptModal() {
    document.getElementById('receiptModal').classList.remove('active');
}

// ---------- Edit / delete a student registration ----------

async function editRegistration(regId) {
    try {
        const res = await fetch(`/api/v1/admin/registrations/${regId}`);
        if (!res.ok) return alert('រកមិនឃើញការចុះឈ្មោះនេះទេ (Registration not found)');
        const r = await res.json();

        // Fill the course dropdown from the live course list before selecting the current one.
        const courseSelect = document.getElementById('regCourseInput');
        courseSelect.innerHTML = '';
        const courses = await (await fetch('/api/v1/courses?active_only=false')).json();
        courses.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.textContent = c.title;
            courseSelect.appendChild(opt);
        });

        document.getElementById('regIdInput').value = r.id;
        document.getElementById('regInvoiceLabel').innerText = r.invoice_id;
        document.getElementById('regNameInput').value = r.student_name;
        document.getElementById('regPhoneInput').value = r.phone_number;
        document.getElementById('regTelegramInput').value = (r.telegram_username || '').replace('@', '');
        courseSelect.value = r.course_id;
        document.getElementById('regCurrencyInput').value = r.currency;

        document.getElementById('registrationModal').classList.add('active');
    } catch (e) {
        console.error(e);
    }
}

async function handleSaveRegistration(e) {
    e.preventDefault();
    const id = document.getElementById('regIdInput').value;

    const payload = {
        student_name: document.getElementById('regNameInput').value.trim(),
        phone_number: document.getElementById('regPhoneInput').value.trim(),
        telegram_username: document.getElementById('regTelegramInput').value.trim(),
        course_id: parseInt(document.getElementById('regCourseInput').value),
        currency: document.getElementById('regCurrencyInput').value
    };

    try {
        const res = await fetch(`/api/v1/admin/registrations/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            document.getElementById('registrationModal').classList.remove('active');
            alert('បានរក្សាទុកព័ត៌មានសិស្សជោគជ័យ! (Student updated successfully)');
            loadDashboardStats();
            loadRegistrations();
        } else {
            const err = await res.json();
            alert(`Update failed: ${err.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
        alert('Connection error while saving.');
    }
}

async function deleteRegistration(regId, invoiceId) {
    if (!confirm(`តើអ្នកពិតជាចង់លុប ${invoiceId} មែនទេ?\nទិន្នន័យ វិក័យបត្រ និង Link ក្រុម នឹងបាត់ជាអចិន្ត្រៃយ៍។\n\n(Permanently delete this registration, its receipt and group link?)`)) return;

    try {
        const res = await fetch(`/api/v1/admin/registrations/${regId}`, { method: 'DELETE' });
        if (res.ok) {
            alert('បានលុបជោគជ័យ! (Deleted successfully)');
            loadDashboardStats();
            loadRegistrations();
        } else {
            const err = await res.json();
            alert(`Delete failed: ${err.detail || 'Unknown error'}`);
        }
    } catch (e) {
        console.error(e);
        alert('Connection error while deleting.');
    }
}

async function loadCourses() {
    try {
        const res = await fetch('/api/v1/courses?active_only=false');
        if (!res.ok) return;

        const courses = await res.json();
        const container = document.getElementById('adminCourseList');
        if (!container) return;

        container.innerHTML = '';
        courses.forEach(c => {
            const card = document.createElement('div');
            card.className = 'course-card';

            const statusBadge = c.is_active
                ? `<span class="badge-online" style="font-size:0.75rem;"><span class="dot-online"></span> Active</span>`
                : `<span class="badge-offline" style="background:rgba(245,158,11,0.2); color:#f59e0b; border:1px solid rgba(245,158,11,0.4); font-size:0.75rem;"><span class="dot-offline" style="background:#f59e0b;"></span> Coming Soon</span>`;

            const groupBadge = c.telegram_group_link
                ? `<div style="font-size:0.78rem; color:#38bdf8; margin-top:0.35rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(c.telegram_group_link)}">🔗 Group: ${escapeHtml(c.telegram_group_link)}</div>`
                : `<div style="font-size:0.78rem; color:#94a3b8; margin-top:0.35rem;">🔗 Telegram Group: System Default</div>`;

            card.innerHTML = `
                ${c.image_url ? `<img src="${escapeHtml(c.image_url)}" alt="${escapeHtml(c.title)}" style="width:100%; height:150px; object-fit:cover; border-radius:var(--radius-md) var(--radius-md) 0 0;">` : ''}
                <div class="course-body">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <h3 class="course-title" style="margin-bottom:0; flex:1;">${escapeHtml(c.title)}</h3>
                        ${statusBadge}
                    </div>
                    <p class="course-desc">${escapeHtml(c.description || '')}</p>
                    <div style="margin-bottom:0.5rem; font-weight:bold; color:#10b981;">
                        $${c.price_usd} / ${c.price_khr.toLocaleString()} KHR
                    </div>
                    ${groupBadge}
                    <div style="display:flex; gap:0.5rem; margin-top:1rem;">
                        <button onclick="editCourse(${c.id})" class="btn btn-outline btn-sm">✏️ កែប្រែ (Edit)</button>
                        <button onclick="deleteCourse(${c.id})" class="btn btn-outline btn-sm" style="color:#ef4444; border-color:rgba(239,68,68,0.3);">🗑️ លុប (Delete)</button>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Failed loading courses:", e);
    }
}

async function handleCourseImageUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    const note = document.getElementById('courseImageNote');
    note.innerText = '⌛ កំពុង Upload...';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/v1/admin/course-image', { method: 'POST', body: formData });
        const data = await res.json();

        if (!res.ok) {
            note.innerText = `Upload failed: ${data.detail || 'Unknown error'}`;
            return;
        }

        // Held in a hidden field and sent with the course when it is saved.
        document.getElementById('courseImageUrlInput').value = data.image_url;
        showCoursePreview(data.image_url);
        note.innerText = '✅ Upload ជោគជ័យ! សូមចុច "រក្សាទុក" ដើម្បីបញ្ចប់។';
    } catch (err) {
        console.error(err);
        note.innerText = 'Connection error while uploading.';
    }
}

function showCoursePreview(url) {
    const img = document.getElementById('coursePreviewImg');
    if (!img) return;
    if (url) {
        img.src = url + (url.startsWith('/static/') ? '?t=' + Date.now() : '');
        img.style.display = 'block';
    } else {
        img.removeAttribute('src');
        img.style.display = 'none';
    }
}

function openCourseModal() {
    document.getElementById('courseModalTitle').innerText = 'បន្ថែមវគ្គសិក្សាថ្មី (Add New Course)';
    document.getElementById('courseIdInput').value = '';
    document.getElementById('courseImageUrlInput').value = '';
    document.getElementById('courseFileInput').value = '';
    document.getElementById('courseImageNote').innerText = 'JPG, PNG ឬ WEBP។ រូបនេះបង្ហាញនៅលើកាតវគ្គសិក្សាដល់សិស្ស។';
    showCoursePreview('');
    document.getElementById('courseTitleInput').value = '';
    document.getElementById('courseDescInput').value = '';
    document.getElementById('courseUsdInput').value = '';
    document.getElementById('courseKhrInput').value = '';
    document.getElementById('courseDurationInput').value = '4 Weeks';
    const groupLinkInput = document.getElementById('courseGroupLinkInput');
    if (groupLinkInput) groupLinkInput.value = '';
    const activeCheck = document.getElementById('courseIsActiveInput');
    if (activeCheck) activeCheck.checked = true;
    document.getElementById('courseModal').classList.add('active');
}

async function editCourse(id) {
    const res = await fetch(`/api/v1/courses/${id}`);
    if (!res.ok) return;
    const c = await res.json();

    document.getElementById('courseModalTitle').innerText = 'កែប្រែវគ្គសិក្សា (Edit Course)';
    document.getElementById('courseIdInput').value = c.id;
    document.getElementById('courseTitleInput').value = c.title;
    document.getElementById('courseDescInput').value = c.description || '';
    document.getElementById('courseUsdInput').value = c.price_usd;
    document.getElementById('courseKhrInput').value = c.price_khr;
    document.getElementById('courseDurationInput').value = c.duration || '4 Weeks';
    const groupLinkInput = document.getElementById('courseGroupLinkInput');
    if (groupLinkInput) groupLinkInput.value = c.telegram_group_link || '';

    const activeCheck = document.getElementById('courseIsActiveInput');
    if (activeCheck) activeCheck.checked = c.is_active;

    document.getElementById('courseImageUrlInput').value = c.image_url || '';
    document.getElementById('courseFileInput').value = '';
    document.getElementById('courseImageNote').innerText = c.image_url
        ? 'ជ្រើសរូបថ្មីដើម្បីជំនួស ឬទុកដដែលបើមិនចង់ប្តូរ។'
        : 'JPG, PNG ឬ WEBP។ រូបនេះបង្ហាញនៅលើកាតវគ្គសិក្សាដល់សិស្ស។';
    showCoursePreview(c.image_url || '');

    document.getElementById('courseModal').classList.add('active');
}

async function handleSaveCourse(e) {
    e.preventDefault();
    const id = document.getElementById('courseIdInput').value;
    const groupLinkInput = document.getElementById('courseGroupLinkInput');
    const activeCheck = document.getElementById('courseIsActiveInput');

    const payload = {
        title: document.getElementById('courseTitleInput').value,
        description: document.getElementById('courseDescInput').value,
        price_usd: parseFloat(document.getElementById('courseUsdInput').value),
        price_khr: parseFloat(document.getElementById('courseKhrInput').value),
        duration: document.getElementById('courseDurationInput').value,
        image_url: document.getElementById('courseImageUrlInput').value || null,
        telegram_group_link: groupLinkInput ? (groupLinkInput.value.trim() || null) : null,
        is_active: activeCheck ? activeCheck.checked : true
    };

    const url = id ? `/api/v1/courses/${id}` : '/api/v1/courses';
    const method = id ? 'PUT' : 'POST';

    const res = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        document.getElementById('courseModal').classList.remove('active');
        loadCourses();
    } else {
        alert('Failed saving course');
    }
}

async function deleteCourse(id) {
    if (!confirm("តើអ្នកពិតជាចង់លុបវគ្គសិក្សានេះមែនទេ? (Delete course?)")) return;
    const res = await fetch(`/api/v1/courses/${id}`, { method: 'DELETE' });
    if (res.ok) loadCourses();
}

async function loadSettings() {
    try {
        const res = await fetch('/api/v1/admin/settings');
        if (!res.ok) return;
        const s = await res.json();

        document.getElementById('settingTelegramLink').value = s.TELEGRAM_CONTACT_LINK || '';
        document.getElementById('settingGroupLink').value = s.TELEGRAM_GROUP_LINK || '';
        document.getElementById('settingPhone').value = s.CONTACT_PHONE || '';

        const preview = document.getElementById('khqrPreviewImg');
        if (preview && s.KHQR_IMAGE_URL) {
            preview.src = s.KHQR_IMAGE_URL;
            preview.style.display = 'block';
        }
    } catch (e) {
        console.error(e);
    }
}

async function handleSaveSettings(e) {
    e.preventDefault();
    const payload = {
        TELEGRAM_CONTACT_LINK: document.getElementById('settingTelegramLink').value,
        TELEGRAM_GROUP_LINK: document.getElementById('settingGroupLink').value,
        CONTACT_PHONE: document.getElementById('settingPhone').value
    };

    const res = await fetch('/api/v1/admin/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });

    if (res.ok) {
        alert("បានរក្សាទុកការកំណត់ជោគជ័យ! (Settings saved successfully)");
    } else {
        alert("Failed to save settings");
    }
}

async function handleKhqrUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/v1/admin/settings/khqr-upload', {
            method: 'POST',
            body: formData
        });

        if (res.ok) {
            const data = await res.json();
            const preview = document.getElementById('khqrPreviewImg');
            if (preview) {
                preview.src = data.khqr_image_url + '?t=' + Date.now();
                preview.style.display = 'block';
            }
            alert("បាន Upload រូប KHQR ជោគជ័យ! (KHQR image uploaded successfully)");
        } else {
            const err = await res.json();
            alert(`Upload failed: ${err.detail || 'Unknown error'}`);
        }
    } catch (err) {
        console.error(err);
        alert('Upload failed');
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

// ---------- Admin Live Chat ----------

let activeStudentUserId = null;

function initAdminChat() {
    const refreshBtn = document.getElementById('refreshAdminChatBtn');
    const chatForm = document.getElementById('adminChatForm');
    const clearHistoryBtn = document.getElementById('clearAdminChatHistoryBtn');

    loadAdminConversations();

    // Poll conversations & active messages every 4 seconds
    setInterval(() => {
        loadAdminConversations();
        if (activeStudentUserId) {
            loadAdminActiveChatMessages(activeStudentUserId, false);
        }
    }, 4000);

    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadAdminConversations();
            if (activeStudentUserId) loadAdminActiveChatMessages(activeStudentUserId, true);
        });
    }

    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', async () => {
            if (!activeStudentUserId) return alert('សូមជ្រើសរើសសិស្សជាមុន (Select a student first)');
            if (!confirm('តើអ្នកប្រាកដជាចង់លុបប្រវត្តិឆាតទាំងអស់របស់សិស្សនេះមែនទេ? (Clear all chat history for this student?)')) return;

            try {
                const res = await fetch(`/api/v1/chat/history?student_id=${activeStudentUserId}`, { method: 'DELETE' });
                if (res.ok) {
                    loadAdminActiveChatMessages(activeStudentUserId, true);
                    loadAdminConversations();
                } else {
                    alert('មិនអាចលុបប្រវត្តិឆាតបានទេ');
                }
            } catch (e) {
                console.error("Admin clear chat error:", e);
            }
        });
    }

    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!activeStudentUserId) return alert('សូមជ្រើសរើសសិស្សដើម្បីផ្ញើសារ (Select a student first)');

            const input = document.getElementById('adminChatInput');
            const msg = input.value.trim();
            if (!msg) return;

            const sendBtn = document.getElementById('adminChatSendBtn');
            if (sendBtn) sendBtn.disabled = true;

            try {
                const res = await fetch('/api/v1/chat/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        message: msg,
                        student_user_id: activeStudentUserId
                    })
                });

                if (res.ok) {
                    input.value = '';
                    loadAdminActiveChatMessages(activeStudentUserId, true);
                    loadAdminConversations();
                } else {
                    const err = await res.json();
                    alert(`សារមិនអាចផ្ញើបាន: ${err.detail || 'Error'}`);
                }
            } catch (e) {
                console.error("Admin chat send error:", e);
            } finally {
                if (sendBtn) sendBtn.disabled = false;
            }
        });
    }
}

async function loadAdminConversations() {
    const list = document.getElementById('adminConvList');
    if (!list) return;

    try {
        const res = await fetch('/api/v1/chat/conversations');
        if (!res.ok) return;

        const convs = await res.json();

        if (convs.length === 0) {
            list.innerHTML = `
                <div style="text-align:center; color:#94a3b8; padding:2rem; font-size:0.85rem;">
                    💬 មិនទាន់មានសារពីសិស្សនៅឡើយទេ
                </div>
            `;
            return;
        }

        list.innerHTML = '';
        convs.forEach(c => {
            const item = document.createElement('div');
            item.className = `conv-item ${c.student_id === activeStudentUserId ? 'active' : ''}`;
            item.onclick = () => selectStudentConversation(c.student_id, c.full_name, c.phone_number, c.telegram_username, c.is_online);

            const unreadBadge = c.unread_count > 0
                ? `<span class="badge-unread">${c.unread_count} ថ្មី</span>`
                : '';

            const statusBadge = c.is_online
                ? `<span class="badge-online"><span class="dot-online"></span> Online</span>`
                : `<span class="badge-offline"><span class="dot-offline"></span> Offline</span>`;

            item.innerHTML = `
                <div class="conv-item-header">
                    <strong style="color:#fff; font-size:0.95rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;">${escapeHtml(c.full_name)}</strong>
                    <div class="conv-item-badges">
                        ${statusBadge}
                        ${unreadBadge}
                    </div>
                </div>
                <div style="font-size:0.82rem; color:#60a5fa; margin-bottom:0.35rem; word-break:break-all;">
                    👤 @${escapeHtml(c.username)} · 📞 ${escapeHtml(c.phone_number)}
                </div>
                <div style="font-size:0.83rem; color:var(--text-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                    💬 ${escapeHtml(c.latest_message || '—')}
                </div>
                <div style="font-size:0.72rem; color:#64748b; margin-top:0.25rem; text-align:right;">
                    ${c.latest_time}
                </div>
            `;
            list.appendChild(item);
        });
    } catch (e) {
        console.error("Error loading admin conversations:", e);
    }
}

function selectStudentConversation(studentId, fullName, phone, telegram, isOnline = false) {
    activeStudentUserId = studentId;

    const nameEl = document.getElementById('adminActiveStudentName');
    const infoEl = document.getElementById('adminActiveStudentInfo');
    const formEl = document.getElementById('adminChatForm');
    const clearBtn = document.getElementById('clearAdminChatHistoryBtn');

    const statusTag = isOnline
        ? `<span class="badge-online" style="margin-left:0.5rem;"><span class="dot-online"></span> Online</span>`
        : `<span class="badge-offline" style="margin-left:0.5rem;"><span class="dot-offline"></span> Offline</span>`;

    if (nameEl) nameEl.innerHTML = `💬 ឆាតជាមួយ: <strong>${escapeHtml(fullName)}</strong> ${statusTag}`;
    if (infoEl) infoEl.innerText = `📞 ${phone} · ✈️ @${telegram.replace('@', '')}`;
    if (formEl) formEl.style.display = 'flex';
    if (clearBtn) clearBtn.style.display = 'inline-block';

    loadAdminConversations();
    loadAdminActiveChatMessages(studentId, true);
}

async function loadAdminActiveChatMessages(studentId, autoScroll = false) {
    const box = document.getElementById('adminChatMessages');
    if (!box) return;

    try {
        const res = await fetch(`/api/v1/chat/messages?student_id=${studentId}`);
        if (!res.ok) return;

        const msgs = await res.json();

        if (msgs.length === 0) {
            box.innerHTML = `
                <div style="text-align:center; color:#94a3b8; padding:3rem; font-size:0.85rem;">
                    💬 មិនទាន់មានសារក្នុងប្រវត្តិឆាតនេះទេ។ សរសេរសារខាងក្រោមដើម្បីផ្ញើទៅសិស្ស។
                </div>
            `;
            return;
        }

        box.innerHTML = '';
        msgs.forEach(m => {
            const isAdmin = m.sender_role === 'ADMIN';
            const bubble = document.createElement('div');
            bubble.className = `chat-bubble ${isAdmin ? 'chat-bubble-student' : 'chat-bubble-admin'}`;
            bubble.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; font-weight:700; font-size:0.78rem; opacity:0.85; margin-bottom:0.25rem;">
                    <span>${isAdmin ? '🛡️ អ្នក (Admin)' : '🎓 ' + escapeHtml(m.sender_name)}</span>
                    <button onclick="deleteAdminMessage(${m.id})" title="លុបសារនេះ (Delete Message)" style="background:none; border:none; color:rgba(255,255,255,0.7); cursor:pointer; font-size:0.75rem; padding:0 0.2rem;">🗑️</button>
                </div>
                <div>${escapeHtml(m.message)}</div>
                <div class="chat-time">${m.created_at}</div>
            `;
            box.appendChild(bubble);
        });

        if (autoScroll) {
            box.scrollTop = box.scrollHeight;
        }
    } catch (e) {
        console.error("Error loading chat messages for admin:", e);
    }
}

async function deleteAdminMessage(msgId) {
    if (!confirm('តើអ្នកចង់លុបសារនេះមែនទេ? (Delete this message?)')) return;
    try {
        const res = await fetch(`/api/v1/chat/messages/${msgId}`, { method: 'DELETE' });
        if (res.ok) {
            if (activeStudentUserId) loadAdminActiveChatMessages(activeStudentUserId, false);
            loadAdminConversations();
        } else {
            alert('មិនអាចលុបសារបានទេ');
        }
    } catch (e) {
        console.error("Admin delete message error:", e);
    }
}


// Student Portal & KHQR Checkout Interactivity

document.addEventListener('DOMContentLoaded', () => {
    initRegistrationModal();
    initCheckoutPage();
    initRedeemForm();
    loadMyRegistrations();
    initStudentChat();
});

// Global state
let selectedCourseId = null;

function initRegistrationModal() {
    const modal = document.getElementById('registrationModal');
    if (!modal) return;

    const closeBtn = document.getElementById('modalCloseBtn');
    const form = document.getElementById('registrationForm');

    // Attach click listener to "Register" buttons
    document.querySelectorAll('.btn-register').forEach(btn => {
        btn.addEventListener('click', (e) => {
            selectedCourseId = btn.getAttribute('data-course-id');
            const title = btn.getAttribute('data-course-title');
            const priceUsd = btn.getAttribute('data-course-price-usd');
            const priceKhr = btn.getAttribute('data-course-price-khr');

            const hiddenInput = document.getElementById('selectedCourseIdInput');
            if (hiddenInput) hiddenInput.value = selectedCourseId;

            document.getElementById('modalCourseTitle').innerText = title;
            document.getElementById('displayPriceUsd').innerText = `$${priceUsd}`;
            document.getElementById('displayPriceKhr').innerText = `${Number(priceKhr).toLocaleString()} KHR`;

            modal.classList.add('active');
        });
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            modal.classList.remove('active');
        });
    }

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const courseIdVal = document.getElementById('selectedCourseIdInput')?.value || selectedCourseId;
            if (!courseIdVal || isNaN(parseInt(courseIdVal))) {
                alert('សូមជ្រើសរើសវគ្គសិក្សាជាមុនសិន (Please select a valid course)');
                return;
            }

            const submitBtn = form.querySelector('button[type="submit"]') || document.getElementById('submitRegBtn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '⌛ កំពុងបង្កើត Invoice...';
            }

            const payload = {
                course_id: parseInt(courseIdVal),
                student_name: document.getElementById('studentName').value.trim(),
                phone_number: document.getElementById('phoneNumber').value.trim(),
                telegram_username: document.getElementById('telegramUsername').value.trim(),
                currency: document.getElementById('paymentCurrency').value
            };

            try {
                const res = await fetch('/api/v1/registrations', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) {
                    const err = await res.json();
                    let msg = 'Failed to submit registration';
                    if (typeof err.detail === 'string') msg = err.detail;
                    else if (Array.isArray(err.detail)) msg = err.detail.map(d => d.msg).join(', ');
                    alert(`Error: ${msg}`);

                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.innerHTML = 'បន្តទៅកាន់ការទូទាត់ប្រាក់ KHQR →';
                    }
                    return;
                }

                const data = await res.json();
                // Redirect to KHQR Checkout Page
                window.location.href = `/checkout/${data.invoice_id}`;
            } catch (err) {
                console.error("Submission error:", err);
                alert('Connection error. Please check network connection and try again.');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'បន្តទៅកាន់ការទូទាត់ប្រាក់ KHQR →';
                }
            }
        });
    }
}

function initRedeemForm() {
    const form = document.getElementById('redeemForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const input = document.getElementById('redeemCodeInput');
        const btn = document.getElementById('redeemBtn');
        const result = document.getElementById('redeemResult');
        const errBox = document.getElementById('redeemError');

        const code = input.value.trim().toUpperCase();
        if (!code) return;

        btn.disabled = true;
        btn.innerHTML = '⌛ កំពុងពិនិត្យ...';
        errBox.style.display = 'none';
        result.style.display = 'none';

        try {
            const res = await fetch('/api/v1/registrations/redeem-code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code })
            });
            const data = await res.json();

            if (!res.ok) {
                errBox.innerText = `⚠️ ${data.detail || 'Unknown error'}`;
                errBox.style.display = 'block';
                return;
            }

            document.getElementById('redeemMessage').innerText =
                `${data.message}${data.course_title ? ' — ' + data.course_title : ''}`;
            document.getElementById('redeemLinkBtn').href = data.invite_link;
            result.style.display = 'block';
            input.value = '';
        } catch (err) {
            console.error(err);
            errBox.innerText = '⚠️ Connection error. Please try again.';
            errBox.style.display = 'block';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '🔓 បើកសោ (Unlock)';
        }
    });
}

let pollInterval = null;

function initCheckoutPage() {
    const checkoutContainer = document.getElementById('checkoutContainer');
    if (!checkoutContainer) return;

    const invoiceId = checkoutContainer.getAttribute('data-invoice-id');
    if (!invoiceId) return;

    loadPublicSettings(invoiceId);

    // Start polling payment status every 4 seconds
    checkStatus(invoiceId);
    pollInterval = setInterval(() => checkStatus(invoiceId), 4000);

    // Setup receipt upload form
    const receiptForm = document.getElementById('receiptForm');
    if (receiptForm) {
        receiptForm.addEventListener('submit', (e) => handleReceiptUpload(e, invoiceId));
    }

    // The send button stays locked until a receipt is picked, so a student can
    // never message the Admin without attaching proof of payment.
    const receiptFile = document.getElementById('receiptFileInput');
    if (receiptFile) {
        receiptFile.addEventListener('change', () => {
            const file = receiptFile.files?.[0];
            const btn = document.getElementById('receiptSubmitBtn');
            const name = document.getElementById('receiptChosenName');
            const hint = document.getElementById('receiptHint');

            if (btn) btn.disabled = !file;
            if (name) {
                name.style.display = file ? 'block' : 'none';
                name.innerText = file ? `✅ បានជ្រើស: ${file.name}` : '';
            }
            if (hint) {
                hint.innerText = file
                    ? 'ចុចប៊ូតុងខាងលើ — វិក័យបត្រនឹងផ្ញើទៅ Admin ហើយ Telegram នឹងបើកជូនអ្នក។'
                    : '⚠️ សូមជ្រើសឯកសារវិក័យបត្រជាមុន ទើបប៊ូតុងដំណើរការ។';
            }
        });
    }

    // Allow re-upload after a rejection
    const retryBtn = document.getElementById('retryUploadBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', () => {
            document.getElementById('khqrRejectedBox').style.display = 'none';
            document.getElementById('khqrPendingBox').style.display = 'block';
        });
    }
}

async function loadPublicSettings(invoiceId) {
    try {
        const res = await fetch('/api/v1/settings/public');
        if (!res.ok) return;
        const s = await res.json();

        const khqrImg = document.getElementById('khqrImage');
        if (khqrImg && s.khqr_image_url) {
            khqrImg.src = s.khqr_image_url + (s.khqr_image_url.includes('?') ? '&' : '?') + 't=' + Date.now();
        }

        const telegramBtn = document.getElementById('telegramContactBtn');
        if (telegramBtn && s.telegram_contact_link) {
            const hasQuery = s.telegram_contact_link.includes('?');
            const prefill = encodeURIComponent(`Invoice ID: ${invoiceId}`);
            telegramBtn.href = `${s.telegram_contact_link}${hasQuery ? '&' : '?'}text=${prefill}`;
        }

        const phoneLine = document.getElementById('checkoutPhoneLine');
        if (phoneLine && s.contact_phone) {
            phoneLine.innerText = `📞 ឬទាក់ទងតាមទូរស័ព្ទ: ${s.contact_phone}`;
        }
    } catch (e) {
        console.error("Failed loading public settings:", e);
    }
}

async function handleReceiptUpload(e, invoiceId) {
    e.preventDefault();
    const fileInput = document.getElementById('receiptFileInput');
    const file = fileInput?.files?.[0];
    if (!file) {
        alert('សូមជ្រើសរើសរូបភាពវិក័យបត្របង់ប្រាក់ជាមុនសិន (Please choose a receipt file)');
        return;
    }

    const submitBtn = document.getElementById('receiptSubmitBtn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⌛ កំពុង Upload...';
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(`/api/v1/registrations/${invoiceId}/receipt`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) {
            const err = await res.json();
            alert(`Upload failed: ${err.detail || 'Unknown error'}`);
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '⬆️ ផ្ញើវិក័យបត្រទៅ Admin (Send Receipt to Admin)';
            }
            return;
        }

        // Receipt is stored; now hand the student straight to Telegram so both
        // halves happen from the single button press.
        const telegramBtn = document.getElementById('telegramContactBtn');
        if (telegramBtn && telegramBtn.href && telegramBtn.href !== '#') {
            window.open(telegramBtn.href, '_blank');
        }

        checkStatus(invoiceId);
    } catch (err) {
        console.error("Receipt upload error:", err);
        alert('Connection error while uploading receipt. Please try again.');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '⬆️ ផ្ញើវិក័យបត្រទៅ Admin (Send Receipt to Admin)';
        }
    }
}

async function checkStatus(invoiceId) {
    try {
        const res = await fetch(`/api/v1/registrations/${invoiceId}/status`);
        if (!res.ok) return;

        const data = await res.json();

        const statusBadge = document.getElementById('checkoutStatusBadge');
        const pendingBox = document.getElementById('khqrPendingBox');
        const submittedBox = document.getElementById('khqrSubmittedBox');
        const rejectedBox = document.getElementById('khqrRejectedBox');
        const successBox = document.getElementById('khqrSuccessBox');
        const inviteLinkBtn = document.getElementById('telegramInviteBtn');
        const amountDisplay = document.getElementById('khqrAmountDisplay');
        const submittedPreview = document.getElementById('submittedReceiptPreview');

        if (amountDisplay) {
            amountDisplay.innerText = data.currency === 'USD'
                ? `$${parseFloat(data.amount).toFixed(2)}`
                : `${parseInt(data.amount).toLocaleString()} KHR`;
        }

        // Hide every box, then show the one matching current status
        [pendingBox, submittedBox, rejectedBox, successBox].forEach(box => {
            if (box) box.style.display = 'none';
        });

        if (data.status === 'PAID') {
            if (pollInterval) clearInterval(pollInterval);

            if (statusBadge) {
                statusBadge.className = 'status-badge status-paid';
                statusBadge.innerHTML = '✓ Admin បានអនុម័ត (ACCEPTED)';
            }
            if (successBox) successBox.style.display = 'block';
            if (inviteLinkBtn && data.invite_link) {
                inviteLinkBtn.href = data.invite_link;
            }
        } else if (data.status === 'SUBMITTED') {
            if (statusBadge) {
                statusBadge.className = 'status-badge status-submitted';
                statusBadge.innerHTML = '🧾 កំពុងរង់ចាំ Admin ត្រួតពិនិត្យ (UNDER REVIEW)';
            }
            if (submittedBox) submittedBox.style.display = 'block';
            if (submittedPreview && data.receipt_image_url) {
                submittedPreview.src = data.receipt_image_url;
                submittedPreview.style.display = 'block';
            }
        } else if (data.status === 'REJECTED') {
            if (statusBadge) {
                statusBadge.className = 'status-badge status-rejected';
                statusBadge.innerHTML = '✕ វិក័យបត្រមិនត្រូវបានទទួលយក (REJECTED)';
            }
            if (rejectedBox) rejectedBox.style.display = 'block';
        } else {
            if (statusBadge) {
                statusBadge.className = 'status-badge status-pending';
                statusBadge.innerHTML = '<span class="pulse-dot"></span> រង់ចាំការទូទាត់ប្រាក់ (WAITING FOR PAYMENT)';
            }
            if (pendingBox) pendingBox.style.display = 'block';
        }
    } catch (e) {
        console.error("Error polling payment status:", e);
    }
}

async function loadMyRegistrations() {
    const sec = document.getElementById('myRegistrationsSection');
    const list = document.getElementById('myRegistrationsList');
    if (!sec || !list) return;

    try {
        const res = await fetch('/api/v1/registrations/my-registrations');
        if (!res.ok) return;
        const regs = await res.json();
        if (!Array.isArray(regs) || regs.length === 0) {
            sec.style.display = 'none';
            return;
        }

        sec.style.display = 'block';
        list.innerHTML = '';

        regs.forEach(r => {
            const card = document.createElement('div');
            card.style.cssText = 'background: rgba(15, 23, 42, 0.6); border: 1px solid var(--glass-border); border-radius: var(--radius-md); padding: 1rem 1.25rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;';

            let statusHtml = '';
            let actionBtn = '';

            if (r.status === 'PAID') {
                statusHtml = `<span class="status-badge status-paid">✓ Admin បានអនុម័ត (APPROVED)</span>`;
                if (r.invite_link) {
                    actionBtn = `<a href="${r.invite_link}" target="_blank" class="btn btn-primary" style="background: linear-gradient(135deg, #0088cc, #005580); border:none;">🚀 ចូល Telegram Group</a>`;
                }
            } else if (r.status === 'SUBMITTED') {
                statusHtml = `<span class="status-badge status-submitted">⏳ កំពុងរង់ចាំ Admin ពិនិត្យ</span>`;
                actionBtn = `<a href="/checkout/${r.invoice_id}" class="btn btn-outline btn-sm">🧾 មើលស្ថានភាព</a>`;
            } else if (r.status === 'REJECTED') {
                statusHtml = `<span class="status-badge status-rejected">✕ វិក័យបត្រត្រូវបដិសេធ</span>`;
                actionBtn = `<a href="/checkout/${r.invoice_id}" class="btn btn-khqr btn-sm">⬆️ Upload ឡើងវិញ</a>`;
            } else {
                statusHtml = `<span class="status-badge status-pending"><span class="pulse-dot"></span> រង់ចាំការទូទាត់</span>`;
                actionBtn = `<a href="/checkout/${r.invoice_id}" class="btn btn-khqr btn-sm">💳 ទៅកាន់ Checkout →</a>`;
            }

            card.innerHTML = `
                <div>
                    <h4 style="color:#fff; font-size:1.05rem; font-weight:700; margin-bottom:0.3rem;">${escapeHtml(r.course_title)}</h4>
                    <p style="color:var(--text-muted); font-size:0.83rem; margin-bottom:0.4rem;">
                        Invoice: <code>${r.invoice_id}</code> · តម្លៃ: ${r.amount} ${r.currency}
                    </p>
                    <div>${statusHtml}</div>
                </div>
                <div>${actionBtn}</div>
            `;
            list.appendChild(card);
        });
    } catch (e) {
        console.error("Error loading my registrations:", e);
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function initStudentChat() {
    const trigger = document.getElementById('floatingChatTrigger');
    const box = document.getElementById('floatingChatBox');
    const closeBtn = document.getElementById('closeFloatingChatBtn');
    const chatForm = document.getElementById('studentChatForm');

    if (!trigger || !box) return;

    // Toggle floating chat window
    trigger.addEventListener('click', () => {
        const isActive = box.classList.contains('active');
        if (isActive) {
            box.classList.remove('active');
        } else {
            box.classList.add('active');
            loadStudentChatMessages();
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            box.classList.remove('active');
        });
    }

    const clearHistoryBtn = document.getElementById('clearStudentChatHistoryBtn');
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', async () => {
            if (!confirm('តើអ្នកប្រាកដជាចង់លុបប្រវត្តិឆាតទាំងអស់មែនទេ? (Clear all chat history?)')) return;
            try {
                const res = await fetch('/api/v1/chat/history', { method: 'DELETE' });
                if (res.ok) {
                    loadStudentChatMessages();
                } else {
                    alert('មិនអាចលុបប្រវត្តិឆាតបានទេ');
                }
            } catch (e) {
                console.error("Clear chat error:", e);
            }
        });
    }

    loadDirectTelegramLink();
    checkChatStatus();

    // Poll status & messages every 4 seconds
    setInterval(() => {
        checkChatStatus();
        if (box.classList.contains('active')) {
            loadStudentChatMessages();
        }
    }, 4000);

    if (chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('studentChatInput');
            const msg = input.value.trim();
            if (!msg) return;

            const sendBtn = document.getElementById('studentChatSendBtn');
            if (sendBtn) sendBtn.disabled = true;

            try {
                const res = await fetch('/api/v1/chat/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg })
                });

                if (res.ok) {
                    input.value = '';
                    loadStudentChatMessages();
                } else {
                    const err = await res.json();
                    alert(`សារមិនអាចផ្ញើបាន: ${err.detail || 'Error'}`);
                }
            } catch (e) {
                console.error("Chat send error:", e);
            } finally {
                if (sendBtn) sendBtn.disabled = false;
            }
        });
    }
}

async function checkChatStatus() {
    try {
        const res = await fetch('/api/v1/chat/status');
        if (!res.ok) return;

        const data = await res.json();

        // Update Admin Online/Offline badge
        const badge = document.getElementById('adminStatusBadge');
        if (badge) {
            if (data.admin_online) {
                badge.className = 'badge-online';
                badge.innerHTML = '<span class="dot-online"></span> Admin Online';
            } else {
                badge.className = 'badge-offline';
                badge.innerHTML = '<span class="dot-offline"></span> Admin Offline';
            }
        }

        // Update Unread Badge on floating trigger button
        const unreadBadge = document.getElementById('floatingChatUnread');
        if (unreadBadge) {
            if (data.unread_count > 0) {
                unreadBadge.innerText = data.unread_count;
                unreadBadge.style.display = 'inline-block';
            } else {
                unreadBadge.style.display = 'none';
            }
        }
    } catch (e) {
        console.error("Error checking chat status:", e);
    }
}

async function loadDirectTelegramLink() {
    const btn = document.getElementById('directTelegramAdminBtn');
    if (!btn) return;
    try {
        const res = await fetch('/api/v1/settings/public');
        if (res.ok) {
            const s = await res.json();
            if (s.telegram_contact_link) {
                btn.href = s.telegram_contact_link;
            }
        }
    } catch (e) {
        console.error(e);
    }
}

async function loadStudentChatMessages() {
    const box = document.getElementById('studentChatMessages');
    if (!box) return;

    try {
        const res = await fetch('/api/v1/chat/messages');
        if (!res.ok) return;
        const msgs = await res.json();

        if (msgs.length === 0) {
            box.innerHTML = `
                <div style="text-align:center; color:#94a3b8; padding:2rem; font-size:0.85rem;">
                    👋 មិនទាន់មានសារនៅឡើយទេ! អ្នកអាចសរសេរសារផ្ញើទៅ Admin នៅខាងក្រោម។
                </div>
            `;
            return;
        }

        box.innerHTML = '';
        msgs.forEach(m => {
            const isStudent = m.sender_role === 'STUDENT';
            const bubble = document.createElement('div');
            bubble.className = `chat-bubble ${isStudent ? 'chat-bubble-student' : 'chat-bubble-admin'}`;
            bubble.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; font-weight:700; font-size:0.78rem; opacity:0.85; margin-bottom:0.25rem;">
                    <span>${isStudent ? 'អ្នក (You)' : '🛡️ Admin'}</span>
                    <button onclick="deleteStudentMessage(${m.id})" title="លុបសារនេះ (Delete Message)" style="background:none; border:none; color:rgba(255,255,255,0.7); cursor:pointer; font-size:0.75rem; padding:0 0.2rem;">🗑️</button>
                </div>
                <div>${escapeHtml(m.message)}</div>
                <div class="chat-time">${m.created_at}</div>
            `;
            box.appendChild(bubble);
        });

        box.scrollTop = box.scrollHeight;
    } catch (e) {
        console.error("Error loading chat messages:", e);
    }
}

async function deleteStudentMessage(msgId) {
    if (!confirm('តើអ្នកចង់លុបសារនេះមែនទេ? (Delete this message?)')) return;
    try {
        const res = await fetch(`/api/v1/chat/messages/${msgId}`, { method: 'DELETE' });
        if (res.ok) {
            loadStudentChatMessages();
        } else {
            alert('មិនអាចលុបសារបានទេ');
        }
    } catch (e) {
        console.error("Delete message error:", e);
    }
}




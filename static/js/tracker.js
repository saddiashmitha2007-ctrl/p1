/**
 * Real-time Duplicate Detection & Interactive Checks
 * Debounces user typing in Description / Location / Title and calls /api/check-duplicates.
 */

document.addEventListener('DOMContentLoaded', () => {
  const descInput = document.getElementById('complaintDesc');
  const titleInput = document.getElementById('complaintTitle');
  const locationInput = document.getElementById('complaintLocation');
  const categorySelect = document.getElementById('complaintCategory');
  const duplicateAlertBox = document.getElementById('duplicateAlertBox');
  const duplicateList = document.getElementById('duplicateList');
  const duplicateConfirmedHidden = document.getElementById('isDuplicateConfirmed');
  const duplicateOfIdHidden = document.getElementById('duplicateOfId');

  let debounceTimer = null;

  async function checkDuplicates() {
    if (!descInput && !titleInput) return;

    const desc = descInput ? descInput.value.trim() : '';
    const title = titleInput ? titleInput.value.trim() : '';
    const loc = locationInput ? locationInput.value.trim() : '';
    const cat = categorySelect ? categorySelect.value : '';

    if (desc.length < 5 && title.length < 5) {
      if (duplicateAlertBox) duplicateAlertBox.style.display = 'none';
      return;
    }

    try {
      const response = await fetch('/api/check-duplicates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: desc,
          title: title,
          location: loc,
          category: cat
        })
      });

      if (!response.ok) return;

      const data = await response.json();
      const duplicates = data.duplicates || [];

      if (duplicates.length > 0 && duplicateAlertBox && duplicateList) {
        duplicateList.innerHTML = '';
        duplicates.slice(0, 3).forEach(dup => {
          const item = document.createElement('div');
          item.className = 'duplicate-card';
          item.innerHTML = `
            <div>
              <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.25rem;">
                <span class="similarity-badge">${dup.similarity_score}% Match</span>
                <strong><a href="/complaint/${dup.complaint_id}" target="_blank">${dup.complaint_code}</a></strong>
                <span class="badge badge-${dup.status.toLowerCase().replace(' ', '-')}">${dup.status}</span>
              </div>
              <div style="font-weight:600; font-size:0.92rem;">${escapeHtml(dup.title)}</div>
              <div style="font-size:0.82rem; color:#64748b;">📍 ${escapeHtml(dup.location)} &bull; Assigned to: ${escapeHtml(dup.assigned_worker)}</div>
            </div>
            <div style="display:flex; gap:0.5rem; align-items:center;">
              <button type="button" class="btn btn-sm btn-outline" onclick="confirmSameIssue(${dup.complaint_id}, '${dup.complaint_code}')">
                This is the same problem
              </button>
            </div>
          `;
          duplicateList.appendChild(item);
        });

        duplicateAlertBox.style.display = 'block';
      } else if (duplicateAlertBox) {
        duplicateAlertBox.style.display = 'none';
      }

    } catch (err) {
      console.error("Duplicate check error:", err);
    }
  }

  window.checkDuplicatesRealtime = checkDuplicates;

  window.confirmSameIssue = function(complaintId, complaintCode) {
    if (duplicateConfirmedHidden) duplicateConfirmedHidden.value = "1";
    if (duplicateOfIdHidden) duplicateOfIdHidden.value = complaintId;

    if (duplicateAlertBox) {
      duplicateAlertBox.innerHTML = `
        <div style="background-color: #ecfdf5; border: 1px solid #a7f3d0; padding: 0.85rem; border-radius: 8px; color: #065f46;">
          <strong>Linked as Duplicate:</strong> You indicated this matches existing complaint <strong>${complaintCode}</strong>.
          Submitting will link your report directly to the existing active ticket so the maintenance worker receives updated information without creating a fragmented request.
        </div>
      `;
    }
  };

  function escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Bind input events
  [descInput, titleInput, locationInput, categorySelect].forEach(input => {
    if (input) {
      input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(checkDuplicates, 450);
      });
    }
  });
});

async function loadEvaluation() {
    const c = document.getElementById('evaluation-container');
    c.innerHTML = '<p class="pe-empty">Loading…</p>';
    try {
        const data = await fetch(`/admin/practices/${practiceId}/evaluation`).then(r => r.json());
        if (!data.success) { c.innerHTML = `<p class="rail-error">${data.error}</p>`; return; }
        const ev = data.evaluation;
        let h = `<div class="rail-go-row"><span class="rail-go ${ev.is_go ? 'go' : 'nogo'}">${ev.is_go ? 'GO' : 'NO-GO'}</span>`
              + `<span class="rail-muted">${Math.round(ev.confidence * 100)}% confidence</span></div>`;
        if (ev.weather) {
            h += `<div class="rail-chips">`
               + `<span class="rail-chip">${ev.weather.temperature_f?.toFixed(0) ?? '–'}°F (feels ${ev.weather.feels_like_f?.toFixed(0) ?? '–'}°)</span>`
               + `<span class="rail-chip">wind ${ev.weather.wind_speed_mph?.toFixed(0) ?? '–'} mph</span>`
               + `<span class="rail-chip">precip ${ev.weather.precipitation_chance ?? 0}%</span></div>`;
        }
        if (ev.violations && ev.violations.length) {
            for (const v of ev.violations) {
                h += `<div class="rail-violation ${v.severity}"><b>${v.severity.toUpperCase()}</b> ${v.message}</div>`;
            }
        } else {
            h += `<p class="rail-ok">No violations detected</p>`;
        }
        c.innerHTML = h;
    } catch (err) { c.innerHTML = `<p class="rail-error">${err.message}</p>`; }
}

async function loadRSVPs() {
    try {
        const { rsvps, summary } = await fetch(`/admin/practices/${practiceId}/rsvps`).then(r => r.json());
        document.getElementById('rsvp-summary').innerHTML =
            `<div class="rsvp-strip">`
          + `<div class="rsvp-cell"><span class="n">${summary.going}</span><span class="lbl">Going</span></div>`
          + `<div class="rsvp-cell"><span class="n">${summary.maybe}</span><span class="lbl">Maybe</span></div>`
          + `<div class="rsvp-cell"><span class="n">${summary.not_going}</span><span class="lbl">Out</span></div></div>`;
        const list = document.getElementById('rsvp-list');
        if (!rsvps.length) { list.innerHTML = '<p class="pe-empty">No RSVPs yet</p>'; return; }
        list.innerHTML = rsvps.map(r =>
            `<div class="rsvp-row"><span class="dot ${r.status}" aria-hidden="true"></span>`
          + `<span class="rsvp-name">${r.user_name}</span><span class="rsvp-tag">${r.status.replace('_',' ')}</span></div>`
        ).join('');
    } catch (err) {
        document.getElementById('rsvp-list').innerHTML = `<p class="rail-error">${err.message}</p>`;
    }
}

async function loadLeadConfirmations() {
    const c = document.getElementById('lead-confirmations-container');
    try {
        const { leads } = await fetch(`/admin/practices/${practiceId}/leads/data`).then(r => r.json());
        if (!leads.length) { c.innerHTML = '<p class="pe-empty">No leads assigned</p>'; return; }
        c.innerHTML = leads.map(l => {
            const role = l.role === 'coach' ? 'Coach' : l.role === 'lead' ? 'Lead' : 'Assist';
            return `<div class="conf-row">`
                 + `<span class="conf-name">${l.name} <span class="conf-role">${role}</span></span>`
                 + `<label class="toggle-row mini"><input type="checkbox" ${l.confirmed ? 'checked' : ''} `
                 + `onchange="toggleLeadConfirmation(${l.id})" aria-label="Confirm ${l.name}">`
                 + `<span class="toggle-track" aria-hidden="true"></span></label>`
                 + `<span class="conf-state ${l.confirmed ? 'on' : ''}">${l.confirmed ? 'Confirmed' : 'Pending'}</span></div>`;
        }).join('');
    } catch (err) { c.innerHTML = `<p class="rail-error">${err.message}</p>`; }
}

async function toggleLeadConfirmation(leadId) {
    try {
        const result = await fetch(`/admin/practices/${practiceId}/leads/${leadId}/toggle-confirm`, {
            method: 'POST', headers: {'Content-Type': 'application/json'}
        }).then(r => r.json());
        showToast(result.success ? result.message : (result.error || 'Failed'), result.success ? 'success' : 'error');
    } catch (err) { showToast('Error: ' + err.message, 'error'); }
    loadLeadConfirmations();
}

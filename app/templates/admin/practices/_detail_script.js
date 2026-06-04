// Selected ids injected server-side (ids match the option-list endpoints).
const practiceId = {{ practice.id if practice else 'null' }};
const selLocationId = {{ practice.location_id if practice else 'null' }};
const selActivities = {{ (practice.activities | map(attribute='id') | list) | tojson if practice else '[]' }};
const selTypes = {{ (practice.practice_types | map(attribute='id') | list) | tojson if practice else '[]' }};
const selCoaches = {{ (practice.leads | selectattr('role','equalto','coach') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const selLeads = {{ (practice.leads | selectattr('role','equalto','lead') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const selAssists = {{ (practice.leads | selectattr('role','equalto','assist') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};

document.addEventListener('DOMContentLoaded', async () => {
    await loadFormData();
    {% if practice %}
    document.getElementById('header-meta').textContent = new Date('{{ practice.date.isoformat() }}')
        .toLocaleString([], {weekday: 'long', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'});
    loadRSVPs();
    loadLeadConfirmations();
    {% endif %}
});

async function loadFormData() {
    try {
        const [locs, acts, types, people] = await Promise.all([
            fetch('/admin/practices/locations/data').then(r => r.json()),
            fetch('/admin/practices/activities/data').then(r => r.json()),
            fetch('/admin/practices/types/data').then(r => r.json()),
            fetch('/admin/practices/people/data').then(r => r.json()),
        ]);

        const locationSelect = document.getElementById('location_id');
        (locs.locations || []).forEach(loc => {
            const opt = document.createElement('option');
            opt.value = loc.id;
            opt.textContent = loc.name + (loc.spot ? ` — ${loc.spot}` : '');
            if (loc.id === selLocationId) opt.selected = true;
            locationSelect.appendChild(opt);
        });

        peRenderTagPills('activities-pills', acts.activities || [], selActivities);
        peRenderTagPills('types-pills', types.types || [], selTypes);
        peRenderPersonPills('coaches-pills', 'coaches-summary', people.coaches || [], selCoaches);
        peRenderPersonPills('leads-pills', 'leads-summary', people.leads || [], selLeads);
        peRenderPersonPills('assists-pills', 'assists-summary', people.assists || [], selAssists);

        if (selAssists.length > 0) toggleAssists();

        document.getElementById('people-search').addEventListener('input', () =>
            peFilterPeople('people-search', ['coaches-pills', 'leads-pills', 'assists-pills']));
    } catch (err) {
        console.error('Error loading form data:', err);
        showToast('Error loading form data', 'error');
    }
}

function toggleAssists() {
    const box = document.getElementById('assists-collapsible');
    const btn = document.getElementById('assists-toggle');
    const chevron = btn.querySelector('.chevron');
    const text = document.getElementById('assists-toggle-text');
    const nowOpen = box.classList.toggle('hidden') === false;
    btn.setAttribute('aria-expanded', nowOpen ? 'true' : 'false');
    chevron.classList.toggle('expanded', nowOpen);
    text.textContent = nowOpen ? 'Hide' : 'Show';
}

document.getElementById('practice-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const fd = new FormData(form);

    const locationId = parseInt(fd.get('location_id'));
    if (!fd.get('date') || isNaN(locationId)) {
        showToast('Date and Location are required', 'error');
        return;
    }

    const socialVal = fd.get('social_location_id');
    const payload = {
        date: fd.get('date'),
        location_id: locationId,
        social_location_id: socialVal ? parseInt(socialVal) : null,
        activity_ids: peCollectIds('activities-pills'),
        type_ids: peCollectIds('types-pills'),
        coach_ids: peCollectIds('coaches-pills'),
        lead_ids: peCollectIds('leads-pills'),
        assist_ids: peCollectIds('assists-pills'),
        warmup_description: fd.get('warmup_description') || null,
        workout_description: fd.get('workout_description') || null,
        cooldown_description: fd.get('cooldown_description') || null,
        is_dark_practice: fd.get('is_dark_practice') === 'on',
    };
    if (practiceId) payload.status = fd.get('status');

    form.classList.add('form-loading');
    try {
        const resp = await fetch(form.action, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        if (resp.ok && result.success) {
            showToast(result.message || 'Practice saved', 'success');
            setTimeout(() => { window.location.href = '/admin/practices'; }, 800);
        } else {
            showToast(result.error || 'Failed to save practice', 'error');
            form.classList.remove('form-loading');
        }
    } catch (err) {
        showToast('Error saving practice: ' + err.message, 'error');
        form.classList.remove('form-loading');
    }
});

{% if practice %}
{% include 'admin/practices/_detail_context.js' %}
{% endif %}

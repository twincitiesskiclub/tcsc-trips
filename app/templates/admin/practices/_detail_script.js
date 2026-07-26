// Selected ids injected server-side (ids match the option-list endpoints).
const practiceId = {{ practice.id if practice else 'null' }};
const selLocationId = {{ practice.location_id if practice else 'null' }};
const selActivities = {{ (practice.activities | map(attribute='id') | list) | tojson if practice else '[]' }};
const selTypes = {{ (practice.practice_types | map(attribute='id') | list) | tojson if practice else '[]' }};
const selCoaches = {{ (practice.leads | selectattr('role','equalto','coach') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const selLeads = {{ (practice.leads | selectattr('role','equalto','lead') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const savedPlanReactions = {{ (practice.plan_reactions or []) | tojson if practice else '[]' }};
let activitiesData = [];
let typesData = [];
let planReactionController = null;
let formReferenceLoadError = null;
const reactionSettingsLoadError =
    'Could not load reaction Settings. Try again.';

function selectedTagIds(containerId) {
    return peCollectIds(containerId);
}

/* Leads are collected from the availability picker when it's present
   (editing an existing practice); new practices fall back to the plain
   person-pill picker since lead-candidates needs a saved practice id. */
function collectLeadIds() {
    const picker = document.getElementById('lead-picker');
    if (picker) {
        // resolveLeadIds preserves the server-rendered assignment when the
        // picker failed or hasn't finished loading -- an empty checkbox set
        // would otherwise tell edit_practice to delete every assigned lead.
        const {ids, preserved} = resolveLeadIds(picker, selLeads);
        if (preserved) {
            showToast(
                'Lead availability never loaded — saved everything else and '
                + 'left the assigned leads unchanged.', 'error');
        }
        return ids;
    }
    return peCollectIds('leads-pills');
}

function refreshPlanReactionSelection() {
    if (!planReactionController) return;
    planReactionController.setSelection(
        selectedTagIds('types-pills'),
        selectedTagIds('activities-pills'),
    );
}

function initializePlanReactionEditor(referenceError = null) {
    const referencesReady = !referenceError;
    try {
        planReactionController = PracticePlanReactionEditor.mount({
            root: document.getElementById('plan-reaction-editor'),
            types: referencesReady ? typesData : [],
            activities: referencesReady ? activitiesData : [],
            selectedTypeIds: referencesReady ? selectedTagIds('types-pills') : [],
            selectedActivityIds: referencesReady
                ? selectedTagIds('activities-pills')
                : [],
            savedSnapshot: practiceId ? savedPlanReactions : null,
            referenceError: referenceError,
        });
    } catch (error) {
        if (referenceError) throw error;
        console.error('Reaction Settings data is invalid:', error);
        initializePlanReactionEditor(reactionSettingsLoadError);
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    await loadFormData();
    {% if practice %}
    document.getElementById('header-meta').textContent = new Date('{{ practice.date.isoformat() }}')
        .toLocaleString([], {weekday: 'long', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'});
    loadRSVPs();
    loadLeadConfirmations();
    loadLeadPicker();
    {% endif %}
});

async function loadFormData() {
    const references = await PracticePlanReactionEditor.loadReferenceData(fetch);
    const locationSelect = document.getElementById('location_id');
    references.locations.forEach(loc => {
        const opt = document.createElement('option');
        opt.value = loc.id;
        opt.textContent = loc.name + (loc.spot ? ` — ${loc.spot}` : '');
        if (loc.id === selLocationId) opt.selected = true;
        locationSelect.appendChild(opt);
    });

    activitiesData = references.activities;
    typesData = references.types;
    peRenderTagPills(
        'activities-pills', activitiesData, selActivities,
        refreshPlanReactionSelection
    );
    peRenderTagPills(
        'types-pills', typesData, selTypes, refreshPlanReactionSelection
    );
    initializePlanReactionEditor(
        references.reactionSettingsReady ? null : reactionSettingsLoadError
    );

    const people = references.people;
    peRenderPersonPills('coaches-pills', 'coaches-summary', people.coaches, selCoaches);
    peRenderPersonPills('leads-pills', 'leads-summary', people.leads, selLeads);

    document.getElementById('people-search').addEventListener('input', () =>
        peFilterPeople('people-search', ['coaches-pills', 'leads-pills']));

    if (references.failed.length) {
        formReferenceLoadError = 'Could not load form options. Refresh and try again.';
        console.error('Reference data failed:', references.failed.join(', '));
        showToast(formReferenceLoadError, 'error');
    }
}

document.getElementById('practice-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (formReferenceLoadError) {
        showToast(formReferenceLoadError, 'error');
        return;
    }
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
        lead_ids: collectLeadIds(),
        leads_needed: parseInt(fd.get('leads_needed'), 10),
        workout_description: fd.get('workout_description') || null,
        logistics_notes: fd.get('logistics_notes') || null,
        is_dark_practice: fd.get('is_dark_practice') === 'on',
    };
    if (practiceId) payload.status = fd.get('status');

    try {
        payload.plan_reactions = planReactionController.snapshot();
    } catch (error) {
        showToast(error.message || 'Check Plan reactions.', 'error');
        return;
    }

    form.classList.add('form-loading');
    try {
        const resp = await fetch(form.action, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload),
        });
        const result = await resp.json();
        if (resp.ok && result.success) {
            if (result.availability_warning) {
                // The practice saved, but it fell inside an OPEN availability
                // poll it can't join — no letter, no availability collected.
                // Stashed rather than toasted here because this page redirects
                // in 800ms; the list page flashes it on arrival (see
                // flashPendingAvailabilityWarning in admin_practices.js).
                try {
                    window.sessionStorage.setItem(
                        'tcsc-availability-warning', result.availability_warning);
                } catch (e) { /* storage blocked; the server already logged it */ }
            }
            showToast(result.message || 'Practice saved', 'success');
            setTimeout(() => { window.location.href = '/admin/practices'; }, 800);
        } else {
            if (
                planReactionController &&
                PracticePlanReactionEditor.isReactionField(result.field)
            ) {
                planReactionController.showError(result.error);
            }
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

// Selected ids injected server-side (ids match the option-list endpoints).
const practiceId = {{ practice.id if practice else 'null' }};
const selLocationId = {{ practice.location_id if practice else 'null' }};
const selActivities = {{ (practice.activities | map(attribute='id') | list) | tojson if practice else '[]' }};
const selTypes = {{ (practice.practice_types | map(attribute='id') | list) | tojson if practice else '[]' }};
const selCoaches = {{ (practice.leads | selectattr('role','equalto','coach') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const selLeads = {{ (practice.leads | selectattr('role','equalto','lead') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const selAssists = {{ (practice.leads | selectattr('role','equalto','assist') | map(attribute='user_id') | select | list) | tojson if practice else '[]' }};
const savedPlanReactions = {{ (practice.plan_reactions or []) | tojson if practice else '[]' }};
let activitiesData = [];
let typesData = [];
let planReactionMode = practiceId ? 'snapshot' : 'derived';
let planReactionError = null;

function setPlanReactionError(message) {
    planReactionError = message || null;
    const status = document.getElementById('plan-reaction-status');
    status.textContent = planReactionError || '';
    status.classList.toggle('field-error', Boolean(planReactionError));
}

function selectedTagIds(containerId) {
    return peCollectIds(containerId);
}

function resolveCurrentDefaults() {
    const sources = [
        ...typesData
            .filter(item => selectedTagIds('types-pills').includes(item.id))
            .sort((left, right) => left.name.localeCompare(right.name))
            .map(item => ({...item, sourceLabel: `Workout Type ${item.name}`})),
        ...activitiesData
            .filter(item => selectedTagIds('activities-pills').includes(item.id))
            .sort((left, right) => left.name.localeCompare(right.name))
            .map(item => ({...item, sourceLabel: `Activity ${item.name}`})),
    ];
    const seen = new Map();
    const merged = [];
    for (const source of sources) {
        for (const option of (source.default_plan_reactions || [])) {
            const previous = seen.get(option.emoji);
            if (previous && previous.label !== option.label) {
                return {
                    reactions: [],
                    error: `:${option.emoji}: conflicts between ${previous.source} and ${source.sourceLabel}`,
                };
            }
            if (!previous) {
                seen.set(option.emoji, {
                    label: option.label,
                    source: source.sourceLabel,
                });
                merged.push({...option});
            }
        }
    }
    if (merged.length > PlanReactionEditor.MAX) {
        return {
            reactions: [],
            error: 'Selected defaults produce more than 4 reactions',
        };
    }
    return {reactions: merged, error: null};
}

function refreshDerivedPlanReactions() {
    if (planReactionMode === 'derived' || planReactionMode === 'restore') {
        const resolved = resolveCurrentDefaults();
        setPlanReactionError(resolved.error);
        PlanReactionEditor.set(
            document.getElementById('plan-reaction-rows'),
            resolved.reactions,
            planReactionCallbacks(),
        );
        updatePlanReactionAddState();
    }
}

function markCustomized() {
    planReactionMode = 'custom';
    setPlanReactionError(null);
}

function planReactionCallbacks() {
    return {
        onChange() {
            markCustomized();
            updatePlanReactionAddState();
        },
        onEmptyFocus() {
            document.getElementById('add-plan-reaction').focus();
        },
    };
}

function updatePlanReactionAddState() {
    const rows = document.getElementById('plan-reaction-rows');
    const add = document.getElementById('add-plan-reaction');
    const count = rows.querySelectorAll('.plan-reaction-row').length;
    add.disabled = count >= PlanReactionEditor.MAX;
    if (count >= PlanReactionEditor.MAX && !planReactionError) {
        document.getElementById('plan-reaction-status').textContent =
            'Maximum of 4 reactions.';
    } else if (!planReactionError) {
        document.getElementById('plan-reaction-status').textContent = '';
    }
}

function initializePlanReactionEditor() {
    const rows = document.getElementById('plan-reaction-rows');
    if (practiceId) {
        PlanReactionEditor.set(
            rows, savedPlanReactions, planReactionCallbacks()
        );
    } else {
        refreshDerivedPlanReactions();
    }

    document.getElementById('add-plan-reaction').addEventListener('click', () => {
        if (PlanReactionEditor.add(rows, planReactionCallbacks())) {
            rows.querySelector(
                '.plan-reaction-row:last-child .plan-reaction-emoji'
            ).focus();
        }
        updatePlanReactionAddState();
    });
    document.getElementById('restore-plan-reactions').addEventListener('click', () => {
        planReactionMode = practiceId ? 'restore' : 'derived';
        refreshDerivedPlanReactions();
    });
    updatePlanReactionAddState();
}

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

        activitiesData = acts.activities || [];
        typesData = types.types || [];
        peRenderTagPills(
            'activities-pills', activitiesData, selActivities,
            refreshDerivedPlanReactions
        );
        peRenderTagPills(
            'types-pills', typesData, selTypes, refreshDerivedPlanReactions
        );
        initializePlanReactionEditor();
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
        workout_description: fd.get('workout_description') || null,
        logistics_notes: fd.get('logistics_notes') || null,
        is_dark_practice: fd.get('is_dark_practice') === 'on',
    };
    if (practiceId) payload.status = fd.get('status');

    if (
        (planReactionMode === 'derived' || planReactionMode === 'restore') &&
        planReactionError
    ) {
        showToast(planReactionError, 'error');
        return;
    }

    if (planReactionMode === 'custom') {
        const reactions = PlanReactionEditor.get(
            document.getElementById('plan-reaction-rows')
        );
        const incomplete = reactions.find(item => !item.emoji || !item.label);
        if (incomplete) {
            setPlanReactionError(
                'Complete both fields or remove the unfinished reaction.'
            );
            const row = Array.from(document.querySelectorAll(
                '#plan-reaction-rows .plan-reaction-row'
            )).find(item => {
                const emoji = item.querySelector(
                    '.plan-reaction-emoji'
                ).value.trim();
                const label = item.querySelector(
                    '.plan-reaction-label'
                ).value.trim();
                return !emoji || !label;
            });
            if (row) {
                const emoji = row.querySelector('.plan-reaction-emoji');
                const label = row.querySelector('.plan-reaction-label');
                (!emoji.value.trim() ? emoji : label).focus();
            }
            return;
        }
        payload.plan_reactions = reactions;
    } else if (planReactionMode === 'restore') {
        payload.restore_plan_reaction_defaults = true;
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
            showToast(result.message || 'Practice saved', 'success');
            setTimeout(() => { window.location.href = '/admin/practices'; }, 800);
        } else {
            if (result.field === 'plan_reactions') {
                setPlanReactionError(result.error);
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

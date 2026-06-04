/* Reusable controls for the practice editor page (pills, person search, assists).
   Loaded by admin/practices/detail.html. Globals are prefixed `pe`. */

function peRoleEmoji(person) {
    if (!person.tags || person.tags.length === 0) return null;
    const preferred = ['HEAD_COACH', 'ASSISTANT_COACH', 'PRACTICES_LEAD', 'PRACTICES_DIRECTOR'];
    for (const tagName of preferred) {
        const tag = person.tags.find(t => t.name === tagName);
        if (tag && tag.emoji) return tag.emoji;
    }
    const withEmoji = person.tags.find(t => t.emoji);
    return withEmoji ? withEmoji.emoji : null;
}

/* Activity / Type pills, selected by id. Toggles `.selected` on click. */
function peRenderTagPills(containerId, data, selectedIds) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    if (!data || data.length === 0) {
        container.innerHTML = '<span class="pe-empty">None defined</span>';
        return;
    }
    for (const item of data) {
        const label = document.createElement('button');
        label.type = 'button';
        label.className = 'pe-pill' + (selectedIds.includes(item.id) ? ' selected' : '');
        label.dataset.value = item.id;
        label.setAttribute('aria-pressed', selectedIds.includes(item.id) ? 'true' : 'false');
        label.textContent = item.name;
        label.onclick = () => {
            const on = label.classList.toggle('selected');
            label.setAttribute('aria-pressed', on ? 'true' : 'false');
        };
        container.appendChild(label);
    }
}

function peCreatePersonPill(person, isSelected, containerId, summaryId) {
    const label = document.createElement('button');
    label.type = 'button';
    label.className = 'person-pill' + (isSelected ? ' selected' : '');
    label.dataset.value = person.id;
    label.dataset.name = person.name.toLowerCase();
    label.setAttribute('aria-pressed', isSelected ? 'true' : 'false');

    const check = document.createElement('span');
    check.className = 'check-icon';
    check.setAttribute('aria-hidden', 'true');
    check.innerHTML = '<svg viewBox="0 0 10 10" fill="none"><path d="M2 5.5L4 7.5L8 3" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    label.appendChild(check);

    const nameSpan = document.createElement('span');
    nameSpan.textContent = person.name;
    label.appendChild(nameSpan);

    const roleEmoji = peRoleEmoji(person);
    if (roleEmoji) {
        const emojiSpan = document.createElement('span');
        emojiSpan.className = 'role-emoji';
        emojiSpan.textContent = roleEmoji;
        label.appendChild(emojiSpan);
    }

    label.onclick = () => {
        const on = label.classList.toggle('selected');
        label.setAttribute('aria-pressed', on ? 'true' : 'false');
        peUpdateSummary(containerId, summaryId);
    };
    return label;
}

function peRenderPersonPills(containerId, summaryId, data, selectedIds) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    for (const person of data) {
        container.appendChild(peCreatePersonPill(person, selectedIds.includes(person.id), containerId, summaryId));
    }
    if (!data || data.length === 0) {
        container.innerHTML = '<span class="pe-empty">No people available</span>';
    }
    peUpdateSummary(containerId, summaryId);
}

function peUpdateSummary(containerId, summaryId) {
    const summary = document.getElementById(summaryId);
    if (!summary) return;
    const container = document.getElementById(containerId);
    const selected = container.querySelectorAll('.person-pill.selected');

    summary.innerHTML = '';
    if (selected.length === 0) {
        const none = document.createElement('span');
        none.className = 'none-text';
        none.textContent = 'None selected';
        summary.appendChild(none);
        return;
    }
    selected.forEach(label => {
        const chip = document.createElement('span');
        chip.className = 'selected-chip';
        chip.textContent = label.querySelector('span:nth-child(2)').textContent;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.setAttribute('aria-label', 'Remove');
        removeBtn.innerHTML = '&times;';
        removeBtn.onclick = (e) => {
            e.stopPropagation();
            label.classList.remove('selected');
            label.setAttribute('aria-pressed', 'false');
            peUpdateSummary(containerId, summaryId);
        };
        chip.appendChild(removeBtn);
        summary.appendChild(chip);
    });
}

/* Live name filter across the three people containers. */
function peFilterPeople(searchInputId, sectionIds) {
    const query = document.getElementById(searchInputId).value.toLowerCase().trim();
    for (const sectionId of sectionIds) {
        const container = document.getElementById(sectionId);
        if (!container) continue;
        container.querySelectorAll('.person-pill').forEach(pill => {
            const name = pill.dataset.name || '';
            pill.classList.toggle('hidden', !!query && !name.includes(query));
        });
    }
}

/* Collect selected ids (ints) from a pill container. */
function peCollectIds(containerId) {
    return Array.from(document.querySelectorAll('#' + containerId + ' .selected'))
        .map(el => parseInt(el.dataset.value));
}

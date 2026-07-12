window.PlanReactionEditor = (() => {
    const MAX = 4;

    function row(option, callbacks = {}) {
        const onChange = callbacks.onChange || (() => {});
        const onCommit = callbacks.onCommit || (() => {});
        const changed = (commit = false) => {
            onChange();
            if (commit) onCommit();
        };
        const wrap = document.createElement('div');
        wrap.className = 'plan-reaction-row';

        const emoji = document.createElement('input');
        emoji.type = 'text';
        emoji.className = 'plan-reaction-emoji cfg-field';
        emoji.maxLength = 82;
        emoji.placeholder = ':emoji:';
        emoji.setAttribute('aria-label', 'Slack emoji shortcode');
        emoji.value = option.emoji ? `:${option.emoji}:` : '';

        const label = document.createElement('input');
        label.type = 'text';
        label.className = 'plan-reaction-label cfg-field cfg-field-wide';
        label.maxLength = 80;
        label.placeholder = 'What this reaction means';
        label.setAttribute('aria-label', 'Member-facing reaction label');
        label.value = option.label || '';

        const up = document.createElement('button');
        up.type = 'button';
        up.textContent = 'Up';
        up.setAttribute('aria-label', 'Move reaction up');
        up.onclick = () => {
            if (wrap.previousElementSibling) {
                wrap.parentNode.insertBefore(wrap, wrap.previousElementSibling);
            }
            changed(true);
        };

        const down = document.createElement('button');
        down.type = 'button';
        down.textContent = 'Down';
        down.setAttribute('aria-label', 'Move reaction down');
        down.onclick = () => {
            if (wrap.nextElementSibling) {
                wrap.parentNode.insertBefore(wrap.nextElementSibling, wrap);
            }
            changed(true);
        };

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = 'Remove';
        remove.setAttribute('aria-label', 'Remove reaction');
        remove.onclick = () => {
            wrap.remove();
            changed(true);
        };

        for (const button of [up, down, remove]) {
            button.className = 'plan-reaction-action';
        }

        emoji.addEventListener('input', onChange);
        label.addEventListener('input', onChange);
        emoji.addEventListener('change', onCommit);
        label.addEventListener('change', onCommit);
        wrap.append(emoji, label, up, down, remove);
        return wrap;
    }

    function set(container, options, callbacks = {}) {
        container.replaceChildren();
        (options || []).forEach(option => {
            container.appendChild(row(option, callbacks));
        });
    }

    function get(container) {
        return Array.from(container.querySelectorAll('.plan-reaction-row')).map(item => ({
            emoji: item.querySelector('.plan-reaction-emoji').value.trim(),
            label: item.querySelector('.plan-reaction-label').value.trim(),
        }));
    }

    function add(container, callbacks = {}) {
        if (container.querySelectorAll('.plan-reaction-row').length >= MAX) {
            return false;
        }
        container.appendChild(row({emoji: '', label: ''}, callbacks));
        (callbacks.onChange || (() => {}))();
        return true;
    }

    return {MAX, set, get, add};
})();

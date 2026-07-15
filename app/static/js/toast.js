/**
 * Shared toast notification system for TCSC Admin pages
 *
 * Usage:
 *   showToast('Operation successful', 'success');
 *   showToast('Something went wrong', 'error');
 *   showToast('Please note...', 'info');
 *   showToast('Warning message', 'warning');
 */
window.showToast = function(message, type = 'info') {
    // Create or get container
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'fixed top-4 right-4 z-50 flex flex-col gap-2';
        document.body.appendChild(container);
    }

    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ',
        warning: '⚠'
    };

    const colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        info: 'bg-tcsc-navy',
        warning: 'bg-yellow-500'
    };

    const toast = document.createElement('div');
    toast.className = `${colors[type] || colors.info} text-white px-4 py-3 rounded-tcsc shadow-lg flex items-center gap-3 min-w-[280px] max-w-md transform translate-x-full transition-transform duration-300`;

    const icon = document.createElement('span');
    icon.className = 'text-lg flex-shrink-0';
    icon.textContent = icons[type] || icons.info;

    const messageNode = document.createElement('span');
    messageNode.className = 'flex-1 text-sm';
    messageNode.textContent = String(message ?? '');

    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'text-white/70 hover:text-white text-xl leading-none flex-shrink-0';
    dismiss.setAttribute('aria-label', 'Dismiss notification');
    dismiss.textContent = '×';
    dismiss.addEventListener('click', () => toast.remove());

    toast.append(icon, messageNode, dismiss);

    container.appendChild(toast);

    // Trigger slide-in animation
    requestAnimationFrame(() => {
        toast.classList.remove('translate-x-full');
    });

    // Auto-dismiss after 4 seconds
    setTimeout(() => {
        toast.classList.add('translate-x-full');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
};

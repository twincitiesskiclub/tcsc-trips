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
        success: '&#10003;',
        error: '&#10007;',
        info: '&#8505;',
        warning: '&#9888;'
    };

    const colors = {
        success: 'bg-green-600',
        error: 'bg-red-600',
        info: 'bg-tcsc-navy',
        warning: 'bg-yellow-500'
    };

    const toast = document.createElement('div');
    toast.className = `${colors[type] || colors.info} text-white px-4 py-3 rounded-tcsc shadow-lg flex items-center gap-3 min-w-[280px] max-w-md transform translate-x-full transition-transform duration-300`;
    toast.innerHTML = `
        <span class="text-lg flex-shrink-0">${icons[type] || icons.info}</span>
        <span class="flex-1 text-sm">${message}</span>
        <button class="text-white/70 hover:text-white text-xl leading-none flex-shrink-0" onclick="this.parentElement.remove()">&times;</button>
    `;

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

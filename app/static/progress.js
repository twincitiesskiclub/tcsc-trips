// progress.js — Progress bar navigation for multi-section forms

document.addEventListener('DOMContentLoaded', () => {
  const steps = document.querySelectorAll('.progress-step');
  if (!steps.length) return;

  steps.forEach(step => {
    step.addEventListener('click', () => {
      const targetId = step.dataset.section;
      const target = document.getElementById(targetId);
      if (!target) return;

      // Update active step
      steps.forEach(s => s.classList.remove('progress-step--active'));
      step.classList.add('progress-step--active');

      // Scroll to section
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // Update active step on scroll
  const sections = Array.from(steps).map(s => document.getElementById(s.dataset.section)).filter(Boolean);

  let ticking = false;
  window.addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const scrollY = window.scrollY + 120; // offset for sticky header/progress bar
      let activeIndex = 0;
      sections.forEach((section, i) => {
        if (section.offsetTop <= scrollY) {
          activeIndex = i;
        }
      });
      steps.forEach(s => s.classList.remove('progress-step--active'));
      steps[activeIndex].classList.add('progress-step--active');
      ticking = false;
    });
  });
});

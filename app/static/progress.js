document.addEventListener('DOMContentLoaded', function () {
  var steps = document.querySelectorAll('.progress-step');
  var lines = document.querySelectorAll('.progress-bar__line');
  var sections = [];

  steps.forEach(function (step) {
    var id = step.getAttribute('data-section');
    var el = document.getElementById(id);
    if (el) sections.push({ id: id, el: el, step: step });
  });

  if (sections.length === 0) return;

  function updateProgress(activeIndex) {
    steps.forEach(function (step, i) {
      step.classList.remove('progress-step--active', 'progress-step--completed');
      if (i < activeIndex) {
        step.classList.add('progress-step--completed');
        var num = step.querySelector('.progress-step__number');
        if (num) num.textContent = '✓';
      } else if (i === activeIndex) {
        step.classList.add('progress-step--active');
        var num = step.querySelector('.progress-step__number');
        if (num) num.textContent = String(i + 1);
      } else {
        var num = step.querySelector('.progress-step__number');
        if (num) num.textContent = String(i + 1);
      }
    });

    lines.forEach(function (line, i) {
      if (i < activeIndex) {
        line.classList.add('progress-bar__line--completed');
      } else {
        line.classList.remove('progress-bar__line--completed');
      }
    });
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        for (var i = 0; i < sections.length; i++) {
          if (sections[i].el === entry.target) {
            updateProgress(i);
            break;
          }
        }
      }
    });
  }, {
    rootMargin: '-20% 0px -60% 0px',
    threshold: 0
  });

  sections.forEach(function (s) { observer.observe(s.el); });

  steps.forEach(function (step) {
    step.addEventListener('click', function () {
      var id = step.getAttribute('data-section');
      var target = document.getElementById(id);
      if (target) {
        var offset = document.querySelector('.progress-bar').offsetHeight + 20;
        var top = target.getBoundingClientRect().top + window.pageYOffset - offset;
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });
});

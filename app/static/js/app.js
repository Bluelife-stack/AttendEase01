/**
 * AttendEase — Main Application Scripts
 */

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar && overlay) {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
  }
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar && overlay) {
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
  }
}

// Auto dismiss flash messages after 6 seconds
document.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(flash => {
    setTimeout(() => {
      flash.style.transition = 'opacity 0.4s ease';
      flash.style.opacity = '0';
      setTimeout(() => flash.remove(), 400);
    }, 6000);
  });

  // Prevent multiple form submissions
  const forms = document.querySelectorAll('form:not([method="get"])');
  forms.forEach(form => {
    form.addEventListener('submit', function() {
      const btn = form.querySelector('button[type="submit"]');
      if (btn && !btn.disabled) {
        // slight timeout so the form data is captured before disabling
        setTimeout(() => {
          btn.disabled = true;
          btn.style.opacity = '0.7';
          btn.style.cursor = 'not-allowed';
        }, 50);
      }
    });
  });
});

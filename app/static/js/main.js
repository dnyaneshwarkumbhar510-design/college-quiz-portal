/**
 * COLLEGE QUIZ PORTAL - MAIN CLIENT JAVASCRIPT
 */

// Mobile Navigation Toggle
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('mobileNavToggle');
  const mobileMenu = document.getElementById('mobileNavMenu');
  const hamburgerIcon = toggleBtn?.querySelector('.hamburger-icon');

  if (toggleBtn && mobileMenu) {

    // Toggle mobile navigation
    toggleBtn.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.toggle('open');

      toggleBtn.setAttribute(
        'aria-expanded',
        isOpen ? 'true' : 'false'
      );

      toggleBtn.setAttribute(
        'aria-label',
        isOpen
          ? 'Close navigation menu'
          : 'Open navigation menu'
      );

      // Change hamburger icon
      if (hamburgerIcon) {
        hamburgerIcon.textContent = isOpen ? '✕' : '☰';
      }
    });

    // Close menu when a navigation link is clicked
    mobileMenu.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => {
        mobileMenu.classList.remove('open');

        toggleBtn.setAttribute('aria-expanded', 'false');
        toggleBtn.setAttribute(
          'aria-label',
          'Open navigation menu'
        );

        if (hamburgerIcon) {
          hamburgerIcon.textContent = '☰';
        }
      });
    });

    // Close mobile menu when switching to desktop
    window.addEventListener('resize', () => {
      if (window.innerWidth > 768) {
        mobileMenu.classList.remove('open');

        toggleBtn.setAttribute('aria-expanded', 'false');
        toggleBtn.setAttribute(
          'aria-label',
          'Open navigation menu'
        );

        if (hamburgerIcon) {
          hamburgerIcon.textContent = '☰';
        }
      }
    });
  }


  // Dismiss feedback banners
  document.querySelectorAll('.alert-dismiss-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const alert = e.target.closest('.alert');

      if (alert) {
        alert.remove();
      }
    });
  });
});


// CSV Export Helper
function downloadCsv(filename, rows) {
  const csvContent =
    'data:text/csv;charset=utf-8,' +
    rows
      .map(row =>
        row
          .map(cell => {
            const str =
              cell === null || cell === undefined
                ? ''
                : String(cell);

            if (
              str.includes(',') ||
              str.includes('"') ||
              str.includes('\n')
            ) {
              return `"${str.replace(/"/g, '""')}"`;
            }

            return str;
          })
          .join(',')
      )
      .join('\n');

  const encodedUri = encodeURI(csvContent);

  const link = document.createElement('a');

  link.setAttribute('href', encodedUri);
  link.setAttribute('download', filename);

  document.body.appendChild(link);

  link.click();

  document.body.removeChild(link);
}
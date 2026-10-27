/**
 * COLLEGE QUIZ PORTAL - MAIN CLIENT JAVASCRIPT
 */

// Mobile Navigation Toggle
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('mobileNavToggle');
  const mobileMenu = document.getElementById('mobileNavMenu');
  
  if (toggleBtn && mobileMenu) {
    toggleBtn.addEventListener('click', () => {
      mobileMenu.classList.toggle('hidden');
    });
  }

  // Dismiss feedback banners
  document.querySelectorAll('.alert-dismiss-btn').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      const alert = e.target.closest('.alert');
      if (alert) alert.remove();
    });
  });
});

// CSV Export Helper
function downloadCsv(filename, rows) {
  const csvContent = 'data:text/csv;charset=utf-8,' + rows.map(row => 
    row.map(cell => {
      const str = cell === null || cell === undefined ? '' : String(cell);
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    }).join(',')
  ).join('\n');

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

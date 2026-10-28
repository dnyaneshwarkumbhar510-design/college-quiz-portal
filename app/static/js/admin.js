/**
 * COLLEGE QUIZ PORTAL - FACULTY ADMIN JAVASCRIPT
 */

document.addEventListener('DOMContentLoaded', () => {
  // Mobile drawer toggle
  const sidebar = document.getElementById('adminSidebar');
  const openBtn = document.getElementById('openSidebarBtn');
  const closeBtn = document.getElementById('closeSidebarBtn');
  const overlay = document.getElementById('sidebarOverlay');

  const closeSidebar = () => {
    sidebar?.classList.remove('open');
    if (overlay) {
      overlay.classList.add('hidden');
      overlay.style.display = 'none';
    }
  };

  const openSidebar = () => {
    sidebar?.classList.add('open');
    if (overlay) {
      overlay.classList.remove('hidden');
      overlay.style.display = 'block';
    }
  };

  if (openBtn) openBtn.addEventListener('click', openSidebar);
  if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
  if (overlay) overlay.addEventListener('click', closeSidebar);

  // Close drawer when any sidebar navigation link is clicked on mobile or tablet
  document.querySelectorAll('.sidebar-nav a').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 1024) {
        closeSidebar();
      }
    });
  });

  // Close drawer on Escape key press
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeSidebar();
    }
  });

  // Automatically close mobile drawer if window is resized to desktop width
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1024) {
      closeSidebar();
    }
  });
});

// Toggle Quiz Publish Status
async function toggleQuizPublish(quizId, currentStatus) {
  const targetStatus = !currentStatus;
  try {
    const res = await fetch(`/api/admin/quizzes/${quizId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_published: targetStatus })
    });
    const data = await res.json();
    if (data.success) {
      window.location.reload();
    } else {
      alert(data.message || 'Failed to update quiz publish state.');
    }
  } catch (err) {
    alert('Network communication failure.');
  }
}

// Delete Quiz
let quizToDeleteId = null;

function openDeleteQuizModal(quizId, quizTitle) {
  quizToDeleteId = quizId;
  const titleSpan = document.getElementById('deleteQuizTitle');
  if (titleSpan) titleSpan.textContent = quizTitle;
  const modal = document.getElementById('deleteQuizModal');
  if (modal) modal.classList.add('open');
}

function closeDeleteQuizModal() {
  quizToDeleteId = null;
  const modal = document.getElementById('deleteQuizModal');
  if (modal) modal.classList.remove('open');
}

async function confirmDeleteQuiz() {
  if (!quizToDeleteId) return;
  try {
    const res = await fetch(`/api/admin/quizzes/${quizToDeleteId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (data.success) {
      window.location.reload();
    } else {
      alert(data.message || 'Failed to delete quiz.');
    }
  } catch (err) {
    alert('Error deleting quiz.');
  }
}

// Question Editor Modal Logic
let currentEditingQuestionId = null;

function openAddQuestionModal() {
  currentEditingQuestionId = null;
  document.getElementById('questionModalTitle').textContent = 'Add Question';
  document.getElementById('questionForm').reset();
  document.getElementById('questionIdInput').value = '';
  document.getElementById('questionModalError').classList.add('hidden');
  document.getElementById('questionEditorModal').classList.add('open');
}

function openEditQuestionModal(questionJson) {
  const q = typeof questionJson === 'string' ? JSON.parse(questionJson) : questionJson;
  currentEditingQuestionId = q.id;
  document.getElementById('questionModalTitle').textContent = 'Edit Question';
  document.getElementById('questionIdInput').value = q.id;
  document.getElementById('qTextInput').value = q.question_text || '';
  document.getElementById('qOptA').value = q.option_a || '';
  document.getElementById('qOptB').value = q.option_b || '';
  document.getElementById('qOptC').value = q.option_c || '';
  document.getElementById('qOptD').value = q.option_d || '';
  document.getElementById('qCorrectSelect').value = q.correct_answer || 'A';
  document.getElementById('qMarksInput').value = q.marks || 1;
  document.getElementById('qExplanationInput').value = q.explanation || '';
  document.getElementById('questionModalError').classList.add('hidden');
  document.getElementById('questionEditorModal').classList.add('open');
}

function closeQuestionModal() {
  document.getElementById('questionEditorModal').classList.remove('open');
}

async function handleSaveQuestion(e, targetQuizId) {
  e.preventDefault();
  const qId = document.getElementById('questionIdInput').value;
  const qText = document.getElementById('qTextInput').value.trim();
  const optA = document.getElementById('qOptA').value.trim();
  const optB = document.getElementById('qOptB').value.trim();
  const optC = document.getElementById('qOptC').value.trim();
  const optD = document.getElementById('qOptD').value.trim();
  const correct = document.getElementById('qCorrectSelect').value;
  const marks = parseFloat(document.getElementById('qMarksInput').value) || 1.0;
  const explanation = document.getElementById('qExplanationInput').value.trim();

  const errBox = document.getElementById('questionModalError');
  errBox.classList.add('hidden');

  if (!qText || !optA || !optB || !optC || !optD) {
    errBox.textContent = 'Please fill out question text and all four options.';
    errBox.classList.remove('hidden');
    return;
  }

  const payload = {
    quiz_id: targetQuizId,
    question_text: qText,
    option_a: optA,
    option_b: optB,
    option_c: optC,
    option_d: optD,
    correct_answer: correct,
    marks: marks,
    explanation: explanation
  };

  try {
    const url = qId ? `/api/admin/questions/${qId}` : '/api/admin/questions';
    const method = qId ? 'PUT' : 'POST';

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.success) {
      window.location.reload();
    } else {
      errBox.textContent = data.message || 'Failed to save question.';
      errBox.classList.remove('hidden');
    }
  } catch (err) {
    errBox.textContent = 'Network communication failure.';
    errBox.classList.remove('hidden');
  }
}

// Delete Question Modal Logic
let questionToDeleteId = null;

function openDeleteQuestionModal(questionId) {
  questionToDeleteId = questionId;
  document.getElementById('deleteQuestionModal').classList.add('open');
}

function closeDeleteQuestionModal() {
  questionToDeleteId = null;
  document.getElementById('deleteQuestionModal').classList.remove('open');
}

async function confirmDeleteQuestion(quizId) {
  if (!questionToDeleteId) return;
  try {
    const res = await fetch(`/api/admin/questions/${questionToDeleteId}?quizId=${quizId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (data.success) {
      window.location.reload();
    } else {
      alert(data.message || 'Failed to delete question.');
    }
  } catch (err) {
    alert('Error communicating with server.');
  }
}

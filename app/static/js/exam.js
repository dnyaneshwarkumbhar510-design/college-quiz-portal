/**
 * COLLEGE QUIZ PORTAL - EXAMINATION ENGINE (VANILLA JS)
 * High-Integrity, Server-Synchronized Timer, Dynamic Palette, Auto-Submit
 */

class ExaminationEngine {
  constructor(quizId) {
    this.quizId = quizId;
    this.quiz = null;
    this.attempt = null;
    this.questions = [];
    this.currentIndex = 0;
    this.answers = {}; // question_id -> 'A' | 'B' | 'C' | 'D' | null
    this.remainingSeconds = 0;
    this.isSubmitting = false;
    this.timerInterval = null;

    this.init();
  }

  async init() {
    this.showLoading();

    try {
      const res = await fetch('/api/student/start-quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quizId: this.quizId })
      });

      const data = await res.json();
      if (!data.success) {
        this.showError(data.message || 'Failed to initialize examination session.');
        return;
      }

      if (data.isCompleted && data.attemptId) {
        window.location.replace(`/student/results/${data.attemptId}`);
        return;
      }

      this.quiz = data.quiz;
      this.attempt = data.attempt;
      this.questions = data.questions || [];
      this.remainingSeconds = data.remainingSeconds || 900;

      if (this.questions.length === 0) {
        this.showError('No questions available in this examination unit.');
        return;
      }

      this.setupBeforeUnload();
      this.startCountdownTimer();
      this.render();
    } catch (err) {
      this.showError('Network connectivity error. Please check your internet connection.');
    }
  }

  setupBeforeUnload() {
    window.addEventListener('beforeunload', (e) => {
      if (!this.isSubmitting) {
        e.preventDefault();
        e.returnValue = 'An examination is in progress. Are you sure you want to navigate away?';
        return 'An examination is in progress. Are you sure you want to navigate away?';
      }
    });
  }

  startCountdownTimer() {
    this.updateTimerDisplay();
    this.timerInterval = setInterval(() => {
      if (this.remainingSeconds <= 1) {
        clearInterval(this.timerInterval);
        this.remainingSeconds = 0;
        this.updateTimerDisplay();
        this.submitFinal(true); // Auto-submit on timer expiry
        return;
      }
      this.remainingSeconds--;
      this.updateTimerDisplay();
    }, 1000);
  }

  updateTimerDisplay() {
    const timerElem = document.getElementById('examTimer');
    const timerBox = document.getElementById('examTimerBox');
    if (!timerElem) return;

    const mins = Math.floor(this.remainingSeconds / 60);
    const secs = this.remainingSeconds % 60;
    const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    timerElem.textContent = formatted;

    if (this.remainingSeconds <= 120 && this.remainingSeconds > 0) {
      timerBox?.classList.add('urgent');
    } else {
      timerBox?.classList.remove('urgent');
    }
  }

  selectOption(optKey) {
    const q = this.questions[this.currentIndex];
    if (!q) return;
    this.answers[q.id] = optKey;
    this.renderQuestion();
    this.renderPalette();
  }

  clearSelection() {
    const q = this.questions[this.currentIndex];
    if (!q) return;
    delete this.answers[q.id];
    this.renderQuestion();
    this.renderPalette();
  }

  goToNext() {
    if (this.currentIndex < this.questions.length - 1) {
      this.currentIndex++;
      this.renderQuestion();
      this.renderPalette();
    }
  }

  goToPrevious() {
    if (this.currentIndex > 0) {
      this.currentIndex--;
      this.renderQuestion();
      this.renderPalette();
    }
  }

  goToQuestion(idx) {
    if (idx >= 0 && idx < this.questions.length) {
      this.currentIndex = idx;
      this.renderQuestion();
      this.renderPalette();
    }
  }

  openSubmitModal() {
    const answeredCount = Object.keys(this.answers).length;
    const totalCount = this.questions.length;
    const unattemptedCount = totalCount - answeredCount;

    document.getElementById('modalTotalQuestions').textContent = totalCount;
    document.getElementById('modalAnsweredCount').textContent = answeredCount;
    document.getElementById('modalUnansweredCount').textContent = unattemptedCount;

    const warningBox = document.getElementById('modalWarningBox');
    if (unattemptedCount > 0) {
      warningBox.innerHTML = `
        <div class="alert alert-warning" style="margin-bottom: 0;">
          <span>⚠️ You have <strong>${unattemptedCount} unanswered questions</strong>! Unattempted questions receive 0 marks.</span>
        </div>
      `;
    } else {
      warningBox.innerHTML = `
        <div class="alert alert-success" style="margin-bottom: 0;">
          <span>✓ All <strong>${totalCount} questions answered</strong>! Your responses are ready for immediate evaluation.</span>
        </div>
      `;
    }

    const modal = document.getElementById('submitConfirmModal');
    modal.classList.add('open');
  }

  closeSubmitModal() {
    const modal = document.getElementById('submitConfirmModal');
    modal.classList.remove('open');
  }

  async submitFinal(isAutoSubmit = false) {
    if (this.isSubmitting) return;
    this.isSubmitting = true;
    this.closeSubmitModal();

    if (this.timerInterval) clearInterval(this.timerInterval);

    // Show submitting overlay
    document.getElementById('submittingOverlay').classList.remove('hidden');

    try {
      const res = await fetch('/api/student/submit-quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          attemptId: this.attempt.id,
          answers: this.answers
        })
      });

      const data = await res.json();
      if (data.success && data.attemptId) {
        window.location.replace(`/student/results/${data.attemptId}`);
      } else {
        alert(data.message || 'Evaluation submission failed. Please notify the invigilator.');
        this.isSubmitting = false;
        document.getElementById('submittingOverlay').classList.add('hidden');
      }
    } catch (err) {
      alert('Network failure transmitting examination responses. Please try submitting again.');
      this.isSubmitting = false;
      document.getElementById('submittingOverlay').classList.add('hidden');
    }
  }

  render() {
    document.getElementById('examLoadingState').classList.add('hidden');
    document.getElementById('examMainWorkArea').classList.remove('hidden');

    document.getElementById('headerQuizTitle').textContent = this.quiz.title;
    document.getElementById('headerSubjectName').textContent = this.quiz.subject_name || 'Subject';
    document.getElementById('headerUnitBadge').textContent = `Unit ${this.quiz.unit_number || 1}`;

    this.renderQuestion();
    this.renderPalette();
  }

  renderQuestion() {
    const q = this.questions[this.currentIndex];
    const total = this.questions.length;
    const selected = this.answers[q.id];

    document.getElementById('qCounter').textContent = `Question ${this.currentIndex + 1} of ${total}`;
    document.getElementById('qMarks').textContent = `(${q.marks} Mark${q.marks > 1 ? 's' : ''})`;
    document.getElementById('qText').textContent = q.question_text;

    // Progress bar
    const progressPct = Math.round(((this.currentIndex + 1) / total) * 100);
    document.getElementById('qProgressFill').style.width = `${progressPct}%`;

    // Clear button visibility
    const clearBtn = document.getElementById('clearSelectionBtn');
    if (selected) {
      clearBtn.classList.remove('hidden');
    } else {
      clearBtn.classList.add('hidden');
    }

    // Options rendering
    const optionsContainer = document.getElementById('mcqOptionsContainer');
    optionsContainer.innerHTML = '';

    const opts = [
      { key: 'A', text: q.option_a },
      { key: 'B', text: q.option_b },
      { key: 'C', text: q.option_c },
      { key: 'D', text: q.option_d }
    ];

    opts.forEach(opt => {
      const isChosen = selected === opt.key;
      const optItem = document.createElement('div');
      optItem.className = `mcq-option-item ${isChosen ? 'selected' : ''}`;
      optItem.onclick = () => this.selectOption(opt.key);

      optItem.innerHTML = `
        <div class="mcq-key-circle">${opt.key}</div>
        <div class="mcq-option-text">${this.escapeHtml(opt.text)}</div>
      `;
      optionsContainer.appendChild(optItem);
    });

    // Prev / Next button states
    const prevBtn = document.getElementById('prevQuestionBtn');
    const nextBtn = document.getElementById('nextQuestionBtn');

    prevBtn.disabled = this.currentIndex === 0;
    if (this.currentIndex === total - 1) {
      nextBtn.textContent = 'Review All';
      nextBtn.onclick = () => this.openSubmitModal();
    } else {
      nextBtn.textContent = 'Next Question →';
      nextBtn.onclick = () => this.goToNext();
    }
  }

  renderPalette() {
    const paletteContainer = document.getElementById('paletteGrid');
    paletteContainer.innerHTML = '';
    const total = this.questions.length;

    let answeredCount = 0;

    for (let i = 0; i < total; i++) {
      const q = this.questions[i];
      const hasAnswered = !!this.answers[q.id];
      if (hasAnswered) answeredCount++;

      const isCurrent = i === this.currentIndex;

      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'palette-btn';

      if (isCurrent) {
        btn.classList.add('current');
      } else if (hasAnswered) {
        btn.classList.add('answered');
      }

      btn.textContent = i + 1;
      btn.onclick = () => this.goToQuestion(i);
      paletteContainer.appendChild(btn);
    }

    document.getElementById('paletteAnsweredCount').textContent = `${answeredCount} Answered`;
    document.getElementById('paletteSummaryAnswered').textContent = answeredCount;
    document.getElementById('paletteSummaryRemaining').textContent = total - answeredCount;
  }

  showLoading() {
    document.getElementById('examLoadingState')?.classList.remove('hidden');
    document.getElementById('examErrorState')?.classList.add('hidden');
    document.getElementById('examMainWorkArea')?.classList.add('hidden');
  }

  showError(msg) {
    document.getElementById('examLoadingState')?.classList.add('hidden');
    document.getElementById('examMainWorkArea')?.classList.add('hidden');
    const errState = document.getElementById('examErrorState');
    if (errState) {
      errState.classList.remove('hidden');
      document.getElementById('examErrorMessage').textContent = msg;
    }
  }

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
}

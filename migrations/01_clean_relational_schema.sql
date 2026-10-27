-- ========================================================
-- COLLEGE QUIZ PORTAL - DATABASE MIGRATION V2 (CLEAN ARCHITECTURE)
-- PostgreSQL / Supabase Schema
-- Single Source of Truth with Relational Integrity
-- ========================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================================
-- 1. PROFILES / USERS (Unified Authenticated Entities)
-- ========================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id TEXT UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('student', 'faculty', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- 2. STUDENTS TABLE
-- Supported Divisions: A, B, C, D, E, F, G, H, I, J, K, L, M, N, O, P, Q
-- ========================================================
CREATE TABLE IF NOT EXISTS public.students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id TEXT,
    profile_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    full_name TEXT NOT NULL,
    roll_number TEXT NOT NULL,
    class_name TEXT NOT NULL,
    division TEXT NOT NULL CHECK (division IN (
        'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q'
    )),
    department TEXT NOT NULL,
    email TEXT,
    student_id_number TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_student_roll_class_div UNIQUE (roll_number, class_name, division)
);

-- ========================================================
-- 3. FACULTY / ADMIN TABLE
-- Credentials strictly protected server-side
-- ========================================================
CREATE TABLE IF NOT EXISTS public.faculty (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id TEXT,
    profile_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department TEXT NOT NULL,
    password_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- 4. SUBJECTS TABLE (Academic Courses)
-- ========================================================
CREATE TABLE IF NOT EXISTS public.subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    class_name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- 5. QUIZZES TABLE (Flexible Quiz Size: 5, 10, 15, 20, 30, 40+ Qs)
-- ========================================================
CREATE TABLE IF NOT EXISTS public.quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    subject_id UUID REFERENCES public.subjects(id) ON DELETE SET NULL,
    subject TEXT,
    unit_number INT NOT NULL DEFAULT 1 CHECK (unit_number >= 1),
    unit_title TEXT,
    class_name TEXT NOT NULL,
    division TEXT DEFAULT 'All',
    department TEXT NOT NULL,
    duration INT NOT NULL DEFAULT 15 CHECK (duration >= 1),
    total_questions INT NOT NULL DEFAULT 0,
    marks_per_question NUMERIC(5, 2) NOT NULL DEFAULT 1.0,
    total_marks NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    pass_percentage NUMERIC(5, 2) NOT NULL DEFAULT 40.0 CHECK (pass_percentage BETWEEN 1 AND 100),
    created_by UUID REFERENCES public.faculty(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    published BOOLEAN NOT NULL DEFAULT false,
    randomize_questions BOOLEAN NOT NULL DEFAULT false,
    randomize_options BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- 6. QUESTIONS TABLE (Real Faculty-Created Questions)
-- ========================================================
CREATE TABLE IF NOT EXISTS public.questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    question_type TEXT NOT NULL DEFAULT 'mcq' CHECK (question_type IN ('mcq', 'multiple_choice')),
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_answer TEXT NOT NULL CHECK (correct_answer IN ('A', 'B', 'C', 'D')),
    explanation TEXT,
    marks NUMERIC(5, 2) NOT NULL DEFAULT 1.0 CHECK (marks >= 0.5),
    created_by UUID REFERENCES public.faculty(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- 7. QUIZ_QUESTIONS TABLE (Authoritative Relational Join Table)
-- Permanently stores Quiz <-> Question associations with explicit ordering
-- Prevents orphan questions and preserves relationships permanently
-- ========================================================
CREATE TABLE IF NOT EXISTS public.quiz_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID NOT NULL REFERENCES public.quizzes(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    question_order INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_quiz_question UNIQUE (quiz_id, question_id)
);

-- ========================================================
-- 8. ATTEMPTS TABLE (Server-Timed Student Examination Sessions)
-- ========================================================
CREATE TABLE IF NOT EXISTS public.attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID NOT NULL REFERENCES public.quizzes(id) ON DELETE CASCADE,
    student_id UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    server_end_time TIMESTAMPTZ NOT NULL,
    total_questions INT NOT NULL DEFAULT 0,
    attempted_questions INT NOT NULL DEFAULT 0,
    correct_answers INT NOT NULL DEFAULT 0,
    wrong_answers INT NOT NULL DEFAULT 0,
    unattempted INT NOT NULL DEFAULT 0,
    total_marks NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    obtained_marks NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    percentage NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'PASS', 'FAIL')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ========================================================
-- 9. ANSWERS TABLE (Individual Question Attempt Records)
-- ========================================================
CREATE TABLE IF NOT EXISTS public.answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID NOT NULL REFERENCES public.attempts(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    selected_answer TEXT CHECK (selected_answer IN ('A', 'B', 'C', 'D')),
    is_correct BOOLEAN NOT NULL DEFAULT false,
    marks_awarded NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_attempt_question UNIQUE (attempt_id, question_id)
);

-- ========================================================
-- INDEXES FOR MAXIMUM QUERY EFFICIENCY & INTEGRITY
-- ========================================================
CREATE INDEX IF NOT EXISTS idx_students_roll ON public.students(roll_number, class_name, division);
CREATE INDEX IF NOT EXISTS idx_students_dept ON public.students(department, class_name);
CREATE INDEX IF NOT EXISTS idx_quizzes_subject ON public.quizzes(subject_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_published ON public.quizzes(published, status);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz ON public.quiz_questions(quiz_id, question_order);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_question ON public.quiz_questions(question_id);
CREATE INDEX IF NOT EXISTS idx_attempts_quiz_student ON public.attempts(quiz_id, student_id);
CREATE INDEX IF NOT EXISTS idx_attempts_student ON public.attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_answers_attempt ON public.answers(attempt_id);

-- ========================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ========================================================
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faculty ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quizzes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.answers ENABLE ROW LEVEL SECURITY;

-- Subjects policies
CREATE POLICY "Allow read subjects" ON public.subjects FOR SELECT USING (true);
CREATE POLICY "Allow manage subjects" ON public.subjects FOR ALL USING (true) WITH CHECK (true);

-- Quizzes policies
CREATE POLICY "Allow read quizzes" ON public.quizzes FOR SELECT USING (true);
CREATE POLICY "Allow manage quizzes" ON public.quizzes FOR ALL USING (true) WITH CHECK (true);

-- Questions & Quiz Questions policies
CREATE POLICY "Allow read questions" ON public.questions FOR SELECT USING (true);
CREATE POLICY "Allow manage questions" ON public.questions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow read quiz_questions" ON public.quiz_questions FOR SELECT USING (true);
CREATE POLICY "Allow manage quiz_questions" ON public.quiz_questions FOR ALL USING (true) WITH CHECK (true);

-- Students policies
CREATE POLICY "Allow read students" ON public.students FOR SELECT USING (true);
CREATE POLICY "Allow manage students" ON public.students FOR ALL USING (true) WITH CHECK (true);

-- Attempts & Answers policies
CREATE POLICY "Allow read attempts" ON public.attempts FOR SELECT USING (true);
CREATE POLICY "Allow manage attempts" ON public.attempts FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow read answers" ON public.answers FOR SELECT USING (true);
CREATE POLICY "Allow manage answers" ON public.answers FOR ALL USING (true) WITH CHECK (true);

-- Profiles & Faculty
CREATE POLICY "Allow read profiles" ON public.profiles FOR SELECT USING (true);
CREATE POLICY "Allow read faculty" ON public.faculty FOR SELECT USING (true);

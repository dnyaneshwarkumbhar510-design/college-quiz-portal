-- ========================================================
-- COLLEGE QUIZ PORTAL - SAFE MIGRATION FROM V1 TO V2
-- Preserves existing valid data and upgrades schema
-- ========================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Create profiles table if it doesn't exist
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id TEXT UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'faculty', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Ensure faculty table exists
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

-- Seed initial faculty account if not exists
INSERT INTO public.faculty (full_name, email, department, password_hash)
VALUES ('Prof. Ankita Gadekar', 'ankita.gadekar@nmiet.edu.in', 'Computer Engineering', 'nmiet@45')
ON CONFLICT (email) DO NOTHING;

-- 3. Upgrade quizzes table with flexible columns
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS subject TEXT;
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS duration INT DEFAULT 15;
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS total_questions INT DEFAULT 0;
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS marks_per_question NUMERIC(5, 2) DEFAULT 1.0;
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS pass_percentage NUMERIC(5, 2) DEFAULT 40.0;
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES public.faculty(id) ON DELETE SET NULL;
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft';
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS published BOOLEAN DEFAULT false;
ALTER TABLE public.quizzes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- Synchronize published from is_published if upgrading from v1
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'quizzes' AND column_name = 'is_published'
    ) THEN
        UPDATE public.quizzes SET published = is_published WHERE published IS NULL OR published = false;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'quizzes' AND column_name = 'duration_minutes'
    ) THEN
        UPDATE public.quizzes SET duration = duration_minutes WHERE duration IS NULL OR duration = 15;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'quizzes' AND column_name = 'passing_percentage'
    ) THEN
        UPDATE public.quizzes SET pass_percentage = passing_percentage WHERE pass_percentage IS NULL OR pass_percentage = 40.0;
    END IF;
END $$;

-- 4. Upgrade questions table
ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS question_type TEXT DEFAULT 'mcq';
ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES public.faculty(id) ON DELETE SET NULL;
ALTER TABLE public.questions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

-- 5. Create authoritative quiz_questions relationship table
CREATE TABLE IF NOT EXISTS public.quiz_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID NOT NULL REFERENCES public.quizzes(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
    question_order INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unique_quiz_question UNIQUE (quiz_id, question_id)
);

-- Safely migrate any existing direct questions.quiz_id associations to quiz_questions
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'questions' AND column_name = 'quiz_id'
    ) THEN
        INSERT INTO public.quiz_questions (quiz_id, question_id, question_order, created_at)
        SELECT 
            q.quiz_id, 
            q.id, 
            ROW_NUMBER() OVER (PARTITION BY q.quiz_id ORDER BY q.created_at ASC) as question_order,
            COALESCE(q.created_at, now())
        FROM public.questions q
        WHERE q.quiz_id IS NOT NULL
        ON CONFLICT (quiz_id, question_id) DO NOTHING;
    END IF;
END $$;

-- Update quiz question counts and total marks accurately based on quiz_questions
UPDATE public.quizzes q
SET 
    total_questions = (
        SELECT COUNT(*) FROM public.quiz_questions qq WHERE qq.quiz_id = q.id
    ),
    total_marks = COALESCE((
        SELECT SUM(ques.marks) 
        FROM public.quiz_questions qq 
        JOIN public.questions ques ON qq.question_id = ques.id 
        WHERE qq.quiz_id = q.id
    ), 0);

-- Enable RLS and add policies
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faculty ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_questions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read profiles" ON public.profiles FOR SELECT USING (true);
CREATE POLICY "Allow read faculty" ON public.faculty FOR SELECT USING (true);
CREATE POLICY "Allow read quiz_questions" ON public.quiz_questions FOR SELECT USING (true);
CREATE POLICY "Allow manage quiz_questions" ON public.quiz_questions FOR ALL USING (true) WITH CHECK (true);

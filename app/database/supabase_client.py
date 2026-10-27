import os
import sqlite3
import uuid
import logging
from config import Config

logger = logging.getLogger(__name__)

# Initialize Supabase client if credentials are configured
supabase_client = None

if Config.SUPABASE_URL and Config.SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        logger.info("Supabase client initialized successfully with remote URL: %s", Config.SUPABASE_URL)
    except Exception as e:
        logger.error("Failed to initialize Supabase client: %s", e)
        supabase_client = None

def get_supabase_client():
    """Returns the remote Supabase client if configured, or None."""
    return supabase_client

def get_db_connection():
    """
    Returns a persistent database connection with foreign key enforcement and dict row factory.
    Used for local persistent relational storage or offline verification.
    Guarantees permanent disk persistence across server restarts and page refreshes.
    """
    db_path = Config.SQLITE_DB_PATH
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

get_local_db_conn = get_db_connection

def init_local_schema():
    """
    Initializes the clean relational schema locally if using local persistent storage.
    Enforces exact relational constraints:
    - profiles
    - students
    - faculty
    - subjects
    - quizzes
    - questions
    - quiz_questions (authoritative join table)
    - attempts
    - answers
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Profiles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        auth_user_id TEXT UNIQUE,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('student', 'faculty', 'admin')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 2. Students
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id TEXT PRIMARY KEY,
        auth_user_id TEXT,
        profile_id TEXT REFERENCES profiles(id) ON DELETE SET NULL,
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
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CONSTRAINT unique_student_roll_class_div UNIQUE (roll_number, class_name, division)
    );
    """)

    # 3. Faculty
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS faculty (
        id TEXT PRIMARY KEY,
        auth_user_id TEXT,
        profile_id TEXT REFERENCES profiles(id) ON DELETE SET NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL,
        password_hash TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 4. Subjects
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id TEXT PRIMARY KEY,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        class_name TEXT NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 5. Quizzes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        subject_id TEXT REFERENCES subjects(id) ON DELETE SET NULL,
        subject TEXT,
        unit_number INTEGER NOT NULL DEFAULT 1,
        unit_title TEXT,
        class_name TEXT NOT NULL,
        division TEXT DEFAULT 'All',
        department TEXT NOT NULL,
        duration INTEGER NOT NULL DEFAULT 15,
        total_questions INTEGER NOT NULL DEFAULT 0,
        marks_per_question REAL NOT NULL DEFAULT 1.0,
        total_marks REAL NOT NULL DEFAULT 0.0,
        pass_percentage REAL NOT NULL DEFAULT 40.0,
        created_by TEXT REFERENCES faculty(id) ON DELETE SET NULL,
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
        published INTEGER NOT NULL DEFAULT 0,
        randomize_questions INTEGER NOT NULL DEFAULT 0,
        randomize_options INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 6. Questions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        question_text TEXT NOT NULL,
        question_type TEXT NOT NULL DEFAULT 'mcq',
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_answer TEXT NOT NULL CHECK (correct_answer IN ('A', 'B', 'C', 'D')),
        explanation TEXT,
        marks REAL NOT NULL DEFAULT 1.0,
        created_by TEXT REFERENCES faculty(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 7. Quiz Questions (Authoritative Join Table)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quiz_questions (
        id TEXT PRIMARY KEY,
        quiz_id TEXT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        question_order INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        CONSTRAINT unique_quiz_question UNIQUE (quiz_id, question_id)
    );
    """)

    # 8. Attempts
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attempts (
        id TEXT PRIMARY KEY,
        quiz_id TEXT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
        student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        started_at TEXT NOT NULL,
        submitted_at TEXT,
        server_end_time TEXT NOT NULL,
        total_questions INTEGER NOT NULL DEFAULT 0,
        attempted_questions INTEGER NOT NULL DEFAULT 0,
        correct_answers INTEGER NOT NULL DEFAULT 0,
        wrong_answers INTEGER NOT NULL DEFAULT 0,
        unattempted INTEGER NOT NULL DEFAULT 0,
        total_marks REAL NOT NULL DEFAULT 0.0,
        obtained_marks REAL NOT NULL DEFAULT 0.0,
        percentage REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'PASS', 'FAIL')),
        created_at TEXT NOT NULL
    );
    """)

    # 9. Answers
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        id TEXT PRIMARY KEY,
        attempt_id TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        selected_answer TEXT CHECK (selected_answer IN ('A', 'B', 'C', 'D')),
        is_correct INTEGER NOT NULL DEFAULT 0,
        marks_awarded REAL NOT NULL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        CONSTRAINT unique_attempt_question UNIQUE (attempt_id, question_id)
    );
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_students_roll ON students(roll_number, class_name, division);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quizzes_subject ON quizzes(subject_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quizzes_published ON quizzes(published, status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz ON quiz_questions(quiz_id, question_order);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quiz_questions_question ON quiz_questions(question_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_quiz_student ON attempts(quiz_id, student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_answers_attempt ON answers(attempt_id);")

    # Initial Faculty user seed if not exists
    cursor.execute("SELECT id FROM faculty WHERE email = ?", (Config.FACULTY_EMAIL,))
    if not cursor.fetchone():
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fac_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO faculty (id, full_name, email, department, password_hash, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (fac_id, Config.FACULTY_NAME, Config.FACULTY_EMAIL, 'Computer Engineering', Config.FACULTY_PASSWORD, now, now))
    
    conn.commit()
    conn.close()
    logger.info("Local relational schema initialized with strict foreign keys.")

// TypeScript shapes matching the backend API (see http://localhost:8000/docs).

export type Role = "student" | "guardian" | "teacher" | "admin";
export type ConsentStatus = "approved" | "pending" | "not_required";

export interface User {
  id: string;
  email: string;
  role: Role;
}

export interface AuthResponse {
  user: User;
  consent_status: ConsentStatus | null;
}

export interface StudentSignup {
  account_type: "student";
  email: string;
  password: string;
  display_name: string;
  date_of_birth: string; // YYYY-MM-DD
  grade_level: number;
  guardian_email: string | null;
}

export interface GuardianSignup {
  account_type: "guardian";
  email: string;
  password: string;
}

export interface Profile {
  user_id: string;
  display_name: string;
  date_of_birth: string;
  grade_level: number;
  language: string;
  consent_status: ConsentStatus;
}

export interface ProfileUpdate {
  display_name?: string;
  grade_level?: number;
}

export interface InviteInfo {
  student_display_name: string;
  consent_version: string;
  expires_at: string;
}

export interface ConsentResult {
  student_id: string;
  status: "approved";
  consent_version: string;
  consent_given_at: string;
}

export interface Topic {
  id: string;
  subject_id: string;
  name: string;
  grade_band: string;
  question_count: number;
  area_id: string;
  area_name: string;
}

/** What the browser may know about a lesson. Never contains an answer. */
export interface LessonState {
  has_question: boolean;
  question_text: string | null;
  question_type: "numeric" | "multiple_choice" | "true_false" | "fill_blank" | null;
  question_options: string[] | null; // multiple choice only; never says which is right
  hint_level: number;
  max_hint_level: number;
  mastery: number; // saved mastery for this topic, 0..1
  mastery_level: MasteryLevel;
}

export type MasteryLevel = "not_started" | "learning" | "practising" | "mastered";

export interface SkillProgress {
  id: string;
  name: string;
  course_level: "school" | "university" | "professional" | null;
  grade_band: string;
  question_count: number;
  mastery: number;
  level: MasteryLevel;
  questions_done: number;
  questions_solved: number;
  last_practiced_at: string | null;
  needs_first: string[];
  history: number[];
}

export interface AreaProgress {
  id: string;
  name: string;
  mastery: number;
  skills: SkillProgress[];
}

export interface Progress {
  areas: AreaProgress[];
  recommended_skill_id: string | null;
}

export interface LessonMessage {
  id: string;
  role: "student" | "teacher" | "system";
  content: string;
  whiteboard: unknown[] | null;
  created_at: string;
}

export interface LessonSession {
  id: string;
  topic: { id: string; name: string };
  status: "active" | "ended";
  started_at: string;
  lesson: LessonState;
  messages: LessonMessage[];
}

export type TurnIntent = "start" | "message" | "hint" | "dont_get_it";

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: { field: string; message: string }[];
  };
}

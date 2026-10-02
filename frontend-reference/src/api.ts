// Base URL của FastAPI; có thể ghi đè bằng VITE_BACKEND_URL khi deploy.
// Mặc định dùng 127.0.0.1, KHÔNG dùng "localhost": trên Windows + Docker Desktop, localhost phân giải ra ::1
// (IPv6) trước, nơi wslrelay.exe giữ cổng nhưng không chuyển tiếp được vào container → request treo/reset
// lúc được lúc không ("Can't reach the Lumina server"). Có test chặn việc đổi lại (api.test.ts).
// VITE_BACKEND_URL="/" = cùng origin với trang web (khi Caddy phục vụ cả frontend lẫn /api, xem docker-compose.public.yml).
const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const ACCESS_TOKEN_KEY = "lumina_access_token";

export interface AuthUser {
  id: string;
  email: string;
  target_level: string | null;
  timer_mode_enabled: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface NotebookFolder {
  id: string;
  name: string;
  created_at: string;
}

export interface NotebookDocument {
  id: string;
  title: string;
  source_type: string;
  file_size_kb: number | null;
  tags: string[] | null;
  starred: boolean;
  language: string;
  status: string;
  folder_id: string | null;
  created_at: string;
}

export interface DueVocabulary {
  id: string;
  term: string;
  definition: string | null;
  source_url: string | null;
  example_sentence: string | null;
  synonyms: string[] | null;
  antonyms: string[] | null;
  created_at: string;
}

export interface LookupSense {
  part_of_speech: string;
  level: string;
  meaning_vi: string;
  example_en: string;
}

export interface LookupResult {
  definition: string;
  synonyms: string[];
  antonyms: string[];
  example_sentence: string;
  ipa?: string | null;
  senses?: LookupSense[];
}

export interface ClassicQuestion {
  id: string;
  question_text: string;
  options: string[];
}

export interface ClassicSession {
  session_id: string;
  questions: ClassicQuestion[];
}

export interface ChatSource {
  chunk_id: string;
  excerpt: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: ChatSource[] | null;
  created_at: string;
}

export interface SkimScanSession {
  session_id: string;
  passage_id: string;
  title: string | null;
  content: string;
  source_document_id: string | null;
  questions: ClassicQuestion[];
  time_limit_seconds: number;
}

export interface WritingInsightResponse {
  insight_type: string;
  title: string;
  description: string;
  original_text: string | null;
  suggested_text: string | null;
}

export interface WritingSubmission {
  submission_id: string;
  source_type: "document_summary" | "extended_topic" | "free_topic";
  prompt_text: string;
}

export interface WritingResult {
  score: number;
  cefr_level: string;
  ielts_band: string;
  source_type: "document_summary" | "extended_topic" | "free_topic";
  rubric_scores: {
    task_response: number;
    coherence_cohesion: number;
    lexical_resource: number;
    grammatical_range_accuracy: number;
  } | null;
  insights: WritingInsightResponse[];
}

// Lưu access token trong browser để các request private dùng lại phiên đăng nhập.
export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

// Xóa token lúc logout hoặc khi backend trả 401 (token hết hạn/không hợp lệ).
export function clearAccessToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

// Lỗi từ backend/mạng. `code` là nguyên nhân cụ thể (vd ollama_unreachable) để UI chọn thông điệp
// và nút xử lý; `message` là câu người dùng đọc được (hoặc chính mã lỗi với endpoint cũ trả chuỗi).
export class ApiError extends Error {
  code: string;
  retryable: boolean;
  status?: number;

  constructor(message: string, code: string, retryable = false, status?: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
    this.status = status;
  }
}

// Wrapper tập trung xử lý URL, JSON headers, Bearer token và lỗi HTTP.
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${path}`, { ...options, headers });
  } catch {
    // Mất mạng / backend tắt / CORS: browser chỉ báo "Failed to fetch" khó hiểu nên đổi thành mã riêng.
    throw new ApiError("Can't reach the Lumina server.", "network_unreachable", true);
  }
  if (response.status === 401) {
    clearAccessToken();
    window.dispatchEvent(new Event("lumina-auth-changed"));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    // detail là chuỗi mã lỗi (endpoint cũ) hoặc object {code, message, retryable} (lỗi AI có nguyên nhân cụ thể).
    const detail = body.detail;
    if (Array.isArray(detail)) {
      // FastAPI trả mảng lỗi khi dữ liệu gửi lên không hợp lệ (422).
      throw new ApiError("Some of the information you entered isn't valid.", "validation_error", false, response.status);
    }
    if (detail && typeof detail === "object") {
      throw new ApiError(detail.message ?? "Something went wrong.", detail.code ?? "unknown", detail.retryable ?? false, response.status);
    }
    if (typeof detail === "string" && detail) {
      throw new ApiError(detail, detail, response.status >= 500, response.status);
    }
    throw new ApiError(`Backend request failed (${response.status})`, `http_${response.status}`, response.status >= 500, response.status);
  }
  // Mọi thao tác ghi thành công (ôn từ, nộp bài, gửi lượt nói...) có thể cộng streak/XP ở
  // backend, nên báo cho useLearningStats tải lại số liệu thay vì bắt từng view tự gọi.
  if (options.method && options.method !== "GET" && !path.startsWith("/api/auth")) {
    window.dispatchEvent(new Event("lumina-stats-refresh"));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

// Đăng nhập và lưu access token vào localStorage để các request sau tự động gắn Bearer.
export async function login(email: string, password: string): Promise<AuthTokens> {
  const tokens = await request<AuthTokens>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token);
  return tokens;
}

// Tạo tài khoản mới; chưa tự đăng nhập, caller phải gọi login() sau khi register thành công.
export function register(email: string, password: string, targetLevel: string) {
  return request<AuthUser>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, target_level: targetLevel || null }),
  });
}

// Xác minh email / quên & đặt lại mật khẩu bằng mã OTP 6 số gửi qua email.
const postJson = (path: string, body: object) =>
  request<void>(path, { method: "POST", body: JSON.stringify(body) });
export const verifyEmail = (email: string, code: string) => postJson("/api/auth/verify-email", { email, code });
export const resendVerification = (email: string) => postJson("/api/auth/resend-verification", { email });
export const forgotPassword = (email: string) => postJson("/api/auth/forgot-password", { email });
export const resetPassword = (email: string, code: string, newPassword: string) =>
  postJson("/api/auth/reset-password", { email, code, new_password: newPassword });

// Lấy thông tin user đang đăng nhập (dùng token hiện tại để xác định danh tính).
export function getCurrentUser() {
  return request<AuthUser>("/api/users/me");
}

// Bật/tắt "chế độ bấm giờ" — chỉ khi bật thì các view kỹ năng mới gửi duration_seconds
// lúc nộp bài, để study_time_log ghi lại (xem useStudyTimer.ts).
export function setTimerMode(enabled: boolean) {
  return request<AuthUser>("/api/users/me", {
    method: "PATCH",
    body: JSON.stringify({ timer_mode_enabled: enabled }),
  });
}

// Phút học 7 ngày gần nhất theo kỹ năng — luôn 0 nếu chưa từng bật chế độ bấm giờ.
export interface WeeklyActivity {
  timer_mode_enabled: boolean;
  minutes_by_skill: Record<"reading" | "listening" | "writing" | "speaking", number>;
  total_minutes: number;
}

export function getWeeklyActivity() {
  return request<WeeklyActivity>("/api/activity/weekly-summary");
}

// "Pick up where you left off": hoạt động gần nhất trên cả 4 kỹ năng, không phụ thuộc bấm giờ.
export interface RecentActivityItem {
  skill: "reading" | "listening" | "writing" | "speaking";
  title: string;
  score: number | null;
  created_at: string;
}

export function getRecentActivity(limit = 5) {
  return request<RecentActivityItem[]>(`/api/activity/recent?limit=${limit}`);
}

// Streak + XP thật của user (bảng streaks). Ngoài 3 field trong api-spec mục 7, backend trả
// thêm số liệu XP/level và các ngày có học gần đây để vẽ lưới streak.
export interface StreakSummary {
  current_streak: number;
  longest_streak: number;
  last_active_date: string | null;
  today_active: boolean;
  total_xp: number;
  level: number;
  xp_into_level: number;
  xp_for_next_level: number;
  recent_active_dates: string[];
  // >0: chuỗi vừa đứt, làm quiz >=10 câu đạt >=70% trong ngày để lấy lại.
  restorable_streak: number;
  // Freeze còn lại: mỗi 7 ngày liên tiếp được tặng 1 (tối đa 2), tự dùng khi bỏ lỡ ngày.
  freezes_available: number;
}

export function getStreaks() {
  return request<StreakSummary>("/api/streaks");
}

// Điểm trung bình động (0-100) theo kỹ năng — chỉ kỹ năng đã có điểm; cefr_level chỉ có với writing.
export interface SkillProgress {
  skill_name: "reading" | "listening" | "writing" | "speaking";
  score: number | null;
  cefr_level: string | null;
  updated_at: string | null;
}

export function getSkills() {
  return request<SkillProgress[]>("/api/skills");
}

// ---------- Adaptive Learning Engine (api-spec mục 7) ----------

export interface AdaptiveError {
  id: string;
  error_type: string;
  spaced_repetition_level: number;
  detail: { source?: string; original_text?: string; corrected_text?: string; explanation?: string } | null;
  created_at: string | null;
  priority_score: number;
}

export interface AdaptiveHabits {
  window_days: number;
  active_days: number;
  activities_per_active_day: number;
  studied_today: boolean;
  peak_hour: number | null;
  activity_by_skill: Record<string, number>;
  preferred_skill: string | null;
  quiz_score_change: number | null;
  progress_trend: "improving" | "stable" | "declining" | "insufficient_data";
}

export interface AdaptiveQuiz {
  quiz_id: string;
  questions: { question_text: string; options: string[]; error_type: string }[];
}

export interface AdaptiveQuizResult {
  attempt_id: string;
  score: number;
  results: { is_correct: boolean; correct_option_index: number; explanation: string }[];
  streak_restored: boolean;
}

export function listAdaptiveErrors(limit = 50) {
  return request<AdaptiveError[]>(`/api/adaptive/errors?limit=${limit}`);
}

export function getAdaptiveHabits() {
  return request<AdaptiveHabits>("/api/adaptive/habits");
}

export function generateAdaptiveQuiz(focusErrorTypes: string[] | null, numQuestions = 5) {
  return request<AdaptiveQuiz>("/api/adaptive/quizzes/generate", {
    method: "POST",
    body: JSON.stringify({ focus_error_types: focusErrorTypes, num_questions: numQuestions }),
  });
}

export function submitAdaptiveQuiz(quizId: string, answers: number[]) {
  return request<AdaptiveQuizResult>(`/api/adaptive/quizzes/${quizId}/attempts`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

// Liệt kê toàn bộ folder Notebook của user hiện tại.
export function listFolders() {
  return request<NotebookFolder[]>("/api/notebook-folders");
}

// Tạo 1 folder Notebook mới để phân loại tài liệu.
export function createFolder(name: string) {
  return request<NotebookFolder>("/api/notebook-folders", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

// Liệt kê tài liệu (phân trang), lọc theo folder nếu có truyền folderId.
export function listDocuments(folderId?: string) {
  const query = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  return request<{ items: NotebookDocument[]; total: number; limit: number; offset: number }>(
    `/api/documents${query}`,
  );
}

// Upload file .docx/audio; backend ingest .docx đồng bộ nên response đã có status ready/failed.
export function uploadDocument(file: File, folderId?: string, tags: string[] = []) {
  const body = new FormData();
  body.append("file", file);
  if (folderId) body.append("folder_id", folderId);
  tags.forEach((tag) => body.append("tags", tag));
  return request<NotebookDocument>("/api/documents", { method: "POST", body });
}

// Đổi folder/tags/starred của 1 document đã upload — không đổi được file gốc.
export function updateDocument(documentId: string, input: { starred?: boolean; tags?: string[]; folder_id?: string }) {
  return request<NotebookDocument>(`/api/documents/${documentId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

// Xóa vĩnh viễn 1 document (và toàn bộ document_chunks/vocab liên quan qua CASCADE).
export function deleteDocument(documentId: string) {
  return request<void>(`/api/documents/${documentId}`, { method: "DELETE" });
}

// Gọi Reading lookup của FastAPI thay cho endpoint prototype Express.
export function lookupWord(term: string, contextSentence: string) {
  return request<LookupResult>("/api/reading/lookup", {
    method: "POST",
    body: JSON.stringify({ term, context_sentence: contextSentence }),
  });
}

// Lưu từ đã tra vào Vocabulary backend với URL nguồn của Reading view.
export function saveVocabulary(input: {
  term: string;
  definition: string;
  sourceUrl: string;
  exampleSentence: string;
  synonyms: string[];
  antonyms: string[];
  ipa?: string;
  partOfSpeech?: string;
}) {
  return request<NotebookDocument>("/api/vocab", {
    method: "POST",
    body: JSON.stringify({
      term: input.term,
      definition: input.definition,
      source_url: input.sourceUrl,
      ipa: input.ipa,
      part_of_speech: input.partOfSpeech,
      example_sentence: input.exampleSentence,
      synonyms: input.synonyms,
      antonyms: input.antonyms,
    }),
  });
}

// Tạo Classic Mode session từ document đã ingestion xong.
export function createClassicSession(documentId: string, numQuestions = 5) {
  return request<ClassicSession>("/api/reading/classic/sessions", {
    method: "POST",
    body: JSON.stringify({ document_id: documentId, num_questions: numQuestions }),
  });
}

// Gửi đáp án về backend để chấm và nhận citation source_chunk_id.
export function submitClassicSession(
  sessionId: string,
  questionId: string,
  selectedOptionIndex: number,
  durationSeconds?: number,
) {
  return request<{
    score: number;
    results: Array<{
      question_id: string;
      correct_option_index: number;
      source_chunk_id: string | null;
    }>;
  }>(`/api/reading/sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      answers: [{ question_id: questionId, selected_option_index: selectedOptionIndex }],
      duration_seconds: durationSeconds,
    }),
  });
}

// Nộp nhiều đáp án 1 lần (dùng cho luồng "trả lời tất cả câu hỏi rồi submit" của Classic Mode).
export function submitClassicAnswers(
  sessionId: string,
  answers: Array<{ question_id: string; selected_option_index: number }>,
  durationSeconds?: number,
) {
  return request<{
    score: number;
    results: Array<{ question_id: string; correct_option_index: number; source_chunk_id: string | null; explanation?: string | null }>;
  }>(`/api/reading/sessions/${sessionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ answers, duration_seconds: durationSeconds }),
  });
}

// Lấy toàn bộ lịch sử chat RAG (NotebookLM-style) của 1 document, theo thứ tự thời gian.
export function getChatHistory(documentId: string) {
  return request<ChatMessage[]>(`/api/documents/${documentId}/chat`);
}

// Gửi 1 câu hỏi RAG về document; backend tìm chunk liên quan rồi gọi Gemini trả lời có trích dẫn.
export type ChatProvider = "gemini" | "ollama";

export function sendChatMessage(documentId: string, message: string, provider: ChatProvider = "gemini") {
  return request<{ user_message: ChatMessage; assistant_message: ChatMessage }>(
    `/api/documents/${documentId}/chat`,
    { method: "POST", body: JSON.stringify({ message, provider }) },
  );
}

// Tạo phiên Skim & Scan mới — truyền documentId (passage thật từ tài liệu) hoặc topic (AI tự sinh).
export function createSkimScanSession(input: { level: string; documentId?: string; topic?: string; timeLimitSeconds?: number; questionType?: "multiple_choice" | "tfng" }) {
  return request<SkimScanSession>("/api/reading/skim-scan/sessions", {
    method: "POST",
    body: JSON.stringify({
      level: input.level,
      document_id: input.documentId,
      topic: input.topic,
      time_limit_seconds: input.timeLimitSeconds,
      question_type: input.questionType,
    }),
  });
}

// Lấy danh sách từ vựng đến hạn ôn tập (next_review_at <= hiện tại) theo lịch SM-2.
export function listDueVocabulary() {
  return request<DueVocabulary[]>("/api/vocab/due");
}

// Thêm các từ nghe sai ở Dictation vào lịch ôn SM-2 (backend tra nghĩa bằng Ollama, tối đa limit từ/lần).
export function importVocabularyFromErrors(limit = 5) {
  return request<DueVocabulary[]>(`/api/vocab/from-errors?limit=${limit}`, { method: "POST" });
}

// Ghi nhận 1 lượt ôn từ (quality 0-5) — backend tính lại ease_factor/next_review_at bằng SM-2.
export function reviewVocabulary(vocabItemId: string, quality: number) {
  return request<{ next_review_at: string; ease_factor: number }>(
    `/api/vocab/${vocabItemId}/review`,
    { method: "POST", body: JSON.stringify({ quality }) },
  );
}

// Tạo writing_submissions mới (nguồn free_topic dùng promptText tự nhập làm đề bài).
export function createWritingSubmission(promptText: string) {
  return request<WritingSubmission>("/api/writing/submissions", {
    method: "POST",
    body: JSON.stringify({ source_type: "free_topic", prompt_text: promptText }),
  });
}

// Nộp bài luận để Gemini chấm điểm (rubric 4 tiêu chí + insights grammar/vocabulary/style).
export function submitWritingEssay(submissionId: string, submittedText: string, durationSeconds?: number) {
  return request<WritingResult>(`/api/writing/submissions/${submissionId}/submit`, {
    method: "POST",
    body: JSON.stringify({ submitted_text: submittedText, duration_seconds: durationSeconds }),
  });
}

// ---------------------------------------------------------------- Listening (Podcast/Dictation)

export interface PodcastItem {
  id: string;
  title: string;
  status: string;
  duration_seconds: number | null;
}

export interface TranscriptWord {
  text: string;
  start_ms: number;
  end_ms: number;
}

export interface DictationResult {
  score: number;
  errors: Array<{ type: "missing" | "extra" | "wrong"; word: string; position: number }>;
}

export function listPodcasts() {
  return request<PodcastItem[]>("/api/listening/podcasts");
}

export function createPodcast(documentId: string) {
  return request<{ id: string; status: string; duration_seconds: number | null }>(
    "/api/listening/podcasts",
    { method: "POST", body: JSON.stringify({ document_id: documentId }) },
  );
}

export function getPodcastTranscript(podcastId: string) {
  return request<{ segments: TranscriptWord[] }>(`/api/listening/podcasts/${podcastId}/transcript`);
}

export function createDictation(podcastId: string) {
  return request<{ attempt_id: string; audio_url: string }>("/api/listening/dictation", {
    method: "POST",
    body: JSON.stringify({ podcast_id: podcastId }),
  });
}

export function submitDictation(attemptId: string, transcribedText: string, durationSeconds?: number) {
  return request<DictationResult>(`/api/listening/dictation/${attemptId}/submit`, {
    method: "POST",
    body: JSON.stringify({ transcribed_text: transcribedText, duration_seconds: durationSeconds }),
  });
}

export interface ComprehensionQuestion {
  question: string;
  options: string[];
  correct_index: number;
  trap_note: string;
  evidence_text: string;
  evidence_start_ms: number | null;
  evidence_end_ms: number | null;
}

export interface QuizResult {
  score: number;
  correct_count: number;
  total: number;
  correct: boolean[];
}

export interface QuizHistoryItem {
  id: string;
  podcast_id: string;
  podcast_title: string;
  created_at: string;
  score: number;
  correct_count: number;
  total: number;
}

export function submitQuiz(attemptId: string, picks: Array<number | null>, durationSeconds?: number) {
  return request<QuizResult>(`/api/listening/quizzes/${attemptId}/submit`, {
    method: "POST",
    body: JSON.stringify({ picks, duration_seconds: durationSeconds }),
  });
}

export function listQuizzes() {
  return request<QuizHistoryItem[]>("/api/listening/quizzes");
}

export function createComprehension(podcastId: string, numQuestions = 4) {
  return request<{ attempt_id: string; questions: ComprehensionQuestion[] }>(
    `/api/listening/podcasts/${podcastId}/comprehension`,
    { method: "POST", body: JSON.stringify({ num_questions: numQuestions }) },
  );
}

// Audio nằm sau JWT nên <audio src> không tự gắn được Bearer: tải về dạng blob rồi phát.
export async function fetchAudioObjectUrl(path: string): Promise<string> {
  const token = getAccessToken();
  const response = await fetch(`${BACKEND_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error(`Audio request failed (${response.status})`);
  }
  return URL.createObjectURL(await response.blob());
}

// ---------------------------------------------------------------- Movie Context (nhánh TTS fallback)

export interface MovieContextMatch {
  match_id: string;
  source_type: "real_video" | "tts_fallback";
  phrase_text: string;
  is_saved: boolean;
  // tts_fallback: chỉ có audio_url. real_video: video_url + title + mốc thời gian dòng phụ đề khớp.
  audio_url: string | null;
  video_url: string | null;
  title: string | null;
  platform: string | null; // "demo" = cảnh mô phỏng; khác = phim thật
  start_ms: number | null;
  end_ms: number | null;
}

// Có cảnh video khớp phụ đề thì trả luôn (nhanh); không có thì backend sinh 3 câu thoại + audio đọc
// mẫu (LLM + TTS nên có thể mất vài giây).
// Dòng phụ đề của video chứa cảnh khớp; is_match = dòng chứa cụm từ người học tìm.
export interface SubtitleCue {
  text: string;
  start_ms: number;
  end_ms: number;
  is_match: boolean;
}

export function getMovieSubtitles(matchId: string) {
  return request<SubtitleCue[]>(`/api/movie-context/matches/${matchId}/subtitles`);
}

export function searchMovieContext(phrase: string) {
  return request<{ matches: MovieContextMatch[] }>(
    `/api/movie-context/search?phrase=${encodeURIComponent(phrase)}`,
  );
}

export function saveMovieMatch(matchId: string) {
  return request<void>(`/api/movie-context/matches/${matchId}/save`, { method: "POST" });
}

// ---------------------------------------------------------------- Speaking + Phrasebook

export interface Scenario {
  id: string;
  title: string;
  description: string | null;
  difficulty_level: string | null;
  goal: string | null;
  formality_level: string;
}

export interface SuggestedPhrase {
  phrase: string;
  meaning: string;
  source_note: string;
}

export interface SpeakingTurn {
  turn_id: string;
  user_transcript: string | null;
  response_text: string | null;
  response_audio_url: string | null;
  pronunciation_score: number | null;
  pronunciation_advice: string | null;
  pronunciation_assessment_failed: boolean;
  intent_score: number | null;
  politeness_score: number | null;
  intent_feedback: string | null;
  politeness_feedback: string | null;
  suggested_phrases: SuggestedPhrase[];
  stt_provider_used: string | null;
  // Lưu theo từng lượt (migration 0020) nên xem lại phiên cũ vẫn có; lượt cũ trước migration thì trống.
  natural_rephrase: string | null;
  literal_translation: { original: string; natural: string; explanation: string }[];
}

export interface SlangPhrase {
  id: string;
  phrase_text: string;
  meaning: string;
  example_sentence: string | null;
  formality_level: string;
  topic_tags: string[];
  source_reference: string;
}

export interface PhrasebookEntry {
  id: string;
  slang_phrase_id: string | null;
  conversation_turn_id: string | null;
  phrase_text: string;
  meaning: string | null;
  example_sentence: string | null;
  formality_level: string | null;
  source_reference: string | null;
}

export function listScenarios() {
  return request<Scenario[]>("/api/speaking/scenarios");
}

export function createSpeakingSession(scenarioId: string) {
  return request<{ session_id: string }>("/api/speaking/sessions", {
    method: "POST",
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function sendSpeakingTurn(sessionId: string, audio: Blob, provider: ChatProvider, durationSeconds?: number) {
  const body = new FormData();
  body.append("audio", audio, "turn.wav");
  const query = durationSeconds ? `&duration_seconds=${durationSeconds}` : "";
  return request<SpeakingTurn>(`/api/speaking/sessions/${sessionId}/turns?provider=${provider}${query}`, {
    method: "POST",
    body,
  });
}

// IELTS Speaking giả lập (backlog 2.3).
export interface IeltsExam {
  part1_questions: string[];
  cue_card: { topic: string; bullets: string[] };
  part3_questions: string[];
  part2_prep_seconds: number;
  part2_speak_seconds: number;
}

export interface IeltsAnswer {
  transcript: string;
  pronunciation_score: number | null;
  words_per_minute: number | null;
}

export interface IeltsEstimate {
  fluency_coherence: number;
  lexical_resource: number;
  grammatical_range: number;
  pronunciation: number | null;
  overall: number;
  feedback_vi: string;
  attempt_id: string;
  previous_overall: number | null;
}

export interface IeltsAttempt {
  id: string;
  created_at: string;
  topic: string | null;
  overall: number;
  fluency_coherence: number;
  lexical_resource: number;
  grammatical_range: number;
  pronunciation: number | null;
  words_per_minute: number | null;
  feedback_vi: string;
}

export function listIeltsAttempts() {
  return request<IeltsAttempt[]>("/api/speaking/ielts/attempts");
}

export function createIeltsExam(topic?: string) {
  return request<IeltsExam>("/api/speaking/ielts/exam", {
    method: "POST",
    body: JSON.stringify({ topic: topic || null }),
  });
}

export function sendIeltsAnswer(audio: Blob, durationSeconds: number) {
  const body = new FormData();
  body.append("audio", audio, "ielts.wav");
  return request<IeltsAnswer>(`/api/speaking/ielts/answer?duration_seconds=${Math.max(1, durationSeconds)}`, {
    method: "POST",
    body,
  });
}

export function estimateIelts(
  answers: Array<{
    part: number;
    question: string;
    transcript: string;
    pronunciation_score: number | null;
    words_per_minute: number | null;
  }>,
  topic?: string,
) {
  return request<IeltsEstimate>("/api/speaking/ielts/estimate", {
    method: "POST",
    body: JSON.stringify({ answers, topic: topic || null }),
  });
}

export function listSlang(formalityLevel?: string) {
  const query = formalityLevel ? `?formality_level=${encodeURIComponent(formalityLevel)}` : "";
  return request<SlangPhrase[]>(`/api/speaking/slang${query}`);
}

export function listPhrasebook() {
  return request<PhrasebookEntry[]>("/api/speaking/phrasebook");
}

export function savePhrase(input: {
  slangPhraseId?: string;
  conversationTurnId?: string;
  phraseText?: string;
  meaning?: string;
  exampleSentence?: string;
}) {
  return request<PhrasebookEntry>("/api/speaking/phrasebook", {
    method: "POST",
    body: JSON.stringify({
      slang_phrase_id: input.slangPhraseId,
      conversation_turn_id: input.conversationTurnId,
      phrase_text: input.phraseText,
      meaning: input.meaning,
      example_sentence: input.exampleSentence,
    }),
  });
}

// Rearrange the Block (Reading = sắp xếp câu, Writing = sắp xếp cụm ngữ pháp). Backend chỉ trả
// thứ tự chuẩn (correct_order) SAU khi nộp bài.
export type RearrangeSkill = "reading" | "writing";

export interface RearrangeBlock {
  id: string;
  text: string;
}

export interface RearrangeAttempt {
  attempt_id: string;
  blocks: RearrangeBlock[];
  // Chỉ có ở Writing: true = câu có nhiều thứ tự hợp lệ, thứ tự lạ được Ollama xét.
  is_open_form: boolean | null;
}

export interface RearrangeResult {
  // Thang 0-1 (số khối đúng vị trí / tổng số khối).
  score: number;
  correct_order: string[];
  graded_by: "rules" | "ollama";
  explanation: string | null;
}

export function createRearrange(skill: RearrangeSkill) {
  return request<RearrangeAttempt>(`/api/${skill}/rearrange`, { method: "POST" });
}

export function submitRearrange(skill: RearrangeSkill, attemptId: string, blockOrder: string[]) {
  return request<RearrangeResult>(`/api/${skill}/rearrange/${attemptId}/submit`, {
    method: "POST",
    body: JSON.stringify({ block_order: blockOrder }),
  });
}

// ---------------------------------------------------------------- Endpoint bổ sung (Reading/Writing/Adaptive)

export interface GuessContextAttempt {
  attempt_id: string;
  challenge_sentence: string;
  options: string[];
}

export function createGuessContext(input: { term?: string; vocabItemId?: string }) {
  return request<GuessContextAttempt>("/api/reading/guess-context", {
    method: "POST",
    body: JSON.stringify({ term: input.term, vocab_item_id: input.vocabItemId }),
  });
}

export function submitGuessContext(attemptId: string, selectedOptionIndex: number) {
  return request<{ correct: boolean; correct_option_index: number }>(
    `/api/reading/guess-context/${attemptId}/submit`,
    { method: "POST", body: JSON.stringify({ selected_option_index: selectedOptionIndex }) },
  );
}

export interface SentenceVerdict {
  meaning_fits: boolean;
  grammar_ok: boolean;
  corrected_sentence: string;
  feedback_vi: string;
}

// Chấm câu người học tự đặt với 1 từ đã lưu (câu sai ngữ pháp được backend ghi vào sổ lỗi).
export function checkVocabSentence(vocabItemId: string, sentence: string) {
  return request<SentenceVerdict>(`/api/vocab/${vocabItemId}/check-sentence`, {
    method: "POST",
    body: JSON.stringify({ sentence }),
  });
}

export function createStory(vocabItemIds: string[], theme?: string, length: "short" | "medium" | "long" = "medium") {
  return request<{ id: string; content: string; missing_terms: string[] }>("/api/stories", {
    method: "POST",
    body: JSON.stringify({ vocab_item_ids: vocabItemIds, theme: theme || undefined, length }),
  });
}

// Backend yêu cầu đúng 1 trong 2: topic (người học tự nêu chủ đề) hoặc certificate_style.
export function suggestWritingPrompt(input: { topic?: string; certificateStyle?: "toeic" | "ielts" | "cambridge" }) {
  return request<{ prompt_text: string | null; prompt_options: string[] | null }>("/api/writing/prompts/suggest", {
    method: "POST",
    body: JSON.stringify({ source_type: "free_topic", topic: input.topic, certificate_style: input.certificateStyle }),
  });
}

// Xem trước lỗi ngữ pháp trên văn bản thô (raw_text): backend không lưu gì.
export function checkGrammarPreview(rawText: string) {
  return request<{
    insights: { offset_start: number; offset_end: number; original_text: string; suggested_text: string; explanation: string }[];
  }>("/api/writing/grammar-check", { method: "POST", body: JSON.stringify({ raw_text: rawText }) });
}

export function rephraseSentence(submissionId: string, sentenceText?: string) {
  return request<{ original_sentence: string; suggested_sentences: { text: string; explanation: string }[] }>(
    "/api/writing/rephrase",
    { method: "POST", body: JSON.stringify({ submission_id: submissionId, sentence_text: sentenceText || undefined }) },
  );
}

export interface ReviewQueueItem {
  item_type: "vocab" | "error";
  item_id: string;
  priority_score: number;
  label: string | null;
}

export function getReviewQueue() {
  return request<ReviewQueueItem[]>("/api/adaptive/review-queue");
}

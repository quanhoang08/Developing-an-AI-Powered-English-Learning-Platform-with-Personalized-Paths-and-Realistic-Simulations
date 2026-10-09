import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, BookOpen, Eye, EyeOff, Headphones, KeyRound, Loader2, Lock, LogIn, Mail, Mic, PenLine, X } from "lucide-react";
import { forgotPassword, getAccessToken, login, register, resendVerification, resetPassword, verifyEmail } from "../api";

interface AuthPanelProps {
  onAuthChanged: () => void;
}

const INPUT_CLASS =
  "w-full bg-transparent py-3 pr-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none read-only:text-slate-500";

// Độ mạnh mật khẩu chỉ là gợi ý phía client (backend mới là nơi áp luật: tối thiểu 8 ký tự).
const strengthOf = (pw: string) =>
  Math.min(4, Number(pw.length >= 8) + Number(pw.length >= 12) + Number(/[a-z]/.test(pw) && /[A-Z]/.test(pw)) + Number(/\d/.test(pw)) + Number(/[^A-Za-z0-9]/.test(pw)));
const STRENGTH = [
  { label: "Too short", bar: "bg-slate-300" },
  { label: "Weak", bar: "bg-rose-400" },
  { label: "Fair", bar: "bg-amber-400" },
  { label: "Good", bar: "bg-lime-500" },
  { label: "Strong", bar: "bg-emerald-500" },
];

const SKILLS = [
  { icon: BookOpen, label: "Reading that adapts to your level" },
  { icon: Headphones, label: "Listening with real podcasts & films" },
  { icon: Mic, label: "Speaking practice with instant feedback" },
  { icon: PenLine, label: "Writing graded like an examiner" },
];
const CHIPS = ["resilient", "break the ice", "ubiquitous"];

const rows = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } };
const row = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } };

// Ô nhập có icon trái; viền sáng lên khi focus (focus-within) để không phải theo dõi state focus.
const Field: React.FC<{ icon: React.ElementType; trailing?: React.ReactNode; children: React.ReactNode }> = ({ icon: Icon, trailing, children }) => (
  <motion.div variants={row} className="flex items-center gap-2.5 rounded-xl bg-white px-3.5 ring-1 ring-slate-900/10 transition-shadow focus-within:ring-2 focus-within:ring-indigo-500/60 focus-within:shadow-[0_0_0_4px_rgba(31,87,73,0.08)]">
    <Icon className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
    {children}
    {trailing}
  </motion.div>
);

// Login/register UI dùng trực tiếp auth API của FastAPI backend.
// Sau khi đăng nhập, component này không render gì ở header nữa — tài khoản/đăng xuất
// được quản lý ở Sidebar (xem App.tsx + Sidebar.tsx), tránh trùng 2 nơi điều khiển auth.
export const AuthPanel: React.FC<AuthPanelProps> = ({ onAuthChanged }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  // "verify": nhập mã OTP xác minh email; "forgot": xin mã đặt lại; "reset": nhập mã + mật khẩu mới.
  const [mode, setMode] = useState<"auth" | "verify" | "forgot" | "reset">("auth");
  const [code, setCode] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(Boolean(getAccessToken()));
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    // Cho phép bất kỳ view nào (vd LockedFeature, Sidebar) mở popup này mà không cần lift state.
    const openHandler = () => setIsOpen(true);
    window.addEventListener("lumina-open-auth", openHandler);
    return () => window.removeEventListener("lumina-open-auth", openHandler);
  }, []);

  useEffect(() => {
    // Đồng bộ khi đăng xuất xảy ra ở nơi khác (Sidebar) — nút Connect phải hiện lại đúng lúc.
    const syncHandler = () => setIsLoggedIn(Boolean(getAccessToken()));
    window.addEventListener("lumina-auth-changed", syncHandler);
    return () => window.removeEventListener("lumina-auth-changed", syncHandler);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setIsOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  // Submit form: register (nếu đang ở chế độ đăng ký) rồi login ngay, gộp 2 bước thành 1 lượt bấm.
  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setIsSubmitting(true);
    try {
      if (mode === "forgot") {
        await forgotPassword(email);
        setMode("reset");
        setNotice("If that email has an account, we sent a 6-digit code to it.");
        return;
      }
      if (mode === "reset") {
        await resetPassword(email, code, password);
        setPassword("");
        setCode("");
        setMode("auth");
        setNotice("Password updated. Log in with your new password.");
        return;
      }
      if (mode === "verify") {
        await verifyEmail(email, code);
        setCode("");
      } else if (isRegistering) {
        await register(email, password, "");
      }
      await login(email, password);
      setIsLoggedIn(true);
      setIsOpen(false);
      // Xóa trạng thái form: lần mở sau (sau khi đăng xuất) phải về màn đăng nhập sạch, không còn mật khẩu/bước cũ.
      setMode("auth");
      setIsRegistering(false);
      setPassword("");
      setShowPassword(false);
      setCode("");
      setNotice(null);
      window.dispatchEvent(new Event("lumina-auth-changed"));
      onAuthChanged();
    } catch (submitError) {
      if ((submitError as { code?: string }).code === "email_not_verified") {
        // Production bắt buộc xác minh: register/login bị 403 -> chuyển sang bước nhập mã (register đã gửi mã sẵn).
        if (mode === "auth" && !isRegistering) await resendVerification(email).catch(() => undefined);
        setIsRegistering(false);
        setMode("verify");
        setNotice("We sent a 6-digit code to your email. Enter it to verify your account.");
      } else {
        const errorCode = (submitError as { code?: string }).code;
        setError(
          errorCode === "invalid_or_expired_code"
            ? "That code is wrong or has expired. Use \"Resend code\" to get a new one."
            : errorCode === "invalid_credentials" || (submitError as Error)?.message === "invalid_credentials"
              ? "Wrong email or password. Please try again."
              : submitError instanceof Error ? submitError.message : "Authentication failed",
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoggedIn) {
    return null;
  }

  const title = mode === "verify" ? "Verify your email" : mode === "forgot" ? "Forgot password" : mode === "reset" ? "Set a new password" : isRegistering ? "Create your account" : "Welcome back";
  const subtitle = mode === "verify" ? "Enter the 6-digit code we emailed you." : mode === "forgot" ? "We'll email you a 6-digit code." : mode === "reset" ? "Enter the code and choose a new password." : isRegistering ? "One step to register and connect." : "Connect your Lumina account to continue.";
  const submitLabel = isSubmitting ? "Connecting..." : mode === "verify" ? "Verify and log in" : mode === "forgot" ? "Send code" : mode === "reset" ? "Update password" : isRegistering ? "Register and connect" : "Log in";
  const switchTab = (registering: boolean) => { setIsRegistering(registering); setError(null); setNotice(null); };
  const showStrength = mode === "auth" && isRegistering && password.length > 0;
  const strength = strengthOf(password);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        title="Connect to FastAPI backend"
        className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-indigo-700 text-white text-xs font-semibold hover:bg-indigo-800 active:scale-95 transition-all cursor-pointer"
      >
        <LogIn className="w-3.5 h-3.5" /> Connect
      </button>

      {createPortal(
        <AnimatePresence>
          {isOpen && (
            <motion.div
              className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 backdrop-blur-sm p-4"
              onClick={() => setIsOpen(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.div
                role="dialog"
                aria-modal="true"
                aria-label={title}
                onClick={(event) => event.stopPropagation()}
                initial={{ opacity: 0, y: 24, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 12, scale: 0.97 }}
                transition={{ type: "spring", stiffness: 340, damping: 30 }}
                className="grid w-full max-w-3xl overflow-hidden rounded-3xl bg-[#fffdf8] shadow-[0_40px_80px_-30px_rgba(32,29,24,0.7)] md:grid-cols-[1fr_1.05fr]"
              >
                {/* Panel thương hiệu (ẩn trên mobile) */}
                <aside className="relative hidden overflow-hidden bg-gradient-to-br from-indigo-700 via-indigo-800 to-slate-900 p-8 text-white md:flex md:flex-col">
                  <motion.div aria-hidden="true" className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10" animate={{ scale: [1, 1.12, 1] }} transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }} />
                  <motion.div aria-hidden="true" className="absolute -bottom-24 -left-10 h-64 w-64 rounded-full bg-emerald-300/10" animate={{ scale: [1.1, 1, 1.1] }} transition={{ duration: 9, repeat: Infinity, ease: "easeInOut" }} />
                  <div className="relative flex items-center gap-2.5">
                    <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 font-display text-lg font-bold">L</span>
                    <span className="font-display text-xl font-bold">Lumina</span>
                  </div>
                  <h3 className="relative mt-8 font-display text-2xl font-bold leading-snug">Learn English with an AI that knows your words.</h3>
                  <motion.ul className="relative mt-6 space-y-3 text-sm text-white/85" initial="hidden" animate="show" variants={{ hidden: {}, show: { transition: { staggerChildren: 0.1, delayChildren: 0.25 } } }}>
                    {SKILLS.map(({ icon: Icon, label }) => (
                      <motion.li key={label} variants={{ hidden: { opacity: 0, x: -14 }, show: { opacity: 1, x: 0 } }} className="flex items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/10"><Icon className="h-4 w-4" /></span>
                        {label}
                      </motion.li>
                    ))}
                  </motion.ul>
                  {/* Chip từ vựng trôi nhẹ ở cuối panel (hàng riêng để không đè lên chữ) */}
                  <div className="relative mt-auto flex flex-wrap gap-2 pt-6" aria-hidden="true">
                    {CHIPS.map((c) => (
                      <motion.span key={c} className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/80 ring-1 ring-white/15"
                        animate={{ y: [0, -6, 0] }} transition={{ duration: 4.5, delay: CHIPS.indexOf(c) * 0.7, repeat: Infinity, ease: "easeInOut" }}>
                        {c}
                      </motion.span>
                    ))}
                  </div>
                </aside>

                <form onSubmit={handleSubmit} className="relative space-y-4 p-7 md:p-8">
                  <button
                    type="button"
                    onClick={() => setIsOpen(false)}
                    aria-label="Close"
                    className="absolute right-4 top-4 rounded-full p-1.5 text-slate-400 transition-colors hover:bg-slate-900/5 hover:text-slate-700"
                  >
                    <X className="h-4 w-4" />
                  </button>

                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div key={title} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.16 }} className="pr-8">
                      <h2 className="font-display text-2xl font-bold text-slate-900">{title}</h2>
                      <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
                    </motion.div>
                  </AnimatePresence>

                  {mode === "auth" && (
                    <div role="tablist" aria-label="Log in or register" className="relative grid grid-cols-2 rounded-xl bg-slate-900/5 p-1 text-xs font-semibold">
                      {[false, true].map((reg) => (
                        <button key={String(reg)} type="button" role="tab" aria-selected={isRegistering === reg} onClick={() => switchTab(reg)}
                          className={`relative z-10 rounded-lg py-2 transition-colors cursor-pointer ${isRegistering === reg ? "text-slate-900" : "text-slate-500 hover:text-slate-700"}`}>
                          {isRegistering === reg && (
                            <motion.span layoutId="auth-tab-pill" className="absolute inset-0 -z-10 rounded-lg bg-white shadow-sm" transition={{ type: "spring", stiffness: 420, damping: 34 }} />
                          )}
                          {reg ? "Register" : "Log in"}
                        </button>
                      ))}
                    </div>
                  )}

                  <motion.div key={`${mode}-${isRegistering}`} variants={rows} initial="hidden" animate="show" className="space-y-3">
                    <Field icon={Mail}>
                      <input
                        type="email"
                        required
                        autoFocus={mode === "auth" || mode === "forgot"}
                        readOnly={mode === "verify" || mode === "reset"}
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        placeholder="Email"
                        className={INPUT_CLASS}
                      />
                    </Field>
                    {(mode === "verify" || mode === "reset") && (
                      <Field icon={KeyRound}>
                        <input
                          inputMode="numeric"
                          autoComplete="one-time-code"
                          required
                          pattern="\d{6}"
                          maxLength={6}
                          value={code}
                          onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
                          placeholder="6-digit code"
                          className={`${INPUT_CLASS} tracking-[0.3em]`}
                        />
                      </Field>
                    )}
                    {(mode === "auth" || mode === "reset") && (
                      <Field
                        icon={Lock}
                        trailing={
                          <button type="button" onClick={() => setShowPassword((v) => !v)} aria-label={showPassword ? "Hide password" : "Show password"} className="rounded-md p-1 text-slate-400 hover:text-slate-700 cursor-pointer">
                            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        }
                      >
                        <input
                          type={showPassword ? "text" : "password"}
                          required
                          minLength={8}
                          value={password}
                          onChange={(event) => setPassword(event.target.value)}
                          placeholder={mode === "reset" ? "New password (at least 8 characters)" : "Password (at least 8 characters)"}
                          className={INPUT_CLASS}
                        />
                      </Field>
                    )}
                  </motion.div>

                  <AnimatePresence initial={false}>
                    {showStrength && (
                      <motion.div key="strength" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                        <div className="flex gap-1.5" aria-hidden="true">
                          {[1, 2, 3, 4].map((n) => (
                            <span key={n} className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                              <motion.span className={`block h-full rounded-full ${STRENGTH[strength].bar}`} initial={false} animate={{ width: strength >= n ? "100%" : "0%" }} transition={{ duration: 0.25 }} />
                            </span>
                          ))}
                        </div>
                        <p className="mt-1 text-[11px] text-slate-500">Password strength: <b className="text-slate-700">{STRENGTH[strength].label}</b></p>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {notice && (
                    <motion.p role="status" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                      {notice}
                    </motion.p>
                  )}
                  {error && (
                    // key={error}: mỗi lỗi mới rung lại một lần.
                    <motion.p key={error} role="alert" initial={{ opacity: 0 }} animate={{ opacity: 1, x: [0, -7, 7, -5, 5, 0] }} transition={{ duration: 0.4 }} className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                      {error}
                    </motion.p>
                  )}

                  <motion.button
                    type="submit"
                    disabled={isSubmitting}
                    whileTap={{ scale: 0.98 }}
                    className="group relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-indigo-700 px-3 py-3 text-sm font-semibold text-white shadow-[0_10px_20px_-10px_rgba(31,87,73,0.8)] transition-colors hover:bg-indigo-800 disabled:opacity-60 cursor-pointer"
                  >
                    <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 -skew-x-12 bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 group-hover:translate-x-[300%]" />
                    {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                    <span className="relative">{submitLabel}</span>
                    {!isSubmitting && <ArrowRight className="relative h-4 w-4 transition-transform group-hover:translate-x-1" />}
                  </motion.button>

                  {(mode === "verify" || mode === "reset") && (
                    <button
                      type="button"
                      onClick={() => (mode === "verify" ? resendVerification(email) : forgotPassword(email)).then(() => setNotice("New code sent."))}
                      className="w-full text-xs font-semibold text-indigo-700 hover:text-indigo-800 cursor-pointer"
                    >
                      Resend code
                    </button>
                  )}
                  {mode === "auth" && !isRegistering && (
                    <button
                      type="button"
                      onClick={() => { setMode("forgot"); setError(null); }}
                      className="w-full text-xs font-semibold text-slate-500 hover:text-slate-700 cursor-pointer"
                    >
                      Forgot password?
                    </button>
                  )}
                  {mode !== "auth" && (
                    <button
                      type="button"
                      onClick={() => { setMode("auth"); setError(null); setNotice(null); }}
                      className="w-full text-xs font-semibold text-indigo-700 hover:text-indigo-800 cursor-pointer"
                    >
                      Back to log in
                    </button>
                  )}
                </form>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </>
  );
};

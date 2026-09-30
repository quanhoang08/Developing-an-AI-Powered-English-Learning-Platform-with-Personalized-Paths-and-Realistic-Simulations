import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { motion } from "motion/react";
import { LogIn, UserPlus, X } from "lucide-react";
import { forgotPassword, getAccessToken, login, register, resendVerification, resetPassword, verifyEmail } from "../api";

interface AuthPanelProps {
  onAuthChanged: () => void;
}

const INPUT_CLASS =
  "w-full rounded-xl bg-white px-3.5 py-2.5 text-sm ring-1 ring-slate-900/10 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/60 transition-shadow";

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

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        title="Connect to FastAPI backend"
        className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-indigo-700 text-white text-xs font-semibold hover:bg-indigo-800 active:scale-95 transition-all cursor-pointer"
      >
        <LogIn className="w-3.5 h-3.5" /> Connect
      </button>

      {isOpen && createPortal(
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-sm p-4"
          onClick={() => setIsOpen(false)}
        >
          <motion.form
            onSubmit={handleSubmit}
            onClick={(event) => event.stopPropagation()}
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
            className="w-full max-w-sm space-y-4 rounded-3xl bg-[#fffdf8] p-7 shadow-[0_40px_80px_-30px_rgba(32,29,24,0.6)]"
          >
            <div className="flex items-start justify-between">
              <div>
                <h2 className="flex items-center gap-2 font-display text-2xl font-bold text-slate-900">
                  {isRegistering ? <UserPlus className="h-5 w-5 text-indigo-600" /> : <LogIn className="h-5 w-5 text-indigo-600" />}
                  {mode === "verify" ? "Verify your email" : mode === "forgot" ? "Forgot password" : mode === "reset" ? "Set a new password" : isRegistering ? "Create your account" : "Welcome back"}
                </h2>
                <p className="text-xs text-slate-500 mt-1">
                  {mode === "verify" ? "Enter the 6-digit code we emailed you." : mode === "forgot" ? "We'll email you a 6-digit code." : mode === "reset" ? "Enter the code and choose a new password." : isRegistering ? "One step to register and connect." : "Connect your Lumina account to continue."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                aria-label="Close"
                className="p-1.5 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-900/5 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <input
              type="email"
              required
              readOnly={mode === "verify" || mode === "reset"}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Email"
              className={INPUT_CLASS}
            />
            {(mode === "verify" || mode === "reset") && <input
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              pattern="\d{6}"
              maxLength={6}
              value={code}
              onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
              placeholder="6-digit code"
              className={INPUT_CLASS}
            />}
            {(mode === "auth" || mode === "reset") && <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={mode === "reset" ? "New password (at least 8 characters)" : "Password (at least 8 characters)"}
              className={INPUT_CLASS}
            />}
            {notice && (
              <p role="status" className="text-xs text-emerald-800 bg-emerald-50 rounded-lg px-3 py-2">
                {notice}
              </p>
            )}
            {error && (
              <p role="alert" className="text-xs text-red-700 bg-red-50 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-indigo-700 px-3 py-3 text-sm font-semibold text-white hover:bg-indigo-800 active:scale-[0.98] transition-all disabled:opacity-50 cursor-pointer"
            >
              {isSubmitting ? "Connecting..." : mode === "verify" ? "Verify and log in" : mode === "forgot" ? "Send code" : mode === "reset" ? "Update password" : isRegistering ? "Register and connect" : "Log in"}
            </button>
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
            <button
              type="button"
              onClick={() => { if (mode === "auth") setIsRegistering((value) => !value); else setMode("auth"); setError(null); setNotice(null); }}
              className="w-full text-xs font-semibold text-indigo-700 hover:text-indigo-800 cursor-pointer"
            >
              {mode !== "auth" ? "Back to log in" : isRegistering ? "Already have an account? Log in" : "Need an account? Register"}
            </button>
          </motion.form>
        </div>,
        document.body,
      )}
    </>
  );
};

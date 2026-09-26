import React from "react";
import { LogIn } from "lucide-react";
import { CatMascot } from "./CatMascot";

interface LockedFeatureProps {
  featureName: string;
}

// Chặn truy cập mọi view ngoài Dashboard tới khi user đăng nhập thật với backend.
export const LockedFeature: React.FC<LockedFeatureProps> = ({ featureName }) => {
  const requestAuth = () => window.dispatchEvent(new Event("lumina-open-auth"));

  return (
    <div className="flex flex-col items-center justify-center text-center px-6 py-16 max-w-xl mx-auto">
      <div className="relative mb-6">
        <div className="absolute inset-x-2 bottom-0 h-20 rounded-full bg-indigo-200/60 blur-2xl" aria-hidden="true" />
        <CatMascot mouthOpen={0} mood="thinking" className="relative h-44 w-auto" />
      </div>
      <h2 className="font-display text-3xl font-bold text-slate-900 mb-3">
        {featureName} is waiting for you
      </h2>
      <p className="text-base text-slate-500 max-w-md mb-8 leading-relaxed">
        Connect your Lumina account to sync progress, documents and vocabulary. The dashboard
        preview stays open; everything else needs an account.
      </p>
      <button
        onClick={requestAuth}
        className="flex items-center gap-2 px-6 py-3 rounded-2xl bg-indigo-700 text-white text-sm font-semibold shadow-[0_14px_24px_-12px_rgba(31,87,73,0.8)] hover:bg-indigo-800 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.97] transition-all cursor-pointer"
      >
        <LogIn className="w-4 h-4" /> Connect account
      </button>
    </div>
  );
};

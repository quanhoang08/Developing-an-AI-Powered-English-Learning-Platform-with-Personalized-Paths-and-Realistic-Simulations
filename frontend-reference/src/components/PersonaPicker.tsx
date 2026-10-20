// Chọn tính cách của mèo: dùng chung cho Speaking, Live Call (lựa chọn lưu bằng usePersona).
import React from "react";
import { CatPersona, PERSONA_ORDER, PERSONAS, usePersona } from "../catPersonas";

export const PersonaPicker: React.FC<{ disabled?: boolean }> = ({ disabled }) => {
  const [persona, setPersona] = usePersona();
  return (
    <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Cat personality">
      {PERSONA_ORDER.map((id: CatPersona) => {
        const def = PERSONAS[id];
        const picked = id === persona;
        return (
          <button
            key={id}
            role="radio"
            aria-checked={picked}
            disabled={disabled}
            onClick={() => setPersona(id)}
            title={def.tagline}
            className={`rounded-2xl px-2 py-2.5 text-center transition-all disabled:opacity-50 ${
              picked ? def.ui.picked : "bg-white ring-1 ring-slate-900/10 hover:-translate-y-0.5"
            }`}
          >
            <span className="block text-xl leading-none">{def.emoji}</span>
            <span className="block text-[11px] font-bold text-slate-800 mt-1">{def.name}</span>
          </button>
        );
      })}
    </div>
  );
};

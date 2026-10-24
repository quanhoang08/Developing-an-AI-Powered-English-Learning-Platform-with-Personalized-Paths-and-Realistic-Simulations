// Các tab phụ tách khỏi 4 kỹ năng chính để mỗi tab gọn: Games & Rewards, Community, Exam Prep, Study Tools.
import React from "react";
import { ActiveTab } from "../types";
import { CommunityCard } from "./CommunityCard";
import { DailyQuestsCard } from "./DailyQuestsCard";
import { ExamGoalCard } from "./ExamGoalCard";
import { GuildCard, WalletCard } from "./EconomyCard";
import { GrammarPanel } from "./GrammarPanel";
import { IeltsPanel } from "./IeltsPanel";
import { MiniGamesCard } from "./MiniGamesCard";
import { ParaphraseBankPanel } from "./ParaphraseBankPanel";
import { ReadabilityPanel } from "./ReadabilityPanel";
import { ReadingExtrasPanel } from "./ReadingExtrasPanel";
import { ToeicPanel } from "./ToeicPanel";

type Section = Extract<ActiveTab, "games" | "community" | "exam" | "tools">;

export const ExtrasView: React.FC<{ section: Section }> = ({ section }) => (
  <div className="space-y-6">
    {section === "games" && (
      <>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <DailyQuestsCard />
          <WalletCard />
        </div>
        <MiniGamesCard />
      </>
    )}
    {section === "community" && (
      <>
        <CommunityCard />
        <GuildCard />
      </>
    )}
    {section === "exam" && (
      <>
        <ExamGoalCard />
        <ToeicPanel />
        <IeltsPanel />
      </>
    )}
    {section === "tools" && (
      <>
        <ReadingExtrasPanel />
        <GrammarPanel />
        <ParaphraseBankPanel />
        <ReadabilityPanel />
      </>
    )}
  </div>
);

// @vitest-environment jsdom
import React from "react";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CountdownTimer } from "./CountdownTimer";
import { isTimerLocked } from "../timerLock";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const clock = () => screen.getByLabelText("Choose timer duration").textContent;
const openMenu = () => fireEvent.click(screen.getByLabelText("Choose timer duration"));
const tick = (ms: number) => act(() => void vi.advanceTimersByTime(ms));
const setCustom = (value: string) => {
  openMenu();
  fireEvent.change(screen.getByLabelText("Custom duration"), { target: { value } });
};

describe("suggested presets per skill", () => {
  it.each([
    ["reading", "04:00"], // B2 mặc định → TOEIC Part 7 bài đơn
    ["listening", "04:00"],
    ["writing", "08:00"],
    ["speaking", "00:45"],
  ] as const)("%s starts on its first preset", (skill, expected) => {
    render(<CountdownTimer skill={skill} level="B2" />);
    expect(clock()).toBe(expected);
  });

  it("filters reading presets by CEFR level", () => {
    render(<CountdownTimer skill="reading" level="C2" />);
    expect(clock()).toBe("20:00"); // C2 bỏ TOEIC, bắt đầu từ IELTS 1 passage
    openMenu();
    expect(screen.queryByText(/TOEIC/)).toBeNull();
    expect(screen.getByText("IELTS Reading · full test")).toBeTruthy();
  });

  it("choosing a preset sets the time without starting", () => {
    render(<CountdownTimer skill="writing" />);
    openMenu();
    fireEvent.click(screen.getByText("IELTS Task 2 · essay"));
    expect(clock()).toBe("40:00");
    tick(5000);
    expect(clock()).toBe("40:00");
  });
});

describe("countdown", () => {
  it("counts down after Start and stops on Pause", () => {
    render(<CountdownTimer skill="writing" />);
    fireEvent.click(screen.getByLabelText("Start timer"));
    tick(3000);
    expect(clock()).toBe("07:57");
    fireEvent.click(screen.getByLabelText("Pause timer"));
    tick(10000);
    expect(clock()).toBe("07:57");
  });

  it("resumes from where it paused", () => {
    render(<CountdownTimer skill="writing" />);
    fireEvent.click(screen.getByLabelText("Start timer"));
    tick(2000);
    fireEvent.click(screen.getByLabelText("Pause timer"));
    fireEvent.click(screen.getByLabelText("Start timer"));
    tick(2000);
    expect(clock()).toBe("07:56");
  });

  it("autoStart with initialSeconds runs immediately", () => {
    render(<CountdownTimer skill="reading" initialSeconds={90} autoStart />);
    expect(clock()).toBe("01:30");
    tick(1000);
    expect(clock()).toBe("01:29");
  });

  it("shows Time's up at zero and Restart resets to the last duration", () => {
    render(<CountdownTimer skill="speaking" />); // 00:45
    fireEvent.click(screen.getByLabelText("Start timer"));
    tick(45_000);
    expect(clock()).toBe("Time's up");
    tick(5000);
    expect(clock()).toBe("Time's up");
    fireEvent.click(screen.getByLabelText("Restart timer"));
    expect(clock()).toBe("00:45");
  });
});

describe("navigation lock", () => {
  it("is free before Start and locked once running", () => {
    render(<CountdownTimer skill="writing" />);
    expect(isTimerLocked()).toBe(false);
    fireEvent.click(screen.getByLabelText("Start timer"));
    expect(isTimerLocked()).toBe(true);
  });

  it("stays locked while paused mid-count (leaving would reset it)", () => {
    render(<CountdownTimer skill="writing" />);
    fireEvent.click(screen.getByLabelText("Start timer"));
    tick(3000);
    fireEvent.click(screen.getByLabelText("Pause timer"));
    expect(isTimerLocked()).toBe(true);
  });

  it("is free when paused right at the start value", () => {
    render(<CountdownTimer skill="writing" />);
    fireEvent.click(screen.getByLabelText("Start timer"));
    fireEvent.click(screen.getByLabelText("Pause timer"));
    expect(isTimerLocked()).toBe(false);
  });

  it("unlocks when a new time is picked (reset)", () => {
    render(<CountdownTimer skill="writing" />);
    fireEvent.click(screen.getByLabelText("Start timer"));
    tick(3000);
    openMenu();
    fireEvent.click(screen.getByText("IELTS Task 1 · report"));
    expect(isTimerLocked()).toBe(false);
  });

  it("unlocks when time runs out", () => {
    render(<CountdownTimer skill="speaking" />);
    fireEvent.click(screen.getByLabelText("Start timer"));
    tick(45_000);
    expect(clock()).toBe("Time's up");
    expect(isTimerLocked()).toBe(false);
  });

  it("locks immediately with autoStart and unlocks on unmount", () => {
    const { unmount } = render(<CountdownTimer skill="reading" initialSeconds={90} autoStart />);
    expect(isTimerLocked()).toBe(true);
    unmount();
    expect(isTimerLocked()).toBe(false);
  });
});

describe("custom duration", () => {
  it("accepts plain minutes", () => {
    render(<CountdownTimer skill="writing" />);
    setCustom("25");
    fireEvent.click(screen.getByText("Set"));
    expect(clock()).toBe("25:00");
  });

  it("accepts m:ss and submits with Enter", () => {
    render(<CountdownTimer skill="writing" />);
    setCustom("1:30");
    fireEvent.submit(screen.getByLabelText("Custom duration"));
    expect(clock()).toBe("01:30");
  });

  it.each(["", "abc", "0", "0:00", "1:75", "181", "-5", "1.5"])("rejects %j", (value) => {
    render(<CountdownTimer skill="writing" />);
    setCustom(value);
    expect((screen.getByText("Set") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.submit(screen.getByLabelText("Custom duration"));
    expect(clock()).toBe("08:00");
  });

  it("allows the 180-minute maximum", () => {
    render(<CountdownTimer skill="writing" />);
    setCustom("180");
    fireEvent.click(screen.getByText("Set"));
    expect(clock()).toBe("180:00");
  });
});

import { describe, expect, it } from "vitest";
import { peakVelocity } from "./BasketballUploadButton";

// Mẫu con trỏ mỗi 10ms: vuốt lên 2px/ms trong 60ms.
const flickUp = Array.from({ length: 7 }, (_, i) => ({ x: 100, y: 300 - 20 * i, t: i * 10 }));

describe("peakVelocity", () => {
  it("keeps the flick speed even if the pointer rests before release (touchpad)", () => {
    const rest = { x: 100, y: 180, t: 400 };
    const v = peakVelocity([...flickUp, rest]);
    expect(v.vx).toBeCloseTo(0);
    expect(v.vy).toBeCloseTo(-2);
  });

  it("treats a slow drag as placing the ball, not throwing", () => {
    const slow = Array.from({ length: 10 }, (_, i) => ({ x: 100 + i, y: 300, t: i * 50 }));
    expect(peakVelocity(slow)).toEqual({ vx: 0, vy: 0 });
  });
});

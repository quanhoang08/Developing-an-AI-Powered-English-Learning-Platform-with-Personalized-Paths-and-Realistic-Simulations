import { describe, expect, it } from "vitest";
import { launchVelocity, trajectory } from "./BasketballUploadButton";

describe("launchVelocity", () => {
  it("throws opposite to the pull direction", () => {
    const v = launchVelocity(0, 100); // kéo xuống -> ném lên
    expect(v.vx).toBeCloseTo(0);
    expect(v.vy).toBeLessThan(0);
  });

  it("caps the power at the maximum pull length", () => {
    expect(launchVelocity(0, 1000)).toEqual(launchVelocity(0, 150));
  });
});

describe("trajectory", () => {
  it("rises then falls back under gravity and stops at the floor", () => {
    const v = launchVelocity(0, 120);
    const dots = trajectory(200, 192, v.vx, v.vy, 400);
    const highest = Math.min(...dots.map((dot) => dot.y));
    expect(highest).toBeLessThan(70); // lên cao hơn vành rổ
    expect(dots[dots.length - 1].y).toBeGreaterThan(highest); // rồi rơi xuống lại
    expect(dots.every((dot) => dot.y <= 192)).toBe(true);
  });
});

import { describe, expect, it } from "vitest";
import { floatToPcm16, pcm16ToFloat, tagSource } from "./liveAudio";

describe("tagSource for live captions", () => {
  it("prefixes the source byte without changing the audio", () => {
    const tagged = new Uint8Array(tagSource(1, new Int16Array([1, -2]).buffer));
    expect(Array.from(tagged)).toEqual([1, 1, 0, 254, 255]);
  });
});

describe("PCM16 conversion for Gemini Live", () => {
  it("clamps and round-trips samples", () => {
    const pcm = new Int16Array(floatToPcm16(new Float32Array([0, 1, -1, 2, -2, 0.5])));
    expect(Array.from(pcm)).toEqual([0, 32767, -32768, 32767, -32768, 16383]);
    const back = pcm16ToFloat(pcm.buffer);
    expect(back[2]).toBe(-1);
    expect(back[5]).toBeCloseTo(0.5, 3);
  });
});

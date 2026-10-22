// Mèo 3D (three.js + react-three-fiber) dựng hoàn toàn từ hình khối cơ bản nên không cần file model.
// `mouthOpen` (0..1) nhóp nhép theo giọng nói, `mood` đổi tư thế, `persona` đổi màu lông + phụ kiện + nhịp điệu.
// Đầu mèo luôn quay theo con trỏ chuột. Tải lười qua CatStage để không làm nặng các trang không có mèo.
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { CatMood } from "./CatMascot";
import { CatPersona, PERSONAS } from "../catPersonas";

interface Cat3DProps {
  mouthOpen: number;
  mood: CatMood;
  persona: CatPersona;
  // Bad Kitty cau mày khi người học trả lời sai / phát âm chưa chuẩn.
  frown?: boolean;
  // "stage": đứng trên bục sân khấu (Speaking); "hero": đứng thẳng trên nền trang (Dashboard, màn khóa).
  variant?: "stage" | "hero";
  className?: string;
}

const damp = THREE.MathUtils.damp;
// Độ nâng mèo khi ngồi lên ghế đẩu (mặt ghế cao 0.54, đáy thân mèo ở 0.19).
const SEAT_LIFT = 0.37;
const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

// Bóng đổ mềm dưới chân (gradient tròn) rẻ hơn shadow map và đẹp hơn một đĩa xám phẳng.
let blobTexture: THREE.CanvasTexture | null = null;
const getBlobTexture = () => {
  if (blobTexture) return blobTexture;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  const gradient = ctx.createRadialGradient(64, 64, 4, 64, 64, 64);
  gradient.addColorStop(0, "rgba(0,0,0,0.55)");
  gradient.addColorStop(0.6, "rgba(0,0,0,0.18)");
  gradient.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 128, 128);
  blobTexture = new THREE.CanvasTexture(canvas);
  return blobTexture;
};

// Vật liệu "lông": sheen tạo viền sáng mờ ở mép như lông tơ thật.
const Flat: React.FC<{ color: string; opacity?: number }> = ({ color, opacity }) => {
  const sheen = useMemo(() => new THREE.Color(color).lerp(new THREE.Color("#ffffff"), 0.55), [color]);
  return (
    <meshPhysicalMaterial
      color={color}
      roughness={0.72}
      sheen={1}
      sheenRoughness={0.45}
      sheenColor={sheen}
      transparent={opacity !== undefined}
      opacity={opacity ?? 1}
    />
  );
};

// Bục sân khấu riêng từng tính cách + vòng sáng ở mép.
const Platform: React.FC<{ persona: CatPersona }> = ({ persona }) => {
  const look = PERSONAS[persona].look;
  return (
    <group>
      <mesh position={[0, -0.06, 0]}>
        <cylinderGeometry args={[1.55, 1.62, 0.12, 64]} />
        <meshStandardMaterial color={look.platform} roughness={0.45} metalness={persona === "polite" ? 0.25 : 0.1} />
      </mesh>
      <mesh position={[0, 0.003, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[1.38, 1.46, 64]} />
        <meshBasicMaterial color={look.rim} transparent opacity={0.85} />
      </mesh>
    </group>
  );
};

// Hạt sáng bay lên quanh mèo: vàng lấp lánh (Sir Whiskers), tia neon (Bad Kitty), đốm ấm (Chill Buddy).
const MOTE_COUNT = 16;
const Motes: React.FC<{ persona: CatPersona; mood: CatMood }> = ({ persona, mood }) => {
  const look = PERSONAS[persona].look;
  const refs = useRef<(THREE.Mesh | null)[]>([]);
  const live = useRef(mood);
  live.current = mood;
  const colors = persona === "polite" ? ["#ffd166", "#fff1b8", "#ffffff"] : persona === "rebel" ? [look.accent, look.ear, "#ffffff"] : ["#fff1dc", look.accent, "#ffd9b8"];
  const seeds = useMemo(
    () =>
      Array.from({ length: MOTE_COUNT }, (_, i) => ({
        angle: (i / MOTE_COUNT) * Math.PI * 2 + ((i * 0.37) % 1),
        radius: 1.1 + ((i * 0.61) % 1) * 0.9,
        speed: 0.5 + ((i * 0.29) % 1) * 0.7,
        offset: (i * 0.173) % 1,
        size: 0.04 + ((i * 0.53) % 1) * 0.06,
      })),
    [],
  );
  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const boost = live.current === "speaking" ? 2.2 : live.current === "listening" ? 1.4 : 1;
    refs.current.forEach((mote, i) => {
      if (!mote) return;
      const seed = seeds[i];
      const progress = (t * 0.12 * look.tempo * boost * seed.speed + seed.offset) % 1;
      const angle = seed.angle + t * 0.15 * seed.speed;
      const fade = Math.sin(progress * Math.PI);
      mote.position.set(Math.cos(angle) * seed.radius, 0.3 + progress * 3.6, Math.sin(angle) * seed.radius * 0.6 - 0.2);
      mote.scale.setScalar(seed.size * (0.4 + fade));
      mote.rotation.y = t * seed.speed * 2;
      (mote.material as THREE.MeshBasicMaterial).opacity = fade * 0.9;
    });
  });
  return (
    <group>
      {seeds.map((_, i) => (
        <mesh
          key={i}
          ref={(node) => {
            refs.current[i] = node;
          }}
        >
          {persona === "buddy" ? <sphereGeometry args={[1, 10, 10]} /> : <octahedronGeometry args={[1, 0]} />}
          <meshBasicMaterial color={colors[i % colors.length]} transparent opacity={0} depthWrite={false} />
        </mesh>
      ))}
    </group>
  );
};

const TailSegment: React.FC<{ color: string; segment: React.RefObject<THREE.Group | null>; children?: React.ReactNode }> = ({
  color,
  segment,
  children,
}) => (
  <group ref={segment}>
    <mesh position={[0, 0.2, 0]}>
      <capsuleGeometry args={[0.14, 0.26, 8, 14]} />
      <Flat color={color} />
    </mesh>
    <group position={[0, 0.4, 0]}>{children}</group>
  </group>
);

const CatModel: React.FC<Omit<Cat3DProps, "className">> = ({ mouthOpen, mood, persona, frown, variant = "stage" }) => {
  const look = PERSONAS[persona].look;
  const live = useRef({ mouthOpen, mood, frown: Boolean(frown) });
  live.current = { mouthOpen, mood, frown: Boolean(frown) };
  const frownLevel = useRef(0);

  const root = useRef<THREE.Group>(null);
  const body = useRef<THREE.Group>(null);
  const head = useRef<THREE.Group>(null);
  const earL = useRef<THREE.Group>(null);
  const earR = useRef<THREE.Group>(null);
  const eyeL = useRef<THREE.Group>(null);
  const eyeR = useRef<THREE.Group>(null);
  const gaze = useRef<THREE.Group>(null);
  const armL = useRef<THREE.Group>(null);
  const armR = useRef<THREE.Group>(null);
  const elbowL = useRef<THREE.Group>(null);
  const elbowR = useRef<THREE.Group>(null);
  const kneeL = useRef<THREE.Group>(null);
  const kneeR = useRef<THREE.Group>(null);
  const browL = useRef<THREE.Group>(null);
  const browR = useRef<THREE.Group>(null);
  const legL = useRef<THREE.Group>(null);
  const legR = useRef<THREE.Group>(null);
  const tail1 = useRef<THREE.Group>(null);
  const tail2 = useRef<THREE.Group>(null);
  const tail3 = useRef<THREE.Group>(null);
  const mouthClosed = useRef<THREE.Group>(null);
  const mouthOpenMesh = useRef<THREE.Group>(null);
  const dots = useRef<THREE.Group>(null);
  const rings = useRef<(THREE.Mesh | null)[]>([]);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    const { mouthOpen: open, mood: currentMood, frown: wantFrown } = live.current;
    const tempo = look.tempo;
    const speaking = currentMood === "speaking";
    const listening = currentMood === "listening";
    const thinking = currentMood === "thinking";
    const beat = speaking ? 2 : 1;
    frownLevel.current = damp(frownLevel.current, wantFrown && persona === "rebel" ? 1 : 0, 6, dt);
    const f = frownLevel.current;

    const dance = persona === "rebel";
    const seated = persona === "buddy";
    const amp = speaking ? 1 : 0.7;
    const w = t * 6.5; // nhịp nhảy của Bad Kitty
    if (root.current) {
      if (dance) {
        root.current.position.y = Math.abs(Math.sin(w)) * 0.16 * amp;
        root.current.rotation.z = Math.sin(w) * 0.07 * amp;
      } else if (seated) {
        root.current.position.y = SEAT_LIFT + Math.sin(t * 2) * 0.01;
        root.current.rotation.z = Math.sin(t * 0.7) * 0.02; // hơi đổi trọng tâm như người ngồi thật
      } else {
        root.current.position.y = Math.sin(t * 2 * beat) * 0.045;
        root.current.rotation.z = 0;
      }
    }
    const beatNod = (seated ? Math.sin(t * 3) * 0.03 : 0) + (dance ? Math.abs(Math.sin(w)) * 0.12 * amp : 0);
    const beatTilt = (seated ? Math.sin(t * 1.5) * 0.04 : 0) + (dance ? Math.sin(w) * 0.1 * amp : 0);
    if (body.current) body.current.scale.set(1 + Math.sin(t * 2) * 0.012, 1 + Math.sin(t * 2) * 0.02, 1);

    // Đầu: nhìn theo chuột + tư thế theo mood + nhịp gật đầu khi nói (Bad Kitty gật mạnh như headbang).
    if (head.current) {
      const nod = speaking ? Math.sin(t * 7 * tempo) * (persona === "rebel" ? 0.16 : 0.07) : 0;
      const baseTilt = persona === "rebel" ? 0.12 : persona === "buddy" ? -0.08 : 0;
      const tilt = baseTilt + (listening ? 0.2 : 0) + (thinking ? -0.15 + Math.sin(t * 3) * 0.05 : 0) + Math.sin(t * 1.2 * tempo) * 0.03;
      head.current.rotation.y = damp(head.current.rotation.y, state.pointer.x * 0.5 - 0.2 + (thinking ? 0.3 : 0), 6, dt);
      head.current.rotation.x = damp(head.current.rotation.x, -state.pointer.y * 0.25 + (thinking ? -0.2 : 0) + nod + beatNod + f * 0.18, 8, dt);
      head.current.rotation.z = damp(head.current.rotation.z, tilt + beatTilt, 5, dt);
    }

    // Tai: dựng lên khi nghe, thỉnh thoảng giật nhẹ.
    const twitch = Math.pow(Math.max(0, Math.sin(t * 1.3)), 30) * 0.25;
    const perk = listening ? 0.12 + Math.sin(t * 6) * 0.04 : 0;
    if (earL.current) earL.current.rotation.z = 0.3 - perk + twitch;
    if (earR.current) earR.current.rotation.z = -0.3 + perk - twitch * 0.4;

    // Mắt: chớp mỗi ~4 giây, to hơn khi nghe, liếc lên-phải khi nghĩ.
    const phase = t % 4.2;
    const blink = phase < 0.14 ? 1 - Math.sin((phase / 0.14) * Math.PI) * 0.92 : 1;
    const eyeSize = listening ? 1.12 : 1;
    eyeL.current?.scale.set(eyeSize, blink * eyeSize, eyeSize);
    eyeR.current?.scale.set(eyeSize, blink * eyeSize, eyeSize);
    if (gaze.current) {
      const tx = thinking ? 0.05 : Math.sin(t * 0.5) * 0.025;
      const ty = thinking ? 0.06 : 0;
      gaze.current.position.x = damp(gaze.current.position.x, tx, 6, dt);
      gaze.current.position.y = damp(gaze.current.position.y, ty, 6, dt);
    }

    // Miệng: khép (chữ w) hoặc mở theo biên độ giọng nói.
    const amount = clamp01(open);
    if (mouthClosed.current) mouthClosed.current.visible = amount < 0.06;
    if (mouthOpenMesh.current) {
      mouthOpenMesh.current.visible = amount >= 0.06;
      mouthOpenMesh.current.scale.set(1, 0.3 + amount * 1.3, 1);
      mouthOpenMesh.current.position.y = -0.22 - amount * 0.05;
    }

    // Tay + chân như người thật: tay có vai + khuỷu, chân có hông + đầu gối.
    // Sir Whiskers đứng khoanh tay (thỉnh thoảng thả lỏng); Bad Kitty nhún nhảy cả tay lẫn chân;
    // Chill Buddy ngồi ghế đẩu, tay đặt trên đùi, chân gác lên thanh ngang. Khi nói thì ai cũng vẫy tay.
    const waveL = speaking ? Math.abs(Math.sin(t * 5 * tempo)) * 0.9 : 0;
    const waveR = speaking ? Math.abs(Math.sin(t * 5 * tempo + 1.6)) * 0.9 : 0;
    const crossed = persona === "polite" && !speaking && t % 14 < 9.5;
    const moveArm = (shoulder: THREE.Group | null, elbow: THREE.Group | null, side: 1 | -1, wave: number, phase: number) => {
      if (!shoulder || !elbow) return;
      // x/y/z = vị trí vai; srx/srz = góc vai (srz > 0: dạng ra ngoài); eex = gập khuỷu về trước; ez = khép khuỷu vào trong.
      let pose = { x: 0.6, y: 1.4, z: 0.18, srx: Math.sin(t * 1.3 + phase) * 0.04, srz: 0.12 + wave, eex: -0.25 - wave * 0.5, ez: 0 };
      if (crossed) pose = { x: 0.52, y: side === 1 ? 1.31 : 1.36, z: side === 1 ? 0.56 : 0.5, srx: -0.9, srz: 0, eex: 0, ez: 1.57 };
      else if (dance) {
        const swing = Math.sin(w + phase) * 0.5 + 0.5;
        pose = { x: 0.6, y: 1.4, z: 0.18, srx: Math.sin(w * 2 + phase) * 0.4 * amp, srz: 0.5 + swing * 1.7 * amp, eex: -0.6 * amp, ez: swing * amp };
      } else if (seated) pose = { x: 0.6, y: 1.4, z: 0.18, srx: -0.35, srz: 0.12 + wave, eex: -0.3 - wave * 0.5, ez: 0 };
      const rate = dance ? 22 : 8;
      shoulder.position.x = damp(shoulder.position.x, side * pose.x, rate, dt);
      shoulder.position.y = damp(shoulder.position.y, pose.y, rate, dt);
      shoulder.position.z = damp(shoulder.position.z, pose.z, rate, dt);
      shoulder.rotation.x = damp(shoulder.rotation.x, pose.srx, rate, dt);
      shoulder.rotation.z = damp(shoulder.rotation.z, side * pose.srz, rate, dt);
      elbow.rotation.x = damp(elbow.rotation.x, pose.eex, rate, dt);
      elbow.rotation.z = damp(elbow.rotation.z, -side * pose.ez, rate, dt);
    };
    moveArm(armL.current, elbowL.current, -1, waveL, 0);
    moveArm(armR.current, elbowR.current, 1, waveR, Math.PI);

    const moveLeg = (hip: THREE.Group | null, knee: THREE.Group | null, side: 1 | -1) => {
      if (!hip || !knee) return;
      // y = độ cao hông; hx = gập hông (âm: đùi đưa ra trước); kx = gập gối (dương: cẳng chân gập ra sau).
      let pose = { y: 0.7, hx: 0, kx: 0, splay: 0.03 };
      if (dance) {
        const lift = Math.max(0, side === -1 ? Math.sin(w) : -Math.sin(w)) * amp;
        pose = { y: 0.7, hx: -0.6 * lift, kx: 0.9 * lift, splay: 0.08 };
      } else if (seated) {
        pose = { y: 0.3, hx: -1.5, kx: 1.5 + Math.sin(t * 2 + (side === 1 ? Math.PI : 0)) * 0.12, splay: 0.1 };
      }
      hip.position.y = damp(hip.position.y, pose.y, 10, dt);
      hip.rotation.x = damp(hip.rotation.x, pose.hx, 14, dt);
      hip.rotation.z = damp(hip.rotation.z, side * pose.splay, 10, dt);
      knee.rotation.x = damp(knee.rotation.x, pose.kx, 14, dt);
    };
    moveLeg(legL.current, kneeL.current, -1);
    moveLeg(legR.current, kneeR.current, 1);

    // Bad Kitty: cau mày (lông mày chúc vào trong + hạ xuống) và mếu miệng khi trả lời sai / phát âm chưa chuẩn.
    for (const side of [-1, 1] as const) {
      const brow = side === -1 ? browL.current : browR.current;
      if (!brow) continue;
      brow.position.set(side * (0.34 - f * 0.07), 0.49 - f * 0.05, 0.69);
      brow.rotation.z = side * (f * 0.55 - (1 - f) * 0.1);
    }
    if (mouthClosed.current && persona === "rebel") {
      mouthClosed.current.rotation.z = 0.14 * (1 - f) + Math.PI * f;
      mouthClosed.current.position.y = -0.16 - f * 0.08;
    }
    const tail = 2 * tempo * beat;
    if (tail1.current) tail1.current.rotation.z = -0.5 + Math.sin(t * tail) * 0.25;
    if (tail2.current) tail2.current.rotation.z = -0.3 + Math.sin(t * tail - 0.8) * 0.4;
    if (tail3.current) tail3.current.rotation.z = Math.sin(t * tail - 1.6) * 0.5;

    // Ba chấm "đang nghĩ" nhấp nháy lần lượt.
    if (dots.current) {
      dots.current.visible = thinking;
      dots.current.children.forEach((dot, index) => dot.scale.setScalar(0.6 + Math.max(0, Math.sin(t * 5 - index * 0.8)) * 0.6));
    }

    // Vòng sóng dưới chân lan ra khi nghe / nói.
    rings.current.forEach((ring, index) => {
      if (!ring) return;
      ring.visible = listening || speaking;
      const progress = (t * 0.7 + index * 0.5) % 1;
      ring.scale.setScalar(0.7 + progress * 1.7);
      (ring.material as THREE.MeshBasicMaterial).opacity = (1 - progress) * 0.55;
    });
  });

  const fur = look.fur;
  const eye = (side: 1 | -1, ref: React.RefObject<THREE.Group | null>) => (
    <group ref={ref} position={[side * 0.34, 0.15, 0.7]}>
      <mesh scale={[1, 1.3, 0.6]}>
        <sphereGeometry args={[0.13, 24, 24]} />
        <meshStandardMaterial color={look.iris} roughness={0.2} />
      </mesh>
      <mesh position={[0, 0, 0.02]} scale={[0.74, 1, 0.6]}>
        <sphereGeometry args={[0.13, 24, 24]} />
        <meshStandardMaterial color="#17101a" roughness={0.2} />
      </mesh>
      <mesh position={[0.045, 0.07, 0.1]}>
        <sphereGeometry args={[0.045, 12, 12]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>
      <mesh position={[-0.04, -0.07, 0.1]}>
        <sphereGeometry args={[0.022, 10, 10]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>
    </group>
  );

  return (
    <group>
      {/* Bóng + sóng âm dưới chân (đứng yên, không nhún theo mèo) */}
      {variant === "stage" && <Platform persona={persona} />}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.008, 0]}>
        <planeGeometry args={[3.4, 3.4]} />
        <meshBasicMaterial map={getBlobTexture()} transparent depthWrite={false} />
      </mesh>
      <Motes persona={persona} mood={mood} />
      {[0, 1].map((index) => (
        <mesh
          key={index}
          ref={(node) => {
            rings.current[index] = node;
          }}
          rotation={[-Math.PI / 2, 0, 0]}
          position={[0, 0.01, 0]}
          visible={false}
        >
          <ringGeometry args={[0.95, 1.0, 48]} />
          <meshBasicMaterial color={look.rim} transparent opacity={0.5} side={THREE.DoubleSide} />
        </mesh>
      ))}

      {/* Ghế đẩu của Chill Buddy */}
      {persona === "buddy" && (
        <group position={[0, 0, -0.3]}>
          <mesh position={[0, 0.47, 0]}>
            <cylinderGeometry args={[0.6, 0.6, 0.14, 32]} />
            <Flat color={look.accent} />
          </mesh>
          {[0, 1, 2].map((index) => {
            const angle = (index / 3) * Math.PI * 2 + 0.5;
            return (
              <mesh key={index} position={[Math.sin(angle) * 0.4, 0.2, Math.cos(angle) * 0.4]}>
                <cylinderGeometry args={[0.06, 0.06, 0.45, 10]} />
                <Flat color="#8a5a35" />
              </mesh>
            );
          })}
        </group>
      )}

      <group ref={root}>
      {/* Đuôi: 3 đốt lồng nhau */}
      <group position={[0.3, 0.6, -0.55]} rotation={[0, 0, -0.35]}>
        <TailSegment color={fur} segment={tail1}>
          <TailSegment color={fur} segment={tail2}>
            <TailSegment color={look.dark} segment={tail3} />
          </TailSegment>
        </TailSegment>
      </group>

      {/* Chân: hông + đầu gối (đứng thẳng, nhảy đá chân, hoặc ngồi gập 90 độ) */}
      {[-1, 1].map((side) => (
        <group key={side} ref={side === -1 ? legL : legR} position={[side * 0.34, 0.7, 0.08]}>
          <mesh position={[0, -0.14, 0]}>
            <capsuleGeometry args={[0.2, 0.1, 8, 14]} />
            <Flat color={fur} />
          </mesh>
          <group ref={side === -1 ? kneeL : kneeR} position={[0, -0.28, 0]}>
            <mesh position={[0, -0.12, 0]}>
              <capsuleGeometry args={[0.17, 0.06, 8, 14]} />
              <Flat color={fur} />
            </mesh>
            <mesh position={[0, -0.3, 0.12]} scale={[1.2, 0.7, 1.5]}>
              <sphereGeometry args={[0.19, 16, 16]} />
              <Flat color={look.cream} />
            </mesh>
          </group>
        </group>
      ))}

      {/* Thân */}
      <group ref={body} position={[0, 0.95, 0]}>
        <mesh scale={[1.05, 0.95, 0.95]}>
          <sphereGeometry args={[0.8, 32, 32]} />
          <Flat color={fur} />
        </mesh>
        <mesh position={[0, -0.05, 0.42]} scale={[0.66, 0.78, 0.5]}>
          <sphereGeometry args={[0.8, 24, 24]} />
          <Flat color={look.cream} />
        </mesh>
      </group>

      {/* Tay: vai + khuỷu, bàn tay màu kem */}
      {[-1, 1].map((side) => (
        <group key={side} ref={side === -1 ? armL : armR} position={[side * 0.6, 1.4, 0.18]}>
          <mesh position={[0, -0.2, 0]}>
            <capsuleGeometry args={[0.17, 0.16, 8, 14]} />
            <Flat color={fur} />
          </mesh>
          <group ref={side === -1 ? elbowL : elbowR} position={[0, -0.36, 0]}>
            <mesh position={[0, -0.17, 0]}>
              <capsuleGeometry args={[0.15, 0.16, 8, 14]} />
              <Flat color={fur} />
            </mesh>
            <mesh position={[0, -0.45, 0.02]}>
              <sphereGeometry args={[0.16, 16, 16]} />
              <Flat color={look.cream} />
            </mesh>
          </group>
        </group>
      ))}

      {/* Phụ kiện cổ theo tính cách */}
      {persona === "polite" && (
        <group position={[0, 1.42, 0.6]}>
          {[-1, 1].map((side) => (
            <mesh key={side} position={[side * 0.13, 0, 0]} rotation={[0, 0, (side * Math.PI) / 2]}>
              <coneGeometry args={[0.13, 0.26, 3]} />
              <Flat color={look.accent} />
            </mesh>
          ))}
          <mesh>
            <sphereGeometry args={[0.06, 12, 12]} />
            <Flat color="#312e81" />
          </mesh>
        </group>
      )}
      {persona === "rebel" && (
        <group position={[0, 1.5, 0.02]} scale={[1, 1, 0.9]} rotation={[Math.PI / 2, 0, 0]}>
          <mesh>
            <torusGeometry args={[0.56, 0.06, 10, 32]} />
            <Flat color="#111118" />
          </mesh>
          {[0, 1, 2, 3, 4, 5, 6].map((index) => {
            const angle = -0.9 + index * 0.3;
            return (
              <mesh key={index} position={[Math.sin(angle) * 0.56, Math.cos(angle) * 0.56, 0.03]} rotation={[0, 0, -angle]}>
                <coneGeometry args={[0.035, 0.12, 6]} />
                <Flat color={look.accent} />
              </mesh>
            );
          })}
        </group>
      )}

      {/* Đầu */}
      <group ref={head} position={[0, 2.35, 0]} scale={[1.18, 1.1, 1.1]}>
        <mesh scale={[1.15, 0.95, 1]}>
          <sphereGeometry args={[0.8, 40, 40]} />
          <Flat color={fur} />
        </mesh>

        {/* Mảng màu trên đầu: vằn trán (Sir Whiskers, Bad Kitty) hoặc mảng loang (Chill Buddy) */}
        {persona === "buddy" ? (
          <mesh position={[0.5, 0.35, 0.4]} scale={[1, 0.9, 0.35]} rotation={[0, 0.5, 0]}>
            <sphereGeometry args={[0.32, 20, 20]} />
            <Flat color={look.dark} />
          </mesh>
        ) : (
          [-0.18, 0, 0.18].map((x) => (
            <mesh key={x} position={[x, 0.6, 0.47 - Math.abs(x) * 0.5]} rotation={[0.95, 0, -x * 1.2]}>
              <capsuleGeometry args={[0.028, 0.16, 4, 8]} />
              <Flat color={look.dark} />
            </mesh>
          ))
        )}

        {/* Tai */}
        {[-1, 1].map((side) => (
          <group key={side} ref={side === -1 ? earL : earR} position={[side * 0.52, 0.64, 0]}>
            <mesh position={[0, 0.2, 0]} scale={[1, 1.1, 0.6]}>
              <sphereGeometry args={[0.26, 24, 24]} />
              <Flat color={fur} />
            </mesh>
            <mesh position={[0, 0.18, 0.09]} scale={[0.6, 0.7, 0.4]}>
              <sphereGeometry args={[0.26, 20, 20]} />
              <Flat color={look.ear} />
            </mesh>
          </group>
        ))}

        {/* Mào Mohawk của Bad Kitty */}
        {persona === "rebel" &&
          [0.38, 0.12, -0.14, -0.4].map((z, index) => (
            <mesh key={z} position={[0, 0.76 * Math.sqrt(1 - (z / 0.8) ** 2) + 0.12, z]} rotation={[-z * 0.7, 0, 0]}>
              <coneGeometry args={[0.1, 0.34 + index * 0.1, 5]} />
              <Flat color={index % 2 === 0 ? look.accent : look.ear} />
            </mesh>
          ))}

        {/* Tai nghe đeo trên đầu của Chill Buddy */}
        {persona === "buddy" && (
          <group position={[0, 0, -0.2]}>
            <mesh scale={[1, 0.82, 1]}>
              <torusGeometry args={[0.97, 0.06, 10, 40, Math.PI]} />
              <Flat color={look.accent} />
            </mesh>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[side * 0.97, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
                <cylinderGeometry args={[0.24, 0.24, 0.2, 24]} />
                <Flat color="#0f766e" />
              </mesh>
            ))}
          </group>
        )}

        {/* Mõm */}
        <mesh position={[0, -0.2, 0.55]} scale={[1.05, 0.8, 0.6]}>
          <sphereGeometry args={[0.4, 24, 24]} />
          <Flat color={look.cream} />
        </mesh>

        {/* Mắt (kính râm của Bad Kitty phủ lên trên, kính một mắt của Sir Whiskers) */}
        <group ref={gaze}>
          {eye(-1, eyeL)}
          {eye(1, eyeR)}
        </group>
        {persona === "rebel" && (
          <group position={[0, 0.15, 0.78]} rotation={[0, 0, -0.06]}>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[side * 0.34, 0, 0]} scale={[1.25, 0.9, 0.35]}>
                <sphereGeometry args={[0.2, 24, 24]} />
                <meshStandardMaterial color="#0a0a10" roughness={0.15} metalness={0.6} />
              </mesh>
            ))}
            <mesh scale={[1, 0.15, 0.3]}>
              <boxGeometry args={[0.28, 0.2, 0.2]} />
              <Flat color={look.accent} />
            </mesh>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[side * 0.28, 0.06, 0.08]} rotation={[0, 0, side * 0.5]} scale={[1, 0.15, 0.1]}>
                <boxGeometry args={[0.2, 0.2, 0.2]} />
                <meshBasicMaterial color="#ffffff" />
              </mesh>
            ))}
          </group>
        )}
        {persona === "polite" && (
          <mesh position={[0.34, 0.15, 0.83]}>
            <torusGeometry args={[0.2, 0.018, 8, 28]} />
            <meshStandardMaterial color="#d4af37" metalness={0.8} roughness={0.25} />
          </mesh>
        )}

        {/* Lông mày của Bad Kitty (cau lại khi người học sai) */}
        {persona === "rebel" &&
          [-1, 1].map((side) => (
            <group key={side} ref={side === -1 ? browL : browR} position={[side * 0.34, 0.49, 0.69]}>
              <mesh rotation={[0, 0, Math.PI / 2]}>
                <capsuleGeometry args={[0.05, 0.22, 6, 10]} />
                <Flat color={look.accent} />
              </mesh>
            </group>
          ))}

        {/* Má hồng */}
        {[-1, 1].map((side) => (
          <mesh key={side} position={[side * 0.55, -0.12, 0.6]} scale={[1.3, 0.8, 0.35]}>
            <sphereGeometry args={[0.1, 12, 12]} />
            <Flat color={look.ear} opacity={persona === "rebel" ? 0.55 : 0.9} />
          </mesh>
        ))}

        {/* Mũi */}
        <mesh position={[0, -0.05, 0.8]} scale={[1.3, 0.9, 0.8]}>
          <sphereGeometry args={[0.06, 12, 12]} />
          <meshStandardMaterial color="#ff7a93" roughness={0.4} />
        </mesh>

        {/* Miệng khép: chữ w, Bad Kitty nhếch mép lệch một bên */}
        <group ref={mouthClosed} position={[0, -0.16, 0.79]} rotation={[0, 0, persona === "rebel" ? 0.14 : 0]}>
          {[-1, 1].map((side) => (
            <mesh key={side} position={[side * 0.09, 0, 0]} rotation={[0, 0, Math.PI]}>
              <torusGeometry args={[0.09, 0.014, 8, 18, Math.PI]} />
              <meshStandardMaterial color="#3b2a2a" />
            </mesh>
          ))}
        </group>
        {/* Miệng mở */}
        <group ref={mouthOpenMesh} position={[0, -0.22, 0.76]} visible={false}>
          <mesh scale={[1, 1, 0.35]}>
            <sphereGeometry args={[0.13, 20, 20]} />
            <meshStandardMaterial color="#6e2433" roughness={0.6} />
          </mesh>
          <mesh position={[0, -0.05, 0.02]} scale={[0.8, 0.5, 0.4]}>
            <sphereGeometry args={[0.1, 14, 14]} />
            <meshStandardMaterial color="#ff8fa3" roughness={0.6} />
          </mesh>
        </group>

        {/* Ria */}
        {[-1, 1].map((side) =>
          [-0.22, 0, 0.22].map((spread) => (
            <mesh
              key={`${side}${spread}`}
              position={[side * 0.62, -0.14 + spread * 0.25, 0.55]}
              rotation={[0, side * -0.55, Math.PI / 2 + side * spread]}
            >
              <cylinderGeometry args={[0.005, 0.005, 0.5, 4]} />
              <meshBasicMaterial color={persona === "rebel" ? "#e5e7eb" : "#3b2a2a"} />
            </mesh>
          )),
        )}
      </group>

      {/* Ba chấm "đang nghĩ" */}
      <group ref={dots} position={[0.8, 3.3, 0]} visible={false}>
        {[0, 1, 2].map((index) => (
          <mesh key={index} position={[index * 0.3, index * 0.25, 0]}>
            <sphereGeometry args={[0.1 + index * 0.03, 12, 12]} />
            <meshBasicMaterial color={look.rim} />
          </mesh>
        ))}
      </group>
    </group>
    </group>
  );
};

// Chill Buddy ngồi trên ghế nên cao hơn: lùi camera ra một chút cho vừa khung.
const Rig: React.FC<{ persona: CatPersona; variant: "stage" | "hero" }> = ({ persona, variant }) => {
  useFrame(({ camera }) => {
    const seated = persona === "buddy";
    // Bản sân khấu lùi xa hơn để thấy trọn cả bục dưới chân.
    const stage = variant === "stage";
    camera.position.set(seated ? 2.4 : 1.6, seated ? 2.8 : 2.5, seated ? (stage ? 9.4 : 9.5) : stage ? 8.5 : 7.4);
    camera.lookAt(0, seated ? (stage ? 2.0 : 2.2) : stage ? 1.7 : 1.85, 0);
  });
  return null;
};

export const Cat3D: React.FC<Cat3DProps> = ({ className, ...props }) => {
  const look = PERSONAS[props.persona].look;
  const holder = useRef<HTMLDivElement>(null);
  // Tab bị ẩn (display: none) hoặc cuộn khỏi màn hình thì dừng vẽ để khỏi tốn GPU.
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const element = holder.current;
    if (!element || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return (
    <div ref={holder} className={className} role="img" aria-label={`3D cat mascot, ${PERSONAS[props.persona].name}`}>
      <Canvas dpr={[1, 2]} frameloop={visible ? "always" : "never"} camera={{ position: [0, 2.1, 7.6], fov: 32 }}>
        <Rig persona={props.persona} variant={props.variant ?? "stage"} />
        <hemisphereLight args={["#fff7ec", "#b8a898", 0.9]} />
        <directionalLight position={[3, 6, 5]} intensity={1.7} color="#fff3e0" />
        <directionalLight position={[-4, 2, 3]} intensity={0.55} color="#cfe0ff" />
        <pointLight position={[-3, 3, -3]} intensity={30} color={look.rim} />
        <pointLight position={[3, 2, -3]} intensity={14} color={look.rim} />
        <CatModel {...props} />
      </Canvas>
    </div>
  );
};

export default Cat3D;

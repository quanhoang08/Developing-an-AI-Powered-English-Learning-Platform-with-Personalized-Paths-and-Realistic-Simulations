// Thẻ nghiêng 3D nhẹ theo con trỏ (lấy ý tưởng từ Circular3D của infiwebcraft.com), tự tắt khi người dùng bật "reduce motion".
import React from "react";
import { motion, useMotionValue, useReducedMotion, useSpring, useTransform, type HTMLMotionProps } from "motion/react";

const MAX_TILT = 6; // độ; đủ để cảm nhận chiều sâu mà chữ vẫn đọc được

export const TiltCard: React.FC<HTMLMotionProps<"div">> = ({ children, style, onMouseMove, onMouseLeave, ...rest }) => {
  const reduce = useReducedMotion();
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const spring = { stiffness: 220, damping: 22 };
  const rotateY = useSpring(useTransform(px, [0, 1], [-MAX_TILT, MAX_TILT]), spring);
  const rotateX = useSpring(useTransform(py, [0, 1], [MAX_TILT, -MAX_TILT]), spring);
  return (
    <motion.div
      {...rest}
      style={{ ...style, rotateX: reduce ? 0 : rotateX, rotateY: reduce ? 0 : rotateY, transformPerspective: 900 }}
      whileHover={reduce ? undefined : { y: -3 }}
      onMouseMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        px.set((e.clientX - r.left) / r.width);
        py.set((e.clientY - r.top) / r.height);
        onMouseMove?.(e);
      }}
      onMouseLeave={(e) => {
        px.set(0.5);
        py.set(0.5);
        onMouseLeave?.(e);
      }}
    >
      {children}
    </motion.div>
  );
};

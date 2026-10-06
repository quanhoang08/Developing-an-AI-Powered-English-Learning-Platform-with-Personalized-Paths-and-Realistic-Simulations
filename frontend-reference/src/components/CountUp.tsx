// Đếm từ giá trị đang hiển thị lên giá trị thật (số tải xong / chấm xong chạy lên, không nhảy cụt).
import React, { useEffect, useState } from "react";
import { animate } from "motion/react";

export function CountUp({ value }: { value: number }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const controls = animate(shown, value, { duration: 0.9, ease: "easeOut", onUpdate: setShown });
    return () => controls.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ chạy lại khi value đổi
  }, [value]);
  return <>{Math.round(shown).toLocaleString("en-US")}</>;
}

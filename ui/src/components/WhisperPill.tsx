import { motion } from "framer-motion";
import type { FluxVoiceState } from "../lib/ws";

type WhisperPillProps = {
  state: FluxVoiceState;
  isConnected: boolean;
};

const containerByState: Record<FluxVoiceState, { width: number; height: number; opacity: number }> = {
  idle: { width: 26, height: 26, opacity: 0.92 },
  processing: { width: 86, height: 30, opacity: 0.98 },
  playing: { width: 122, height: 34, opacity: 1 },
};

const indicatorByState: Record<FluxVoiceState, string> = {
  idle: "dot",
  processing: "pulse",
  playing: "wave",
};

export function WhisperPill({ state, isConnected }: WhisperPillProps) {
  const shape = containerByState[state];
  const mode = indicatorByState[state];

  return (
    <motion.div
      className="relative flex items-center justify-center rounded-full border border-white/20 bg-black/82 px-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_12px_30px_rgba(0,0,0,0.6)] [-webkit-app-region:drag]"
      animate={{ width: shape.width, height: shape.height, opacity: shape.opacity }}
      transition={{ type: "spring", stiffness: 270, damping: 25, mass: 0.75 }}
      role="status"
      aria-label={`FluxVoice ${state}`}
    >
      {/* Explicit no-drag island for future interactive controls hitbox boundaries. */}
      <motion.span
        className="absolute right-[7px] top-[7px] block h-[7px] w-[7px] rounded-full [-webkit-app-region:no-drag]"
        animate={
          isConnected
            ? {
                backgroundColor: "rgba(255,255,255,1)",
                boxShadow: [
                  "0 0 0 1px rgba(255,255,255,0.5)",
                  "0 0 0 1px rgba(255,255,255,0.85), 0 0 10px rgba(255,255,255,0.35)",
                  "0 0 0 1px rgba(255,255,255,0.5)",
                ],
              }
            : {
                backgroundColor: "rgba(0,0,0,0)",
                boxShadow: "0 0 0 1px rgba(255,255,255,0.55)",
              }
        }
        transition={{ duration: 1.1, repeat: isConnected ? Number.POSITIVE_INFINITY : 0, ease: "easeInOut" }}
        aria-label={isConnected ? "bridge connected" : "bridge disconnected"}
      />

      {mode === "dot" && (
        <motion.div
          className="h-[4px] w-[4px] rounded-full bg-white"
          animate={{ opacity: [0.55, 1, 0.55], scale: [0.95, 1.05, 0.95] }}
          transition={{ duration: 2.6, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        />
      )}

      {mode === "pulse" && (
        <motion.div className="flex items-center gap-[4px]" initial={false}>
          {[0, 1, 2].map((index) => (
            <motion.span
              key={`proc-${index}`}
              className="h-[6px] w-[6px] rounded-full bg-white/85"
              animate={{ opacity: [0.2, 1, 0.2], scale: [0.85, 1.2, 0.85] }}
              transition={{
                duration: 1.15,
                repeat: Number.POSITIVE_INFINITY,
                delay: index * 0.14,
                ease: "easeInOut",
              }}
            />
          ))}
        </motion.div>
      )}

      {mode === "wave" && (
        <motion.div className="flex items-end gap-[3px]" initial={false}>
          {[8, 14, 20, 14, 8].map((height, index) => (
            <motion.span
              key={`play-${index}`}
              className="block w-[3px] rounded-full bg-white"
              style={{ height }}
              animate={{
                scaleY: [0.45, 1, 0.5, 0.9, 0.45],
                opacity: [0.55, 1, 0.7, 0.95, 0.55],
              }}
              transition={{
                duration: 1,
                repeat: Number.POSITIVE_INFINITY,
                delay: index * 0.08,
                ease: "easeInOut",
              }}
            />
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}


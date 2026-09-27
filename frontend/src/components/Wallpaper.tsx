import type { CSSProperties } from "react"

// A calm, colourful wallpaper of flat layered shapes (no gradients). Each shape drifts very
// slowly so the page feels alive; motion stops for users who prefer reduced motion.
const drift = (t: number, dx: number, dy: number) =>
  ({ "--t": `${t}s`, "--dx": `${dx}px`, "--dy": `${dy}px` }) as CSSProperties

export function Wallpaper() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <svg className="h-full w-full" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <rect className="wall-shape" width="1440" height="900" fill="var(--wall-base)" />
        <path className="drift wall-shape" style={drift(22, 30, 20)} d="M-80 -60h720c-40 140-160 250-330 270S70 260-80 330z" fill="var(--wall-1)" />
        <path className="drift wall-shape" style={drift(26, -30, 18)} d="M1520 -40v420c-150 30-290-10-390-110S980 80 1000-40z" fill="var(--wall-3)" />
        <path className="drift wall-shape" style={drift(20, 26, -22)} d="M-80 560c170-80 360-70 520 10s330 150 520 110 330-150 560-120v440H-80z" fill="var(--wall-2)" />
        <path className="drift wall-shape" style={drift(24, -24, -14)} d="M860 980c20-150 160-260 330-260s290 110 330 260z" fill="var(--wall-4)" />
        <path className="drift wall-shape" style={drift(18, 20, 16)} d="M-60 760c150-50 300-30 420 40s150 180 80 230H-60z" fill="var(--wall-5)" />
        <path className="drift wall-shape" style={drift(28, -18, 24)} d="M520 330c90-70 240-80 330-10s80 190-20 240-250 40-320-40-80-130 10-190z" fill="var(--wall-6)" />
      </svg>
    </div>
  )
}

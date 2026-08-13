import React from "react";
import {
  AbsoluteFill,
  Html5Audio,
  interpolate,
  Series,
  staticFile,
  useCurrentFrame,
} from "remotion";

export const PAYNES_CREEK_TEMPLATE_ID = "paynes-creek-vector-v1" as const;

export type EvidenceLevel = "直接证据" | "解释" | "重建" | "未知边界";

export type PaynesCreekScene = {
  id: string;
  title: string;
  narration: string;
  evidence: EvidenceLevel;
  durationInFrames: number;
};

export type PaynesCreekPilotProps = {
  scenes: PaynesCreekScene[];
  narrationAudio: string;
  width: number;
  height: number;
};

const C = {
  ink: "#102A33",
  deep: "#061922",
  teal: "#2B7A78",
  brightTeal: "#46D8CF",
  amber: "#C98234",
  paleAmber: "#F1B766",
  sediment: "#D8E4E5",
  salt: "#F4F6F1",
  clay: "#B97852",
  wood: "#9A6035",
  water: "#1B4A66",
  red: "#D06152",
};

const evidenceColor: Record<EvidenceLevel, string> = {
  "直接证据": C.brightTeal,
  "解释": C.paleAmber,
  "重建": C.amber,
  "未知边界": C.red,
};

const arrow = (x1: number, y1: number, x2: number, y2: number, color = C.amber) => (
  <g stroke={color} strokeWidth={10} strokeLinecap="round" strokeLinejoin="round" fill="none">
    <path d={`M ${x1} ${y1} L ${x2} ${y2}`} />
    <path d={`M ${x2 - 26} ${y2 - 18} L ${x2} ${y2} L ${x2 - 26} ${y2 + 18}`} />
  </g>
);

const saltCrystal = (x: number, y: number, scale = 1) => (
  <polygon
    points={`${x},${y - 28 * scale} ${x + 24 * scale},${y - 8 * scale} ${x + 14 * scale},${y + 25 * scale} ${x - 17 * scale},${y + 22 * scale} ${x - 26 * scale},${y - 9 * scale}`}
    fill={C.salt}
    stroke={C.sediment}
    strokeWidth={5}
  />
);

const jar = (x: number, y: number, scale = 1) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <ellipse cx={0} cy={0} rx={62} ry={19} fill={C.sediment} stroke={C.clay} strokeWidth={9} />
    <path d="M -48 8 C -70 45 -73 126 -48 160 C -22 184 22 184 48 160 C 73 126 70 45 48 8 Z" fill={C.clay} />
    <path d="M -35 54 Q 0 72 35 54 M -42 105 Q 0 124 42 105" fill="none" stroke="#8A563E" strokeWidth={7} opacity={0.7} />
  </g>
);

const pot = (x: number, y: number, scale = 1) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <ellipse cx={0} cy={0} rx={78} ry={24} fill={C.deep} stroke={C.clay} strokeWidth={12} />
    <path d="M -65 9 C -88 58 -70 128 -38 151 L 38 151 C 70 128 88 58 65 9 Z" fill={C.clay} />
  </g>
);

const canoe = (x: number, y: number, scale = 1) => (
  <g transform={`translate(${x} ${y}) scale(${scale})`}>
    <path d="M -220 0 Q 0 82 220 0 Q 150 112 0 122 Q -150 112 -220 0 Z" fill={C.wood} stroke={C.paleAmber} strokeWidth={8} />
    <path d="M -168 17 Q 0 62 168 17" fill="none" stroke="#6E3F25" strokeWidth={8} />
  </g>
);

const SceneArt: React.FC<{id: string; progress: number}> = ({id, progress}) => {
  const drift = interpolate(progress, [0, 1], [-16, 16]);
  const pulse = interpolate(progress, [0, 0.5, 1], [0.88, 1, 0.88]);

  switch (id) {
    case "S01":
      return <>
        <path d="M 80 620 Q 250 430 430 510 T 790 470 L 790 760 L 80 760 Z" fill={C.teal} opacity={0.8} />
        <path d="M 1280 330 Q 1510 260 1810 390 L 1810 760 L 1180 760 Q 1260 570 1280 330 Z" fill={C.clay} opacity={0.82} />
        <path d="M 500 560 C 850 390 1080 660 1440 470" fill="none" stroke={C.amber} strokeWidth={14} strokeDasharray="28 22" />
        {arrow(1390, 490, 1490, 452)}
        <g transform={`translate(${330 + drift} 450) scale(${pulse})`}>{saltCrystal(0, 0, 1.8)}</g>
        <text x="180" y="710" fill={C.salt} fontSize="42">海岸盐场</text>
        <text x="1440" y="710" fill={C.salt} fontSize="42">内陆交换</text>
      </>;
    case "S02":
      return <>
        <path d="M 550 160 L 820 205 L 910 350 L 850 520 L 700 675 L 510 610 L 430 420 Z" fill={C.teal} stroke={C.sediment} strokeWidth={10} />
        <circle cx="700" cy="555" r={18 + pulse * 10} fill={C.amber} />
        <circle cx="700" cy="555" r={60} fill="none" stroke={C.amber} strokeWidth={8} opacity={0.65} />
        <text x="530" y="120" fill={C.salt} fontSize="42">今天的伯利兹南部海岸</text>
        <line x1="1080" y1="490" x2="1690" y2="490" stroke={C.sediment} strokeWidth={12} />
        <line x1="1140" y1="450" x2="1140" y2="530" stroke={C.amber} strokeWidth={12} />
        <line x1="1630" y1="450" x2="1630" y2="530" stroke={C.amber} strokeWidth={12} />
        <text x="1090" y="410" fill={C.paleAmber} fontSize="58" fontWeight={700}>公元 600</text>
        <text x="1510" y="610" fill={C.paleAmber} fontSize="58" fontWeight={700}>900 年</text>
      </>;
    case "S03":
      return <>
        <rect x="555" y="175" width="810" height="220" rx="28" fill={C.wood} stroke={C.paleAmber} strokeWidth={10} />
        <rect x="605" y="225" width="710" height="105" rx="18" fill="#7892A0" />
        <path d="M 905 395 L 1015 395 L 995 485 L 925 485 Z" fill={C.wood} stroke={C.paleAmber} strokeWidth={8} />
        <path d="M 960 255 L 960 540" stroke={C.brightTeal} strokeWidth={22} strokeLinecap="round" />
        <path d="M 960 270 L 960 515" stroke={C.salt} strokeWidth={5} strokeDasharray="20 18" opacity={0.75} />
        <g transform={`translate(960 560) scale(${0.98 + pulse * 0.02})`}>{jar(0, 0, 1.05)}</g>
        <ellipse cx="960" cy="567" rx="48" ry="12" fill={C.brightTeal} opacity={0.8} />
        <rect x="515" y="135" width="890" height="640" rx="44" fill="none" stroke={C.amber} strokeWidth={8} strokeDasharray="24 18" />
        <text x="560" y="120" fill={C.paleAmber} fontSize="36">重建示意：木槽在上 · 陶罐在下 · 液流止于罐内</text>
      </>;
    case "S04":
      return <>
        <g transform={`translate(960 ${260 + drift * 0.25})`}>{pot(0, 0, 1.3)}</g>
        <path d="M 760 550 L 835 365 L 910 550 Z M 1010 550 L 1085 365 L 1160 550 Z" fill={C.clay} opacity={0.9} />
        <g transform={`translate(0 ${8 * pulse})`}>
          <path d="M 820 650 C 760 570 850 520 890 455 C 910 540 980 550 960 650 Z" fill={C.amber} />
          <path d="M 950 650 C 900 575 1005 530 1040 465 C 1065 550 1120 575 1090 650 Z" fill={C.paleAmber} />
        </g>
        <text x="690" y="740" fill={C.sediment} fontSize="42">陶器 + 黏土支座 + 火</text>
      </>;
    case "S05":
      return <>
        <g transform="translate(230 160)">
          <path d="M 80 250 L 310 70 L 540 250 Z" fill={C.amber} />
          <rect x="130" y="250" width="360" height="300" fill={C.wood} />
          {[160, 270, 380, 470].map((x) => <rect key={x} x={x} y="520" width="22" height="150" fill={C.paleAmber} />)}
          <text x="190" y="420" fill={C.salt} fontSize="44">盐厨房</text>
        </g>
        <g transform="translate(1110 185)">
          <path d="M 80 225 L 300 60 L 520 225 Z" fill={C.teal} />
          <rect x="125" y="225" width="350" height="285" fill="#35626B" />
          {[150, 260, 370, 450].map((x) => <rect key={x} x={x} y="490" width="22" height="150" fill={C.sediment} />)}
          <text x="180" y="390" fill={C.salt} fontSize="44">居住空间</text>
        </g>
        <path d="M 820 460 L 1080 460" stroke={C.paleAmber} strokeWidth={10} strokeDasharray="20 18" />
        <text x="810" y="420" fill={C.paleAmber} fontSize="34">相邻</text>
      </>;
    case "S06":
      return <>
        <rect x="120" y="150" width="1680" height="590" rx="38" fill="#153A42" stroke={C.teal} strokeWidth={8} />
        {Array.from({length: 14}, (_, index) => {
          const x = 270 + (index % 7) * 235;
          const y = 270 + Math.floor(index / 7) * 270;
          return <g key={index}>{pot(x, y, 0.53)}</g>;
        })}
        <path d="M 230 680 L 1680 680" stroke={C.amber} strokeWidth={11} />
        <text x="560" y="820" fill={C.salt} fontSize="52" fontWeight={700}>专门作业空间 · 大量制盐粗陶</text>
      </>;
    case "S07":
      return <>
        <g transform="translate(310 180)">
          <path d="M 60 470 Q 250 130 480 470 Z" fill={C.salt} stroke={C.sediment} strokeWidth={10} />
          {saltCrystal(190, 310, 1.1)}{saltCrystal(315, 350, 0.8)}
          <text x="170" y="560" fill={C.salt} fontSize="44">散盐</text>
        </g>
        <g transform="translate(1040 160)">
          {[0, 1, 2].map((i) => <g key={i} transform={`translate(${i * 190} ${i % 2 * 35})`}><rect x="0" y="230" width="145" height="180" rx="25" fill={C.salt} stroke={C.amber} strokeWidth={9} /></g>)}
          <rect x="-70" y="170" width="690" height="330" rx="35" fill="none" stroke={C.amber} strokeWidth={8} strokeDasharray="22 18" />
          <text x="80" y="580" fill={C.paleAmber} fontSize="44">可能的盐饼</text>
        </g>
        <text x="650" y="810" fill={C.red} fontSize="46" fontWeight={700}>不等于“通用货币”</text>
      </>;
    case "S08":
      return <>
        <path d="M 220 640 Q 520 550 850 640 T 1500 640 T 1830 640 L 1830 790 L 220 790 Z" fill={C.water} />
        <g transform={`translate(${950 + drift} 420) rotate(-18)`}>
          <rect x="-390" y="-24" width="720" height="48" rx="24" fill={C.wood} />
          <path d="M 330 -60 Q 520 0 330 60 Z" fill={C.wood} stroke={C.paleAmber} strokeWidth={8} />
        </g>
        <line x1="500" y1="220" x2="1410" y2="220" stroke={C.amber} strokeWidth={8} />
        <line x1="500" y1="185" x2="500" y2="255" stroke={C.amber} strokeWidth={8} />
        <line x1="1410" y1="185" x2="1410" y2="255" stroke={C.amber} strokeWidth={8} />
        <text x="790" y="175" fill={C.salt} fontSize="64" fontWeight={700}>约 1.43 米</text>
        <text x="730" y="835" fill={C.brightTeal} fontSize="42">全尺寸木桨：直接证据</text>
      </>;
    case "S09":
      return <>
        <g transform={`translate(${870 + drift} 500)`}>{canoe(0, 0, 1.45)}</g>
        {[690, 850, 1010].map((x) => <rect key={x} x={x} y="400" width="115" height="90" rx="18" fill={C.salt} opacity={0.9} />)}
        <path d="M 180 680 Q 520 610 900 680 T 1740 680" fill="none" stroke={C.water} strokeWidth={55} />
        <g opacity={0.95}>
          <circle cx="1430" cy="330" r="110" fill="#351F24" stroke={C.red} strokeWidth={8} />
          <text x="1395" y="375" fill={C.salt} fontSize="130" fontWeight={700}>?</text>
          <text x="1240" y="500" fill={C.red} fontSize="40">没有某条船的货单</text>
        </g>
      </>;
    case "S10":
      return <>
        <circle cx="310" cy="500" r="115" fill={C.teal} />
        <text x="225" y="515" fill={C.salt} fontSize="40">沿海盐场</text>
        {[{x: 1040, y: 260}, {x: 1420, y: 480}, {x: 1120, y: 700}].map((p, index) => <g key={index}>
          <path d={`M 420 500 Q 730 ${p.y} ${p.x - 80} ${p.y}`} fill="none" stroke={C.amber} strokeWidth={10} strokeDasharray="24 20" />
          <circle cx={p.x} cy={p.y} r={78} fill="#264A52" stroke={C.paleAmber} strokeWidth={8} />
          <text x={p.x - 22} y={p.y + 24} fill={C.salt} fontSize="70">?</text>
        </g>)}
        <text x="1040" y="860" fill={C.red} fontSize="43">具体路线 · 城市 · 买家：未知</text>
      </>;
    case "S11":
      return <>
        <rect x="120" y="145" width="750" height="620" rx="30" fill="#163943" stroke={C.paleAmber} strokeWidth={8} />
        <rect x="1050" y="145" width="750" height="620" rx="30" fill="#123347" stroke={C.brightTeal} strokeWidth={8} />
        <text x="375" y="220" fill={C.paleAmber} fontSize="50" fontWeight={700}>古代作业时</text>
        <text x="1290" y="220" fill={C.brightTeal} fontSize="50" fontWeight={700}>废弃后淹没</text>
        {[280, 430, 580, 730].map((x) => <rect key={x} x={x} y="350" width="32" height="320" fill={C.wood} />)}
        <path d="M 170 565 L 820 565" stroke={C.clay} strokeWidth={70} />
        {[1210, 1360, 1510, 1660].map((x) => <rect key={x} x={x} y="350" width="32" height="320" fill={C.wood} />)}
        <path d="M 1090 440 Q 1250 400 1420 440 T 1770 440 L 1770 650 L 1090 650 Z" fill={C.water} opacity={0.72} />
        <path d="M 1090 650 L 1770 650" stroke="#2C1E20" strokeWidth={90} />
        <text x="1200" y="715" fill={C.sediment} fontSize="36">缺氧泥炭保存木柱</text>
      </>;
    case "S12":
      return <>
        {[
          {x: 250, label: "浓缩"}, {x: 560, label: "煮卤"}, {x: 870, label: "成盐"},
          {x: 1180, label: "水运"}, {x: 1490, label: "内陆交换"},
        ].map((item, index) => <g key={item.label}>
          <circle cx={item.x} cy="410" r="96" fill={index < 3 ? C.teal : C.wood} stroke={C.paleAmber} strokeWidth={8} />
          <text x={item.x - item.label.length * 24} y="430" fill={C.salt} fontSize="44" fontWeight={700}>{item.label}</text>
          {index < 4 ? arrow(item.x + 108, 410, item.x + 202, 410, C.amber) : null}
        </g>)}
        <rect x="200" y="625" width="970" height="145" rx="28" fill="#174B4C" />
        <text x="270" y="715" fill={C.brightTeal} fontSize="50" fontWeight={700}>能重建：生产与交换机制</text>
        <rect x="1210" y="625" width="510" height="145" rx="28" fill="#44252B" />
        <text x="1265" y="715" fill={C.red} fontSize="46" fontWeight={700}>不能复原：某一船的旅程</text>
      </>;
    default:
      return null;
  }
};

const Scene: React.FC<{scene: PaynesCreekScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const progress = interpolate(frame, [0, Math.max(1, scene.durationInFrames - 1)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(frame, [0, 10, Math.max(11, scene.durationInFrames - 10), scene.durationInFrames - 1], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return <AbsoluteFill style={{backgroundColor: C.deep, color: C.salt, fontFamily: '"Microsoft YaHei", "Noto Sans CJK SC", sans-serif', opacity}}>
    <svg viewBox="0 0 1920 900" width="100%" height="83.333%" role="img" aria-label={scene.title}>
      <rect width="1920" height="900" fill={C.deep} />
      <circle cx="1680" cy="100" r="300" fill={C.ink} opacity={0.32} />
      <circle cx="230" cy="760" r="270" fill={C.ink} opacity={0.24} />
      <SceneArt id={scene.id} progress={progress} />
    </svg>
    <div style={{position: "absolute", top: 46, left: 64, right: 64, display: "flex", alignItems: "center", justifyContent: "space-between"}}>
      <div style={{display: "flex", gap: 20, alignItems: "center"}}>
        <span style={{fontSize: 30, color: C.paleAmber, fontWeight: 800, letterSpacing: 3}}>{scene.id}</span>
        <span style={{fontSize: 42, fontWeight: 800}}>{scene.title}</span>
      </div>
      <span style={{fontSize: 28, fontWeight: 800, color: evidenceColor[scene.evidence], border: `3px solid ${evidenceColor[scene.evidence]}`, borderRadius: 999, padding: "9px 20px"}}>{scene.evidence}</span>
    </div>
    <div style={{position: "absolute", left: 0, right: 0, bottom: 0, minHeight: 230, padding: "38px 130px 42px", display: "flex", alignItems: "center", justifyContent: "center", background: "linear-gradient(180deg, rgba(6,25,34,0) 0%, rgba(6,25,34,.94) 24%, #061922 100%)", borderTop: `2px solid ${C.ink}`}}>
      <div style={{maxWidth: 1540, fontSize: 45, fontWeight: 750, lineHeight: 1.5, letterSpacing: 1.2, textAlign: "center", textShadow: "0 3px 10px rgba(0,0,0,.9)"}}>{scene.narration}</div>
    </div>
  </AbsoluteFill>;
};

export const paynesCreekDurationInFrames = (props: PaynesCreekPilotProps) =>
  props.scenes.reduce((sum, scene) => sum + scene.durationInFrames, 0);

export const PaynesCreekPilot: React.FC<PaynesCreekPilotProps> = (props) => (
  <AbsoluteFill style={{backgroundColor: C.deep}}>
    <Series>
      {props.scenes.map((scene) => <Series.Sequence key={scene.id} durationInFrames={scene.durationInFrames}><Scene scene={scene} /></Series.Sequence>)}
    </Series>
    <Html5Audio src={staticFile(props.narrationAudio)} volume={1} />
  </AbsoluteFill>
);

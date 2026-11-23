/** Decorative hero illustration: a code window, a bug on the faulty line, and a lens scanning for it. */
export default function HeroArt() {
  const lines = [
    { w: 150, c: "#8fb2ff" }, { w: 220, c: "#5b6785" }, { w: 180, c: "#5b6785" }, { w: 120, c: "#c9b8ff" },
    { w: 240, c: "#5b6785", bug: true }, { w: 160, c: "#5b6785" }, { w: 200, c: "#67e8f9" }, { w: 110, c: "#5b6785" },
  ];
  return (
    <svg viewBox="0 0 520 380" className="hero-art" role="img" aria-label="A magnifying glass finding a bug in code">
      <defs>
        <linearGradient id="ha-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22d3ee" /><stop offset="0.5" stopColor="#6d8bff" /><stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
        <radialGradient id="ha-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="rgba(109,139,255,0.45)" /><stop offset="1" stopColor="rgba(109,139,255,0)" />
        </radialGradient>
        <radialGradient id="ha-lens" cx="0.35" cy="0.3" r="0.8">
          <stop offset="0" stopColor="rgba(255,255,255,0.22)" /><stop offset="0.6" stopColor="rgba(94,179,255,0.08)" /><stop offset="1" stopColor="rgba(94,179,255,0.02)" />
        </radialGradient>
        <clipPath id="ha-lens-clip"><circle cx="0" cy="0" r="54" /></clipPath>
        <filter id="ha-blur"><feGaussianBlur stdDeviation="18" /></filter>
      </defs>

      <circle cx="270" cy="190" r="170" fill="url(#ha-glow)" />

      {/* orbiting graph nodes */}
      <g className="ha-orbit">
        {[[60, 70], [470, 90], [480, 300], [40, 300]].map(([x, y], i) => (
          <g key={i}>
            <line x1={x} y1={y} x2={270} y2={190} stroke="url(#ha-grad)" strokeOpacity="0.18" strokeDasharray="3 6" />
            <circle cx={x} cy={y} r="6" fill="#0e1322" stroke="url(#ha-grad)" strokeWidth="2" className="ha-pulse" style={{ animationDelay: `${i * 0.6}s` }} />
          </g>
        ))}
      </g>

      {/* code window */}
      <g transform="translate(110 70)">
        <rect width="320" height="236" rx="16" fill="#0b1020" stroke="rgba(148,163,196,0.22)" />
        <rect width="320" height="34" rx="16" fill="#111a2e" />
        <rect y="20" width="320" height="14" fill="#111a2e" />
        {["#f05252", "#fab219", "#22c55e"].map((c, i) => <circle key={c} cx={20 + i * 16} cy="17" r="5" fill={c} opacity="0.85" />)}
        <rect x="72" y="11" width="120" height="12" rx="6" fill="rgba(148,163,196,0.12)" />
        {lines.map((l, i) => (
          <g key={i}>
            <text x="16" y={64 + i * 22} style={{ fontSize: 10, fill: "#3d4763", fontFamily: "var(--mono)" }}>{i + 1}</text>
            {l.bug && <rect x="30" y={51 + i * 22} width="282" height="20" rx="5" fill="rgba(240,82,82,0.12)" className="ha-hot" />}
            <rect x="38" y={57 + i * 22} width={l.w} height="8" rx="4" fill={l.bug ? "#f08a8a" : l.c} opacity={l.bug ? 0.9 : 0.55} />
          </g>
        ))}
        {/* the bug */}
        <g transform="translate(262 149)" className="ha-bug">
          <ellipse cx="0" cy="0" rx="9" ry="11" fill="#f05252" />
          <circle cx="0" cy="-12" r="5" fill="#f05252" />
          <line x1="0" y1="-11" x2="0" y2="11" stroke="#0b1020" strokeWidth="1.5" />
          {[-6, 0, 6].map((y) => (
            <g key={y}>
              <line x1="-9" y1={y} x2="-16" y2={y - 3} stroke="#f05252" strokeWidth="2" strokeLinecap="round" />
              <line x1="9" y1={y} x2="16" y2={y - 3} stroke="#f05252" strokeWidth="2" strokeLinecap="round" />
            </g>
          ))}
          <line x1="-3" y1="-16" x2="-7" y2="-22" stroke="#f05252" strokeWidth="1.6" strokeLinecap="round" />
          <line x1="3" y1="-16" x2="7" y2="-22" stroke="#f05252" strokeWidth="1.6" strokeLinecap="round" />
        </g>
      </g>

      {/* magnifying glass scanning */}
      <g className="ha-lens">
        <circle r="54" fill="url(#ha-lens)" />
        <g clipPath="url(#ha-lens-clip)">
          <rect x="-60" y="-2" width="120" height="3" fill="#67e8f9" opacity="0.5" className="ha-scan" />
        </g>
        <circle r="54" fill="none" stroke="url(#ha-grad)" strokeWidth="7" />
        <circle r="54" fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth="1" />
        <line x1="40" y1="40" x2="82" y2="82" stroke="url(#ha-grad)" strokeWidth="13" strokeLinecap="round" />
      </g>

      {/* floating chips */}
      <g className="ha-float" style={{ animationDelay: "0s" }}>
        <rect x="18" y="128" width="112" height="32" rx="10" fill="#0e1322" stroke="rgba(94,179,255,0.4)" />
        <circle cx="36" cy="144" r="5" fill="#5eb3ff" />
        <text x="48" y="148" style={{ fontSize: 11.5, fill: "#cfe6ff", fontWeight: 600 }}>E4 · evidence</text>
      </g>
      <g className="ha-float" style={{ animationDelay: "1.2s" }}>
        <rect x="372" y="36" width="132" height="32" rx="10" fill="#0e1322" stroke="rgba(139,92,246,0.45)" />
        <circle cx="390" cy="52" r="5" fill="#8b5cf6" />
        <text x="402" y="56" style={{ fontSize: 11.5, fill: "#e2d8ff", fontWeight: 600 }}>H1 · root cause</text>
      </g>
      <g className="ha-float" style={{ animationDelay: "2.1s" }}>
        <rect x="350" y="318" width="150" height="34" rx="11" fill="#0e1322" stroke="rgba(34,197,94,0.45)" />
        <path d="M368 335 l5 5 l9 -10" fill="none" stroke="#22c55e" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        <text x="390" y="339" style={{ fontSize: 11.5, fill: "#c7f5d6", fontWeight: 600 }}>tests pass · fixed</text>
      </g>
    </svg>
  );
}

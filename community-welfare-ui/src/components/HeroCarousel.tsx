import { useEffect, useState, type ReactElement } from "react";

interface Landmark {
  src: string;
  label: string;
  loc: string;
  shape: "mosque" | "minar" | "faisal" | "monument" | "mausoleum";
}

const LANDMARKS: Landmark[] = [
  { src: "/images/badshahi-mosque.jpg", label: "Badshahi Mosque", loc: "Lahore, Punjab", shape: "mosque" },
  { src: "/images/minar-e-pakistan.jpg", label: "Minar-e-Pakistan", loc: "Lahore, Punjab", shape: "minar" },
  { src: "/images/faisal-mosque.jpg", label: "Faisal Mosque", loc: "Islamabad", shape: "faisal" },
  { src: "/images/pakistan-monument.jpg", label: "Pakistan Monument", loc: "Islamabad", shape: "monument" },
  { src: "/images/quaid-mausoleum.jpg", label: "Quaid-e-Azam Mausoleum", loc: "Karachi, Sindh", shape: "mausoleum" },
];

interface LandmarkSVGProps {
  shape: Landmark["shape"];
}

function LandmarkSVG({ shape }: LandmarkSVGProps) {
  const common = {
    fill: "none",
    stroke: "rgba(255,255,255,.55)",
    strokeWidth: 1.2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  const shapes: Record<Landmark["shape"], ReactElement> = {
    mosque: (
      <svg viewBox="0 0 280 140" style={{ width: "100%", maxWidth: 380, opacity: 0.7 }}>
        <rect x="18" y="35" width="12" height="80" {...common} />
        <rect x="22" y="25" width="4" height="14" {...common} />
        <path d="M20 25 Q24 18 28 25" {...common} />
        <rect x="250" y="35" width="12" height="80" {...common} />
        <rect x="254" y="25" width="4" height="14" {...common} />
        <path d="M252 25 Q256 18 260 25" {...common} />
        <path d="M90 115 L90 80 Q90 40 140 38 Q190 40 190 80 L190 115Z" {...common} />
        <ellipse cx="140" cy="40" rx="12" ry="8" {...common} />
        <path d="M60 115 L60 88 Q60 68 80 66 Q100 68 100 88 L100 115Z" {...common} />
        <path d="M180 115 L180 88 Q180 68 200 66 Q220 68 220 88 L220 115Z" {...common} />
        <path d="M108 115 L108 90 Q118 78 130 78 Q142 78 152 90 L152 115" {...common} />
        <line x1="30" y1="115" x2="250" y2="115" {...common} />
      </svg>
    ),
    minar: (
      <svg viewBox="0 0 200 200" style={{ width: "100%", maxWidth: 240, opacity: 0.7 }}>
        <rect x="60" y="175" width="80" height="15" {...common} />
        <path d="M80 175 L82 120 L90 80 L95 50 L100 20 L105 50 L110 80 L118 120 L120 175Z" {...common} />
        <line x1="86" y1="120" x2="114" y2="120" {...common} />
        <line x1="88" y1="80" x2="112" y2="80" {...common} />
        <line x1="92" y1="50" x2="108" y2="50" {...common} />
        <polygon
          points="100,10 101.8,15.5 107.5,15.5 103,19 104.8,24.5 100,21 95.2,24.5 97,19 92.5,15.5 98.2,15.5"
          stroke="rgba(255,255,255,.7)"
          fill="rgba(255,255,255,.2)"
          strokeWidth={1}
        />
      </svg>
    ),
    faisal: (
      <svg viewBox="0 0 300 180" style={{ width: "100%", maxWidth: 400, opacity: 0.7 }}>
        <path d="M150 20 L240 140 L60 140Z" {...common} />
        <rect x="30" y="60" width="10" height="120" {...common} />
        <path d="M30 60 Q35 48 40 60" {...common} />
        <rect x="260" y="60" width="10" height="120" {...common} />
        <path d="M260 60 Q265 48 270 60" {...common} />
        <path d="M100 140 L100 120 Q130 105 150 105 Q170 105 200 120 L200 140" {...common} />
        <line x1="60" y1="140" x2="240" y2="140" {...common} />
        <path
          d="M145 22 A6 6 0 1 0 155 28 A4 4 0 1 1 145 22Z"
          stroke="rgba(255,255,255,.7)"
          fill="rgba(255,255,255,.15)"
          strokeWidth={1.2}
        />
      </svg>
    ),
    monument: (
      <svg viewBox="0 0 240 200" style={{ width: "100%", maxWidth: 320, opacity: 0.7 }}>
        <path d="M120 100 Q100 60 80 40 Q100 80 120 100Z" {...common} />
        <path d="M120 100 Q160 80 180 60 Q140 80 120 100Z" {...common} />
        <path d="M120 100 Q80 120 60 150 Q100 120 120 100Z" {...common} />
        <path d="M120 100 Q160 120 180 150 Q140 120 120 100Z" {...common} />
        <circle cx="120" cy="100" r="22" {...common} />
        <circle cx="120" cy="100" r="12" {...common} />
        <polygon
          points="120,88 121.8,93.5 127.5,93.5 123,97 124.8,102.5 120,99 115.2,102.5 117,97 112.5,93.5 118.2,93.5"
          stroke="rgba(255,255,255,.7)"
          fill="rgba(255,255,255,.2)"
          strokeWidth={1}
        />
        <path d="M80 165 Q120 155 160 165" {...common} />
      </svg>
    ),
    mausoleum: (
      <svg viewBox="0 0 280 180" style={{ width: "100%", maxWidth: 380, opacity: 0.7 }}>
        <path d="M80 130 L80 90 Q80 40 140 36 Q200 40 200 90 L200 130Z" {...common} />
        <ellipse cx="140" cy="38" rx="14" ry="9" {...common} />
        <rect x="40" y="90" width="40" height="40" {...common} />
        <line x1="52" y1="90" x2="52" y2="130" {...common} />
        <line x1="64" y1="90" x2="64" y2="130" {...common} />
        <rect x="200" y="90" width="40" height="40" {...common} />
        <line x1="212" y1="90" x2="212" y2="130" {...common} />
        <line x1="224" y1="90" x2="224" y2="130" {...common} />
        <rect x="30" y="130" width="220" height="10" {...common} />
        <line x1="20" y1="140" x2="260" y2="140" {...common} />
        <line x1="140" y1="28" x2="140" y2="14" {...common} />
        <path
          d="M140 14 L152 17 L140 20Z"
          stroke="rgba(255,255,255,.6)"
          fill="rgba(47,125,78,.4)"
          strokeWidth={1}
        />
      </svg>
    ),
  };
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        background: "linear-gradient(160deg,#1E3A52 0%,#2D4A6B 100%)",
      }}
    >
      {shapes[shape]}
    </div>
  );
}

interface HeroCarouselProps {
  caption?: string;
  inline?: boolean;
}

export function HeroCarousel({
  caption = "Serving the Pakistani Community in Kuwait",
  inline = true,
}: HeroCarouselProps) {
  const [current, setCurrent] = useState(0);
  const [imgLoaded, setImgLoaded] = useState<Record<number, boolean>>({});
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    const t = setInterval(() => setCurrent((c) => (c + 1) % LANDMARKS.length), 5500);
    return () => clearInterval(t);
  }, [paused]);

  const containerStyle: React.CSSProperties = inline
    ? {
        position: "relative",
        borderRadius: 22,
        overflow: "hidden",
        border: "1.5px solid rgba(255,255,255,.22)",
        boxShadow: "0 8px 40px rgba(20,40,65,.45)",
        height: 380,
        background: "#1E3A52",
        userSelect: "none",
      }
    : {
        position: "relative",
        height: 360,
        overflow: "hidden",
        background: "#1E3A52",
        userSelect: "none",
      };

  return (
    <div
      style={containerStyle}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      aria-label="Pakistan landmarks carousel"
    >
      {LANDMARKS.map((lm, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            inset: 0,
            opacity: i === current ? 1 : 0,
            transition: "opacity 1.6s ease",
            zIndex: i === current ? 1 : 0,
          }}
        >
          <div style={{ position: "absolute", inset: 0 }}>
            <LandmarkSVG shape={lm.shape} />
          </div>
          <div
            style={{
              position: "absolute",
              inset: 0,
              opacity: imgLoaded[i] ? 1 : 0,
              transition: "opacity .8s",
              backgroundImage: imgLoaded[i] ? `url(${lm.src})` : "none",
              backgroundSize: "cover",
              backgroundPosition: "center",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              background:
                "linear-gradient(to bottom,rgba(30,58,82,.1) 0%,rgba(20,40,65,.0) 35%,rgba(20,40,65,.55) 80%,rgba(20,40,65,.80) 100%)",
            }}
          />
          <img
            src={lm.src}
            alt=""
            style={{ display: "none" }}
            onLoad={() => setImgLoaded((p) => ({ ...p, [i]: true }))}
          />
        </div>
      ))}

      {/* Top Pakistan pill */}
      <div style={{ position: "absolute", top: 16, left: 16, zIndex: 10 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
            background: "rgba(255,255,255,.12)",
            backdropFilter: "blur(6px)",
            border: "1px solid rgba(255,255,255,.18)",
            borderRadius: 20,
            padding: "4px 13px",
            fontSize: 11,
            fontWeight: 700,
            color: "rgba(255,255,255,.85)",
            letterSpacing: ".06em",
            textTransform: "uppercase",
          }}
        >
          <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#6ee79a" }} />
          Pakistan
        </div>
      </div>

      {/* Caption + dots */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          padding: "16px 20px",
          zIndex: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          gap: 12,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 10,
              color: "rgba(255,255,255,.52)",
              fontWeight: 700,
              letterSpacing: ".08em",
              textTransform: "uppercase",
              marginBottom: 3,
            }}
          >
            {LANDMARKS[current].loc}
          </div>
          <div
            style={{
              fontSize: inline ? 16 : 18,
              fontWeight: 700,
              color: "#fff",
              lineHeight: 1.2,
              textShadow: "0 1px 4px rgba(0,0,0,.35)",
            }}
          >
            {LANDMARKS[current].label}
          </div>
          <div
            style={{
              fontSize: 11,
              color: "rgba(255,255,255,.45)",
              marginTop: 4,
              fontStyle: "italic",
            }}
          >
            {caption}
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, flexShrink: 0, alignItems: "center", paddingBottom: 2 }}>
          {LANDMARKS.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              aria-label={`Show slide ${i + 1}`}
              style={{
                width: i === current ? 20 : 6,
                height: 6,
                borderRadius: 3,
                background: i === current ? "#fff" : "rgba(255,255,255,.32)",
                border: "none",
                cursor: "pointer",
                transition: "all .35s",
                padding: 0,
              }}
            />
          ))}
        </div>
      </div>

      {/* Arrows */}
      {(["left", "right"] as const).map((dir) => (
        <button
          key={dir}
          onClick={() =>
            setCurrent((c) =>
              dir === "left"
                ? (c - 1 + LANDMARKS.length) % LANDMARKS.length
                : (c + 1) % LANDMARKS.length
            )
          }
          aria-label={dir === "left" ? "Previous slide" : "Next slide"}
          style={{
            position: "absolute",
            [dir]: 12,
            top: "50%",
            transform: "translateY(-50%)",
            zIndex: 10,
            background: "rgba(255,255,255,.1)",
            border: "1px solid rgba(255,255,255,.18)",
            width: 34,
            height: 34,
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            transition: "background .2s",
          } as React.CSSProperties}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,.22)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "rgba(255,255,255,.1)")}
        >
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth={2.5}
            strokeLinecap="round"
          >
            {dir === "left" ? (
              <polyline points="15 18 9 12 15 6" />
            ) : (
              <polyline points="9 18 15 12 9 6" />
            )}
          </svg>
        </button>
      ))}
    </div>
  );
}

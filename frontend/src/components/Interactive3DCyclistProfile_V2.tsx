// Interactive3DCyclistProfile_V2.tsx
import React, { useState } from 'react';

type HoverZone = 'rider-weight' | 'wheel' | 'frame' | 'body' | 'drivetrain' | 'tire' | 'crr' | 'bike-type' | 'ftp' | null;

const Interactive3DCyclistProfile: React.FC = () => {
  const [hoveredZone, setHoveredZone] = useState<HoverZone>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  // All 9 profile settings with educational content
  const profileSettings = [
    {
      id: 'rider-weight',
      label: 'Rider weight',
      value: '75 kg',
      zone: 'rider-weight' as const,
      color: '#ec4899',
      tooltip: {
        title: 'Rider Weight',
        description: 'Your body mass is the foundation of all power calculations. Heavier riders need more power on climbs due to gravity, but weight has minimal impact on flat terrain. Physics modeling accounts for gravitational force (mg) in elevation gain.',
        impact: 'Critical for climbing power accuracy',
      },
    },
    {
      id: 'bike-weight',
      label: 'Bike weight',
      value: '8.0 kg',
      zone: 'frame' as const,
      color: '#f59e0b',
      tooltip: {
        title: 'Bike Weight',
        description: 'Typical road bikes are 7-9kg. Combined with rider weight, this determines total system mass. Lower bike weight reduces power needed on climbs but has negligible impact on flats. Every kg saved = ~3W less power at 10% gradient.',
        impact: 'Moderate impact on climbing efficiency',
      },
    },
    {
      id: 'wheel',
      label: 'Wheel dimension',
      value: '700c',
      zone: 'wheel' as const,
      color: '#ef4444',
      tooltip: {
        title: 'Wheel Dimension',
        description: '700c (622mm) is standard for road bikes. Wheel diameter affects speed calculation from cadence and directly impacts rolling resistance coefficient (Crr). Smaller wheels = higher rotational losses.',
        impact: 'Essential for speed and Crr calculations',
      },
    },
    {
      id: 'cda',
      label: 'CdA (drag area)',
      value: '0.300 m²',
      zone: 'body' as const,
      color: '#10b981',
      tooltip: {
        title: 'Coefficient of Drag Area (CdA)',
        description: 'CdA = Cd × frontal area. This is THE dominant factor at speed. Road position ~0.300, drops ~0.270, TT ~0.200. Wind resistance increases with velocity SQUARED (½ρv²ACd), making CdA exponentially important above 30 km/h.',
        impact: 'MASSIVE - exponential with velocity',
      },
    },
    {
      id: 'crr',
      label: 'Crr (rolling resistance)',
      value: '0.0040',
      zone: 'crr' as const,
      color: '#8b5cf6',
      tooltip: {
        title: 'Coefficient of Rolling Resistance (Crr)',
        description: 'Crr depends on tire width, pressure, quality, and road surface. Lower Crr = less power lost to tire deformation. Modern 28mm tires at optimal pressure: Crr ~0.0040. This directly multiplies with weight and gravity in power calculations.',
        impact: 'Significant on all terrain types',
      },
    },
    {
      id: 'tire-width',
      label: 'Tire width',
      value: '28mm',
      zone: 'tire' as const,
      color: '#a855f7',
      tooltip: {
        title: 'Tire Width',
        description: 'Wider tires (25-32mm) have LOWER rolling resistance than narrow tires at same pressure (contrary to old belief). 28mm is the sweet spot for modern road bikes. Width affects Crr, comfort, and grip. Impacts physics calculations through Crr coefficient.',
        impact: 'Moderate - affects Crr directly',
      },
    },
    {
      id: 'tire-quality',
      label: 'Tire quality',
      value: 'High-end',
      zone: 'tire' as const,
      color: '#a855f7',
      tooltip: {
        title: 'Tire Quality',
        description: 'Premium tires (Continental GP5000, Vittoria Corsa) have Crr ~0.0030-0.0035. Budget tires can be 0.0050+. A 0.0015 Crr difference = ~15W at 30 km/h for a 75kg rider. Physics model adjusts Crr based on tire quality tier.',
        impact: 'High - can swing 10-20W at speed',
      },
    },
    {
      id: 'bike-type',
      label: 'Bike type',
      value: 'Road',
      zone: 'bike-type' as const,
      color: '#3b82f6',
      tooltip: {
        title: 'Bike Type',
        description: 'Bike type determines default CdA and Crr baselines. Road bikes: aggressive position, low CdA. Gravel: upright, higher CdA but wider tires. TT bikes: lowest CdA (~0.200). Physics model uses type-specific aerodynamic and rolling resistance profiles.',
        impact: 'Sets baseline aero and resistance profile',
      },
    },
    {
      id: 'drivetrain',
      label: 'Crank efficiency',
      value: '96%',
      zone: 'drivetrain' as const,
      color: '#eab308',
      tooltip: {
        title: 'Drivetrain Efficiency',
        description: 'Modern drivetrains lose 2-5% of power through friction (chain, cassette, jockey wheels). Clean, well-lubricated: 97-98%. Dirty or worn: 93-95%. Physics model multiplies measured power by efficiency to get actual wheel power output.',
        impact: 'Small but measurable (3-7W typical)',
      },
    },
    {
      id: 'ftp',
      label: 'FTP',
      value: 'Not set',
      zone: 'ftp' as const,
      color: '#14b8a6',
      tooltip: {
        title: 'Functional Threshold Power (FTP)',
        description: 'Your sustainable power output for ~1 hour. FTP is the baseline for all training zones and trend analysis. We calculate this automatically from your uploaded rides using physics-based power modeling. No field test needed!',
        impact: 'Baseline for trend tracking and zones',
      },
    },
  ];

  const handleMouseEnter = (zone: HoverZone, e: React.MouseEvent) => {
    setHoveredZone(zone);
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPos({ x: rect.right + 20, y: rect.top });
  };

  return (
    <div className="w-full max-w-6xl mx-auto p-8">
      <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-8 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-slate-200">
        
        {/* Header */}
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-2">Profile Settings</h2>
          <p className="text-sm text-slate-600">
            Fine-tune your physics model for <span className="font-semibold text-emerald-600">~3-5% accuracy</span>.
            <span className="font-semibold text-blue-600"> Hover over any setting to see how it affects power calculations.</span>
          </p>
        </div>

        {/* Main Grid: Cyclist + Settings */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          
          {/* LEFT: Realistic Cyclist Silhouette (2 columns) */}
          <div className="lg:col-span-2">
            <div className="aspect-square bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl p-8 relative overflow-hidden">
              
              {/* Subtle grid */}
              <div 
                className="absolute inset-0 opacity-[0.03]"
                style={{
                  backgroundImage: `
                    linear-gradient(to right, #94a3b8 1px, transparent 1px),
                    linear-gradient(to bottom, #94a3b8 1px, transparent 1px)
                  `,
                  backgroundSize: '20px 20px',
                }}
              />

              {/* Realistic Cyclist SVG */}
              <svg
                viewBox="0 0 500 500"
                className="w-full h-full"
                style={{
                  filter: 'drop-shadow(0 10px 30px rgba(0,0,0,0.15))',
                  animation: 'gentleSway 4s ease-in-out infinite',
                }}
              >
                <defs>
                  {/* Gradients */}
                  <linearGradient id="riderGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor={hoveredZone === 'rider-weight' ? '#ec4899' : '#64748b'} />
                    <stop offset="100%" stopColor={hoveredZone === 'rider-weight' ? '#db2777' : '#475569'} />
                  </linearGradient>

                  <linearGradient id="bodyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor={hoveredZone === 'body' ? '#10b981' : '#3b82f6'} />
                    <stop offset="100%" stopColor={hoveredZone === 'body' ? '#059669' : '#2563eb'} />
                  </linearGradient>
                  
                  <linearGradient id="frameGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor={
                      hoveredZone === 'frame' ? '#f59e0b' : 
                      hoveredZone === 'bike-type' ? '#3b82f6' : '#334155'
                    } />
                    <stop offset="100%" stopColor={
                      hoveredZone === 'frame' ? '#d97706' : 
                      hoveredZone === 'bike-type' ? '#2563eb' : '#1e293b'
                    } />
                  </linearGradient>

                  <radialGradient id="wheelGradient">
                    <stop offset="0%" stopColor={hoveredZone === 'wheel' ? '#ef4444' : '#1e40af'} />
                    <stop offset="100%" stopColor={hoveredZone === 'wheel' ? '#dc2626' : '#1e3a8a'} />
                  </radialGradient>

                  <linearGradient id="tireGradient">
                    <stop offset="0%" stopColor={
                      hoveredZone === 'tire' ? '#a855f7' : 
                      hoveredZone === 'crr' ? '#8b5cf6' : '#1f2937'
                    } />
                    <stop offset="100%" stopColor={
                      hoveredZone === 'tire' ? '#9333ea' : 
                      hoveredZone === 'crr' ? '#7c3aed' : '#111827'
                    } />
                  </linearGradient>

                  <linearGradient id="drivetrainGradient">
                    <stop offset="0%" stopColor={hoveredZone === 'drivetrain' ? '#eab308' : '#64748b'} />
                    <stop offset="100%" stopColor={hoveredZone === 'drivetrain' ? '#ca8a04' : '#475569'} />
                  </linearGradient>

                  <linearGradient id="ftpGradient">
                    <stop offset="0%" stopColor={hoveredZone === 'ftp' ? '#14b8a6' : '#94a3b8'} />
                    <stop offset="100%" stopColor={hoveredZone === 'ftp' ? '#0d9488' : '#64748b'} />
                  </linearGradient>
                </defs>

                {/* Rear Wheel */}
                <g transform="translate(150, 380)">
                  <circle 
                    cx="0" 
                    cy="0" 
                    r="55" 
                    fill="url(#wheelGradient)"
                    className="transition-all duration-300"
                    style={{
                      filter: hoveredZone === 'wheel' ? 'drop-shadow(0 0 25px #ef4444)' : 'none',
                    }}
                  />
                  {/* Spokes */}
                  {[...Array(16)].map((_, i) => (
                    <line
                      key={i}
                      x1="0"
                      y1="0"
                      x2={Math.cos((i * Math.PI) / 8) * 50}
                      y2={Math.sin((i * Math.PI) / 8) * 50}
                      stroke="white"
                      strokeWidth="1.5"
                      opacity="0.4"
                    />
                  ))}
                  {/* Hub */}
                  <circle cx="0" cy="0" r="8" fill="#334155" />
                  
                  {/* Tire */}
                  <circle 
                    cx="0" 
                    cy="0" 
                    r="59" 
                    fill="none" 
                    stroke="url(#tireGradient)"
                    strokeWidth="8"
                    className="transition-all duration-300"
                    style={{
                      filter: (hoveredZone === 'tire' || hoveredZone === 'crr') ? 'drop-shadow(0 0 20px #a855f7)' : 'none',
                    }}
                  />
                </g>

                {/* Front Wheel */}
                <g transform="translate(380, 380)">
                  <circle 
                    cx="0" 
                    cy="0" 
                    r="55" 
                    fill="url(#wheelGradient)"
                    className="transition-all duration-300"
                    style={{
                      filter: hoveredZone === 'wheel' ? 'drop-shadow(0 0 25px #ef4444)' : 'none',
                    }}
                  />
                  {/* Spokes */}
                  {[...Array(16)].map((_, i) => (
                    <line
                      key={i}
                      x1="0"
                      y1="0"
                      x2={Math.cos((i * Math.PI) / 8) * 50}
                      y2={Math.sin((i * Math.PI) / 8) * 50}
                      stroke="white"
                      strokeWidth="1.5"
                      opacity="0.4"
                    />
                  ))}
                  <circle cx="0" cy="0" r="8" fill="#334155" />
                  
                  {/* Tire */}
                  <circle 
                    cx="0" 
                    cy="0" 
                    r="59" 
                    fill="none" 
                    stroke="url(#tireGradient)"
                    strokeWidth="8"
                    className="transition-all duration-300"
                    style={{
                      filter: (hoveredZone === 'tire' || hoveredZone === 'crr') ? 'drop-shadow(0 0 20px #a855f7)' : 'none',
                    }}
                  />
                </g>

                {/* Frame - More realistic road bike geometry */}
                <g className="transition-all duration-300">
                  {/* Down tube */}
                  <path
                    d="M 150 380 L 250 240"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="12"
                    strokeLinecap="round"
                    style={{
                      filter: (hoveredZone === 'frame' || hoveredZone === 'bike-type') ? 'drop-shadow(0 0 25px #f59e0b)' : 'none',
                    }}
                  />
                  
                  {/* Top tube */}
                  <path
                    d="M 250 240 L 330 200"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="10"
                    strokeLinecap="round"
                  />
                  
                  {/* Seat tube */}
                  <path
                    d="M 250 240 L 240 180"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="11"
                    strokeLinecap="round"
                  />
                  
                  {/* Seat post */}
                  <path
                    d="M 240 180 L 235 145"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  
                  {/* Chainstay */}
                  <path
                    d="M 250 240 L 150 380"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="9"
                    strokeLinecap="round"
                  />
                  
                  {/* Seatstay */}
                  <path
                    d="M 240 180 L 150 380"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  
                  {/* Head tube + fork */}
                  <path
                    d="M 330 200 L 380 380"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="10"
                    strokeLinecap="round"
                  />
                </g>

                {/* Seat */}
                <ellipse
                  cx="235"
                  cy="140"
                  rx="22"
                  ry="7"
                  fill="url(#frameGradient)"
                  className="transition-all duration-300"
                />

                {/* Handlebars */}
                <g className="transition-all duration-300">
                  <path
                    d="M 330 200 L 340 185 M 330 200 L 320 185"
                    stroke="url(#frameGradient)"
                    strokeWidth="7"
                    strokeLinecap="round"
                  />
                  {/* Drops */}
                  <path
                    d="M 340 185 Q 345 195 340 205 M 320 185 Q 315 195 320 205"
                    stroke="url(#frameGradient)"
                    strokeWidth="6"
                    strokeLinecap="round"
                    fill="none"
                  />
                </g>

                {/* Drivetrain */}
                <g className="transition-all duration-300">
                  <circle
                    cx="250"
                    cy="380"
                    r="30"
                    fill="url(#drivetrainGradient)"
                    style={{
                      filter: hoveredZone === 'drivetrain' ? 'drop-shadow(0 0 25px #eab308)' : 'none',
                    }}
                  />
                  {/* Chainring teeth */}
                  {[...Array(12)].map((_, i) => (
                    <rect
                      key={i}
                      x={250 + Math.cos((i * Math.PI) / 6) * 28 - 1}
                      y={380 + Math.sin((i * Math.PI) / 6) * 28 - 2}
                      width="2"
                      height="4"
                      fill="#64748b"
                      transform={`rotate(${i * 30} ${250 + Math.cos((i * Math.PI) / 6) * 28} ${380 + Math.sin((i * Math.PI) / 6) * 28})`}
                    />
                  ))}
                  
                  {/* Crank arm */}
                  <path
                    d="M 250 380 L 225 425"
                    stroke="url(#drivetrainGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  
                  {/* Pedal */}
                  <rect
                    x="215"
                    y="422"
                    width="25"
                    height="10"
                    rx="3"
                    fill="url(#drivetrainGradient)"
                  />
                  
                  {/* Chain */}
                  <path
                    d="M 275 370 L 175 370"
                    stroke="url(#drivetrainGradient)"
                    strokeWidth="4"
                    strokeDasharray="6,6"
                    fill="none"
                  />
                </g>

                {/* Rider - More realistic proportions */}
                <g className="transition-all duration-300">
                  {/* Torso - aggressive road position */}
                  <path
                    d="M 235 145 Q 280 130 330 190"
                    fill="none"
                    stroke="url(#bodyGradient)"
                    strokeWidth="18"
                    strokeLinecap="round"
                    style={{
                      filter: hoveredZone === 'body' ? 'drop-shadow(0 0 30px #10b981)' : 'none',
                    }}
                  />
                  
                  {/* Head - realistic size */}
                  <circle
                    cx="340"
                    cy="110"
                    r="20"
                    fill="url(#riderGradient)"
                    style={{
                      filter: hoveredZone === 'rider-weight' ? 'drop-shadow(0 0 25px #ec4899)' : 'none',
                    }}
                  />
                  
                  {/* Helmet */}
                  <path
                    d="M 325 105 Q 340 90 355 105"
                    fill="none"
                    stroke="url(#riderGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  
                  {/* Arms - on drops */}
                  <path
                    d="M 280 140 L 320 195"
                    stroke="url(#riderGradient)"
                    strokeWidth="12"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 300 135 L 340 195"
                    stroke="url(#riderGradient)"
                    strokeWidth="12"
                    strokeLinecap="round"
                  />

                  {/* Legs - realistic cycling position */}
                  <path
                    d="M 240 180 L 235 280 L 225 425"
                    stroke="url(#riderGradient)"
                    strokeWidth="15"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                  <path
                    d="M 245 190 L 255 300 L 270 360"
                    stroke="url(#riderGradient)"
                    strokeWidth="15"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                </g>

                {/* FTP Badge (top right) */}
                <g 
                  transform="translate(420, 50)"
                  className="transition-all duration-300"
                  style={{
                    filter: hoveredZone === 'ftp' ? 'drop-shadow(0 0 20px #14b8a6)' : 'none',
                  }}
                >
                  <rect
                    x="-35"
                    y="-15"
                    width="70"
                    height="30"
                    rx="8"
                    fill="url(#ftpGradient)"
                  />
                  <text
                    x="0"
                    y="5"
                    textAnchor="middle"
                    fill="white"
                    fontSize="12"
                    fontWeight="bold"
                  >
                    FTP: —
                  </text>
                </g>
              </svg>

              <style>{`
                @keyframes gentleSway {
                  0%, 100% { 
                    transform: rotate(-3deg); 
                  }
                  50% { 
                    transform: rotate(3deg); 
                  }
                }
              `}</style>

              {/* Legend */}
              <div className="absolute bottom-4 left-4 right-4 bg-white/95 backdrop-blur-sm rounded-xl p-3 border border-slate-200 shadow-lg">
                <div className="text-xs font-semibold text-slate-700 mb-2">Interactive Physics Model →</div>
                <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-pink-500"></span> Rider mass
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-500"></span> Wheels
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-amber-500"></span> Frame
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span> CdA/Aero
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-purple-500"></span> Tires/Crr
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-yellow-500"></span> Drivetrain
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* RIGHT: All Settings (3 columns) */}
          <div className="lg:col-span-3 space-y-2.5">
            <div className="text-sm font-semibold text-slate-700 mb-3 flex items-center justify-between">
              <span>Physics Model Parameters (9 total)</span>
              <span className="text-xs text-emerald-600 font-normal">All fields calibrated for precision</span>
            </div>

            {profileSettings.map((setting) => (
              <div
                key={setting.id}
                className="group relative"
                onMouseEnter={(e) => handleMouseEnter(setting.zone, e)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                <div
                  className={`
                    rounded-xl p-3 border-2 transition-all duration-300 cursor-pointer
                    ${hoveredZone === setting.zone
                      ? 'border-current shadow-lg scale-[1.01]'
                      : 'border-slate-200 hover:border-slate-300'
                    }
                  `}
                  style={{
                    borderColor: hoveredZone === setting.zone ? setting.color : undefined,
                    backgroundColor: hoveredZone === setting.zone ? `${setting.color}06` : 'white',
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-2.5 h-2.5 rounded-full transition-all duration-300"
                        style={{
                          backgroundColor: hoveredZone === setting.zone ? setting.color : '#cbd5e1',
                          boxShadow: hoveredZone === setting.zone ? `0 0 12px ${setting.color}` : 'none',
                        }}
                      />
                      <div className="flex-1">
                        <div className="text-sm font-semibold text-slate-900">{setting.label}</div>
                        <div className="text-[11px] text-slate-500 mt-0.5 leading-tight">
                          {hoveredZone === setting.zone ? setting.tooltip.impact : 'Hover to learn physics impact'}
                        </div>
                      </div>
                    </div>
                    <div className="text-sm font-bold text-slate-900">{setting.value}</div>
                  </div>
                </div>

                {/* Enhanced Tooltip */}
                {hoveredZone === setting.zone && (
                  <div
                    className="fixed z-50 w-96 pointer-events-none"
                    style={{
                      left: `${tooltipPos.x}px`,
                      top: `${tooltipPos.y}px`,
                      animation: 'tooltipSlideIn 0.2s ease-out',
                    }}
                  >
                    <div
                      className="rounded-xl border-2 bg-white/98 backdrop-blur-xl p-4 shadow-[0_25px_70px_rgba(0,0,0,0.3)]"
                      style={{ borderColor: setting.color }}
                    >
                      {/* Arrow */}
                      <div
                        className="absolute left-0 top-4 w-3 h-3 -translate-x-1/2 rotate-45 border-l-2 border-b-2"
                        style={{ 
                          borderColor: setting.color,
                          backgroundColor: 'white',
                        }}
                      />

                      <div className="flex items-center gap-2.5 mb-3">
                        <div
                          className="w-9 h-9 rounded-lg flex items-center justify-center"
                          style={{ backgroundColor: `${setting.color}12` }}
                        >
                          <div
                            className="w-3.5 h-3.5 rounded-full"
                            style={{ backgroundColor: setting.color }}
                          />
                        </div>
                        <div className="text-sm font-bold text-slate-900">{setting.tooltip.title}</div>
                      </div>

                      <p className="text-xs text-slate-700 leading-relaxed mb-3">
                        {setting.tooltip.description}
                      </p>

                      <div
                        className="text-xs font-semibold px-2.5 py-1.5 rounded-lg inline-flex items-center gap-1.5"
                        style={{
                          backgroundColor: `${setting.color}12`,
                          color: setting.color,
                        }}
                      >
                        <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" />
                        </svg>
                        {setting.tooltip.impact}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}

            <style>{`
              @keyframes tooltipSlideIn {
                from {
                  opacity: 0;
                  transform: translateX(-15px);
                }
                to {
                  opacity: 1;
                  transform: translateX(0);
                }
              }
            `}</style>

            {/* Save CTA */}
            <div className="mt-6 pt-4 border-t border-slate-200">
              <button className="w-full rounded-xl bg-gradient-to-r from-emerald-500 to-emerald-600 px-6 py-3.5 text-sm font-bold text-white shadow-lg hover:shadow-xl hover:scale-[1.01] transition-all duration-200 flex items-center justify-center gap-2">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                Save Profile Settings
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Interactive3DCyclistProfile;

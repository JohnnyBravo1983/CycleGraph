// frontend/src/components/Profile/ProfileView.tsx
import React from "react";
import { Link } from "react-router-dom";
import { getProfile } from "../../api/profile";

type ProfileData = {
  rider_weight_kg?: number | null;
  bike_weight_kg?: number | null;
  cda?: number | null;
  crr?: number | null;
  crank_efficiency?: number | null;
  bike_type?: string | null;
  tire_width_mm?: number | null;
  tire_quality?: string | null;
  ftp_watts?: number | null;
  profile_version?: number | null;
};

type HoverZone =
  | "rider-weight"
  | "wheel"
  | "frame"
  | "body"
  | "drivetrain"
  | "tire"
  | "crr"
  | "bike-type"
  | "ftp"
  | null;

type TechDeepDive = {
  formula: string;
  variables: string[];
  impact: string[];
  edgeCases: string[];
  accuracyImpact: string;
  futureFeature?: string;
  calculation?: string;
  assumption?: string;
};

type Bullseye = {
  simple: string;
  variance: string;
  whyEditable?: string;
  whyLocked?: string;
};

type ProfileSetting = {
  id: string;
  label: string;
  value: string;
  zone: Exclude<HoverZone, null>;
  color: string;
  editable: boolean;
  bullseye: Bullseye;
  techDeepDive: TechDeepDive;
};

// Interactive 3D Cyclist Component (integrated)
const Interactive3DCyclistProfile: React.FC<{ profile: ProfileData | null }> = ({
  profile,
}) => {
  const [hoveredZone, setHoveredZone] = React.useState<HoverZone>(null);
  const [tooltipPos, setTooltipPos] = React.useState({ x: 0, y: 0 }); // kept (future use)
  const [techExpanded, setTechExpanded] = React.useState(false);

  // Format values from backend data
  const formatValue = (key: keyof ProfileData, suffix = ""): string => {
    const val = profile?.[key];
    if (val === null || val === undefined) return "—";
    if (typeof val === "number") return `${val}${suffix}`;
    return String(val);
  };

  // All profile settings with three-tier info
  const profileSettings: ProfileSetting[] = [
    {
      id: "rider-weight",
      label: "Rider weight",
      value: formatValue("rider_weight_kg", " kg"),
      zone: "rider-weight",
      color: "#ec4899",
      editable: true,
      bullseye: {
        simple:
          "Your body weight is like the base load in physics. Heavier = more energy needed to fight gravity on climbs. Think of it as carrying a backpack uphill - every extra kg matters!",
        whyEditable:
          "This varies dramatically between riders (50-100kg+) and is THE biggest factor in climbing power. We need your exact weight for accurate modeling.",
        variance: "High - 30kg variance typical (±15% power on 8% climb)",
      },
      techDeepDive: {
        formula: "Fg = m × g × sin(θ)",
        variables: [
          "m = total mass (rider + bike + gear) in kg",
          "g = gravitational constant (9.81 m/s²)",
          "θ = gradient angle in degrees",
        ],
        impact: [
          "5% gradient, 75kg rider: 368W to maintain 25 km/h",
          "5% gradient, 85kg rider: 417W to maintain 25 km/h",
          "Difference: 49W (13% more power needed)",
        ],
        edgeCases: [
          "Weight distribution matters: center of gravity affects handling",
          "Includes clothing, bottles, gear (add ~2kg)",
          "Changes throughout ride (water consumption)",
        ],
        accuracyImpact: "±1kg error = ±1-2% power error on climbs",
      },
    },
    {
      id: "bike-weight",
      label: "Bike weight",
      value: formatValue("bike_weight_kg", " kg"),
      zone: "frame",
      color: "#f59e0b",
      editable: true,
      bullseye: {
        simple:
          "Bike weight adds to total system mass. A lighter bike helps on climbs (less gravity to fight) but makes almost zero difference on flats. Think race bike (6.8kg) vs touring bike (12kg).",
        whyEditable:
          "Varies widely: carbon race bikes (6.8kg) to steel tourers (12kg+). Combined with your weight, determines total climbing resistance.",
        variance: "Moderate - 5kg variance typical (±2-3% power on climbs)",
      },
      techDeepDive: {
        formula:
          "Same gravitational formula as rider weight: Fg = (m_rider + m_bike) × g × sin(θ)",
        variables: [
          "m_bike = frame + wheels + components",
          "Typical: Road race (6.8-8kg), Endurance (8-9kg), Gravel (9-11kg)",
        ],
        impact: [
          "8% gradient, 1kg bike weight difference = ~3W at 20 km/h",
          "Flat terrain: <1W difference (negligible)",
          "Descents: heavier bike = slight advantage (momentum)",
        ],
        edgeCases: [
          "UCI minimum: 6.8kg for racing",
          "Wheel weight matters more (rotational inertia)",
          "Accessories: bottle cages, computer, lights add weight",
        ],
        accuracyImpact: "±0.5kg error = ±0.5-1% power error on climbs",
      },
    },
    {
      id: "tire-width",
      label: "Tire width",
      value: formatValue("tire_width_mm", "mm"),
      zone: "tire",
      color: "#a855f7",
      editable: true,
      bullseye: {
        simple:
          "Counter-intuitive: wider tires (28-32mm) actually roll FASTER than skinny tires (23-25mm) at same pressure! Modern science debunked the old 'skinny = fast' myth. Wider = better comfort + grip + speed.",
        whyEditable:
          "Tire width directly affects rolling resistance (Crr). 23mm vs 32mm can be 20% difference in Crr. We need your actual tire size.",
        variance: "High - affects Crr calculation significantly",
      },
      techDeepDive: {
        formula: "Frr = Crr × N (where N = normal force = m×g on flats)",
        variables: [
          "Crr depends heavily on tire width:",
          "23mm @ 120psi: ~0.0050 (old style)",
          "28mm @ 80psi: ~0.0035 (modern optimal)",
          "32mm @ 60psi: ~0.0038 (gravel)",
        ],
        impact: [
          "75kg rider, 25 km/h on flats:",
          "23mm (Crr 0.0050): ~8W rolling resistance",
          "28mm (Crr 0.0035): ~5.6W rolling resistance",
          "Savings: 2.4W (30% reduction!)",
        ],
        edgeCases: [
          "Lower pressure with wider tires = same Crr",
          "Comfort benefit: wider absorbs vibrations",
          "Grip: wider = more contact patch",
          "Aero: wider CAN be slightly worse (marginal)",
        ],
        accuracyImpact: "Wrong tire width = ±15-20% Crr error = ±1-2W error",
      },
    },
    {
      id: "tire-quality",
      label: "Tire quality",
      value: formatValue("tire_quality"),
      zone: "tire",
      color: "#a855f7",
      editable: true,
      bullseye: {
        simple:
          "Tire rubber compound matters! Premium tires (GP5000, Corsa) have special rubber that bends/recovers faster = less energy lost. Budget tires can cost you 10-20W at speed. It's like running shoes - cheap ones make you work harder!",
        whyEditable:
          "Tire quality affects Crr dramatically. Premium (Crr ~0.0030) vs Budget (Crr ~0.0055) = 45% difference! We use your tire quality to adjust Crr calculation.",
        variance: "Very High - biggest Crr factor after tire width",
      },
      techDeepDive: {
        formula: "Crr = f(tire_compound, tire_construction, tread_pattern)",
        variables: [
          "Premium (GP5000, Corsa, Pro One): Crr ~0.0030-0.0035",
          "Mid-range (Rubino, Lithion): Crr ~0.0040-0.0045",
          "Budget (generic): Crr ~0.0050-0.0055",
          "Difference: up to 45% between best and worst!",
        ],
        impact: [
          "75kg rider, 35 km/h on flats:",
          "Premium (0.0032): 7.4W rolling resistance",
          "Budget (0.0052): 12.0W rolling resistance",
          "Cost: 4.6W extra (62% more power!)",
        ],
        edgeCases: [
          "Tire age matters: rubber hardens over time (+10% Crr after 3-4 years)",
          "Temperature: cold tires = higher Crr",
          "Tread pattern: slick < light tread < knobby",
          "Tubeless can be 5-10% lower Crr than clincher",
        ],
        accuracyImpact: "Wrong tire quality = ±20% Crr error = ±2-5W error at speed",
      },
    },
    {
      id: "wheel",
      label: "Wheel dimension",
      value: "700c",
      zone: "wheel",
      color: "#ef4444",
      editable: false,
      bullseye: {
        simple:
          "700c is the standard road bike wheel size (622mm rim diameter). We default to this because 95% of road bikes use it. Different wheel sizes change how Crr and speed are calculated.",
        whyLocked:
          "99% of road bikes are 700c. The few exceptions (650b, 26\", 29\") are obvious (gravel/MTB). Asking everyone is unnecessary complexity. Our 700c default is accurate for the vast majority.",
        variance: "Very Low - standard across road cycling",
      },
      techDeepDive: {
        formula: "v = (rpm × π × d) / 60 (where d = wheel diameter)",
        variables: [
          "700c = 622mm rim + ~27mm tire = ~676mm effective diameter",
          "650b = 584mm rim + tire ≈ 640mm effective",
          "Affects: speed calculation, Crr (smaller = higher Crr)",
        ],
        impact: [
          "700c vs 650b at same cadence: ~5% speed difference",
          "Crr penalty for smaller wheels: ~3-5%",
          "Power impact: marginal (<2W at normal speeds)",
        ],
        edgeCases: [
          "Gravel bikes: may use 650b (but often 700c)",
          "Small frames: sometimes 650c",
          "If you have non-700c, your bike is unusual (you'd know!)",
        ],
        accuracyImpact: "If actually non-700c and we assume 700c: ~2-3% speed error",
        futureFeature: "Advanced mode will allow wheel size customization",
      },
    },
    {
      id: "cda",
      label: "CdA (drag area)",
      value: formatValue("cda", " m²"),
      zone: "body",
      color: "#10b981",
      editable: false,
      bullseye: {
        simple:
          "CdA is your 'air parachute' - how much wind you catch. Lower = slice through air easier. Road position (~0.300) vs TT position (~0.200) = 33% less wind resistance! This is THE biggest factor at high speeds.",
        whyLocked:
          "CdA is VERY hard to measure accurately (requires wind tunnel or fancy sensors). Most riders in road position are 0.280-0.320. Our 0.300 default is the sweet spot for typical road riding. Customizing would require expensive testing.",
        variance: "Moderate - but difficult to measure without wind tunnel",
      },
      techDeepDive: {
        formula: "Fd = ½ρv²ACd (power to overcome drag: Pd = Fd × v)",
        variables: [
          "ρ = air density (1.225 kg/m³ at sea level, 15°C)",
          "v = velocity (m/s)",
          "A = frontal area (m²)",
          "Cd = drag coefficient (~0.9 for cyclist)",
          "CdA = combined metric (m²)",
        ],
        impact: [
          "Impact scales with velocity CUBED (v³)!",
          "30 km/h: 0.300 CdA = 60W, 0.270 CdA = 54W (6W saved)",
          "40 km/h: 0.300 CdA = 142W, 0.270 CdA = 128W (14W saved)",
          "50 km/h: 0.300 CdA = 278W, 0.270 CdA = 250W (28W saved!)",
        ],
        edgeCases: [
          "Position matters: hoods (0.300), drops (0.270), TT bars (0.200)",
          "Clothing: tight kit vs loose = ~5% CdA difference",
          "Helmet: aero helmet vs standard = ~2-3% CdA reduction",
          "Crosswinds: can increase effective CdA by 10-20%",
          "Drafting: reduces CdA by 30-40% when close behind",
        ],
        accuracyImpact: "±0.01 CdA error = ±2-7W error (depends on speed)",
        futureFeature: "Pro mode: CdA estimation from multiple rides (AI-powered)",
      },
    },
    {
      id: "crr",
      label: "Crr (rolling resistance)",
      value: formatValue("crr"),
      zone: "crr",
      color: "#8b5cf6",
      editable: false,
      bullseye: {
        simple:
          "Crr measures how much energy is lost as your tire deforms and un-deforms as it rolls. Lower Crr = less energy wasted. We calculate your Crr based on the tire width and quality you specified - no need to enter it manually!",
        whyLocked:
          "Crr is derived from your tire inputs (width + quality). Since you already told us your tire specs, we calculate the appropriate Crr scientifically. Manual entry would be redundant and error-prone.",
        variance: "Covered by tire width + tire quality inputs",
      },
      techDeepDive: {
        formula: "Frr = Crr × N (where N = normal force = mg on flats)",
        variables: [
          "Crr = coefficient of rolling resistance (dimensionless)",
          "Depends on: tire width, tire quality, pressure, road surface",
          "Modern 28mm premium: ~0.0035-0.0040",
          "23mm budget: ~0.0050-0.0055",
        ],
        impact: [
          "75kg total mass on flats:",
          "Crr 0.0035: 2.57N resistance force",
          "Crr 0.0050: 3.68N resistance force",
          "At 30 km/h: 6.4W vs 9.2W (2.8W difference)",
        ],
        edgeCases: [
          "Road surface: smooth asphalt (×1.0), rough road (×1.2), gravel (×1.5)",
          "Temperature: cold tires = +5-10% Crr",
          "Tire pressure: under-inflated = significantly higher Crr",
          "Tire age: old hard rubber = +10-15% Crr",
        ],
        accuracyImpact: "Crr auto-calculated from tire inputs (±5% typical accuracy)",
        calculation:
          "We use your tire_width + tire_quality to lookup scientific Crr from research database",
      },
    },
    {
      id: "bike-type",
      label: "Bike type",
      value: formatValue("bike_type"),
      zone: "bike-type",
      color: "#3b82f6",
      editable: false,
      bullseye: {
        simple:
          "Bike type sets baseline assumptions for geometry and riding position. Road bikes = drop bars, aggressive position. Gravel = more upright, wider tires. TT bikes = super aero position. We use this to set smart defaults.",
        whyLocked:
          "Bike type is a 'meta-parameter' that helps set other defaults (typical CdA, typical Crr, typical geometry). Since you specified your actual tire specs, and we assume road-standard geometry, asking bike type adds little precision for most users.",
        variance: "Low - mainly affects default CdA assumptions",
      },
      techDeepDive: {
        formula: "N/A - this is a categorical parameter that sets defaults",
        variables: [
          "Road: CdA ~0.300, Crr ~0.0040, aggressive position",
          "Gravel: CdA ~0.320, Crr ~0.0045, upright position, wider tires",
          "TT/Triathlon: CdA ~0.200, Crr ~0.0035, aero bars, disc wheels",
          "Mountain: CdA ~0.350, Crr ~0.0055+, upright, knobby tires",
        ],
        impact: [
          "Mainly affects CdA default if user hasn't customized",
          "Also hints at likely tire types (road = slick, gravel = file tread)",
          "Power impact: mostly captured in CdA and tire parameters",
        ],
        edgeCases: [
          "Many riders have multiple bikes (road + gravel + TT)",
          "Bike type matters less once tire specs and position are known",
          "Hybrid setups: road bike with gravel tires, etc.",
        ],
        accuracyImpact: "Minimal if tire and position (CdA) are already specified",
        futureFeature: "Multi-bike profiles for users with different setups",
      },
    },
    {
      id: "drivetrain",
      label: "Crank efficiency",
      value:
        profile?.crank_efficiency != null
          ? `${Math.round(profile.crank_efficiency * 100)}%`
          : "—",
      zone: "drivetrain",
      color: "#eab308",
      editable: false,
      bullseye: {
        simple:
          "Not all your pedaling power reaches the wheel - some is lost to friction in the chain, cassette, and pulleys. Clean, well-lubed drivetrains are ~96-98% efficient. Dirty, worn chains drop to ~93-95%. We assume proper maintenance.",
        whyLocked:
          "Drivetrain efficiency varies little with good maintenance (96-98%). Measuring it requires lab equipment. Our 96% default assumes you maintain your bike properly (which we assume for road cyclists). The accuracy gain from customization is <1W.",
        variance: "Low - 93-98% range for maintained bikes",
      },
      techDeepDive: {
        formula: "P_wheel = P_crank × η_drivetrain",
        variables: [
          "η = efficiency (dimensionless, 0-1)",
          "Clean, lubed, new: η = 0.98 (2% loss)",
          "Normal maintenance: η = 0.96 (4% loss)",
          "Dirty, worn: η = 0.93 (7% loss)",
          "Very worn, dry: η = 0.90 (10% loss)",
        ],
        impact: [
          "250W crank power:",
          "98% efficient: 245W to wheel (5W lost)",
          "96% efficient: 240W to wheel (10W lost)",
          "93% efficient: 232.5W to wheel (17.5W lost)",
          "Difference between best/worst: 12.5W",
        ],
        edgeCases: [
          "Chain line: cross-chaining reduces efficiency ~1-2%",
          "Jockey wheel bearings: worn = extra friction",
          "Chain length: too long = more friction",
          "Dirt accumulation: exponential efficiency loss",
          "Lube type: wet lube in dry conditions = attracts dirt",
        ],
        accuracyImpact: "±2% efficiency error = ±5W error at 250W output",
        assumption: "We assume proper maintenance (clean, lubed, <2000km on chain)",
      },
    },
    {
      id: "ftp",
      label: "FTP",
      value: profile?.ftp_watts ? `${profile.ftp_watts} W` : "Not set",
      zone: "ftp",
      color: "#14b8a6",
      editable: false,
      bullseye: {
        simple:
          "FTP (Functional Threshold Power) is the maximum power you can sustain for about an hour. It's your fitness baseline - we calculate this automatically from your ride data! No painful FTP test needed. We track how it changes over time.",
        whyLocked:
          "FTP is calculated, not input! We analyze your rides using physics-based power modeling to determine your FTP. This is one of our core features - automatic FTP tracking without field tests or power meters.",
        variance: "N/A - this is an output, not an input",
      },
      techDeepDive: {
        formula: "FTP calculated from critical power curve modeling across multiple rides",
        variables: [
          "Uses 20min, 30min, 60min power efforts from rides",
          "Applies physiology models: CP (critical power) and W' (anaerobic capacity)",
          "Accounts for fatigue, freshness, training load",
          "Typical: 150-400W for recreational to elite cyclists",
        ],
        impact: [
          "FTP is used for:",
          "• Training zone calculations (Z1-Z7)",
          "• Fitness tracking over time",
          "• Power-to-weight ratio (W/kg)",
          "• Performance predictions (race pacing)",
          "Not used in power calculation (it's an output!)",
        ],
        edgeCases: [
          "Requires 50+ rides for accurate FTP calculation",
          "FTP changes with training (track monthly progress)",
          "Altitude affects FTP: -1% per 1000ft above sea level",
          "Heat affects FTP: -2-5% in hot conditions",
        ],
        accuracyImpact: "FTP accuracy depends on ride data quality and quantity",
        calculation:
          "Automated using physics-modeled power from all your rides",
      },
    },
  ];

  const handleMouseEnter = (zone: HoverZone, e: React.MouseEvent) => {
    setHoveredZone(zone);
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPos({ x: rect.right + 20, y: rect.top });
  };

  const hoveredSetting = profileSettings.find((s) => s.zone === hoveredZone);

  return (
    <div className="w-full">
      <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-6 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-slate-200">
        {/* Header with summary */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xl font-bold text-slate-900">Profile Settings</h2>
            {profile?.profile_version != null && (
              <div className="text-xs font-semibold text-slate-700 bg-slate-100 px-3 py-1.5 rounded-full">
                Profile v{profile.profile_version}
              </div>
            )}
          </div>
          <p className="text-sm text-slate-600 mb-3">
            Fine-tune your physics model for{" "}
            <span className="font-semibold text-emerald-600">
              ~3-5% accuracy
            </span>
            .
            <span className="font-semibold text-blue-600">
              {" "}
              Hover over any setting to learn how it affects power calculations.
            </span>
          </p>

          {/* Parameter summary */}
          <div className="flex items-center gap-4 text-xs">
            <div className="inline-flex items-center gap-1.5 bg-emerald-50 border border-emerald-200 rounded-lg px-2.5 py-1.5">
              <span className="font-bold text-emerald-700">✏️ 4 Customizable</span>
              <span className="text-emerald-600">→ Highest impact on accuracy</span>
            </div>
            <div className="inline-flex items-center gap-1.5 bg-blue-50 border border-blue-200 rounded-lg px-2.5 py-1.5">
              <span className="font-bold text-blue-700">🔒 5 Optimized</span>
              <span className="text-blue-600">→ Smart defaults for road cycling</span>
            </div>
          </div>
        </div>

        {/* Main Grid: Cyclist + Settings */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* LEFT: Realistic Cyclist Silhouette (2 columns) */}
          <div className="lg:col-span-2">
            <div className="aspect-square bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl p-6 pb-20 relative overflow-hidden">
              {/* Subtle grid */}
              <div
                className="absolute inset-0 opacity-[0.03]"
                style={{
                  backgroundImage: `
                    linear-gradient(to right, #94a3b8 1px, transparent 1px),
                    linear-gradient(to bottom, #94a3b8 1px, transparent 1px)
                  `,
                  backgroundSize: "20px 20px",
                }}
              />

              {/* Cyclist SVG */}
              <svg
                viewBox="0 0 500 500"
                className="w-full h-full"
                style={{
                  filter: "drop-shadow(0 10px 30px rgba(0,0,0,0.15))",
                  animation: "gentleSway 4s ease-in-out infinite",
                }}
              >
                <defs>
                  <linearGradient id="riderGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop
                      offset="0%"
                      stopColor={hoveredZone === "rider-weight" ? "#ec4899" : "#64748b"}
                    />
                    <stop
                      offset="100%"
                      stopColor={hoveredZone === "rider-weight" ? "#db2777" : "#475569"}
                    />
                  </linearGradient>

                  <linearGradient id="bodyGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop
                      offset="0%"
                      stopColor={hoveredZone === "body" ? "#10b981" : "#3b82f6"}
                    />
                    <stop
                      offset="100%"
                      stopColor={hoveredZone === "body" ? "#059669" : "#2563eb"}
                    />
                  </linearGradient>

                  <linearGradient id="frameGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop
                      offset="0%"
                      stopColor={
                        hoveredZone === "frame"
                          ? "#f59e0b"
                          : hoveredZone === "bike-type"
                            ? "#3b82f6"
                            : "#334155"
                      }
                    />
                    <stop
                      offset="100%"
                      stopColor={
                        hoveredZone === "frame"
                          ? "#d97706"
                          : hoveredZone === "bike-type"
                            ? "#2563eb"
                            : "#1e293b"
                      }
                    />
                  </linearGradient>

                  <radialGradient id="wheelGradient">
                    <stop offset="0%" stopColor={hoveredZone === "wheel" ? "#ef4444" : "#1e40af"} />
                    <stop offset="100%" stopColor={hoveredZone === "wheel" ? "#dc2626" : "#1e3a8a"} />
                  </radialGradient>

                  <linearGradient id="tireGradient">
                    <stop
                      offset="0%"
                      stopColor={
                        hoveredZone === "tire"
                          ? "#a855f7"
                          : hoveredZone === "crr"
                            ? "#8b5cf6"
                            : "#1f2937"
                      }
                    />
                    <stop
                      offset="100%"
                      stopColor={
                        hoveredZone === "tire"
                          ? "#9333ea"
                          : hoveredZone === "crr"
                            ? "#7c3aed"
                            : "#111827"
                      }
                    />
                  </linearGradient>

                  <linearGradient id="drivetrainGradient">
                    <stop
                      offset="0%"
                      stopColor={hoveredZone === "drivetrain" ? "#eab308" : "#64748b"}
                    />
                    <stop
                      offset="100%"
                      stopColor={hoveredZone === "drivetrain" ? "#ca8a04" : "#475569"}
                    />
                  </linearGradient>

                  <linearGradient id="ftpGradient">
                    <stop
                      offset="0%"
                      stopColor={hoveredZone === "ftp" ? "#14b8a6" : "#94a3b8"}
                    />
                    <stop
                      offset="100%"
                      stopColor={hoveredZone === "ftp" ? "#0d9488" : "#64748b"}
                    />
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
                      filter: hoveredZone === "wheel" ? "drop-shadow(0 0 25px #ef4444)" : "none",
                    }}
                  />
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
                  <circle
                    cx="0"
                    cy="0"
                    r="59"
                    fill="none"
                    stroke="url(#tireGradient)"
                    strokeWidth="8"
                    className="transition-all duration-300"
                    style={{
                      filter:
                        hoveredZone === "tire" || hoveredZone === "crr"
                          ? "drop-shadow(0 0 20px #a855f7)"
                          : "none",
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
                      filter: hoveredZone === "wheel" ? "drop-shadow(0 0 25px #ef4444)" : "none",
                    }}
                  />
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
                  <circle
                    cx="0"
                    cy="0"
                    r="59"
                    fill="none"
                    stroke="url(#tireGradient)"
                    strokeWidth="8"
                    className="transition-all duration-300"
                    style={{
                      filter:
                        hoveredZone === "tire" || hoveredZone === "crr"
                          ? "drop-shadow(0 0 20px #a855f7)"
                          : "none",
                    }}
                  />
                </g>

                {/* Frame */}
                <g className="transition-all duration-300">
                  <path
                    d="M 150 380 L 250 240"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="12"
                    strokeLinecap="round"
                    style={{
                      filter:
                        hoveredZone === "frame" || hoveredZone === "bike-type"
                          ? "drop-shadow(0 0 25px #f59e0b)"
                          : "none",
                    }}
                  />
                  <path
                    d="M 250 240 L 330 200"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="10"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 250 240 L 240 180"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="11"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 240 180 L 235 145"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 250 240 L 150 380"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="9"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 240 180 L 150 380"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 330 200 L 380 380"
                    fill="none"
                    stroke="url(#frameGradient)"
                    strokeWidth="10"
                    strokeLinecap="round"
                  />
                </g>

                <ellipse
                  cx="235"
                  cy="140"
                  rx="22"
                  ry="7"
                  fill="url(#frameGradient)"
                  className="transition-all duration-300"
                />

                <g className="transition-all duration-300">
                  <path
                    d="M 330 200 L 340 185 M 330 200 L 320 185"
                    stroke="url(#frameGradient)"
                    strokeWidth="7"
                    strokeLinecap="round"
                  />
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
                      filter:
                        hoveredZone === "drivetrain"
                          ? "drop-shadow(0 0 25px #eab308)"
                          : "none",
                    }}
                  />
                  {[...Array(12)].map((_, i) => (
                    <rect
                      key={i}
                      x={250 + Math.cos((i * Math.PI) / 6) * 28 - 1}
                      y={380 + Math.sin((i * Math.PI) / 6) * 28 - 2}
                      width="2"
                      height="4"
                      fill="#64748b"
                      transform={`rotate(${i * 30} ${
                        250 + Math.cos((i * Math.PI) / 6) * 28
                      } ${380 + Math.sin((i * Math.PI) / 6) * 28})`}
                    />
                  ))}
                  <path
                    d="M 250 380 L 225 425"
                    stroke="url(#drivetrainGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
                  <rect
                    x="215"
                    y="422"
                    width="25"
                    height="10"
                    rx="3"
                    fill="url(#drivetrainGradient)"
                  />
                  <path
                    d="M 275 370 L 175 370"
                    stroke="url(#drivetrainGradient)"
                    strokeWidth="4"
                    strokeDasharray="6,6"
                    fill="none"
                  />
                </g>

                {/* Rider */}
                <g className="transition-all duration-300">
                  <path
                    d="M 235 145 Q 280 130 330 190"
                    fill="none"
                    stroke="url(#bodyGradient)"
                    strokeWidth="18"
                    strokeLinecap="round"
                    style={{
                      filter:
                        hoveredZone === "body"
                          ? "drop-shadow(0 0 30px #10b981)"
                          : "none",
                    }}
                  />
                  <circle
                    cx="340"
                    cy="110"
                    r="20"
                    fill="url(#riderGradient)"
                    style={{
                      filter:
                        hoveredZone === "rider-weight"
                          ? "drop-shadow(0 0 25px #ec4899)"
                          : "none",
                    }}
                  />
                  <path
                    d="M 325 105 Q 340 90 355 105"
                    fill="none"
                    stroke="url(#riderGradient)"
                    strokeWidth="8"
                    strokeLinecap="round"
                  />
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

                {/* FTP Badge */}
                <g
                  transform="translate(420, 50)"
                  className="transition-all duration-300"
                  style={{
                    filter: hoveredZone === "ftp" ? "drop-shadow(0 0 20px #14b8a6)" : "none",
                  }}
                >
                  <rect x="-50" y="-20" width="100" height="40" rx="10" fill="url(#ftpGradient)" />
                  <text
                    x="0"
                    y="7"
                    textAnchor="middle"
                    fill="white"
                    fontSize="16"
                    fontWeight="bold"
                  >
                    {profile?.ftp_watts ? `${profile.ftp_watts}W` : "FTP: —"}
                  </text>
                </g>
              </svg>

              <style>{`
                @keyframes gentleSway {
                  0%, 100% { transform: rotate(-3deg); }
                  50% { transform: rotate(3deg); }
                }
              `}</style>
            </div>

            {/* Legend - BELOW cyclist */}
            <div className="mt-3 bg-white/95 backdrop-blur-sm rounded-xl p-2.5 border border-slate-200 shadow-lg">
              <div className="text-[10px] font-semibold text-slate-700 mb-1.5">
                Interactive Physics Model →
              </div>
              <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[9px]">
                <span className="inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-pink-500"></span> Rider mass
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span> Wheels
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span> Frame
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> CdA/Aero
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-purple-500"></span> Tires/Crr
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-500"></span> Drivetrain
                </span>
              </div>
            </div>
          </div>

          {/* RIGHT: All Settings (3 columns) */}
          <div className="lg:col-span-3 space-y-2">
            <div className="text-sm font-semibold text-slate-700 mb-2 flex items-center justify-between">
              <span>Physics Model Parameters</span>
              <span className="text-xs text-slate-500 font-normal">Hover for details</span>
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
                    ${
                      hoveredZone === setting.zone
                        ? "border-current shadow-lg scale-[1.01]"
                        : "border-slate-200 hover:border-slate-300"
                    }
                  `}
                  style={{
                    borderColor: hoveredZone === setting.zone ? setting.color : undefined,
                    backgroundColor: hoveredZone === setting.zone ? `${setting.color}06` : "white",
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div
                        className="w-2.5 h-2.5 rounded-full transition-all duration-300"
                        style={{
                          backgroundColor: hoveredZone === setting.zone ? setting.color : "#cbd5e1",
                          boxShadow:
                            hoveredZone === setting.zone ? `0 0 12px ${setting.color}` : "none",
                        }}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <div className="text-sm font-semibold text-slate-900">{setting.label}</div>
                          {setting.editable ? (
                            <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
                              ✏️ EDITABLE
                            </span>
                          ) : (
                            <span className="text-[10px] font-bold text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded">
                              🔒 OPTIMIZED
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5 leading-tight">
                          {hoveredZone === setting.zone ? setting.bullseye.variance : "Hover to learn more"}
                        </div>
                      </div>
                    </div>
                    <div className="text-sm font-bold text-slate-900">{setting.value}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* BULLSEYE + TECH DEEP DIVE PANEL - Below everything */}
        {hoveredSetting && (
          <div
            className="mt-6 rounded-2xl border-2 bg-white shadow-lg overflow-hidden"
            style={{ borderColor: hoveredSetting.color }}
          >
            {/* Bullseye Section - Always visible */}
            <div className="p-6" style={{ backgroundColor: `${hoveredSetting.color}05` }}>
              <div className="flex items-start gap-3 mb-4">
                <div
                  className="flex-none w-10 h-10 rounded-xl flex items-center justify-center text-2xl"
                  style={{ backgroundColor: `${hoveredSetting.color}20` }}
                >
                  🎯
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-bold text-slate-900 mb-1">
                    {hoveredSetting.label}
                    {hoveredSetting.editable ? (
                      <span className="ml-2 text-sm font-bold text-emerald-700">✏️ Customizable</span>
                    ) : (
                      <span className="ml-2 text-sm font-bold text-blue-700">🔒 Optimized Default</span>
                    )}
                  </h3>
                  <p className="text-sm text-slate-700 leading-relaxed">{hoveredSetting.bullseye.simple}</p>
                </div>
              </div>

              {/* Why editable/locked */}
              <div
                className="rounded-xl bg-white border-2 p-4"
                style={{ borderColor: `${hoveredSetting.color}40` }}
              >
                <div className="flex items-start gap-2">
                  <div className="flex-none text-lg">💡</div>
                  <div>
                    <div className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">
                      {hoveredSetting.editable ? "Why You Customize This" : "Why This is Locked"}
                    </div>
                    <p className="text-sm text-slate-700 leading-relaxed">
                      {hoveredSetting.editable
                        ? hoveredSetting.bullseye.whyEditable
                        : hoveredSetting.bullseye.whyLocked}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Tech Deep Dive - Collapsible */}
            <div className="border-t-2" style={{ borderColor: hoveredSetting.color }}>
              <button
                onClick={() => setTechExpanded(!techExpanded)}
                className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
                type="button"
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">🔬</span>
                  <span className="text-sm font-bold text-slate-900">Technical Deep Dive</span>
                  <span className="text-xs text-slate-500">(for nerds)</span>
                </div>
                <svg
                  className={`w-5 h-5 text-slate-600 transition-transform ${
                    techExpanded ? "rotate-180" : ""
                  }`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {techExpanded && (
                <div className="px-6 pb-6 space-y-4 bg-slate-50">
                  {/* Formula */}
                  <div className="rounded-lg bg-slate-900 p-4 font-mono">
                    <div className="text-xs font-bold text-emerald-400 mb-2">FORMULA:</div>
                    <div className="text-sm text-white">{hoveredSetting.techDeepDive.formula}</div>
                  </div>

                  {/* Variables */}
                  <div>
                    <div className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-2">
                      Variables:
                    </div>
                    <div className="space-y-1">
                      {hoveredSetting.techDeepDive.variables.map((v, idx) => (
                        <div
                          key={idx}
                          className="text-sm text-slate-700 font-mono bg-white rounded px-3 py-1.5 border border-slate-200"
                        >
                          {v}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Impact */}
                  <div>
                    <div className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-2">
                      Real-World Impact:
                    </div>
                    <div className="space-y-1">
                      {hoveredSetting.techDeepDive.impact.map((imp, idx) => (
                        <div
                          key={idx}
                          className="text-sm text-slate-700 bg-white rounded px-3 py-1.5 border border-slate-200"
                        >
                          {imp}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Edge Cases */}
                  <div>
                    <div className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-2">
                      Edge Cases:
                    </div>
                    <div className="space-y-1">
                      {hoveredSetting.techDeepDive.edgeCases.map((edge, idx) => (
                        <div
                          key={idx}
                          className="text-sm text-slate-700 bg-amber-50 rounded px-3 py-1.5 border border-amber-200"
                        >
                          ⚠️ {edge}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Accuracy Impact */}
                  <div
                    className="rounded-lg p-4"
                    style={{
                      backgroundColor: `${hoveredSetting.color}15`,
                      borderLeft: `4px solid ${hoveredSetting.color}`,
                    }}
                  >
                    <div className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">
                      Accuracy Impact:
                    </div>
                    <div className="text-sm font-semibold text-slate-900">
                      {hoveredSetting.techDeepDive.accuracyImpact}
                    </div>
                  </div>

                  {/* Future Feature / Calculation / Assumption (if exists) */}
                  {hoveredSetting.techDeepDive.futureFeature && (
                    <div className="rounded-lg bg-blue-50 border border-blue-200 p-3">
                      <div className="flex items-start gap-2">
                        <span className="text-lg">🚀</span>
                        <div>
                          <div className="text-xs font-bold text-blue-700 mb-1">COMING SOON:</div>
                          <div className="text-sm text-blue-900">{hoveredSetting.techDeepDive.futureFeature}</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {hoveredSetting.techDeepDive.calculation && (
                    <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
                      <div className="flex items-start gap-2">
                        <span className="text-lg">⚙️</span>
                        <div>
                          <div className="text-xs font-bold text-emerald-700 mb-1">HOW WE CALCULATE:</div>
                          <div className="text-sm text-emerald-900">{hoveredSetting.techDeepDive.calculation}</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {hoveredSetting.techDeepDive.assumption && (
                    <div className="rounded-lg bg-purple-50 border border-purple-200 p-3">
                      <div className="flex items-start gap-2">
                        <span className="text-lg">📋</span>
                        <div>
                          <div className="text-xs font-bold text-purple-700 mb-1">ASSUMPTION:</div>
                          <div className="text-sm text-purple-900">{hoveredSetting.techDeepDive.assumption}</div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Main ProfileView Component
export default function ProfileView() {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [profile, setProfile] = React.useState<ProfileData | null>(null);

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getProfile();
        if (!alive) return;
        setProfile(data as any);
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message || "Kunne ikke hente profilen.");
      } finally {
        if (alive) setLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40">
        <div className="text-sm text-slate-600">Laster profil …</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40">
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="rounded-2xl bg-white/98 backdrop-blur-xl p-5 shadow-[0_20px_60px_rgba(0,0,0,0.25)] border border-white/40">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
          <div className="text-sm font-semibold text-slate-900">Ingen profil ennå</div>
          <div className="mt-1 text-sm text-slate-600">
            Fullfør onboarding for å sette opp profilen din.
          </div>
          <div className="mt-4">
            <Link
              to="/onboarding"
              className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 transition"
            >
              Gå til onboarding
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return <Interactive3DCyclistProfile profile={profile} />;
}

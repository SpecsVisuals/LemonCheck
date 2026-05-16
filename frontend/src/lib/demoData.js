/**
 * demoData.js
 *
 * Static demo DealReport — served client-side for ?demo=true mode.
 *
 * Why this exists instead of calling GET /demo:
 *   The Railway backend (free tier) sleeps after inactivity and takes
 *   10-30 seconds to cold-start. For the demo path — which is the recruiter
 *   entry point — that latency is unacceptable. Serving from a static JS
 *   import is instant, works offline, and has zero Railway dependency.
 *
 *   The backend /demo endpoint still exists for API consumers; this is
 *   purely a frontend optimization for the demo UX path.
 *
 * Keep this in sync with backend/routers/demo.py fallback data.
 */

export const DEMO_REPORT = {
  grade: "B",
  price_delta: -800,
  price_verdict:
    "This 2019 Honda Civic LX is priced $800 BELOW market for comparable listings with similar mileage in this region.",
  summary:
    "This is a solid used car deal — slightly below market price with Honda's well-known reliability backing it up. The mileage is reasonable for the year, and there are no major red flags from the VIN history. A pre-purchase inspection is still recommended before buying any used car.",
  red_flags: [
    {
      title: "No Service History Provided",
      description:
        "The listing doesn't mention any service records. Ask the seller for receipts for oil changes and major services before committing to buy.",
    },
    {
      title: "High Demand Area Markup Risk",
      description:
        "Listings in this metro area trend 3-5% above national averages. The below-market price here may reflect an undisclosed issue — always do a pre-purchase inspection.",
    },
  ],
  green_flags: [
    {
      title: "Below Market Price",
      description:
        "At $800 below the regional median for this trim and mileage, this listing offers good value if the car checks out.",
    },
    {
      title: "Honda Civic Reliability",
      description:
        "The 10th-gen Civic (2016-2021) is one of the most reliable compact cars on the market with low maintenance costs and excellent long-term ownership data.",
    },
    {
      title: "Reasonable Mileage for Year",
      description:
        "At 62,000 miles on a 2019 model, this car is within the expected range (~12k miles/year). No above-average wear concerns.",
    },
  ],
  comps: [
    {
      title: "2019 Honda Civic LX — 58k mi (CarGurus)",
      price: 19200,
      mileage: 58000,
      url: "https://www.cargurus.com",
      delta_vs_this: 1100,
    },
    {
      title: "2019 Honda Civic LX — 67k mi (AutoTrader)",
      price: 17900,
      mileage: 67000,
      url: "https://www.autotrader.com",
      delta_vs_this: -200,
    },
    {
      title: "2019 Honda Civic LX — 71k mi (Cars.com)",
      price: 17400,
      mileage: 71000,
      url: "https://www.cars.com",
      delta_vs_this: -700,
    },
  ],
  negotiation_points: [
    "Comps average $18,167 — open at $17,200 and cite the two listings below market.",
    "No service records provided — ask for a $300 concession to cover a pre-purchase inspection.",
    "14 days on market with no price drop suggests motivation — a $500 reduction is reasonable to request.",
  ],
};

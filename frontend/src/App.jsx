/**
 * App.jsx
 *
 * Root application component. Defines all client-side routes using React Router v6.
 *
 * Routes:
 *   /           → Home (landing page + search input)
 *   /analysis   → Analysis (results page with DealCard)
 *   /login      → Login (magic link auth)
 *   /case-study → CaseStudy (recruiter-facing portfolio page)
 *
 * The ?demo=true query param is handled inside the Home page — it auto-triggers
 * a demo analysis without requiring authentication.
 */

import { Routes, Route } from 'react-router-dom';
import Home from './pages/Home.jsx';
import Analysis from './pages/Analysis.jsx';
import Login from './pages/Login.jsx';
import CaseStudy from './pages/CaseStudy.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/analysis" element={<Analysis />} />
      <Route path="/login" element={<Login />} />
      <Route path="/case-study" element={<CaseStudy />} />
    </Routes>
  );
}

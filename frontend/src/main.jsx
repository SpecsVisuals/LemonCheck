/**
 * main.jsx
 *
 * React application entry point.
 * Mounts the App component into the #root div.
 * Imports global styles — these cascade to all components.
 *
 * React Router is initialized here via BrowserRouter so all child
 * components have access to routing context.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import './styles/global.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);

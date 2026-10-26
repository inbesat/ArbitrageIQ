import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import './index.css';

// T13: five routes behind a typed client. The stylesheet carries the design tokens and
// the base typography; the shell itself lives in App.tsx.
//
// No money is calculated or formatted here, and no decimal string is ever parsed to a
// number (`AGENTS.md` rule 7, `plans/TECH_STACK.md` §3.1).
ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);

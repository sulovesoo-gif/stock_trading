// [지침 준수] 이부분이라고!! 꼭!!
// frontend/src/index.js

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// React 앱을 id가 'root'인 HTML 엘리먼트에 연결합니다.
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import StrategyBoard from './StrategyBoard'; // 기존 App.js 내용을 여기로 옮기세요
import FastScalping from './FastScalping';
import ProgramHistory from './ProgramHistory';

const App = () => {
  return (
    <Router>
      {/* 상단 탭 메뉴 */}
      <nav style={{ padding: '10px', background: '#2C3E50', display: 'flex', gap: '20px' }}>
        <Link to="/program" style={{ color: '#FFD700', textDecoration: 'none', fontWeight: 'bold' }}>📊 프로그램 변동</Link>
        <Link to="/" style={{ color: 'white', textDecoration: 'none', fontWeight: 'bold' }}>🎯 전략 보드</Link>
        <Link to="/fast" style={{ color: '#FF5252', textDecoration: 'none', fontWeight: 'bold' }}>⚡ 실시간 스캘핑</Link>
      </nav>

      <Routes>
        <Route path="/program" element={<ProgramHistory />} />
        <Route path="/" element={<StrategyBoard />} />
        <Route path="/fast" element={<FastScalping />} />
      </Routes>
    </Router>
  );
};

export default App;
// [지침 준수] 이부분이라고!! 꼭!!
// frontend/src/App.js (또는 통합 HTML/JS 예시)

import React, { useState, useEffect } from 'react';
import axios from 'axios';

// 스타일 정의 (기존 app.py의 CSS 로직 이관)
const cardStyle = (sigColor) => ({
  borderTop: `5px solid ${sigColor}`,
  padding: '12px',
  borderRadius: '8px',
  backgroundColor: 'white',
  boxShadow: '2px 2px 8px rgba(0,0,0,0.1)',
  height: '140px'
});

function App() {
  const [signals, setSignals] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null); // 팝업용 상태

  // 1. 데이터 로드 (FastAPI 연결)
  const fetchSignals = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/signals');
      setSignals(res.data);
    } catch (err) {
      console.error("데이터 로드 실패:", err);
    }
  };

  useEffect(() => {
    fetchSignals();
    const timer = setInterval(fetchSignals, 5000); // 5초마다 갱신
    return () => clearInterval(timer);
  }, []);

  return (
    <div style={{ padding: '20px', backgroundColor: '#f5f7f9', minHeight: '100vh' }}>
      <h2>🚀 STRATEGY HIT BOARD PRO</h2>
      
      {/* 5열 그리드 레이아웃 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '15px' }}>
        {signals.map((stock) => (
          <div key={stock.stock_code} style={cardStyle(stock.sig_color)}>
            {/* 시그널 버튼 (클릭 시 즉시 팝업) */}
            <div 
              style={{ color: stock.sig_color, fontWeight: 'bold', cursor: 'pointer', textDecoration: 'underline', fontSize: '12px' }}
              onClick={() => setSelectedStock(stock)}
            >
              {stock.sig_name}
            </div>
            
            <div style={{ margin: '8px 0', fontSize: '15px', fontWeight: 'bold' }}>
              <a href={`https://finance.naver.com/item/main.naver?code=${stock.stock_code}`} target="_blank" rel="noreferrer" style={{ textDecoration: 'none', color: 'black' }}>
                {stock.stock_name}
              </a>
            </div>

            <div style={{ fontSize: '13px' }}>
              현재가: <span style={{ color: stock.change_rate > 0 ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>
                {stock.last_price.toLocaleString()} ({stock.change_rate}%)
              </span>
            </div>
            
            <div style={{ marginTop: '8px', padding: '5px', backgroundColor: '#f9f9f9', fontSize: '11px', borderRadius: '4px', height: '35px', overflow: 'hidden' }}>
              📌 {stock.point}
            </div>
          </div>
        ))}
      </div>

      {/* --- [수정 부분: 초고속 레이어 팝업] --- */}
      {selectedStock && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', padding: '25px', borderRadius: '15px', width: '400px', position: 'relative' }}>
            <span style={{ position: 'absolute', right: '15px', top: '10px', cursor: 'pointer', fontSize: '20px' }} onClick={() => setSelectedStock(null)}>&times;</span>
            
            <h3>📊 {selectedStock.stock_name} 상세 분석</h3>
            <hr />
            <div style={{ lineHeight: '1.8' }}>
              <p><b>RSI:</b> {selectedStock.rsi} | <b>R-SQ:</b> {selectedStock.r_square}</p>
              <p><b>BB 상단:</b> {selectedStock.bb_upper.toLocaleString()}</p>
              <p><b>외인/기관(5일):</b> {selectedStock.foreign_net_5d.toLocaleString()} / {selectedStock.institution_net_5d.toLocaleString()}</p>
              <p style={{ backgroundColor: '#fff3cd', padding: '10px', borderRadius: '5px' }}>
                💡 <b>전략:</b> {selectedStock.target_reason}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
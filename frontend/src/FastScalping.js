import React, { useState, useEffect, useRef } from 'react';


const FastScalping = ({ serverIp = "localhost" }) => {
// const FastScalping = ({ serverIp = "168.107.5.155" }) => {
  const [realtimeData, setRealtimeData] = useState({});
  const ws = useRef(null);

  useEffect(() => {
    // OCI 서버의 Broadcaster(8080포트)에 연결
    ws.current = new WebSocket(`ws://${serverIp}:8080/ws/scalping`);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // 1. 초기 리스트 설정 신호가 오면 전체 틀을 잡음
      if (data.type === "INIT") {
        const initial = {};
        data.stocks.forEach(s => {
          initial[s.code] = { 
            code: s.code, name: s.name, price: 0, speed: 0, strength: 0, updated: 0 
          };
        });
        setRealtimeData(initial);
        return;
      }

      setRealtimeData(prev => ({
        ...prev,
        [data.code]: { 
          ...data, 
          updated: Date.now() 
        }
      }));
    };

    ws.current.onerror = (err) => console.error("WebSocket Error:", err);
    
    return () => { if (ws.current) ws.current.close(); };
  }, [serverIp]);

  // 체결 속도에 따른 경고 색상
  const getSpeedColor = (speed) => {
    if (speed > 10) return '#FF5252'; // 초당 10건 이상: 폭발(Red)
    if (speed > 5) return '#FFAB40';  // 초당 5건 이상: 과열(Orange)
    return '#444';                    // 보통
  };

  return (
    <div style={{ padding: '20px', backgroundColor: '#000', minHeight: '100vh', color: 'white', fontFamily: 'monospace' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ borderLeft: '5px solid #FF5252', paddingLeft: '10px', margin: 0 }}>
         ⚡REAL-TIME SCALPING ENGINE
        </h2>
        <div style={{ fontSize: '12px', color: '#888' }}>
          SERVER: <span style={{ color: '#4CAF50' }}>● {serverIp}</span>
        </div>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
        {Object.values(realtimeData)
          .sort((a, b) => b.speed - a.speed) // 속도 빠른 순 정렬
          .map((stock) => {
            const isWaiting = stock.price === 0; // 데이터 수신 전 상태
            const isHot = Date.now() - stock.updated < 300; 
            const strength = parseFloat(stock.strength) || 0;
            const speed = parseFloat(stock.speed) || 0;

            return (
              <div key={stock.code} style={{
                padding: '15px', 
                borderRadius: '8px', 
                background: '#1a1a1a',
                border: isHot ? `2px solid ${getSpeedColor(speed)}` : '1px solid #333',
                opacity: isWaiting ? 0.6 : 1,
                transition: 'all 0.1s ease-in-out',
                position: 'relative'
              }}>
                {/* 상단: 코드 및 체결 속도 */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '16px', fontWeight: 'bold', color: '#FFD700' }}>{stock.name}({stock.code})</span>
                  {!isWaiting && (
                    <span style={{ 
                      padding: '2px 6px', borderRadius: '4px', background: getSpeedColor(speed),
                      fontSize: '11px', fontWeight: 'bold'
                    }}>
                      {speed.toFixed(1)} T/S
                    </span>
                  )}
                </div>

                {/* 현재가 */}
                <div style={{ fontSize: '32px', fontWeight: 'bold', textAlign: 'center', margin: '15px 0', color: strength >= 100 ? '#FF5252' : '#448AFF' }}>
                  {isWaiting ? "LOADING..." : `${stock.price?.toLocaleString()}원`}
                </div>

                {/* 체결 강도 게이지 */}
                <div style={{ marginBottom: '15px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                    <span>체결강도</span>
                    <span>{strength.toFixed(2)}%</span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: '#333', borderRadius: '3px' }}>
                    <div style={{ 
                      width: `${Math.min(strength, 200) / 2}%`, 
                      height: '100%', 
                      background: strength >= 100 ? 'linear-gradient(90deg, #ff5252, #ff1744)' : '#448aff',
                      borderRadius: '3px',
                      transition: 'width 0.3s ease'
                    }} />
                  </div>
                </div>

                {/* 호가 잔량 바 (HOKA) */}
                <div style={{ borderTop: '1px solid #333', paddingTop: '10px' }}>
                  {stock.hoka ? (
                    <>
                      <div style={{ display: 'flex', height: '12px', background: '#333', borderRadius: '2px', overflow: 'hidden', marginBottom: '8px' }}>
                        <div style={{ 
                          width: `${(stock.hoka.total_ask_v / (parseInt(stock.hoka.total_ask_v) + parseInt(stock.hoka.total_bid_v))) * 100}%`, 
                          backgroundColor: '#448AFF', opacity: 0.8
                        }} />
                        <div style={{ 
                          width: `${(stock.hoka.total_bid_v / (parseInt(stock.hoka.total_ask_v) + parseInt(stock.hoka.total_bid_v))) * 100}%`, 
                          backgroundColor: '#FF5252', opacity: 0.8
                        }} />
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#aaa' }}>
                        <span>매도잔량: {parseInt(stock.hoka.total_ask_v).toLocaleString()}</span>
                        <span>매수잔량: {parseInt(stock.hoka.total_bid_v).toLocaleString()}</span>
                      </div>
                    </>
                  ) : (
                    <div style={{ fontSize: '10px', color: '#555', textAlign: 'center' }}>호가 데이터 수신 대기중...</div>
                  )}
                </div>
                
                {/* 주문 버튼 */}
                <div style={{ display: 'flex', gap: '5px', marginTop: '15px' }}>
                  <button style={{ flex: 1, padding: '8px', background: '#ff5252', border: 'none', color: 'white', fontWeight: 'bold', cursor: 'pointer', borderRadius: '4px' }}>매수</button>
                  <button style={{ flex: 1, padding: '8px', background: '#448aff', border: 'none', color: 'white', fontWeight: 'bold', cursor: 'pointer', borderRadius: '4px' }}>매도</button>
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
};

export default FastScalping;
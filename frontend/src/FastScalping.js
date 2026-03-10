import React, { useState, useEffect, useRef } from 'react';

const FastScalping = ({ serverIp = "168.107.5.155" }) => {
  const [realtimeData, setRealtimeData] = useState({});
  const ws = useRef(null);

  useEffect(() => {
    ws.current = new WebSocket(`ws://${serverIp}:8080/ws/scalping`);
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setRealtimeData(prev => ({
        ...prev,
        [data.code]: { ...data, updated: Date.now() }
      }));
    };
    return () => { if (ws.current) ws.current.close(); };
  }, [serverIp]);

  return (
    <div style={{ padding: '20px', backgroundColor: '#1a1a1a', minHeight: '100vh', color: 'white' }}>
      <h2 style={{ borderLeft: '5px solid #FF5252', paddingLeft: '10px' }}>⚡ FAST SCALPING ENGINE</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '15px' }}>
        {Object.values(realtimeData).sort((a, b) => b.speed - a.speed).map((stock) => {
          const isHot = Date.now() - stock.updated < 300;
          return (
            <div key={stock.code} style={{
              padding: '15px', borderRadius: '12px', background: '#2d2d2d',
              border: isHot ? '2px solid #FF5252' : '1px solid #444',
              boxShadow: isHot ? '0 0 15px rgba(255,82,82,0.5)' : 'none'
            }}>
              <div style={{ fontSize: '14px', color: '#aaa' }}>{stock.code}</div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', margin: '5px 0' }}>{stock.price.toLocaleString()}원</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                <span>강도: {stock.strength}%</span>
                <span>속도: {stock.speed} t/s</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default FastScalping;
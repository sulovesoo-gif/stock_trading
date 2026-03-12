import React, { useState, useEffect, useRef } from 'react';

const FastScalping = () => {
    const [realtimeData, setRealtimeData] = useState({}); // 종목별 카드 데이터
    const [trades, setTrades] = useState([]); // 전체 실시간 체결 리스트
    const [isConnected, setIsConnected] = useState(false);
    const ws = useRef(null);

    useEffect(() => {
        // [설정] OCI 서버의 Broadcaster 연결
        ws.current = new WebSocket(`ws://168.107.5.155:8080/ws/scalping`);
        // ws.current = new WebSocket(`ws://localhost:8080/ws/scalping`);
        
        ws.current.onopen = () => setIsConnected(true);
        ws.current.onclose = () => setIsConnected(false);
        
        ws.current.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // 1. 초기화 데이터 처리
            if (data.type === "INIT") {
                const initial = {};
                data.stocks.forEach(s => {
                    initial[s.code] = { 
                        code: s.code, name: s.name, price: 0, speed: 0, strength: 0, updated: 0, hoka: null 
                    };
                });
                setRealtimeData(initial);
                return;
            }

            // 2. 실시간 체결 리스트 업데이트 (오늘 버전 핵심)
            if (data.price > 0) {
                setTrades(prev => [data, ...prev].slice(0, 30));
            }

            // 3. 종목별 카드 데이터 업데이트 (어제 버전 핵심)
            setRealtimeData(prev => ({
                ...prev,
                [data.code]: { 
                    ...prev[data.code],
                    ...data, 
                    updated: Date.now() 
                }
            }));
        };

        return () => ws.current?.close();
    }, []);

    const styles = {
        container: { padding: '20px', backgroundColor: '#000', minHeight: '100vh', color: 'white', fontFamily: 'monospace' },
        header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '2px solid #333', paddingBottom: '10px' },
        mainGrid: { display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px' },
        cardGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '15px' },
        stockCard: (isHot) => ({
            padding: '12px', borderRadius: '8px', background: '#1a1a1a',
            border: isHot ? '1px solid #FF5252' : '1px solid #333',
            transition: 'all 0.1s'
        }),
        sidePanel: { background: '#111', borderRadius: '8px', padding: '15px', border: '1px solid #333', height: 'calc(100vh - 120px)', overflowY: 'hidden' },
        table: { width: '100%', borderCollapse: 'collapse', fontSize: '12px' },
        gaugeBar: (val, color) => ({
            width: `${Math.min(val, 100)}%`, height: '100%', background: color, borderRadius: '2px', transition: 'width 0.3s'
        })
    };

    return (
        <div style={styles.container}>
            <header style={styles.header}>
                <h2 style={{ margin: 0, color: '#FF5252' }}>⚡ 통합 실시간 스캘핑 시스템</h2>
                <div style={{ fontSize: '12px' }}>
                    STATUS: <span style={{ color: isConnected ? '#4CAF50' : '#FF5252' }}>{isConnected ? "● LIVE" : "○ OFFLINE"}</span>
                </div>
            </header>

            <div style={styles.mainGrid}>
                {/* 왼쪽: 종목별 수급 카드 (어제 버전 + 게이지) */}
                <div style={styles.cardGrid}>
                    {Object.values(realtimeData).sort((a, b) => b.speed - a.speed).map((stock) => {
                        const isHot = Date.now() - stock.updated < 300;
                        return (
                            <div key={stock.code} style={styles.stockCard(isHot)}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                    <span style={{ fontWeight: 'bold', color: '#FFD700' }}>{stock.name}</span>
                                    <span style={{ fontSize: '10px', color: '#888' }}>{stock.speed?.toFixed(1)} T/S</span>
                                </div>
                                <div style={{ fontSize: '20px', fontWeight: 'bold', textAlign: 'center', marginBottom: '10px' }}>
                                    {stock.price?.toLocaleString()}
                                </div>
                                {/* 체결강도 게이지 */}
                                <div style={{ fontSize: '10px', marginBottom: '3px' }}>체결강도 {stock.strength?.toFixed(1)}%</div>
                                <div style={{ width: '100%', height: '4px', background: '#333', borderRadius: '2px', marginBottom: '10px' }}>
                                    <div style={styles.gaugeBar(stock.strength / 2, stock.strength >= 100 ? '#FF5252' : '#448AFF')} />
                                </div>
                                {/* 호가 비중 */}
                                {stock.hoka && (
                                    <div style={{ display: 'flex', height: '4px', borderRadius: '2px', overflow: 'hidden' }}>
                                        <div style={{ width: `${(stock.hoka.total_ask_v / (parseInt(stock.hoka.total_ask_v) + parseInt(stock.hoka.total_bid_v))) * 100}%`, background: '#448AFF' }} />
                                        <div style={{ width: `${(stock.hoka.total_bid_v / (parseInt(stock.hoka.total_ask_v) + parseInt(stock.hoka.total_bid_v))) * 100}%`, background: '#FF5252' }} />
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* 오른쪽: 통합 실시간 체결 내역 (오늘 버전) */}
                <div style={styles.sidePanel}>
                    <h3 style={{ fontSize: '14px', marginTop: 0, color: '#888', borderBottom: '1px solid #333', paddingBottom: '10px' }}>🕒 실시간 타임라인</h3>
                    <div style={{ height: '100%', overflowY: 'auto' }}>
                        <table style={styles.table}>
                            <thead>
                                <tr style={{ color: '#555', textAlign: 'left' }}>
                                    <th>종목</th>
                                    <th>가격</th>
                                    <th style={{ textAlign: 'right' }}>등락</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades.map((t, i) => (
                                    <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                                        <td style={{ padding: '8px 0', color: '#FFD700' }}>{t.name}</td>
                                        <td>{t.price?.toLocaleString()}</td>
                                        <td style={{ textAlign: 'right', color: t.rate > 0 ? '#FF5252' : '#448AFF' }}>
                                            {t.rate > 0 ? '▲' : '▼'}{Math.abs(t.rate)}%
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default FastScalping;
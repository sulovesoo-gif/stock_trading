import React, { useState, useEffect, useRef } from 'react';

const FastScalping = () => {
    const [realtimeData, setRealtimeData] = useState({}); // 종목별 카드 데이터
    const [trades, setTrades] = useState([]); // 전체 실시간 체결 리스트
    const [futures, setFutures] = useState(null); // [추가] 선물 데이터 상태
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

            // 1. 선물 데이터 처리 (H0IFCNT0)
            if (data.type === "FUTURES_TICK") {
                setFutures(data);
                return;
            }

            // 2. 초기화 및 체결 데이터 처리 (기존 로직 유지)
            if (data.type === "INIT") {
                const initial = {};
                data.stocks.forEach(s => {
                    initial[s.code] = { ...s, speed: 0, strength: 0, hoka_ratio: 50, vi_distance: 0 };
                });
                setRealtimeData(initial);
            } // 3. 체결(TICK) 및 [복구] 호가(HOKA) 통합 업데이트
            else if (data.type === "TICK" || data.type === "HOKA") {
                setRealtimeData(prev => ({
                    ...prev,
                    [data.code]: { ...prev[data.code], ...data }
                }));

                // TICK일 때만 타임라인 업데이트
                if (data.type === "TICK") {
                    const { is_hot, is_big_fish, is_abnormal_hoka, is_fake_wall, code } = data;

                    // [수정] 호가 불균형이나 허수벽이 발견된 경우도 타임라인에 포함
                    if (is_big_fish || is_hot || is_abnormal_hoka || is_fake_wall) {
                        let tags = [];
                        if (is_hot) tags.push("🚀가속");
                        if (is_big_fish) tags.push("🐋대형");
                        if (is_abnormal_hoka) tags.push("⚖️불균형");
                        if (is_fake_wall) tags.push("⚠️허수벽");

                        setTrades(prev => [{ 
                            name: realtimeData[data.code]?.name || data.code, 
                            ...data,
                            displayTag: tags.join(' ')
                        }, ...prev].slice(0, 50));
                    }
                }
            }
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
        <div style={{ backgroundColor: '#000', color: '#fff', minHeight: '100vh', padding: '20px' }}>
            {/* [추가] 상단 선물 전광판 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid #333', paddingBottom: '10px' }}>
                <h2 style={{ margin: 0 }}>⚡ 실시간 스캘핑 시스템</h2>
                {futures && (
                    <div style={{ display: 'flex', gap: '15px', alignItems: 'center', backgroundColor: '#111', padding: '5px 15px', borderRadius: '5px', border: '1px solid #f1c40f' }}>
                        <span style={{ color: '#f1c40f', fontSize: '12px', fontWeight: 'bold' }}>KOSPI200 선물</span>
                        <span style={{ fontSize: '18px', fontWeight: 'bold' }}>{futures.price}</span>
                        <span style={{ color: futures.rate > 0 ? '#ff5252' : '#448aff' }}>
                            {futures.rate > 0 ? '▲' : '▼'} {Math.abs(futures.rate)}%
                        </span>
                    </div>
                )}
                <div style={{ color: isConnected ? '#4CAF50' : '#FF5252' }}>{isConnected ? '● Connected' : '○ Disconnected'}</div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: '20px' }}>
                {/* 종목 카드 리스트 */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '15px' }}>
                    {Object.values(realtimeData)
                        .sort((a, b) => {
                            // 1. 거래대금 계산 (누적거래량 * 현재가)
                            const amtA = (a.accum_vol || 0) * (a.price || 0);
                            const amtB = (b.accum_vol || 0) * (b.price || 0);
                            
                            // 2. 거래대금 기준 내림차순 정렬 (큰 돈이 위로)
                            return amtB - amtA;

                            // 만약 '체결 속도'순으로 바꾸고 싶다면 아래 주석을 해제하고 위 리턴을 주석처리하세요.
                            // return (b.speed || 0) - (a.speed || 0); 
                        })
                        .map(s => {
                        // 1. 여기서 색상을 먼저 계산합니다.
                        const priceColor = s.rate > 0 ? '#928989' : s.rate < 0 ? '#448aff' : '#ffffff';
                        // 2. 이제 계산된 변수를 가지고 JSX를 반환합니다.
                        return (
                            <div key={s.code} style={{ 
                                backgroundColor: '#111', padding: '15px', borderRadius: '12px', 
                                border: s.speed > 5 ? '2px solid #FF5252' : '1px solid #333',
                                boxShadow: s.speed > 5 ? '0 0 10px rgba(255,82,82,0.5)' : 'none',
                            }}>
                                {/* 상단 1호가 잔량 수치 표시 (새로 추가한 ask_vol, bid_vol 활용) */}
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#666' }}>
                                    <span>1호가 매도: {s.ask_vol?.toLocaleString()}</span>
                                    <span>1호가 매수: {s.bid_vol?.toLocaleString()}</span>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '5px' }}>
                                    <span style={{ color: '#ffffff', fontWeight: 'bold' }}>{s.name}({s.code})</span>
                                    <span style={{ fontSize: '10px', color: '#ff00ff' }}>VI까지 {s.vi_distance}%</span>
                                </div>


                                {/* [디자인 변경 - 등락에 따른 색상 동적 적용] */}
                                {(() => {
                                    // 1. 색상 및 부호 결정 로직
                                    const isUp = s.rate > 0;
                                    const isDown = s.rate < 0;
                                    const color = isUp ? '#f44336' : (isDown ? '#1E88E5' : '#888');
                                    const sign = isUp ? '▲' : (isDown ? '▼' : '');
                                    
                                    return (
                                        <div style={{ 
                                            textAlign: 'right',
                                            margin: '20px 0', 
                                            fontFamily: "'Noto Sans KR', sans-serif"
                                        }}>
                                            {/* 1. 대형 금액 표시 (금액도 등락 색상에 맞춤) */}
                                            <div style={{ 
                                                fontSize: '32px', 
                                                fontWeight: '800', 
                                                color: color,  // 동적 색상 적용
                                                letterSpacing: '-1px'
                                            }}>
                                                {s.price?.toLocaleString() || 0}
                                            </div>
                                            
                                            {/* 2. 전일대비 라인 */}
                                            <div style={{ 
                                                fontSize: '12px', 
                                                color: '#888', 
                                                display: 'flex', 
                                                justifyContent: 'right', 
                                                gap: '4px',
                                                marginTop: '-3px'
                                            }}>
                                                <span>전일대비</span>
                                                <span style={{ 
                                                    color: color, // 동적 색상 적용
                                                    fontWeight: 'bold'
                                                }}>
                                                    {sign} {Math.abs(s.change)?.toLocaleString() || 0}
                                                </span>
                                                <span style={{ color: color }}>|</span>
                                                <span style={{ 
                                                    color: color, // 동적 색상 적용
                                                    fontWeight: 'bold'
                                                }}>
                                                    {isUp ? '+' : ''}{s.rate}%
                                                </span>
                                            </div>
                                        </div>
                                    );
                                })()}
                                
                                {/* [수정] 위에서 정의한 priceColor 적용 및 화살표 추가 */}
                                {/* <div style={{ 
                                    fontSize: '26px', 
                                    fontWeight: 'bold', 
                                    textAlign: 'right', 
                                    margin: '10px 0', 
                                    color: priceColor 
                                }}>
                                    <span style={{ fontSize: '14px', marginRight: '5px' }}>
                                        {s.rate > 0 ? '▲' : s.rate < 0 ? '▼' : ''}
                                    </span>
                                    {s.price?.toLocaleString()}
                                </div> */}
                                
                                {/* 이하 에너지 바 등 기존 로직 동일 */}
                                {/* <div style={{ marginTop: '10px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', marginBottom: '3px' }}>
                                        <span style={{ color: '#448aff' }}>매도</span>
                                        <span style={{ color: '#ff5252' }}>매수 {s.hoka_ratio}%</span>
                                    </div>
                                    <div style={{ width: '100%', height: '4px', backgroundColor: '#002244', borderRadius: '2px', overflow: 'hidden', display: 'flex' }}>
                                        <div style={{ width: `${s.hoka_ratio}%`, height: '100%', backgroundColor: '#ff5252', transition: 'width 0.3s' }} />
                                    </div>
                                </div> */}

                                {/* [추가] 입체 호가 잔량 분석 (이미지 가이드 반영) */}
                                <div style={{ marginTop: '12px', padding: '8px', backgroundColor: '#050505', borderRadius: '8px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '5px' }}>
                                        <span style={{ color: '#448aff' }}>
                                            <span style={{ fontSize: '9px', display: 'block', color: '#666' }}>매도잔량합</span>
                                            {s.total_ask_vol?.toLocaleString() || 0}
                                        </span>
                                        <span style={{ color: '#ff5252', textAlign: 'right' }}>
                                            <span style={{ fontSize: '9px', display: 'block', color: '#666' }}>매수잔량합</span>
                                            {s.total_bid_vol?.toLocaleString() || 0}
                                        </span>
                                    </div>
                                    <div style={{ width: '100%', height: '6px', backgroundColor: '#448aff', borderRadius: '3px', overflow: 'hidden', display: 'flex' }}>
                                        <div style={{ 
                                            width: `${s.hoka_ratio}%`, 
                                            height: '100%', 
                                            backgroundColor: '#ff5252', 
                                            transition: 'width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                                            marginLeft: 'auto' 
                                        }} />
                                    </div>
                                </div>
                                
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px', fontSize: '12px' }}>
                                    <span style={{ color: '#888' }}>강도: {s.strength}%</span>
                                    <span style={{ color: '#4caf50', fontWeight: 'bold' }}>{s.speed} T/S</span>
                                    {/* <span style={{ color: '#888' }}> { s.total_ask_vol +':'+ s.total_bid_vol} {s.hoka_ratio}%</span> */}
                                </div>
                            </div>
                        );
                    })} {/* [변경] ) 에서 } 로 변경 */}
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
                                        <td style={{ padding: '8px 0', color: '#FFD700' }}>
                                        {t.name} 
                                        {/* 태그 출력: 배경색과 패딩을 주어 더 직관적으로 변경 */}
                                        {t.displayTag && (
                                            <span style={{ 
                                                fontSize: '0.75em', 
                                                marginLeft: '6px', 
                                                padding: '2px 5px', 
                                                backgroundColor: '#333', 
                                                borderRadius: '3px',
                                                color: '#FFF' 
                                            }}>
                                                {t.displayTag}
                                            </span>
                                        )}
                                    </td>
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
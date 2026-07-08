// ui/src/ProgramHistory.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ProgramHistory = () => {
    const [programHistory, setProgramHistory] = useState([]);

    const fetchProgramHistory = async () => {
        try {
            const res = await axios.get('http://168.107.5.155:8000/api/program-history');
            // const res = await axios.get('http://localhost:8000/api/program-history');
            setProgramHistory(res.data);
        } catch (error) {
            console.error("프로그램 매매 내역 로드 실패:", error);
        }
    };

    useEffect(() => {
        fetchProgramHistory();
        const interval = setInterval(fetchProgramHistory, 3000);
        return () => clearInterval(interval);
    }, []);

    const getChangeTypeStyle = (type) => {
        if (type === "PROGRAM_BUY") {
            return { backgroundColor: '#D32F2F', color: '#FFFFFF', fontWeight: 'bold', padding: '4px 8px', borderRadius: '4px' };
        } else if (type === "PROGRAM_SELL") {
            return { backgroundColor: '#1976D2', color: '#FFFFFF', fontWeight: 'bold', padding: '4px 8px', borderRadius: '4px' };
        }
        return { backgroundColor: '#424242', color: '#B0BEC5', padding: '4px 8px', borderRadius: '4px' };
    };

    return (
        <div style={{ padding: '20px', background: '#1A1A1A', color: '#FFF', minHeight: '100vh' }}>
            <div style={{ background: '#2D2D2D', padding: '20px', borderRadius: '8px' }}>
                <h3 style={{ margin: '0 0 20px 0', color: '#FFD700', fontSize: '18px' }}>
                    📊 프로그램 매매 실시간 변동 그리드 (전체 컬럼 모니터링)
                </h3>
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'right', fontSize: '12px' }}>
                        <thead>
                            <tr style={{ borderBottom: '2px solid #444', color: '#AAA', height: '40px', backgroundColor: '#222' }}>
                                <th style={{ padding: '10px', textAlign: 'left' }}>수집 일시</th>
                                <th style={{ padding: '10px', textAlign: 'center' }}>영업 시간</th>
                                <th style={{ padding: '10px', textAlign: 'center' }}>종목</th>
                                <th style={{ padding: '10px' }}>현재가</th>
                                <th style={{ padding: '10px' }}>대비율</th>
                                <th style={{ padding: '10px' }}>누적 거래량</th>
                                <th style={{ padding: '10px' }}>매도 거래량</th>
                                <th style={{ padding: '10px' }}>매수 거래량</th>
                                <th style={{ padding: '10px' }}>순매수 거래량</th>
                                <th style={{ padding: '10px' }}>매도 금액(억)</th>
                                <th style={{ padding: '10px' }}>매수 금액(억)</th>
                                <th style={{ padding: '10px' }}>순매수 금액(억)</th>
                                <th style={{ padding: '10px', color: '#FFD700' }}>량 변동</th>
                                <th style={{ padding: '10px', color: '#FFD700' }}>금액 변동(억)</th>
                                <th style={{ padding: '10px', textAlign: 'center' }}>상태</th>
                            </tr>
                        </thead>
                        <tbody>
                            {programHistory.length === 0 ? (
                                <tr>
                                    <td colSpan="15" style={{ padding: '30px', textAlign: 'center', color: '#888' }}>
                                        오늘 수집된 데이터가 없습니다.
                                    </td>
                                </tr>
                            ) : (
                                programHistory.map((row, idx) => (
                                    <tr key={idx} style={{ borderBottom: '1px solid #3A3A3A', height: '40px', backgroundColor: idx % 2 === 0 ? '#2D2D2D' : '#252525' }}>
                                        {/* 💡 수집시간 분리 안하고 일시 전부 출력 */}
                                        <td style={{ padding: '10px', textAlign: 'left', color: '#AAA', whiteSpace: 'nowrap' }}>{row.collect_time}</td>
                                        <td style={{ padding: '10px', textAlign: 'center' }}>{row.trade_time}</td>
                                        <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#FFD700' }}>{row.stock_name}({row.stock_code})</td>
                                        <td style={{ padding: '10px', fontWeight: 'bold' }}>{row.stock_price?.toLocaleString()}원</td>
                                        <td style={{ padding: '10px', color: row.price_change_rate > 0 ? '#FF5252' : '#448AFF' }}>
                                            {row.price_change_rate}%
                                        </td>
                                        {/* 전체 스냅샷 데이터 추가 */}
                                        <td style={{ padding: '10px', color: '#BBB' }}>{row.accumulated_volume?.toLocaleString()}</td>
                                        <td style={{ padding: '10px', color: '#448AFF' }}>{row.sell_volume?.toLocaleString()}</td>
                                        <td style={{ padding: '10px', color: '#FF5252' }}>{row.buy_volume?.toLocaleString()}</td>
                                        <td style={{ padding: '10px', fontWeight: 'bold', color: row.net_buy_volume >= 0 ? '#FF5252' : '#448AFF' }}>
                                            {row.net_buy_volume?.toLocaleString()}
                                        </td>
                                        <td style={{ padding: '10px', color: '#AAA' }}>{(row.sell_amount / 100000000).toFixed(1)}</td>
                                        <td style={{ padding: '10px', color: '#AAA' }}>{(row.buy_amount / 100000000).toFixed(1)}</td>
                                        <td style={{ padding: '10px', fontWeight: 'bold', color: row.net_buy_amount >= 0 ? '#FF5252' : '#448AFF' }}>
                                            {(row.net_buy_amount / 100000000).toFixed(1)}
                                        </td>
                                        {/* 직전 대비 변동분 */}
                                        <td style={{ padding: '10px', color: row.net_buy_volume_change > 0 ? '#FF5252' : row.net_buy_volume_change < 0 ? '#448AFF' : '#FFF' }}>
                                            {row.net_buy_volume_change > 0 ? '+' : ''}{row.net_buy_volume_change?.toLocaleString()}
                                        </td>
                                        {/* <td style={{ padding: '10px', color: row.net_buy_amount_change > 0 ? '#FF5252' : row.net_buy_amount_change < 0 ? '#448AFF' : '#FFF' }}>
                                            {row.net_buy_amount_change > 0 ? '+' : ''}{Math.round(row.net_buy_amount_change / 100000000)?.toLocaleString()}
                                        </td> */}
                                        <td style={{ padding: '8px', color: row.net_buy_amount_change > 0 ? '#FF5252' : row.net_buy_amount_change < 0 ? '#448AFF' : '#FFF', fontWeight: 'bold' }}>
                                            {(row.net_buy_amount_change / 100000000).toFixed(2)}억
                                        </td>
                                        <td style={{ padding: '10px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                                            <span style={getChangeTypeStyle(row.change_type)}>
                                                {row.change_type}
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default ProgramHistory;
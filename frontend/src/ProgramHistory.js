// ui/src/ProgramHistory.js
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ProgramHistory = () => {
    const [programHistory, setProgramHistory] = useState([]);

    const fetchProgramHistory = async () => {
        try {
            const res = await axios.get('http://168.107.5.155:8000/api/program-history');
            // const res = await axios.get('http://localhosst:8000/api/program-history');
            setProgramHistory(res.data); //
        } catch (error) {
            console.error("프로그램 매매 내역 로드 실패:", error); //
        }
    };

    useEffect(() => {
        fetchProgramHistory(); //
        const interval = setInterval(fetchProgramHistory, 3000); //
        return () => clearInterval(interval); //
    }, []);

    // 대안 2 전용 부드러운 오피스 스타일 틱 배지
    const getChangeTypeStyle = (type) => {
        if (type === "PROGRAM_BUY") {
            return { backgroundColor: '#FEE2E2', color: '#DC2626', fontWeight: 'bold', padding: '3px 6px', borderRadius: '4px', border: '1px solid #FCA5A5' };
        } else if (type === "PROGRAM_SELL") {
            return { backgroundColor: '#DBEAFE', color: '#2563EB', fontWeight: 'bold', padding: '3px 6px', borderRadius: '4px', border: '1px solid #93C5FD' };
        }
        return { backgroundColor: '#F3F4F6', color: '#4B5563', padding: '3px 6px', borderRadius: '4px' };
    };

    // 부드러운 추세 상태 배지
    const getTrendStatusStyle = (status) => {
        if (status === "UP") {
            return { backgroundColor: '#EF4444', color: '#FFFFFF', padding: '3px 6px', borderRadius: '4px', fontWeight: 'bold', fontSize: '11px' };
        } else if (status === "DOWN") {
            return { backgroundColor: '#3B82F6', color: '#FFFFFF', padding: '3px 6px', borderRadius: '4px', fontWeight: 'bold', fontSize: '11px' };
        }
        return { backgroundColor: '#9CA3AF', color: '#FFFFFF', padding: '3px 6px', borderRadius: '4px', fontSize: '11px' };
    };

    return (
        <div style={{ padding: '20px', background: '#F9FAFB', color: '#1F2937', minHeight: '100vh', fontFamily: 'Segoe UI, Roboto, sans-serif' }}>
            <div style={{ background: '#FFFFFF', padding: '24px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', border: '1px solid #E5E7EB' }}>
                <h3 style={{ margin: '0 0 16px 0', color: '#111827', fontSize: '16px', fontWeight: '600', display: 'flex', justifyContent: 'between', alignItems: 'center' }}>
                    <span>📋 프로그램 추세 전환 모니터링 대시보드 (최신 100개 행 제한)</span>
                    <span style={{ fontSize: '12px', color: '#6B7280', fontWeight: 'normal', marginLeft: 'auto' }}>정기 3초 갱신</span>
                </h3>
                
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'right', fontSize: '12px', minWidth: '1300px' }}>
                        <thead>
                            <tr style={{ borderBottom: '2px solid #E5E7EB', color: '#374151', height: '40px', backgroundColor: '#F3F4F6', fontWeight: '600' }}>
                                <th style={{ padding: '10px', textAlign: 'left' }}>수집 일시</th>
                                <th style={{ padding: '10px', textAlign: 'center' }}>영업 시간</th>
                                <th style={{ padding: '10px', textAlign: 'center' }}>종목명</th>
                                <th style={{ padding: '10px' }}>현재가</th>
                                <th style={{ padding: '10px' }}>대비율</th>
                                <th style={{ padding: '10px' }}>누적 거래량</th>
                                <th style={{ padding: '10px' }}>매도 수량/금액</th>
                                <th style={{ padding: '10px' }}>매수 수량/금액</th>
                                <th style={{ padding: '10px' }}>순매수 수량/금액</th>
                                <th style={{ padding: '10px' }}>순매수 변동(억)</th>
                                <th style={{ padding: '10px', textAlign: 'center' }}>틱상태</th>
                                <th style={{ padding: '10px', textAlign: 'center', backgroundColor: '#FEF3C7', color: '#92400E' }}>추세 그룹</th>
                                <th style={{ padding: '10px', textAlign: 'center', backgroundColor: '#FEF3C7', color: '#92400E' }}>추세 방향</th>
                                <th style={{ padding: '10px', backgroundColor: '#FEF3C7', color: '#92400E', textAlign: 'right' }}>전환기 대비 등락</th>
                            </tr>
                        </thead>
                        <tbody>
                            {programHistory.length === 0 ? (
                                <tr>
                                    <td colSpan="14" style={{ padding: '40px', textAlign: 'center', color: '#9CA3AF', backgroundColor: '#FFFFFF' }}>
                                        오늘 발생한 추세 전환(100억 임계치 돌파) 데이터가 없습니다.
                                    </td>
                                </tr>
                            ) : (
                                programHistory.map((row, idx) => {
                                    let stageChangeRate = "0.00%";
                                    let stageChangeColor = "#111827";
                                    if (row.prev_confirmed_price) {
                                        const rate = ((row.stock_price - row.prev_confirmed_price) / row.prev_confirmed_price) * 100;
                                        stageChangeRate = (rate > 0 ? '+' : '') + rate.toFixed(2) + "%";
                                        stageChangeColor = rate > 0 ? '#EF4444' : rate < 0 ? '#3B82F6' : '#111827';
                                    } else {
                                        stageChangeRate = "-";
                                        stageChangeColor = "#9CA3AF";
                                    }

                                    return (
                                        <tr key={idx} style={{ borderBottom: '1px solid #E5E7EB', height: '38px', backgroundColor: idx % 2 === 0 ? '#FFFFFF' : '#F9FAFB' }}>
                                            <td style={{ padding: '10px', textAlign: 'left', color: '#6B7280', whiteSpace: 'nowrap' }}>{row.collect_time}</td>
                                            <td style={{ padding: '10px', textAlign: 'center', color: '#4B5563' }}>{row.trade_time}</td>
                                            <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', color: '#111827' }}>{row.stock_name}</td>
                                            <td style={{ padding: '10px', fontWeight: '500' }}>{row.stock_price?.toLocaleString()}원</td>
                                            <td style={{ padding: '10px', color: row.price_change_rate > 0 ? '#EF4444' : '#3B82F6', fontWeight: '500' }}>{row.price_change_rate}%</td>
                                            <td style={{ padding: '10px', color: '#4B5563' }}>{row.accumulated_volume?.toLocaleString()}</td>
                                            
                                            {/* 매도/매수 상세 데이터 분할 출력 */}
                                            <td style={{ padding: '10px', color: '#4B5563', fontSize: '11px' }}>
                                                {row.sell_volume?.toLocaleString()}<br/>
                                                <span style={{color:'#9CA3AF'}}>{(row.sell_amount / 100000000).toFixed(1)}억</span>
                                            </td>
                                            <td style={{ padding: '10px', color: '#4B5563', fontSize: '11px' }}>
                                                {row.buy_volume?.toLocaleString()}<br/>
                                                <span style={{color:'#9CA3AF'}}>{(row.buy_amount / 100000000).toFixed(1)}억</span>
                                            </td>
                                            <td style={{ padding: '10px', fontWeight: '500', color: row.net_buy_amount >= 0 ? '#EF4444' : '#3B82F6', fontSize: '11px' }}>
                                                {row.net_buy_volume?.toLocaleString()}<br/>
                                                <span>{(row.net_buy_amount / 100000000).toFixed(1)}억</span>
                                            </td>
                                            
                                            <td style={{ padding: '8px', color: row.net_buy_amount_change > 0 ? '#EF4444' : row.net_buy_amount_change < 0 ? '#3B82F6' : '#1F2937', fontWeight: 'bold' }}>
                                                {(row.net_buy_amount_change / 100000000).toFixed(2)}억
                                            </td>
                                            <td style={{ padding: '10px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                                                <span style={getChangeTypeStyle(row.change_type)}>{row.change_type}</span>
                                            </td>

                                            {/* 추세 연산 필드 매핑 및 강조배경 */}
                                            <td style={{ padding: '10px', textAlign: 'center', fontWeight: 'bold', backgroundColor: '#FFFBEB', color: '#B45309' }}>
                                                {row.trend_group_no ? `${row.trend_group_no}기` : '-'}
                                            </td>
                                            <td style={{ padding: '10px', textAlign: 'center', whiteSpace: 'nowrap', backgroundColor: '#FFFBEB' }}>
                                                <span style={getTrendStatusStyle(row.trend_status)}>{row.trend_status}</span>
                                            </td>
                                            <td style={{ padding: '10px', fontWeight: 'bold', color: stageChangeColor, backgroundColor: '#FFFBEB' }}>
                                                {stageChangeRate}
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
};

export default ProgramHistory;
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';

const App = () => {
  const [stocks, setStocks] = useState([]);
  const [topPicks, setTopPicks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
  const [activeTab, setActiveTab] = useState('market'); // 탭 상태 추가
  const [expandedIds, setExpandedIds] = useState([]);

  useEffect(() => {
    const gradeNames = {
      1: "🚀 로켓: 추세폭발", 2: "✨ 바닥탈출: 역발상", 3: "💎 슈퍼: 세력매집",
      4: "🧨 에너지폭발", 5: "🛡️ 세력철벽지지", 
      10: "💀 초과열: 탈출시급", 11: "📉 추세붕괴: 투매발생", 12: "⚠️ 세력대량이탈"
    };
    const gradeColors = {
      1: "#FF5252", 2: "#4DB6AC", 3: "#FFD700", 4: "#FF9800", 5: "#9C27B0",
      10: "#34495E", 11: "#2980B9", 12: "#7F8C8D"
    };

  const fetchData = async () => {
    try {
      const res = await axios.get('http://127.0.0.1:8000/api/signals');

      const processedData = res.data.map(s => {
        const { rsi, r_square: r2, lrl, bb_upper: bb_up, bb_lower: bb_low, last_price: cur_p, ma_short } = s;
        const vol_ratio = s.volume_ratio || 0;
        const f_net = s.foreign_net_5d || 0;
        const i_net = s.institution_net_5d || 0;

        let points = [];
        let minGrade = 99; 

        // --- [매수/매도 시그널 전수 조사: 누적] ---

        // 1️⃣ 로켓 (1등급)
        if (r2 > 0.7 && cur_p > lrl && cur_p > bb_up && (f_net > 0 || i_net > 0)) {
          points.push("🚀로켓"); if (minGrade > 1) minGrade = 1;
        }
        // 2️⃣ 바닥탈출 (2등급)
        if (rsi < 35 && r2 < 0.25 && cur_p > ma_short) {
          points.push("✨바닥탈출"); if (minGrade > 2) minGrade = 2;
        }
        // 3️⃣ 슈퍼매집 (3등급)
        if (cur_p > lrl && r2 >= 0.8 && (f_net > 0 && i_net > 0)) {
          points.push("💎슈퍼매집"); if (minGrade > 3) minGrade = 3;
        }
        // 4️⃣ 에너지폭발 (4등급)
        if ((bb_up - bb_low) / cur_p < 0.05 && cur_p > bb_up && vol_ratio > 250) {
          points.push("🧨에너지폭발"); if (minGrade > 4) minGrade = 4;
        }
        // 5️⃣ 세력철벽지지 (5등급)
        if (cur_p <= lrl * 1.01 && cur_p >= lrl * 0.99 && (f_net > 0 || i_net > 0)) {
          points.push("🛡️철벽지지"); if (minGrade > 5) minGrade = 5;
        }
        // 10️⃣ 초과열매도 (10등급)
        if (rsi > 78 && cur_p > bb_up * 1.05) {
          points.push("💀초과열매도"); if (minGrade > 10) minGrade = 10;
        }
        // 11️⃣ 추세붕괴 (11등급)
        if (cur_p < lrl * 0.95 && f_net < 0 && i_net < 0) {
          points.push("📉추세붕괴"); if (minGrade > 11) minGrade = 11;
        }
        // 12️⃣ 세력이탈 (12등급)
        if (rsi > 70 && f_net < -50000) {
          points.push("⚠️세력이탈"); if (minGrade > 12) minGrade = 12;
        }

        const isSuper = minGrade >= 1 && minGrade <= 3;
        const isUltra = minGrade === 4 || minGrade === 5;
        const isSellStrong = minGrade >= 10;

        return { 
          ...s, 
          sig_grade: minGrade === 99 ? 9 : minGrade, 
          sig_name: gradeNames[minGrade] || "🔍 일반",
          sig_color: gradeColors[minGrade] || "#888888",
          points_count: points.length, // 정렬 1순위 데이터
          display_point: points.length > 0 ? points.join(" & ") : "관망 유지",
          trade_icon: isUltra ? '⚡' : (isSuper ? '💎' : (isSellStrong ? '🚫' : '👀')),
          strat_type: (isSuper || isUltra) ? '창' : (isSellStrong ? '방패' : '관망'),
          is_super: isSuper,
          is_ultra: isUltra,
          is_sell_strong: isSellStrong
        };
      });

      const sortedData = [...processedData].sort((a, b) => {
        if (a.sig_grade !== b.sig_grade) {
          return a.sig_grade - b.sig_grade;
        }
        return b.points_count - a.points_count;
      });

      setStocks(sortedData);
      setTopPicks(sortedData.slice(0, 10)); // 상위 10개 추출
    } catch (err) { console.error(err); }
  };
  fetchData();
  const timer = setInterval(fetchData, 5000);
  return () => clearInterval(timer);
  }, []); // gradeNames, gradeColors are static constants now

  const toggleExpand = useCallback((id) => {
    setExpandedIds(prev => 
      prev.includes(id) 
        ? prev.filter(itemId => itemId !== id) 
        : [...prev, id]
    );
  }, []);

  const renderGauge = useCallback((rate) => {
    const widthPct = Math.min((Math.abs(rate || 0) / 30) * 50, 50); 
  const isPos = rate > 0;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
      <div style={{ 
        position: 'relative', 
        width: '120px',      // 가독성을 위해 전체 길이는 살짝 늘림
        height: '8px',       // 두께를 슬림하게 조정
        background: '#eee',  // 연한 회색 배경
        borderRadius: '10px',
        overflow: 'hidden',
        border: '1px solid #e0e0e0' // 전체 틀에만 아주 연한 테두리
      }}>
        {/* 중앙 기준선 (0%) */}
        <div style={{ 
          position: 'absolute', 
          left: '50%', 
          width: '1px', 
          height: '100%', 
          background: '#ccc', 
          zIndex: 2 
        }}></div>

        {/* 게이지 바 (테두리 제거) */}
        <div style={{ 
          position: 'absolute', 
          left: isPos ? '50%' : `${50 - widthPct}%`, 
          width: `${widthPct}%`, 
          height: '100%', 
          backgroundColor: isPos ? '#FF5252' : '#448AFF',
          transition: 'width 0.3s ease'
        }}></div>
      </div>
      
      {/* 등락률 텍스트 표시 */}
      <span style={{ 
        fontSize: '11px', 
        fontWeight: 'bold', 
        color: isPos ? '#FF5252' : '#448AFF',
        minWidth: '40px'
      }}>
        {isPos ? '+' : ''}{rate}%
      </span>
    </div>
    );
  }, []);

  const calculateStats = useCallback((targetStocks) => {
    const count = targetStocks.length;
    const avg = count > 0 
      ? (targetStocks.reduce((acc, cur) => acc + cur.change_rate, 0) / count).toFixed(2)
      : "0.00";
    return { count, avg };
  }, []);

  const stats = useMemo(() => ({
      total: calculateStats(stocks),
      top: calculateStats(stocks.filter(s => s.sig_grade >= 1 && s.sig_grade <= 3).slice(0, 10)),
      ultra: calculateStats(stocks.filter(s => s.sig_grade === 4 || s.sig_grade === 5)),
      danger: calculateStats(stocks.filter(s => s.sig_grade >= 10 && s.sig_grade <= 12)),
      attack: calculateStats(stocks.filter(s => s.strat_type === '창')),
      defense: calculateStats(stocks.filter(s => s.strat_type === '방패'))
    }), [stocks, calculateStats]);

  // Move getDetails logic inside DetailRow or keep as memoized helper
  const getDetailsData = useCallback((s) => {
    if (!s) return null;

    const offsets = [0.06, 0.03, 0, -0.03, -0.06];
    const rawVolumes = [25.1, 48.2, 12.5, 9.1, 5.1];
    const supplyPoints = offsets.map((offset, i) => ({
      price: Math.round(s.last_price * (1 + offset)),
      volumePct: rawVolumes[i]
    })).sort((a, b) => b.price - a.price);

    const getIcon = (val) => {
      if (val > 50000) return { txt: "🔥 집중매집", clr: "#FF5252" };
      if (val > 0) return { txt: "🔴 순매집", clr: "#FF5252" };
      if (val < -50000) return { txt: "🧊 집중매도", clr: "#448AFF" };
      return { txt: "🔵 순매도", clr: "#448AFF" };
    };

    const f_stat = getIcon(s.foreign_net_5d);
    const i_stat = getIcon(s.institution_net_5d);

    const guides = [
      { label: "과열 유무(RSI)", val: Math.round(s.rsi), desc: s.rsi > 70 ? "⚠️ 지금 사기엔 너무 뜨거워요! (주의)" : "✅ 안정적으로 상승 중입니다." },
      { label: "추세 강도(R-SQ)", val: s.r_square?.toFixed(2), desc: s.r_square > 0.6 ? "🚀 상승 힘이 매우 강력합니다!" : "⏳ 에너지를 모으는 중입니다." },
      { label: "폭발 구간(BB)", val: "상단", desc: s.last_price > s.bb_upper ? "🔥 돌파! 보유자 수익 극대화 구간" : "✅ 안정적인 밴드 내 이동 중" },
      { label: "중심 축(LRL)", val: "위치", desc: s.last_price > s.lrl ? "📈 중심 위에서 힘차게 상승 중" : "📉 중심 아래서 반등 준비 중" },
      { label: "지지선(MA20)", val: "안착", desc: s.last_price > s.ma_short ? "🛡️ 든든한 지지선 위에 있습니다." : "⚠️ 지지선을 이탈해 주의가 필요함" }
    ];

    return { supplyPoints, f_stat, i_stat, guides };
  }, []);

  return (
    <div style={{ padding: '15px', backgroundColor: '#f4f7f6', minHeight: '100vh', fontFamily: 'Malgun Gothic', color: '#333' }}>
      <div style={{ marginBottom: '30px' }}>
        <h4>🎯 오늘의 전략 타격 대상 (TOP 픽)</h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '15px' }}>
          {/* 1. topPicks가 존재할 때만 map 실행 (에러 방지) */}
          {topPicks.map(stock => (
            <div key={stock.stock_code} onClick={() => setSelectedStock(stock)}
                style={{ 
                  background: 'white', 
                  // 2. 가장 강력한 신호의 색상으로 상단 보더 표시
                  borderTop: `5px solid ${stock.sig_color || '#eee'}`, 
                  padding: '12px', 
                  borderRadius: '8px', 
                  boxShadow: '0 2px 4px rgba(0,0,0,0.1)', 
                  cursor: 'pointer',
                  transition: 'transform 0.2s'
                }}>
              
              {/* 3. 누적된 모든 신호를 한눈에 표시 (🚀로켓 & 💎슈퍼매집 등) */}
              <div style={{ 
                fontSize: '11px', 
                color: stock.sig_color || '#888', 
                fontWeight: 'bold',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis' // 글자가 너무 길면 ... 처리
              }}>
                {stock.display_point || "일반 분석"} 
              </div>
              
              <div style={{ margin: '5px 0', minHeight: '36px', display: 'flex', alignItems: 'center' }}>
                <a href={`https://finance.naver.com/item/main.naver?code=${stock.stock_code}`} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()} 
                  style={{ fontSize: '14px', fontWeight: 'bold', color: 'black', textDecoration: 'none' }}>
                  {stock.stock_name}({stock.stock_code})
                </a>
              </div>

              <div style={{ color: (stock.change_rate || 0) > 0 ? '#FF5252' : '#448AFF', fontSize: '13px' }}>
                {/* 4. toLocaleString 에러 방지를 위한 논리 연산자 */}
                {(stock.last_price || 0).toLocaleString()} ({(stock.change_rate || 0) > 0 ? '+' : ''}{stock.change_rate || 0}%)
              </div>
            </div>
          ))}
        </div>
      </div>
      



      {/* 1. 요약 섹션 (사용자 요청대로 4개 구역으로 재구성) */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
        
        
        {/* 0등급: 감시종목 갯수 */}
        <div style={{ flex: 1, background: '#455A64', color: 'white', padding: '15px', borderRadius: '8px' }}>
          <div style={{ fontSize: '11px', opacity: 0.9 }}>📊 감시종목 갯수</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
            {stats.total.count}개 <span style={{ fontSize: '15px' }}>({stats.total.avg}%)</span>
          </div>
          <div style={{ fontSize: '10px', opacity: 0.8, marginTop: '4px' }}>전체 모니터링 대상</div>
        </div>

        {/* 1~3등급: 오늘의 TOP픽 */}
        <div style={{ flex: 1.2, background: 'white', padding: '15px', borderRadius: '8px', borderLeft: '8px solid #FFD700', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '11px', color: '#666' }}>🏆 오늘의 TOP픽 (1~3등급)</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
            {stats.top.count}개 <span style={{ color: stats.top.avg > 0 ? '#FF5252' : '#448AFF' }}>({stats.top.avg}%)</span>
          </div>
          <div style={{ fontSize: '10px', color: '#999', marginTop: '4px' }}>로켓 / 바닥탈출 / 슈퍼매집</div>
        </div>

        {/* 4~5등급: 특급 신호 */}
        <div style={{ flex: 1.2, background: 'white', padding: '15px', borderRadius: '8px', borderLeft: '8px solid #9C27B0', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '11px', color: '#666' }}>⚡ 특급 신호 (4~5등급)</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
            {stats.ultra.count}개 <span style={{ color: stats.ultra.avg > 0 ? '#FF5252' : '#448AFF' }}>({stats.ultra.avg}%)</span>
          </div>
          <div style={{ fontSize: '10px', color: '#999', marginTop: '4px' }}>에너지폭발 / 철벽지지</div>
        </div>

        {/* 10~12등급: 위험 신호 */}
        <div style={{ flex: 1.2, background: 'white', padding: '15px', borderRadius: '8px', borderLeft: '8px solid #34495E', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '11px', color: '#666' }}>🚨 위험 신호 (10~12등급)</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
            {stats.danger.count}개 <span style={{ color: stats.danger.avg > 0 ? '#FF5252' : '#448AFF' }}>({stats.danger.avg}%)</span>
          </div>
          <div style={{ fontSize: '10px', color: '#999', marginTop: '4px' }}>초과열 / 추세붕괴 / 이탈</div>
        </div>

        {/* 전략: 공격타점(창) */}
        <div style={{ flex: 1, background: 'white', padding: '15px', borderRadius: '8px', borderLeft: '8px solid #FF5252', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '11px', color: '#666' }}>⚔️ 공격타점 (창)</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
            {stats.attack.count}개 <span style={{ color: stats.attack.avg > 0 ? '#FF5252' : '#448AFF' }}>({stats.attack.avg}%)</span>
          </div>
          <div style={{ fontSize: '10px', color: '#999', marginTop: '4px' }}>추세 돌파형 전략</div>
        </div>

        {/* 전략: 수비타점(방패) */}
        <div style={{ flex: 1, background: 'white', padding: '15px', borderRadius: '8px', borderLeft: '8px solid #4DB6AC', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '11px', color: '#666' }}>🛡️ 수비타점 (방패)</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>
            {stats.defense.count}개 <span style={{ color: stats.defense.avg > 0 ? '#FF5252' : '#448AFF' }}>({stats.defense.avg}%)</span>
          </div>
          <div style={{ fontSize: '10px', color: '#999', marginTop: '4px' }}>저점 매수형 전략</div>
        </div>


      </div>

      
      

      <div style={{ background: 'white', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
          <thead>
            <tr style={{ background: '#2C3E50', color: 'white' }}>
              <th style={{ padding: '12px', width: '50px' }}>구분</th>
              <th style={{ width: '180px' }}>종목명(코드)</th>
              <th style={{ width: '40px' }}>시장</th>
              <th style={{ width: '60px' }}>현재가</th>
              <th style={{ width: '140px' }}>목표가 / 손절가</th>
              <th style={{ width: '40px' }}>등락률</th>
              <th style={{ width: '150px', paddingLeft: '15px' }}>선정 사유</th>
              <th style={{ width: '230px' }}>핵심 포인트</th>
              <th style={{ width: '180px' }}>추세게이지</th>
              <th style={{ width: '40px' }}>상세</th>
            </tr>
          </thead>
          <tbody>
            {stocks.map(s => (
              <React.Fragment key={s.stock_code}>
                <tr onClick={() => toggleExpand(s.stock_code)}
                    style={{ 
                      borderBottom: '1px solid #eee', 
                      cursor: 'pointer', 
                      height: '52px',
                      background: expandedIds.includes(s.stock_code) ? '#f0f4f8' : 'white' 
                    }}>
                  <td style={{ textAlign: 'center', fontSize: '18px' }}>{s.trade_icon}</td>
                  <td style={{ padding: '0 10px' }}><b>{s.stock_name}</b> <span style={{color:'#888'}}>({s.stock_code})</span></td>
                  <td style={{ textAlign: 'center' }}>{s.market_type || '코스피'}</td>
                  <td style={{ textAlign: 'right', fontWeight: 'bold' }}>{s.last_price.toLocaleString()}</td>
                  <td style={{ textAlign: 'center' }}>
                    <span style={{color:'#FF5252'}}>{(s.last_price * 1.1).toLocaleString()}</span> 
                    <span style={{color:'#ccc', margin: '0 5px'}}>|</span>
                    <span style={{color:'#448AFF'}}>{(s.last_price * 0.95).toLocaleString()}</span>
                  </td>
                  <td style={{ textAlign: 'right', color: s.change_rate > 0 ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>{s.change_rate}%</td>
                  <td style={{ padding: '0 15px', color: '#666' }}>{s.target_reason || "전략 분석 데이터"}</td>
                  <td style={{ color: '#E67E22', fontWeight: 'bold' }}>{s.display_point}</td>
                  <td style={{ padding: '0 15px' }}>{renderGauge(s.change_rate)}</td>
                  <td style={{ textAlign: 'center', color: '#bbb' }}>{expandedIds.includes(s.stock_code) ? '▲' : '▼'}</td>
                </tr>
                {expandedIds.includes(s.stock_code) && (
                  <DetailRow stock={s} getDetails={getDetailsData} />
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* 전략 상세 팝업 */}
      {selectedStock && (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10000 }}>
          <div style={{ background: 'white', width: '900px', borderRadius: '8px', padding: '25px', position: 'relative', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }}>
            <button onClick={() => setSelectedStock(null)} style={{ position: 'absolute', right: '20px', top: '20px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer' }}>&times;</button>
            
            <div style={{ fontSize: '19px', fontWeight: 'bold', paddingBottom: '12px', borderBottom: '1px solid #eee', marginBottom: '20px' }}>
               📊 {selectedStock.stock_name}({selectedStock.stock_code}) 전략분석 | <span style={{color: selectedStock.sig_color}}>{selectedStock.sig_name}</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '0.8fr 1.2fr 2.0fr', gap: '25px', alignItems: 'start' }}>
              
              {/* [1. 수급현황] */}
              <div style={{ minHeight: '120px' }}>
                <p style={{ fontSize: '0.85em', fontWeight: 'bold', borderBottom: '1px solid #4DB6AC', marginBottom: '8px', paddingBottom: '3px' }}>👥 수급 현황</p>
                <div style={{ fontSize: '0.82em', lineHeight: '1.8' }}>
                  외인: <span style={{ color: selectedStock.foreign_net_5d > 0 ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>{selectedStock.foreign_net_5d?.toLocaleString()}</span> 
                  {selectedStock.foreign_net_5d > 0 && (
                    <span style={{ background: '#FF5252', color: 'white', padding: '1px 4px', borderRadius: '3px', fontSize: '0.7em', fontWeight: 'bold', marginLeft: '5px' }}>👽 외인매집</span>
                  )}
                  <br />
                  기관: <span style={{ color: selectedStock.institution_net_5d > 0 ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>{selectedStock.institution_net_5d?.toLocaleString()}</span>
                </div>
              </div>

              {/* [2. 핵심 매물대] */}
              <div style={{ minHeight: '120px' }}>
                <p style={{ fontSize: '0.85em', fontWeight: 'bold', borderBottom: '1px solid #FFD54F', marginBottom: '8px', paddingBottom: '3px' }}>🧱 핵심 매물대</p>
                {[0.04, 0.02, 0, -0.02, -0.04].map((offset, i) => {
                  const pct = [12, 25, 48, 10, 5][i]; // 비중 데이터는 서버에서 가져올 수 있다면 대체 필요
                  const barColor = pct > 15 ? "#FF5252" : "#4DB6AC"; 
                  const price = Math.round(selectedStock.last_price * (1 + offset));
                  return (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', height: '22px', marginBottom: '2px' }}>
                      <div style={{ width: '50px', fontSize: '10px', color: '#aaa', textAlign: 'right', marginRight: '5px' }}>{price.toLocaleString()}</div>
                      <div style={{ flexGrow: 1, background: '#f0f0f0', height: '8px', borderRadius: '2px' }}>
                        <div style={{ width: `${pct}%`, background: barColor, height: '100%', borderRadius: '2px' }}></div>
                      </div>
                      <div style={{ width: '30px', fontSize: '9px', color: '#888', marginLeft: '5px' }}>{pct}%</div>
                    </div>
                  );
                })}
              </div>

              {/* [3. 지표 판독 가이드] */}
              <div style={{ minHeight: '120px' }}>
                <p style={{ fontSize: '0.85em', fontWeight: 'bold', borderBottom: '1px solid #9575CD', marginBottom: '8px', paddingBottom: '3px' }}>💡 지표 판독 가이드</p>
                
                {/* RSI */}
                <div style={{ display: 'flex', alignItems: 'center', height: '22px', fontSize: '0.78em', marginBottom: '2px' }}>
                  <div style={{ minWidth: '130px', fontWeight: 'bold' }}>⚠️ RSI({Math.round(selectedStock.rsi)})</div>
                  <div style={{ marginLeft: '10px' }}>
                    <span style={{ color: selectedStock.rsi > 70 ? '#FF5252' : '#4DB6AC', fontWeight: 'bold' }}>
                      {selectedStock.rsi > 70 ? "과매수" : "정상"}
                    </span>: {selectedStock.rsi > 70 ? "수익실현 고려" : "추세 유지 중"}
                  </div>
                </div>

                {/* R-SQ */}
                <div style={{ display: 'flex', alignItems: 'center', height: '22px', fontSize: '0.78em', marginBottom: '2px' }}>
                  <div style={{ minWidth: '130px', fontWeight: 'bold' }}>📈 R-SQ({selectedStock.r_square?.toFixed(2)})</div>
                  <div style={{ marginLeft: '10px' }}>
                    <span style={{ color: selectedStock.r_square > 0.6 ? '#FF5252' : '#888', fontWeight: 'bold' }}>{selectedStock.r_square > 0.6 ? "강한상승" : "추세준비"}</span>: 홀딩 유지 권장
                  </div>
                </div>

                {/* BB상단 */}
                <div style={{ display: 'flex', alignItems: 'center', height: '22px', fontSize: '0.78em', marginBottom: '2px' }}>
                  <div style={{ minWidth: '130px', fontWeight: 'bold' }}>🚀 BB상단({selectedStock.bb_upper?.toLocaleString()})</div>
                  <div style={{ marginLeft: '10px' }}>
                    <span style={{ color: selectedStock.last_price > selectedStock.bb_upper ? '#FF5252' : '#888', fontWeight: 'bold' }}>상단돌파</span>: 강한 슈팅 구간 진입 (보유자 영역)
                  </div>
                </div>

                {/* LRL */}
                <div style={{ display: 'flex', alignItems: 'center', height: '22px', fontSize: '0.78em', marginBottom: '2px' }}>
                  <div style={{ minWidth: '130px', fontWeight: 'bold' }}>🎯 LRL({selectedStock.lrl?.toLocaleString()})</div>
                  <div style={{ marginLeft: '10px' }}>
                    <span style={{ color: selectedStock.last_price > selectedStock.lrl ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>{selectedStock.last_price > selectedStock.lrl ? "상방추세" : "하방추세"}</span>: 
                    중심축 대비 {(((selectedStock.last_price / selectedStock.lrl) - 1) * 100).toFixed(1)}% 위치
                  </div>
                </div>

                {/* 이평선 */}
                <div style={{ display: 'flex', alignItems: 'center', height: '22px', fontSize: '0.78em', marginBottom: '2px' }}>
                  <div style={{ minWidth: '130px', fontWeight: 'bold' }}>📊 이평선({selectedStock.ma_short?.toLocaleString()})</div>
                  <div style={{ marginLeft: '10px' }}>
                    <span style={{ color: selectedStock.last_price > selectedStock.ma_short ? '#4DB6AC' : '#FF5252', fontWeight: 'bold' }}>{selectedStock.last_price > selectedStock.ma_short ? "지지" : "이탈"}</span>: 하방 경직성 확보
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>
      )}
      {/* 전략 상세 팝업 */}

      
    </div>
  );
};

const DetailRow = React.memo(({ stock, getDetails }) => {
  const d = useMemo(() => getDetails(stock), [stock, getDetails]);
  if (!d) return null;
  return (
    <tr>
      <td colSpan="10" style={{ background: '#f8f9fa', padding: '0px', borderBottom: '2px solid #2C3E50' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 2.5fr', gap: '1px', background: '#dee2e6' }}>
          <div style={{ background: 'white', padding: '10px 15px' }}>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#2C3E50', marginBottom: '8px' }}>👥 5일 수급 분석</div>
            <div style={{ fontSize: '12px', lineHeight: '1.8' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>외인</span>
                <span style={{ color: d.f_stat.clr, fontWeight: 'bold' }}>{d.f_stat.txt} ({stock.foreign_net_5d?.toLocaleString()})</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>기관</span>
                <span style={{ color: d.i_stat.clr, fontWeight: 'bold' }}>{d.i_stat.txt} ({stock.institution_net_5d?.toLocaleString()})</span>
              </div>
            </div>
          </div>
          <div style={{ background: 'white', padding: '10px 15px' }}>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#2C3E50', marginBottom: '8px' }}>🧱 매물대 (금액순)</div>
            {d.supplyPoints.map((p, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', marginBottom: '3px', height: '14px' }}>
                <span style={{ fontSize: '10px', width: '55px', color: '#888', textAlign: 'right', marginRight: '8px' }}>{p.price.toLocaleString()}원</span>
                <div style={{ flex: 1, height: '6px', background: '#eee', borderRadius: '3px' }}>
                  <div style={{ width: `${p.volumePct}%`, height: '100%', background: i < 2 ? '#FF5252' : '#4DB6AC', borderRadius: '3px' }}></div>
                </div>
                <span style={{ fontSize: '10px', width: '25px', textAlign: 'right', marginLeft: '5px', color: '#666' }}>{p.volumePct}%</span>
              </div>
            ))}
          </div>
          <div style={{ background: 'white', padding: '10px 15px' }}>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#2C3E50', marginBottom: '8px' }}>⚠️ 초보자를 위한 핵심 지표 판독</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {d.guides.map((g, i) => (
                <div key={i} style={{ fontSize: '11px', display: 'flex', borderBottom: '1px solid #f0f0f0', paddingBottom: '2px' }}>
                  <span style={{ fontWeight: 'bold', width: '100px', color: '#555' }}>{g.label}</span>
                  <span style={{ color: '#E67E22', fontWeight: 'bold', marginRight: '10px' }}>[{g.val}]</span>
                  <span style={{ color: '#666' }}>{g.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </td>
    </tr>
  );
});

export default App;
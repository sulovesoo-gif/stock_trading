import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';

const App = () => {
  const [stocks, setStocks] = useState([]);
  const [topPicks, setTopPicks] = useState([]);
  const [selectedStock, setSelectedStock] = useState(null);
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
      const res = await axios.get('http://168.107.5.155:8000/api/signals');
      const processedData = res.data.map(s => {
        const { rsi, r_square, lrl, bb_upper, bb_lower, last_price, ma_short, total_shares, detected_time, volume_ratio, foreign_net_5d, institution_net_5d } = s;
        const lrl_gap = s.lrl ? ((s.last_price - s.lrl) / s.lrl) * 100 : 0;

        let points = [];
        let minGrade = 99; 

        // --- [매수/매도 시그널 전수 조사: 누적] ---
        // 0️⃣ 데이터 부재 및 분석 불가 (등급외)
        // 핵심 지표인 RSI와 R-Square가 모두 0이거나 데이터가 유실된 경우
        if (rsi === 0 && r_square === 0 && lrl === 0) {
          points.push("🔍 분석불가: 데이터 대기");
        }else{
          // 1️⃣ 로켓 (1등급)
          if (r_square > 0.7 && last_price > lrl && last_price > bb_upper && (foreign_net_5d > 0 || institution_net_5d > 0)) {
            points.push("🚀로켓"); if (minGrade > 1) minGrade = 1;
          }
          // 2️⃣ 바닥탈출 (2등급)
          if (rsi < 35 && r_square < 0.25 && last_price > ma_short) {
            points.push("✨바닥탈출"); if (minGrade > 2) minGrade = 2;
          }
          // 3️⃣ 슈퍼매집 (3등급)
          if (last_price > lrl && r_square >= 0.8 && (foreign_net_5d > 0 && institution_net_5d > 0)) {
            points.push("💎슈퍼매집"); if (minGrade > 3) minGrade = 3;
          }
          // 4️⃣ 에너지폭발 (4등급)
          if ((bb_upper - bb_lower) / last_price < 0.05 && last_price > bb_upper && volume_ratio > 250) {
            points.push("🧨에너지폭발"); if (minGrade > 4) minGrade = 4;
          }
          // 5️⃣ 세력철벽지지 (5등급)
          if (last_price <= lrl * 1.01 && last_price >= lrl * 0.99 && (foreign_net_5d > 0 || institution_net_5d > 0)) {
            points.push("🛡️철벽지지"); if (minGrade > 5) minGrade = 5;
          }
          // 10️⃣ 초과열매도 (10등급)
          if (rsi > 78 && last_price > bb_upper * 1.05) {
            points.push("💀초과열매도"); if (minGrade > 10) minGrade = 10;
          }
          // 11️⃣ 추세붕괴 (11등급)
          if (last_price < lrl * 0.95 && foreign_net_5d < 0 && institution_net_5d < 0) {
            points.push("📉추세붕괴"); if (minGrade > 11) minGrade = 11;
          }
          // 12️⃣ 세력이탈 (12등급)
          if (rsi > 70 && foreign_net_5d < -50000) {
            points.push("⚠️세력이탈"); if (minGrade > 12) minGrade = 12;
          }
        }

        const is_super = minGrade >= 1 && minGrade <= 3;
        const is_ultra = minGrade === 4 || minGrade === 5;
        const is_sell_strong = minGrade >= 10;

        return { 
          ...s, 
          total_shares,
          detected_time,
          lrl_gap,
          sig_grade: minGrade === 99 ? 9 : minGrade, 
          sig_name: gradeNames[minGrade] || "🔍 일반",
          sig_color: gradeColors[minGrade] || "#888888",
          points_count: points.length, // 정렬 2순위 데이터
          display_point: points.length > 0 ? points.join(" & ") : "관망 유지",
          trade_icon: is_ultra ? '⚡' : (is_super ? '💎' : (is_sell_strong ? '🚫' : '👀')),
          strat_type: (is_super || is_ultra) ? '창' : (is_sell_strong ? '방패' : '관망'),
          is_super,
          is_ultra,
          is_sell_strong
        };
      });

      const sortedData = [...processedData].sort((a, b) => {
        // 1순위: 시그널 등급 (sig_grade) 오름차순 (예: 1등급이 최상단)
        if (a.sig_grade !== b.sig_grade) {
          return a.sig_grade - b.sig_grade;
        }
        // 2순위: 점수 (points_count) 내림차순 (점수 높은 순)
        if (b.points_count !== a.points_count) {
          return b.points_count - a.points_count;
        }
        // 3순위: LRL 대비 등락률 (이격도 낮은 순 - 바닥권 종목 우선)
        if (Math.abs(a.lrl_gap - b.lrl_gap) > 0.01) { // 미세 차이 무시 방지
          return a.lrl_gap - b.lrl_gap;
        }
        // 4순위: 등락률 (change_rate) 내림차순 (수익률/탄력 높은 순)
        return (b.change_rate || 0) - (a.change_rate || 0);
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

  const getDetailsData = useCallback((s) => {
    if (!s) return null;

    // 상장주식수 대비 비율 계산 함수 (헌법 준수: 비율에 따른 단계별 문구)
    const getScoring = (net_5d, total_shares) => {
      const n_net = Number(net_5d) || 0;
      const n_total = Number(total_shares) || 0;

      // 상장주식수가 0인 경우(데이터 미도달) 비율 계산만 생략하고 수량은 반환
      if (n_total === 0) {
        return { 
          txt: n_net > 0 ? "🔴 유입중" : (n_net < 0 ? "🔵 유출중" : "-"), 
          clr: n_net > 0 ? "#FF5252" : (n_net < 0 ? "#448AFF" : "#888"), 
          pct: "0", 
          val: n_net 
        };
      }
      
      const pctRaw = (n_net / n_total) * 100;
      const pct = pctRaw.toFixed(2);
      const comparePct = parseFloat(pct);

      let status = { txt: "🔵 순매도", clr: "#448AFF" };
      if (comparePct >= 0.5) status = { txt: "👑 주도권 장악", clr: "#FF5252" };
      else if (comparePct >= 0.2) status = { txt: "🔥 집중매집", clr: "#FF5252" };
      else if (comparePct >= 0.05) status = { txt: "📈 수급개선", clr: "#FF5252" };
      else if (comparePct > 0) status = { txt: "🔴 소폭유입", clr: "#FF5252" };
      else if (comparePct <= -1.0) status = { txt: "💀 주도권 상실", clr: "#448AFF" };

      return { ...status, pct, val: n_net };
    };

    const foreign_stats = getScoring(s.foreign_net_5d, s.total_shares);
    const institution_stats = getScoring(s.institution_net_5d, s.total_shares);

    // [기존 매물대 오프셋 및 지표 가이드 유지]
    const offsets = [0.04, 0.02, 0, -0.02, -0.04];
    const rawVolumes = [12, 25, 48, 10, 5]; 
    const supplyPoints = offsets.map((offset, i) => ({
      price: Math.round(s.last_price * (1 + offset)),
      volumePct: rawVolumes[i]
    }));

    const guides = [
      { label: "과열 유무(RSI)", val: s.rsi !== null ? Math.round(s.rsi) : "-", desc: s.rsi > 70 ? "⚠️ 과매수: 수익실현 고려" : "✅ 정상: 추세 유지 중" },
      { label: "추세 강도(R-SQ)", val: s.r_square !== null ? s.r_square.toFixed(2) : "-", desc: s.r_square > 0.6 ? "🚀 강한상승: 홀딩 유지" : "⏳ 추세준비: 에너지 응축" },
      { label: "폭발 구간(상단)", val: s.bb_upper?.toLocaleString() || "-", desc: s.last_price > s.bb_upper ? "🔥 상단돌파: 슈팅 구간" : "✅ 정상: 밴드 내 이동" },
      { label: "중심 축(위치)", val: s.lrl?.toLocaleString() || "-", desc: s.last_price > s.lrl ? "📈 상방추세: 중심 위" : "📉 하방추세: 중심 아래" },
      { label: "지지선(안착)", val: s.ma_short?.toLocaleString() || "-", desc: s.last_price > s.ma_short ? "🛡️ 지지: 하방경직 확보" : "⚠️ 이탈: 주의 필요" }
    ];

    return { supplyPoints, foreign_stats, institution_stats, guides };
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

      
      

      <div style={{ background: 'white', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', overflow: 'auto', width: '100%', WebkitOverflowScrolling: 'touch' }}>
        <table style={{ width: '100%', minWidth: '1100px', borderCollapse: 'collapse', fontSize: '12px',  }}>
          <thead>
            <tr style={{ background: '#2C3E50', color: 'white' }}>
              <th style={{ padding: '12px', width: '50px' }}>구분</th>
              <th style={{ width: '180px' }}>종목명(코드)</th>
              <th style={{ width: '40px' }}>시장</th>
              <th style={{ width: '80px' }}>포착시간</th>
              <th style={{ width: '60px' }}>현재가</th>
              <th style={{ width: '140px' }}>목표가 / 손절가</th>
              <th style={{ width: '100px' }}>등락률 (LRL)</th>
              <th style={{ width: '180px', paddingLeft: '15px' }}>선정 사유</th>
              <th style={{ width: '240px' }}>핵심 포인트</th>
              <th style={{ width: '80px' }}>추세게이지</th>
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




                  <td style={{ padding: '0 10px' }}>
                    <a href={`https://finance.naver.com/item/main.naver?code=${s.stock_code}`} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}>
                      <b>{s.stock_name}</b> <span style={{color:'#888'}}>({s.stock_code})</span>
                    </a>
                  </td>
                  <td style={{ textAlign: 'center' }}>{s.market_type || '코스피'}</td>
                  <td style={{ textAlign: 'center', color: '#888' }}>{s.detected_time}</td>
                  <td style={{ textAlign: 'right', fontWeight: 'bold' }}>{s.last_price.toLocaleString()}</td>
                  <td style={{ textAlign: 'center' }}>
                    <span style={{color:'#FF5252'}}>{(s.last_price * 1.1).toLocaleString()}</span> 
                    <span style={{color:'#ccc', margin: '0 5px'}}>|</span>
                    <span style={{color:'#448AFF'}}>{(s.last_price * 0.95).toLocaleString()}</span>
                  </td>
                  {/* <td style={{ textAlign: 'right', color: s.change_rate > 0 ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>{s.change_rate}%</td> */}
                  <td style={{ textAlign: 'right', color: s.change_rate > 0 ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>{s.change_rate}% <span style={{ color: s.lrl_gap > 0 ? '#E67E22' : '#27AE60', fontSize: '10px' }}>(LRL: {s.lrl_gap}%)</span></td>
                  {/* <td style={{ textAlign: 'right', padding: '0 10px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', lineHeight: '1.2' }}>
                      <span style={{ color: s.change_rate > 0 ? '#FF5252' : '#448AFF', fontWeight: 'bold' }}>
                        {s.change_rate}%
                      </span>
                      <span style={{ color: s.lrl_gap > 0 ? '#E67E22' : '#27AE60', fontSize: '10px' }}>
                        LRL: {s.lrl_gap}%
                      </span>
                    </div>
                  </td> */}
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
      {selectedStock && (() => {
        const d = getDetailsData(selectedStock);
        return (
          <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.7)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10000 }}>
            <div style={{ background: 'white', width: '900px', borderRadius: '12px', padding: '30px', position: 'relative' }}>
              <button onClick={() => setSelectedStock(null)} style={{ position: 'absolute', right: '20px', top: '10px', border: 'none', background: 'none', fontSize: '28px', cursor: 'pointer', color: '#999' }}>&times;</button>
              
              <div style={{ fontSize: '15px', fontWeight: 'bold', marginBottom: '2px', paddingBottom: '5px', borderBottom: '2px solid #f0f0f0' }}>
                  📊 {selectedStock.stock_name}(<span style={{fontSize: '14px', color: '#888', fontWeight: 'normal'}}>{selectedStock.stock_code}</span>) 전략 분석 
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '0.8fr 1.2fr 2fr', gap: '30px' }}>
                {/* 수급 */}
                <div style={{ fontSize: '10px', lineHeight: '2.5' }}>
                  <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#2C3E50', marginBottom: '10px', borderBottom: '1px solid #4DB6AC', paddingBottom: '3px' }}>👥 5일 수급 분석</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ color: '#555' }}>외인(5일 누적)</span> 
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <span style={{ color: d.foreign_stats.clr, fontWeight: 'bold', fontSize: '14px' }}>
                        {d.foreign_stats.val?.toLocaleString()} <span style={{ fontSize: '12px', fontWeight: 'normal' }}>({d.foreign_stats.pct}%)</span> 
                      </span>
                      {parseFloat(d.foreign_stats.pct) >= 0.2 && (
                        <span style={{ background: d.foreign_stats.clr, color: 'white', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', marginLeft: '10px' }}>{d.foreign_stats.txt}</span>
                      )}
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ color: '#555' }}>기관(5일 누적)</span> 
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <span style={{ color: d.institution_stats.clr, fontWeight: 'bold', fontSize: '14px' }}>
                        {d.institution_stats.val?.toLocaleString()} <span style={{ fontSize: '12px', fontWeight: 'normal' }}>({d.institution_stats.pct}%)</span>
                      </span>
                      {parseFloat(d.institution_stats.pct) >= 0.2 && (
                        <span style={{ background: d.institution_stats.clr, color: 'white', padding: '2px 6px', borderRadius: '4px', fontSize: '11px', fontWeight: 'bold', marginLeft: '10px' }}>{d.institution_stats.txt}</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* 매물대 - 높이 24px 고정 */}
                <div>
                  <p style={{ fontSize: '13px', fontWeight: 'bold', color: '#2C3E50', borderBottom: '1px solid #FFD54F', paddingBottom: '5px', marginBottom: '12px' }}>🧱 핵심 매물대</p>
                  {d.supplyPoints.map((p, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', height: '18px', marginBottom: '4px' }}>
                      <div style={{ width: '60px', fontSize: '11px', color: '#999', textAlign: 'right', marginRight: '10px' }}>{p.price.toLocaleString()}</div>
                      <div style={{ flexGrow: 1, background: '#f0f0f0', height: '10px', borderRadius: '5px' }}>
                        <div style={{ width: `${p.volumePct}%`, background: p.volumePct > 15 ? "#FF5252" : "#4DB6AC", height: '100%', borderRadius: '5px' }}></div>
                      </div>
                      <div style={{ width: '35px', fontSize: '10px', color: '#666', marginLeft: '10px', textAlign: 'right' }}>{p.volumePct}%</div>
                    </div>
                  ))}
                </div>

                {/* 판독 가이드 - 높이 24px 고정 */}
                <div>
                  <p style={{ fontSize: '13px', fontWeight: 'bold', color: '#2C3E50', borderBottom: '1px solid #9575CD', paddingBottom: '5px', marginBottom: '12px' }}>💡 지표 판독 가이드</p>
                  {d.guides.map((g, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', height: '18px', marginBottom: '4px' }}>
                      <div style={{ width: '110px', fontWeight: 'bold', fontSize: '12px', color: '#555' }}>{g.label}</div>
                      <div style={{ width: '45px', fontWeight: 'bold', color: '#E67E22', textAlign: 'center', fontSize: '12px' }}>[{g.val}]</div>
                      <div style={{ marginLeft: '10px', color: '#666', fontSize: '12px' }}>{g.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );
      })()}
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
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.3fr 2.5fr', gap: '1px', background: '#dee2e6' }}>
          
          {/* [1. 수급 분석] */}
          <div style={{ background: 'white', padding: '12px 15px' }}>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#2C3E50', marginBottom: '10px', borderBottom: '1px solid #4DB6AC', paddingBottom: '3px' }}>👥 5일 수급 분석</div>
            <div style={{ fontSize: '12px', lineHeight: '2.2' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: '#666' }}>외인(5일 누적)</span>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ color: d.foreign_stats.clr, fontWeight: 'bold' }}>
                    {d.foreign_stats.val?.toLocaleString()}({d.foreign_stats.pct}%)
                  </span>
                  {parseFloat(d.foreign_stats.pct) >= 0.2 && (
                    <span style={{ background: d.foreign_stats.clr, color: 'white', padding: '1px 4px', borderRadius: '3px', fontSize: '0.7em', fontWeight: 'bold', marginLeft: '5px' }}>{d.foreign_stats.txt}</span>
                  )}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: '#666' }}>기관(5일 누적)</span>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <span style={{ color: d.institution_stats.clr, fontWeight: 'bold' }}>
                    {d.institution_stats.val?.toLocaleString()}({d.institution_stats.pct}%)
                  </span>
                  {parseFloat(d.institution_stats.pct) >= 0.2 && (
                    <span style={{ background: d.institution_stats.clr, color: 'white', padding: '1px 4px', borderRadius: '3px', fontSize: '0.7em', fontWeight: 'bold', marginLeft: '5px' }}>{d.institution_stats.txt}</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* [2. 핵심 매물대 - 높이 20px씩] */}
          <div style={{ background: 'white', padding: '12px 15px' }}>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#2C3E50', marginBottom: '10px', borderBottom: '1px solid #FFD54F', paddingBottom: '3px' }}>🧱 핵심 매물대</div>
            {d.supplyPoints.map((p, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', height: '20px', marginBottom: '2px' }}>
                <span style={{ fontSize: '10px', width: '50px', color: '#999', textAlign: 'right', marginRight: '8px' }}>{p.price.toLocaleString()}</span>
                <div style={{ flex: 1, height: '8px', background: '#eee', borderRadius: '4px' }}>
                  <div style={{ width: `${p.volumePct}%`, height: '100%', background: p.volumePct > 15 ? '#FF5252' : '#4DB6AC', borderRadius: '4px' }}></div>
                </div>
                <span style={{ fontSize: '9px', width: '25px', textAlign: 'right', marginLeft: '5px', color: '#888' }}>{p.volumePct}%</span>
              </div>
            ))}
          </div>

          {/* [3. 지표 판독 가이드 - 높이 20px씩] */}
          <div style={{ background: 'white', padding: '12px 15px' }}>
            <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#2C3E50', marginBottom: '10px', borderBottom: '1px solid #9575CD', paddingBottom: '3px' }}>💡 지표 판독 가이드</div>
            {d.guides.map((g, i) => (
              <div key={i} style={{ fontSize: '11px', display: 'flex', alignItems: 'center', height: '20px', marginBottom: '2px' }}>
                <span style={{ fontWeight: 'bold', width: '100px', color: '#555' }}>{g.label}</span>
                <span style={{ color: '#E67E22', fontWeight: 'bold', width: '50px', textAlign: 'center' }}>[{g.val}]</span>
                <span style={{ color: '#666', flex: 1, marginLeft: '5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{g.desc}</span>
              </div>
            ))}
          </div>

        </div>
      </td>
    </tr>
  );
});

export default App;
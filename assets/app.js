/* 互動版腳本：讀取頁面上原本的表格（rt-best／rt-log／rt-promo）自動產生分頁、目的地卡、篩選與趨勢圖。
   每日更新只要維持表格的 class 與 data-label、各區塊 .card 的 data-tab，就不需要改這段腳本。 */
(function(){
  var $=function(s,r){return (r||document).querySelector(s)}, $$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
  var wrap=$('.wrap'); if(!wrap) return;
  var TABS=[['overview','總覽'],['prices','價格'],['trend','趨勢'],['promo','促銷'],['leave','請假窗口'],['info','行李・資料・來源']];
  function guess(card){
    var h=$('h2',card), t=h?h.textContent:'';
    if(/🏆|🗾/.test(t)) return 'prices'; if(/📈/.test(t)) return 'trend'; if(/🔥/.test(t)) return 'promo';
    if(/🗓/.test(t)) return 'leave'; if(/🧳|🧩|🔗/.test(t)) return 'info'; return 'overview';
  }
  var cards=$$('.wrap > .card'); cards.forEach(function(c){ if(!c.dataset.tab) c.dataset.tab=guess(c); });
  function num(s){ var m=(s||'').replace(/\s/g,'').match(/\d{1,3}(?:,\d{3})+|\d{4,}/); return m?parseInt(m[0].replace(/,/g,''),10):null; }
  function cell(tr,label){ return $$('td',tr).filter(function(td){return td.getAttribute('data-label')===label})[0]; }
  function leaveN(tr){ var td=cell(tr,'請假'); var m=td&&td.textContent.match(/請\s*(\d)\s*天/); return m?+m[1]:null; }
  function daysN(tr){ var td=cell(tr,'天數')||cell(tr,'日期'); var m=td&&td.textContent.match(/(\d)\s*天/); return m?+m[1]:null; }
  function firstLine(td){ var s=''; for(var n=td.firstChild;n;n=n.nextSibling){ if(n.nodeName==='BR') break; s+=n.textContent; } return s.trim(); }

  /* ---------- 價格卡片 ---------- */
  var DETAIL=['班次','票價','行李費','備註'];
  var bestRows=[];
  $$('table.rt-best').forEach(function(tb){
    tb.classList.add('cards');
    $$('tr',tb).forEach(function(tr,i){
      if(tr.classList.contains('hd')||$('th',tr)) return;
      var tds=$$('td',tr); tds.forEach(function(td){ if(DETAIL.indexOf(td.getAttribute('data-label'))>=0) td.classList.add('x'); });
      var tg=document.createElement('td'); tg.className='tg';
      var b=document.createElement('button'); b.type='button'; b.className='more'; b.textContent='看班次、行李費與備註 ▾'; b.setAttribute('aria-expanded','false');
      b.onclick=function(){ var o=tr.classList.toggle('open'); b.setAttribute('aria-expanded',o); b.textContent=o?'收起 ▴':'看班次、行李費與備註 ▾'; };
      tg.appendChild(b); tr.appendChild(tg);
      var d=$('td.dest',tr), tot=$('td.total',tr), air=$('td.air',tr), dt=cell(tr,'日期');
      bestRows.push({tr:tr,table:tb,idx:i,dest:d?d.textContent.trim():'',price:tot?num(tot.textContent):null,ref:tot?/參考/.test(tot.textContent):false,
        approx:tot?/≈|約|估/.test(tot.textContent):false,air:air?air.textContent.trim():'',date:dt?dt.textContent.trim():'',leave:leaveN(tr),days:daysN(tr),cheap:tot?tot.textContent.trim():''});
    });
  });

  /* ---------- 每日紀錄 → 趨勢 ---------- */
  var log=$('table.rt-log'), series={}, dates=[];
  if(log){
    var heads=$$('tr.hd th',log).map(function(th){return th.textContent.trim()}).slice(1);
    var rows=$$('tr',log).filter(function(tr){return !tr.classList.contains('hd')&&!$('th',tr)}).reverse();
    heads.forEach(function(h){series[h]=[]});
    rows.forEach(function(tr){
      var dc=$('td.date',tr)||$('td',tr); dates.push(dc.textContent.trim());
      heads.forEach(function(h){ var td=cell(tr,h); series[h].push(td?num(firstLine(td)):null); });
    });
  }
  function change(dest){
    var s=series[dest]; if(!s) return null; var v=s.filter(function(x){return x!=null});
    if(v.length<2||s[s.length-1]==null) return null; return s[s.length-1]-v[v.length-2];
  }
  function chgHTML(c){ if(c==null) return ''; if(c===0) return '<span class="chg flat">與前次持平</span>';
    return '<span class="chg '+(c>0?'up':'down')+'">'+(c>0?'▲ ':'▼ ')+Math.abs(c).toLocaleString()+' 比前次</span>'; }

  /* ---------- 總覽：目的地卡 ---------- */
  var take=cards.filter(function(c){return c.dataset.tab==='overview'})[0];
  var by={}, order=[];
  bestRows.forEach(function(r){ if(!r.dest) return; if(!by[r.dest]){by[r.dest]=[];order.push(r.dest)} by[r.dest].push(r); });
  var picks=order.map(function(d){
    var rs=by[d].slice().sort(function(a,b){ return (a.ref-b.ref)||((a.price||1e9)-(b.price||1e9)); }); return rs[0];
  }).sort(function(a,b){return (a.ref-b.ref)||((a.price||1e9)-(b.price||1e9))});
  var ov=document.createElement('div'); ov.className='card'; ov.dataset.tab='overview';
  ov.innerHTML='<h2>各目的地最低價（含行李）</h2><p class="small" style="margin-top:0">點一下目的地，看這個地方所有日期與詳情。</p><div class="dgrid" id="dgrid"></div>';
  var g=$('#dgrid',ov);
  picks.forEach(function(r,i){
    var t=document.createElement('button'); t.type='button'; t.className='dtile'+(i===0&&!r.ref?' top':'');
    var lv=(r.days?'<span class="tag t-fsc">玩 '+r.days+' 天</span>':'')+(r.leave!=null?'<span class="tag '+(r.leave<=2?'t-best':'t-other')+'">請 '+r.leave+' 天</span>':'');
    t.innerHTML='<span class="n">'+r.dest+(i===0&&!r.ref?' <span class="tag t-best">最便宜</span>':'')+'</span>'+
      '<span class="p'+(r.ref?' ref':'')+'">'+(r.ref?'參考 ':'')+(r.price?(r.approx?'≈ ':'')+'NT$'+r.price.toLocaleString():r.cheap)+'</span>'+
      chgHTML(change(r.dest))+'<span class="m">'+r.air+'<br>'+r.date.replace(/^20\d\d\//,'')+'</span><span class="row">'+lv+'</span>';
    t.onclick=function(){ setFilter('dest',r.dest); show('prices'); };
    g.appendChild(t);
  });
  if(take) take.before(ov); else wrap.insertBefore(ov,wrap.querySelector('.card'));
  // 最省假窗口捷徑
  var oneWins=$$('[data-tab="leave"] .win.one');
  if(oneWins.length){
    var q=document.createElement('div'); q.innerHTML='<div class="sec-t">有價格的省假窗口</div><div class="grid"></div>';
    oneWins.forEach(function(w){ if(/\d{1,3},\d{3}/.test(w.textContent)) $('.grid',q).appendChild(w.cloneNode(true)); });
    if($('.grid',q).children.length) ov.appendChild(q);
  }

  /* ---------- 價格篩選 ---------- */
  var F={dest:'all',leave:'all',days:'all',sort:'def'};
  function uniq(k){ var s={}; bestRows.forEach(function(r){ if(r[k]!=null) s[r[k]]=1; }); return Object.keys(s).map(Number).sort(function(a,b){return a-b}); }
  var leaveOpts=uniq('leave'), dayOpts=uniq('days');
  var priceCards=$$('.card[data-tab="prices"]');
  var bar=document.createElement('div'); bar.className='fbar';
  function grp(key,label,opts){
    var s='<span class="lbl">'+label+'</span>';
    opts.forEach(function(o){ s+='<button type="button" data-k="'+key+'" data-v="'+o[0]+'" aria-pressed="'+(F[key]===o[0])+'">'+o[1]+'</button>'; });
    return s;
  }
  bar.innerHTML=grp('dest','目的地',[['all','全部']].concat(order.map(function(d){return [d,d]})))+'<span class="sp"></span>'+
    grp('leave','請假',[['all','不限']].concat(leaveOpts.map(function(n){return [String(n),'請 '+n+' 天']})))+'<span class="sp"></span>'+
    (dayOpts.length>1?grp('days','天數',[['all','不限']].concat(dayOpts.map(function(n){return [String(n),'玩 '+n+' 天']})))+'<span class="sp"></span>':'')+
    grp('sort','排序',[['def','預設'],['price','價格低到高'],['leave','請假少優先']]);
  bar.addEventListener('click',function(e){ var b=e.target.closest('button'); if(b) setFilter(b.dataset.k,b.dataset.v); });
  var emptyMsg=document.createElement('p'); emptyMsg.className='empty'; emptyMsg.hidden=true; emptyMsg.textContent='沒有符合條件的日期，換個請假天數或目的地看看。';
  if(priceCards[0]){ var h2=$('h2',priceCards[0]); h2.after(bar); bar.after(emptyMsg); }
  function setFilter(k,v){
    F[k]=v; $$('button',bar).forEach(function(b){ if(b.dataset.k===k) b.setAttribute('aria-pressed',b.dataset.v===v); }); applyF();
  }
  function applyF(){
    var vis=0;
    bestRows.forEach(function(r){
      var ok=(F.dest==='all'||r.dest===F.dest)&&(F.leave==='all'||String(r.leave)===F.leave)&&(F.days==='all'||String(r.days)===F.days);
      r.tr.hidden=!ok; if(ok) vis++;
    });
    $$('table.rt-best').forEach(function(tb){
      var rs=bestRows.filter(function(r){return r.table===tb});
      rs.sort(function(a,b){
        if(F.sort==='price') return (a.price||1e9)-(b.price||1e9);
        if(F.sort==='leave') return ((a.leave||9)-(b.leave||9))||((a.price||1e9)-(b.price||1e9));
        return a.idx-b.idx;
      });
      var body=rs.length?rs[0].tr.parentNode:null; rs.forEach(function(r){ body.appendChild(r.tr); });
      var card=tb.closest('.card'); var any=rs.some(function(r){return !r.tr.hidden});
      if(card!==priceCards[0]) card.dataset.empty=any?'':'1';
    });
    emptyMsg.hidden=vis>0;
    if(current==='prices') show('prices',true);
  }

  /* ---------- 促銷：預設隱藏已結束 ---------- */
  var promo=$('table.rt-promo'), showEnded=false;
  if(promo){
    var pr=$$('tr',promo).filter(function(tr){return !tr.classList.contains('hd')&&!$('th',tr)});
    var ended=pr.filter(function(tr){return /已結束/.test(tr.textContent)}); ended.forEach(function(tr){tr.classList.add('ended')});
    var pb=document.createElement('div'); pb.className='fbar';
    pb.innerHTML='<span class="lbl">進行中 '+(pr.length-ended.length)+' 則</span><button type="button" aria-pressed="false">也顯示已結束（'+ended.length+'）</button>';
    var btn=$('button',pb); btn.onclick=function(){ showEnded=!showEnded; btn.setAttribute('aria-pressed',showEnded); ended.forEach(function(tr){tr.hidden=!showEnded}); };
    ended.forEach(function(tr){tr.hidden=true});
    var pc=promo.closest('.card'); $('h2',pc).after(pb);
  }

  /* ---------- 趨勢圖 ---------- */
  if(log && dates.length){
    var tc=log.closest('.card'), box=document.createElement('div'); box.className='trend';
    Object.keys(series).forEach(function(dest){
      var s=series[dest], pts=s.map(function(v,i){return v==null?null:[i,v]}).filter(Boolean);
      var el=document.createElement('div'); el.className='tcard';
      var last=s[s.length-1], c=change(dest);
      var W=200,H=64,P=6, vs=pts.map(function(p){return p[1]}), mn=Math.min.apply(null,vs), mx=Math.max.apply(null,vs);
      if(mx===mn){mx+=1;mn-=1}
      var X=function(i){return P+(dates.length>1?i*(W-2*P)/(dates.length-1):(W-2*P)/2)}, Y=function(v){return P+(mx-v)*(H-2*P)/(mx-mn)};
      var svg='';
      if(pts.length){
        var d=pts.map(function(p,k){return (k?'L':'M')+X(p[0]).toFixed(1)+' '+Y(p[1]).toFixed(1)}).join(' ');
        var a=d+' L'+X(pts[pts.length-1][0]).toFixed(1)+' '+(H-P)+' L'+X(pts[0][0]).toFixed(1)+' '+(H-P)+' Z';
        var lp=pts[pts.length-1];
        svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img" aria-label="'+dest+' 每日最低價走勢">'+
          '<line x1="0" x2="'+W+'" y1="'+(H-P)+'" y2="'+(H-P)+'" stroke="var(--line)" stroke-width="1"/>'+
          '<path d="'+a+'" fill="var(--blue-soft)" stroke="none"/>'+
          '<path d="'+d+'" fill="none" stroke="var(--blue)" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>'+
          pts.map(function(p){return '<circle cx="'+X(p[0]).toFixed(1)+'" cy="'+Y(p[1]).toFixed(1)+'" r="'+(p===lp?3.5:2)+'" fill="'+(p===lp?'var(--blue)':'var(--card)')+'" stroke="var(--blue)" stroke-width="1.5" vector-effect="non-scaling-stroke"/>'}).join('')+'</svg>';
      } else svg='<p class="empty">還沒有紀錄</p>';
      var md=function(t){var m=t.match(/(\d{4})-(\d{2})-(\d{2})/);return m?(+m[2])+'/'+(+m[3]):t};
      el.innerHTML='<div class="h"><b>'+dest+'</b><span class="v">'+(last!=null?'NT$'+last.toLocaleString():'—')+'</span></div>'+chgHTML(c)+svg+
        '<div class="ax"><span>'+md(dates[0])+'</span><span>'+(pts.length?'最低 '+mn.toLocaleString().replace(/^-/,''):'')+'</span><span>'+md(dates[dates.length-1])+'</span></div>';
      if(pts.length) $('.ax span:nth-child(2)',el).textContent='最低 '+Math.min.apply(null,vs).toLocaleString();
      box.appendChild(el);
    });
    var sc=log.closest('.scroll'), det=document.createElement('details'); det.className='fold';
    det.innerHTML='<summary>看每日紀錄表</summary>'; sc.before(det); det.appendChild(sc);
    var note=det.nextElementSibling; if(note&&note.classList.contains('small')) det.appendChild(note);
    det.before(box);
  }

  /* ---------- 分頁 ---------- */
  var nav=document.createElement('nav'); nav.className='tabs'; nav.setAttribute('role','tablist'); nav.setAttribute('aria-label','頁面分區');
  var counts={prices:bestRows.filter(function(r){return !r.ref}).length, promo:promo?$$('tr',promo).filter(function(tr){return !$('th',tr)&&!tr.classList.contains('ended')}).length:0};
  TABS.forEach(function(t){
    if(!$('.card[data-tab="'+t[0]+'"]')) return;
    var b=document.createElement('button'); b.type='button'; b.setAttribute('role','tab'); b.dataset.t=t[0];
    b.innerHTML=t[1]+(counts[t[0]]?'<span class="cnt">'+counts[t[0]]+'</span>':''); b.onclick=function(){ show(t[0]); };
    nav.appendChild(b);
  });
  var header=$('header',wrap); header.after(nav);
  var current='overview';
  function show(id,keep){
    if(!$('.card[data-tab="'+id+'"]')) id='overview';
    current=id;
    $$('.wrap > .card').forEach(function(c){ c.hidden=c.dataset.tab!==id||c.dataset.empty==='1'; });
    $$('button',nav).forEach(function(b){ b.setAttribute('aria-selected',b.dataset.t===id) });
    if(!keep){
      if(location.hash.slice(1)!==id){ try{ history.replaceState(null,'','#'+id) }catch(e){ } }
      var top=nav.getBoundingClientRect().top+window.scrollY-8; if(window.scrollY>top) window.scrollTo(0,top);
    }
  }
  window.addEventListener('hashchange',function(){ show(location.hash.slice(1)||'overview') });
  show(location.hash.slice(1)||'overview',true);
})();

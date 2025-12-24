function filterList(input, cls){
  const q = (input.value || "").toLowerCase();
  document.querySelectorAll("." + cls).forEach(el => {
    const t = (el.innerText || "").toLowerCase();
    el.style.display = t.includes(q) ? "" : "none";
  });
}

(function connectWS(){
  if(!window.__ROOM__ || window.__ROOM__ === "number:0") return;

  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/ws?room=${encodeURIComponent(window.__ROOM__)}`);

  ws.onopen = () => {
    setInterval(() => { try { ws.send("ping"); } catch(e){} }, 25000);
  };

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if(msg.event === "message:new"){
        location.reload();
      }
    } catch(e){}
  };

  ws.onclose = () => setTimeout(connectWS, 1500);
})();

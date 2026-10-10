class PhotographyEventsCardEditor extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:"open"}); }
  setConfig(config) { this._config = {title:typeof config.title==="string"?config.title.slice(0,256):DEFAULT_CONFIG.title,
    mode:Object.hasOwn(CORE_VIEW,config.mode)?config.mode:MODE_HERO,entry_id:typeof config.entry_id==="string"?config.entry_id.slice(0,128):""}; this._render(); }
  set hass(value) { this._hass = value; this._render(); }
  _render() {
    if (!this._config) return;
    this.shadowRoot.innerHTML = `<style>label{display:block;margin:16px 0}input,select{display:block;width:100%;padding:12px;box-sizing:border-box}</style>
      <label>Title<input data-field="title" value="${escapeHtml(this._config.title)}"></label>
      <label>Initial view<select data-field="mode">${[[MODE_HERO,"Can't Miss"],["watching","Watching"],[MODE_OUTLOOK,"Year Planner"],[MODE_BIRDS,"Birds"]].map(([v,t])=>`<option value="${v}" ${v===this._config.mode?"selected":""}>${t}</option>`).join("")}</select></label>
      <p>Core-backed read-only views. Choose the integration entry below only if automatic discovery is unavailable.</p>
      <label>Entry ID<input data-field="entry_id" value="${escapeHtml(this._config.entry_id)}"></label>`;
    for (const input of this.shadowRoot.querySelectorAll("[data-field]")) input.addEventListener("change",()=>{
      this._config = {...this._config,[input.dataset.field]:input.value};
      this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:true,composed:true}));
    });
  }
}

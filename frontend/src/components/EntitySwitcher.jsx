import { Building2, ChevronDown, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";

/**
 * Global Entity Switcher (Multi-Entity — Fase 0).
 * Memilih konteks entitas legal aktif (PT/CV) atau "Semua Entitas".
 * Memfilter data transaksi (Orders, Customers, KPI order) per entity_id.
 */
export default function EntitySwitcher({ entities = [], value = "all", onChange, canSwitch = true }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const active = entities.find((e) => e.id === value);

  // User terkunci 1 entitas (sales/warehouse — Model 1 silo): tampilkan badge statis.
  if (!canSwitch) {
    const only = active || entities[0];
    const lockLabel = only?.short_name || only?.legal_name || "Entitas";
    return (
      <div className="entity-switcher" data-testid="entity-switcher-locked">
        <div className="entity-switcher-trigger" title="Entitas Anda (terkunci)" style={{ cursor: "default" }}>
          <Building2 size={14} />
          <span className="entity-switcher-label">{lockLabel}</span>
        </div>
      </div>
    );
  }

  const label = value === "all" ? "Semua Entitas" : (active?.short_name || active?.legal_name || "Entitas");

  const options = [{ id: "all", short_name: "Semua Entitas", type: "" }, ...entities];

  return (
    <div className="entity-switcher" ref={ref}>
      <button
        type="button"
        data-testid="entity-switcher"
        className="entity-switcher-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Pilih konteks entitas"
      >
        <Building2 size={14} />
        <span className="entity-switcher-label">{label}</span>
        <ChevronDown size={13} className={open ? "rotate-180 transition-transform" : "transition-transform"} />
      </button>
      {open && (
        <div className="entity-switcher-menu" role="listbox" data-testid="entity-switcher-menu">
          {options.map((opt) => (
            <button
              key={opt.id}
              type="button"
              role="option"
              aria-selected={value === opt.id}
              data-testid={`entity-option-${opt.id}`}
              className={`entity-switcher-item ${value === opt.id ? "active" : ""}`}
              onClick={() => { onChange?.(opt.id); setOpen(false); }}
            >
              <span className="flex items-center gap-2 min-w-0">
                <Building2 size={13} className="shrink-0" />
                <span className="truncate">
                  {opt.id === "all" ? "Semua Entitas" : (opt.legal_name || opt.short_name)}
                  {opt.type ? <span className="entity-tag">{opt.type}</span> : null}
                </span>
              </span>
              {value === opt.id && <Check size={14} className="shrink-0 text-[#007AFF]" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

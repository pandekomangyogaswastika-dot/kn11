/**
 * Approval Rules Settings
 * Configure approval rules untuk berbagai entity types
 */
import { useState, useEffect } from "react";
import axios, { API } from "../../services/apiClient";
import {
  AlertCircle, CheckCircle2, Edit2, Loader2, Plus, Settings, Trash2, X
} from "lucide-react";
import KNSelect from "../../components/KNSelect";


// Helper
function fmtNum(n) {
  return new Intl.NumberFormat("id-ID").format(n || 0);
}

const ENTITY_TYPES = [
  { value: "special_order", label: "Special Order (OD)" },
  { value: "purchase_order", label: "Purchase Order (PO)" },
  { value: "transfer", label: "Transfer Antar-Entitas" },
  { value: "price_approval", label: "Price Approval" },
  { value: "invoice", label: "Invoice" },
];

const OPERATORS = [
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" },
  { value: "eq", label: "=" },
];

const ROLES = [
  { value: "manager", label: "Manager" },
  { value: "admin", label: "Admin" },
  { value: "owner", label: "Owner" },
];

export default function ApprovalRulesSettings({ currentUser }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingRule, setEditingRule] = useState(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    entity_type: "special_order",
    threshold_field: "total_amount",
    threshold_operator: "gt",
    threshold_value: "",
    approver_role: "manager",
    description: "",
    priority: 100,
    is_active: true,
  });

  const token = localStorage.getItem("kn_token");
  const isAdmin = currentUser?.role === "admin";

  useEffect(() => {
    loadRules();
  }, []);

  async function loadRules() {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/approval-rules`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setRules(res.data || []);
      setError(null);
    } catch (e) {
      setError("Gagal memuat rules: " + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setFormData({
      name: "",
      entity_type: "special_order",
      threshold_field: "total_amount",
      threshold_operator: "gt",
      threshold_value: "",
      approver_role: "manager",
      description: "",
      priority: 100,
      is_active: true,
    });
    setEditingRule(null);
    setShowCreateForm(false);
  }

  function handleEdit(rule) {
    setFormData({
      name: rule.name,
      entity_type: rule.entity_type,
      threshold_field: rule.threshold_field,
      threshold_operator: rule.threshold_operator,
      threshold_value: rule.threshold_value,
      approver_role: rule.approver_role,
      description: rule.description || "",
      priority: rule.priority,
      is_active: rule.is_active,
    });
    setEditingRule(rule);
    setShowCreateForm(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!formData.threshold_value || parseFloat(formData.threshold_value) < 0) {
      return setError("Threshold value harus >= 0");
    }

    try {
      if (editingRule) {
        // Update
        await axios.patch(
          `${API}/approval-rules/${editingRule.id}`,
          { ...formData, threshold_value: parseFloat(formData.threshold_value) },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setNotice(`Rule "${formData.name}" berhasil diupdate!`);
      } else {
        // Create
        await axios.post(
          `${API}/approval-rules`,
          { ...formData, threshold_value: parseFloat(formData.threshold_value) },
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setNotice(`Rule "${formData.name}" berhasil dibuat!`);
      }
      resetForm();
      loadRules();
    } catch (e) {
      setError("Gagal menyimpan: " + (e.response?.data?.detail || e.message));
    }
  }

  async function handleDelete(rule) {
    if (!window.confirm(`Hapus rule "${rule.name}"?`)) return;

    try {
      await axios.delete(`${API}/approval-rules/${rule.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setNotice(`Rule "${rule.name}" berhasil dihapus!`);
      loadRules();
    } catch (e) {
      setError("Gagal menghapus: " + (e.response?.data?.detail || e.message));
    }
  }

  async function toggleActive(rule) {
    try {
      await axios.patch(
        `${API}/approval-rules/${rule.id}`,
        { is_active: !rule.is_active },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      loadRules();
    } catch (e) {
      setError("Gagal toggle status: " + (e.response?.data?.detail || e.message));
    }
  }

  if (!isAdmin) {
    return (
      <div className="view-container">
        <div className="notice-bar danger">
          <AlertCircle size={14} /> Hanya admin yang dapat manage approval rules.
        </div>
      </div>
    );
  }

  return (
    <div data-testid="approval-rules-settings" className="view-container">
      {/* Notice */}
      {notice && (
        <div className="notice-bar success">
          <CheckCircle2 size={14} /> {notice}
          <button onClick={() => setNotice(null)}><X size={12} /></button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="notice-bar danger">
          <AlertCircle size={14} /> {error}
          <button onClick={() => setError(null)}><X size={12} /></button>
        </div>
      )}

      {/* Header */}
      <div className="view-header">
        <div>
          <h1 className="view-title">
            <Settings size={20} /> Approval Rules
          </h1>
          <p className="view-subtitle">
            Konfigurasi approval rules untuk berbagai entity types
          </p>
        </div>
        {!showCreateForm && (
          <button
            data-testid="create-rule-btn"
            className="primary-button"
            onClick={() => setShowCreateForm(true)}
          >
            <Plus size={14} /> Buat Rule Baru
          </button>
        )}
      </div>

      {/* Create/Edit Form */}
      {showCreateForm && (
        <div className="form-card" data-testid="rule-form">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">
              {editingRule ? "Edit Rule" : "Buat Rule Baru"}
            </h3>
            <button className="icon-button" onClick={resetForm}>
              <X size={14} />
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-row-2col">
              <div className="form-group">
                <label className="form-label">Nama Rule <span className="req">*</span></label>
                <input
                  data-testid="rule-name"
                  className="form-input"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Contoh: Special Order High Value"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Entity Type <span className="req">*</span></label>
                <KNSelect
                  data-testid="rule-entity-type"
                  className="form-select"
                  value={formData.entity_type}
                  onValueChange={v => setFormData({ ...formData, entity_type: v })}
                  options={ENTITY_TYPES.map(t => ({ value: t.value, label: t.label }))}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Description</label>
              <input
                data-testid="rule-description"
                className="form-input"
                value={formData.description}
                onChange={e => setFormData({ ...formData, description: e.target.value })}
                placeholder="Deskripsi rule..."
              />
            </div>

            <div className="form-row-3col">
              <div className="form-group">
                <label className="form-label">Threshold Field <span className="req">*</span></label>
                <input
                  data-testid="rule-threshold-field"
                  className="form-input"
                  value={formData.threshold_field}
                  onChange={e => setFormData({ ...formData, threshold_field: e.target.value })}
                  placeholder="total_amount"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Operator <span className="req">*</span></label>
                <KNSelect
                  data-testid="rule-operator"
                  className="form-select"
                  value={formData.threshold_operator}
                  onValueChange={v => setFormData({ ...formData, threshold_operator: v })}
                  options={OPERATORS.map(op => ({ value: op.value, label: `${op.label} (${op.value})` }))}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Threshold Value <span className="req">*</span></label>
                <input
                  data-testid="rule-threshold-value"
                  className="form-input"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formData.threshold_value}
                  onChange={e => setFormData({ ...formData, threshold_value: e.target.value })}
                  placeholder="10000000"
                  required
                />
              </div>
            </div>

            <div className="form-row-3col">
              <div className="form-group">
                <label className="form-label">Approver Role <span className="req">*</span></label>
                <KNSelect
                  data-testid="rule-approver-role"
                  className="form-select"
                  value={formData.approver_role}
                  onValueChange={v => setFormData({ ...formData, approver_role: v })}
                  options={ROLES.map(r => ({ value: r.value, label: r.label }))}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Priority</label>
                <input
                  data-testid="rule-priority"
                  className="form-input"
                  type="number"
                  min="1"
                  value={formData.priority}
                  onChange={e => setFormData({ ...formData, priority: parseInt(e.target.value) })}
                />
                <p className="form-help text-xs">Lower = higher priority</p>
              </div>

              <div className="form-group">
                <label className="form-check-label mt-6">
                  <input
                    type="checkbox"
                    data-testid="rule-is-active"
                    checked={formData.is_active}
                    onChange={e => setFormData({ ...formData, is_active: e.target.checked })}
                  />
                  {" "}Active
                </label>
              </div>
            </div>

            <div className="form-actions">
              <button type="button" className="secondary-button" onClick={resetForm}>
                Batal
              </button>
              <button type="submit" data-testid="save-rule-btn" className="primary-button">
                <CheckCircle2 size={14} /> {editingRule ? "Update" : "Buat"} Rule
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Rules List */}
      {loading ? (
        <div className="loading-state">
          <Loader2 size={24} className="spin" />
          <p>Memuat approval rules...</p>
        </div>
      ) : rules.length === 0 ? (
        <div className="empty-state">
          <Settings size={32} style={{ opacity: 0.3 }} />
          <p>Belum ada approval rules.</p>
          {!showCreateForm && (
            <button className="primary-button" onClick={() => setShowCreateForm(true)}>
              <Plus size={14} /> Buat Rule Pertama
            </button>
          )}
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Rule Name</th>
                <th>Entity Type</th>
                <th>Condition</th>
                <th>Approver</th>
                <th>Priority</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rules.map(rule => (
                <tr key={rule.id} data-testid={`rule-row-${rule.id}`}>
                  <td>
                    <div className="font-medium">{rule.name}</div>
                    {rule.description && (
                      <div className="text-xs text-muted">{rule.description}</div>
                    )}
                  </td>
                  <td>
                    <span className="feature-badge badge-blue">
                      {ENTITY_TYPES.find(t => t.value === rule.entity_type)?.label || rule.entity_type}
                    </span>
                  </td>
                  <td className="font-mono text-sm">
                    {rule.threshold_field} {OPERATORS.find(o => o.value === rule.threshold_operator)?.label} <span className="tabular-nums">{fmtNum(rule.threshold_value)}</span>
                  </td>
                  <td>
                    <span className="feature-badge badge-purple">
                      {ROLES.find(r => r.value === rule.approver_role)?.label || rule.approver_role}
                    </span>
                  </td>
                  <td className="text-center">{rule.priority}</td>
                  <td>
                    <button
                      data-testid={`toggle-rule-${rule.id}`}
                      className={`status-pill ${rule.is_active ? "pill-success" : "pill-muted"}`}
                      onClick={() => toggleActive(rule)}
                    >
                      {rule.is_active ? "Active" : "Inactive"}
                    </button>
                  </td>
                  <td>
                    <div className="flex gap-2">
                      <button
                        data-testid={`edit-rule-${rule.id}`}
                        className="icon-button"
                        onClick={() => handleEdit(rule)}
                      >
                        <Edit2 size={14} />
                      </button>
                      <button
                        data-testid={`delete-rule-${rule.id}`}
                        className="icon-button danger"
                        onClick={() => handleDelete(rule)}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

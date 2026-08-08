import { useState } from 'react';
import { Eye, EyeOff, Plus, Trash2, UserPlus, Users, X } from 'lucide-react';
import type { Employee, EmployeeFormData } from '../types';
import { EMPTY_EMPLOYEE } from '../types';
import { getEmailDomain, isPersonalEmail, passwordIsStrong, passwordsMatch } from '../utils/validation';

interface Props {
  employees: Employee[];
  companyEmailDomains: string[];
  onSave: (data: EmployeeFormData) => Promise<void>;
  onUpdateDisplayName: (employee: Employee, displayName: string) => Promise<void>;
  onDelete: (employee: Employee) => Promise<void>;
  onClose: () => void;
}

export default function EmployeeManager({
  employees,
  companyEmailDomains,
  onSave,
  onUpdateDisplayName,
  onDelete,
  onClose,
}: Props) {
  const [form, setForm] = useState<EmployeeFormData>(EMPTY_EMPLOYEE);
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState('');
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const allowedDomains = companyEmailDomains.length > 0 ? companyEmailDomains : ['behtechlabs.com'];
  const domainHint = allowedDomains.map((domain) => `@${domain}`).join(', ');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!passwordsMatch(form.password, form.password_confirm)) {
      setError('Şifreler eşleşmiyor');
      return;
    }
    if (!passwordIsStrong(form.password)) {
      setError('Şifre güvenlik gereksinimlerini karşılamıyor');
      return;
    }
    if (isPersonalEmail(form.email)) {
      setError('Personel için kurumsal e-posta kullanın (Gmail, Hotmail vb. kabul edilmez)');
      return;
    }
    if (!allowedDomains.includes(getEmailDomain(form.email))) {
      setError(`Personel e-postası ${domainHint} domainlerinden biri olmalıdır`);
      return;
    }
    if (!form.display_name.trim()) {
      setError('Personel adı zorunludur (mesajlarda kullanılır)');
      return;
    }

    setSaving(true);
    try {
      await onSave(form);
      setForm(EMPTY_EMPLOYEE);
      setSuccess('Personel eklendi. Doğrulama e-postası gönderildi.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Personel eklenemedi');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel-lg">
        <div className="flex shrink-0 items-center justify-between border-b border-surface-200 px-5 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-surface-900">
              <Users size={18} />
              Personel Yönetimi
            </h2>
            <p className="text-xs text-surface-800/50">
              Personel e-postası {domainHint} olmalıdır
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
            <X size={20} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <form onSubmit={handleSubmit} className="mb-6 space-y-3 rounded-xl border border-surface-200 bg-surface-50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-surface-800">
              <UserPlus size={15} /> Yeni Personel
            </h3>
            {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
            {success && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p>}
            <div>
              <label className="label-field">Kullanıcı Adı</label>
              <input
                className="input-field"
                value={form.username}
                onChange={(e) => setForm((prev) => ({ ...prev, username: e.target.value }))}
                required
              />
            </div>
            <div>
              <label className="label-field">Kurumsal E-posta</label>
              <input
                type="email"
                className="input-field"
                value={form.email}
                onChange={(e) => setForm((prev) => ({ ...prev, email: e.target.value }))}
                placeholder={`personel@${allowedDomains[0]}`}
                required
              />
            </div>
            <div>
              <label className="label-field">Personel Adı (mesajlarda görünür)</label>
              <input
                className="input-field"
                value={form.display_name}
                onChange={(e) => setForm((prev) => ({ ...prev, display_name: e.target.value }))}
                placeholder="Örn: Ahmet"
                maxLength={100}
                required
              />
            </div>
            <div>
              <label className="label-field">Şifre</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="input-field pr-10"
                  value={form.password}
                  onChange={(e) => setForm((prev) => ({ ...prev, password: e.target.value }))}
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-800/40"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <div>
              <label className="label-field">Şifre Tekrar</label>
              <div className="relative">
                <input
                  type={showPasswordConfirm ? 'text' : 'password'}
                  className="input-field pr-10"
                  value={form.password_confirm}
                  onChange={(e) => setForm((prev) => ({ ...prev, password_confirm: e.target.value }))}
                  minLength={8}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPasswordConfirm((prev) => !prev)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-800/40"
                >
                  {showPasswordConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
            <button type="submit" disabled={saving} className="btn-primary w-full justify-center">
              <Plus size={16} />
              {saving ? 'Ekleniyor...' : 'Personel Ekle'}
            </button>
          </form>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-surface-800">Mevcut Personel</h3>
            {employees.length === 0 ? (
              <p className="text-sm text-surface-800/50">Henüz personel eklenmedi.</p>
            ) : (
              employees.map((employee) => (
                <div
                  key={employee.id}
                  className="rounded-lg border border-surface-200 px-3 py-2.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-surface-900">{employee.username}</p>
                      <p className="text-xs text-surface-800/50">
                        {employee.email}
                        {!employee.email_verified ? ' · Doğrulanmadı' : ''}
                      </p>
                      {editingId === employee.id ? (
                        <div className="mt-2 flex gap-2">
                          <input
                            className="input-field py-1.5 text-sm"
                            value={editingName}
                            onChange={(e) => setEditingName(e.target.value)}
                            maxLength={100}
                          />
                          <button
                            type="button"
                            disabled={updatingId === employee.id}
                            onClick={async () => {
                              const name = editingName.trim();
                              if (!name) {
                                setError('Personel adı boş olamaz');
                                return;
                              }
                              setError('');
                              setUpdatingId(employee.id);
                              try {
                                await onUpdateDisplayName(employee, name);
                                setEditingId(null);
                                setEditingName('');
                              } catch (err) {
                                setError(err instanceof Error ? err.message : 'Güncellenemedi');
                              } finally {
                                setUpdatingId(null);
                              }
                            }}
                            className="btn-secondary px-2 py-1 text-xs"
                          >
                            Kaydet
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setEditingId(null);
                              setEditingName('');
                            }}
                            className="btn-secondary px-2 py-1 text-xs"
                          >
                            İptal
                          </button>
                        </div>
                      ) : (
                        <p className="mt-1 text-xs text-brand-700">
                          Mesaj adı: {employee.display_name?.trim() || '—'}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 gap-1">
                      {editingId !== employee.id ? (
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(employee.id);
                            setEditingName(employee.display_name || '');
                            setError('');
                          }}
                          className="rounded-lg px-2 py-1 text-xs text-surface-700 hover:bg-surface-100"
                        >
                          Ad düzenle
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={() => onDelete(employee)}
                        className="rounded-lg p-1.5 text-surface-800/50 hover:bg-red-50 hover:text-red-600"
                        title="Sil"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="flex shrink-0 justify-end border-t border-surface-200 px-5 py-3">
          <button type="button" onClick={onClose} className="btn-secondary">Kapat</button>
        </div>
      </div>
    </div>
  );
}

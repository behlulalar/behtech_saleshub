import { useEffect, useState } from 'react';
import { Eye, EyeOff, Save, Settings, Trash2, X } from 'lucide-react';
import ConfirmDialog from './ConfirmDialog';
import { useLocale } from '../i18n/locale';
import type { DeleteAccountData, UpdateProfileData, UserProfile } from '../types';
import { passwordIsStrong, passwordsMatch } from '../utils/validation';

interface Props {
  profile: UserProfile;
  onSave: (data: UpdateProfileData) => Promise<UserProfile>;
  onResendVerification: () => Promise<void>;
  onDeleteAccount: (data: DeleteAccountData) => Promise<void>;
  onClose: () => void;
}

export default function AccountSettings({
  profile,
  onSave,
  onResendVerification,
  onDeleteAccount,
  onClose,
}: Props) {
  const { app } = useLocale();
  const t = app.accountSettings;

  const [email, setEmail] = useState(profile.email);
  const [companyName, setCompanyName] = useState(profile.company_name || '');
  const [displayName, setDisplayName] = useState(profile.display_name || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showNewPasswordConfirm, setShowNewPasswordConfirm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resending, setResending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [emailVerified, setEmailVerified] = useState(!!profile.email_verified);
  const [deletePassword, setDeletePassword] = useState('');
  const [confirmUsername, setConfirmUsername] = useState('');
  const [showDeletePassword, setShowDeletePassword] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  useEffect(() => {
    setEmail(profile.email);
    setCompanyName(profile.company_name || '');
    setDisplayName(profile.display_name || '');
    setEmailVerified(!!profile.email_verified);
  }, [profile]);

  const showCompanyName =
    profile.role === 'owner' && profile.account_type === 'company';
  const showDisplayName = profile.role === 'employee';

  const roleLabel =
    profile.role === 'owner' ? t.owner : t.employee;
  const accountTypeLabel =
    profile.account_type === 'company' ? t.company : t.individual;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    const changingPassword = !!(currentPassword || newPassword || newPasswordConfirm);
    if (changingPassword) {
      if (!currentPassword) {
        setError(t.currentPassword);
        return;
      }
      if (!passwordsMatch(newPassword, newPasswordConfirm)) {
        setError('Şifreler eşleşmiyor');
        return;
      }
      if (!passwordIsStrong(newPassword)) {
        setError('Şifre güvenlik gereksinimlerini karşılamıyor');
        return;
      }
    }

    const payload: UpdateProfileData = {};
    if (email.trim().toLowerCase() !== profile.email) {
      payload.email = email.trim().toLowerCase();
    }
    if (showCompanyName && companyName.trim() !== (profile.company_name || '')) {
      payload.company_name = companyName.trim();
    }
    if (showDisplayName && displayName.trim() !== (profile.display_name || '')) {
      payload.display_name = displayName.trim();
    }
    if (changingPassword) {
      payload.current_password = currentPassword;
      payload.new_password = newPassword;
      payload.new_password_confirm = newPasswordConfirm;
    }

    if (Object.keys(payload).length === 0) {
      setSuccess(t.saved);
      return;
    }

    setSaving(true);
    try {
      const updated = await onSave(payload);
      setEmail(updated.email);
      setCompanyName(updated.company_name || '');
      setDisplayName(updated.display_name || '');
      setEmailVerified(!!updated.email_verified);
      setCurrentPassword('');
      setNewPassword('');
      setNewPasswordConfirm('');
      setSuccess(t.saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Kayıt başarısız');
    } finally {
      setSaving(false);
    }
  };

  const handleResend = async () => {
    setError('');
    setResending(true);
    try {
      await onResendVerification();
      setSuccess(t.verificationSent);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gönderilemedi');
    } finally {
      setResending(false);
    }
  };

  const handleDeleteClick = () => {
    setError('');
    setSuccess('');

    if (!deletePassword) {
      setError(t.deletePassword);
      return;
    }
    if (confirmUsername.trim().toLowerCase() !== profile.username.toLowerCase()) {
      setError(t.confirmUsernameHint);
      return;
    }

    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    setDeleting(true);
    setError('');
    try {
      await onDeleteAccount({
        password: deletePassword,
        confirm_username: confirmUsername.trim(),
      });
      setShowDeleteConfirm(false);
    } catch (err) {
      setShowDeleteConfirm(false);
      setError(err instanceof Error ? err.message : 'Silme başarısız');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-panel modal-panel-lg">
        <div className="flex shrink-0 items-center justify-between border-b border-surface-200 px-5 py-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-surface-900">
              <Settings size={18} />
              {t.title}
            </h2>
            <p className="text-xs text-surface-800/50">{t.subtitle}</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-1.5 hover:bg-surface-100">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {error && <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
          {success && <p className="mb-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p>}

          <section className="space-y-3 rounded-xl border border-surface-200 bg-surface-50 p-4">
            <h3 className="text-sm font-semibold text-surface-800">{t.profileSection}</h3>

            <div>
              <label className="label-field">{t.username}</label>
              <input className="input-field bg-surface-100" value={profile.username} readOnly />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label-field">{t.role}</label>
                <input className="input-field bg-surface-100" value={roleLabel} readOnly />
              </div>
              <div>
                <label className="label-field">{t.accountType}</label>
                <input className="input-field bg-surface-100" value={accountTypeLabel} readOnly />
              </div>
            </div>

            <div>
              <label className="label-field">{t.email}</label>
              <input
                type="email"
                className="input-field"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
              <p className="mt-1 text-xs text-surface-800/50">{t.emailChangeNote}</p>
            </div>

            {showCompanyName && (
              <div>
                <label className="label-field">{t.companyName}</label>
                <input
                  className="input-field"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  maxLength={100}
                />
              </div>
            )}

            {showDisplayName && (
              <div>
                <label className="label-field">Mesajlarda görünen ad</label>
                <input
                  className="input-field"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  maxLength={100}
                  required
                />
                <p className="mt-1 text-xs text-surface-800/50">
                  Hazır mesajlarda &quot;BehTech ekibinden ...&quot; kısmında kullanılır.
                </p>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-surface-200 bg-white px-3 py-2">
              <div>
                <p className="text-xs font-medium text-surface-700">{t.emailStatus}</p>
                <p className={`text-sm font-semibold ${emailVerified ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {emailVerified ? t.verified : t.unverified}
                </p>
              </div>
              {!emailVerified && (
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resending}
                  className="btn-secondary py-1.5 text-xs"
                >
                  {resending ? t.resending : t.resendVerification}
                </button>
              )}
            </div>
          </section>

          <section className="mt-4 space-y-3 rounded-xl border border-surface-200 p-4">
            <h3 className="text-sm font-semibold text-surface-800">{t.passwordSection}</h3>
            <p className="text-xs text-surface-800/50">{t.passwordHint}</p>

            <div>
              <label className="label-field">{t.currentPassword}</label>
              <div className="relative">
                <input
                  type={showCurrentPassword ? 'text' : 'password'}
                  className="input-field pr-10"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-surface-500 hover:bg-surface-100"
                >
                  {showCurrentPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div>
              <label className="label-field">{t.newPassword}</label>
              <div className="relative">
                <input
                  type={showNewPassword ? 'text' : 'password'}
                  className="input-field pr-10"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-surface-500 hover:bg-surface-100"
                >
                  {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div>
              <label className="label-field">{t.confirmPassword}</label>
              <div className="relative">
                <input
                  type={showNewPasswordConfirm ? 'text' : 'password'}
                  className="input-field pr-10"
                  value={newPasswordConfirm}
                  onChange={(e) => setNewPasswordConfirm(e.target.value)}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPasswordConfirm((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-surface-500 hover:bg-surface-100"
                >
                  {showNewPasswordConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>
          </section>

          <section className="mt-4 space-y-3 rounded-xl border border-red-200 bg-red-50/40 p-4">
            <h3 className="text-sm font-semibold text-red-700">{t.deleteSection}</h3>
            <p className="text-xs leading-relaxed text-red-700/80">
              {profile.role === 'owner' ? t.deleteWarningOwner : t.deleteWarningEmployee}
            </p>

            <div>
              <label className="label-field">{t.deletePassword}</label>
              <div className="relative">
                <input
                  type={showDeletePassword ? 'text' : 'password'}
                  className="input-field pr-10"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowDeletePassword((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-surface-500 hover:bg-surface-100"
                >
                  {showDeletePassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div>
              <label className="label-field">{t.confirmUsername}</label>
              <input
                className="input-field"
                value={confirmUsername}
                onChange={(e) => setConfirmUsername(e.target.value)}
                placeholder={profile.username}
                autoComplete="off"
              />
              <p className="mt-1 text-xs text-surface-800/50">{t.confirmUsernameHint}</p>
            </div>

            <button
              type="button"
              onClick={handleDeleteClick}
              disabled={deleting}
              className="btn-danger w-full justify-center"
            >
              <Trash2 size={16} />
              {deleting ? t.deleting : t.deleteAccount}
            </button>
          </section>

          <div className="mt-4 flex gap-2">
            <button type="button" onClick={onClose} className="btn-secondary flex-1 justify-center">
              {app.confirm.cancel}
            </button>
            <button type="submit" disabled={saving} className="btn-primary flex-1 justify-center">
              <Save size={16} />
              {saving ? t.saving : t.save}
            </button>
          </div>
        </form>
      </div>

      <ConfirmDialog
        open={showDeleteConfirm}
        title={app.confirm.title}
        message={profile.role === 'owner' ? t.deleteConfirmOwner : t.deleteConfirmEmployee}
        confirmLabel={app.confirm.deleteAccount}
        cancelLabel={app.confirm.cancel}
        variant="danger"
        loading={deleting}
        onConfirm={handleDeleteConfirm}
        onCancel={() => !deleting && setShowDeleteConfirm(false)}
      />
    </div>
  );
}

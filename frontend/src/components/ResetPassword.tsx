import { useState } from 'react';
import { Lock, Save } from 'lucide-react';
import BrandLogo from './BrandLogo';
import { api } from '../api';

interface Props {
  token: string;
  onSuccess: () => void;
}

export default function ResetPassword({ token, onSuccess }: Props) {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      setError('Şifreler eşleşmiyor');
      return;
    }

    setError('');
    setLoading(true);
    try {
      const res = await api.resetPassword(token, password);
      setMessage(res.message);
      setTimeout(onSuccess, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'İşlem başarısız');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-subtle p-4">
      <div className="card w-full max-w-md p-8">
        <BrandLogo className="mb-6 h-10" />
        <h1 className="mb-2 text-2xl font-bold text-surface-900">Yeni Şifre Belirle</h1>
        <p className="mb-6 text-sm text-surface-800/60">Hesabınız için yeni bir şifre oluşturun.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label-field">Yeni Şifre</label>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
              <input
                type="password"
                className="input-field pl-9"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
          </div>
          <div>
            <label className="label-field">Şifre Tekrar</label>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-800/40" />
              <input
                type="password"
                className="input-field pl-9"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </div>
          </div>

          {message && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>}
          {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

          <button type="submit" disabled={loading || !!message} className="btn-primary w-full justify-center">
            <Save size={16} />
            {loading ? 'Kaydediliyor...' : 'Şifreyi Güncelle'}
          </button>
        </form>
      </div>
    </div>
  );
}

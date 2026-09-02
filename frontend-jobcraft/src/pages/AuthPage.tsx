import React, { useState } from 'react';
import { useJobCraft } from '../context/JobCraftContext';
import { Sparkles } from 'lucide-react';

type Mode = 'login' | 'register';

/**
 * 登录 / 注册页
 *
 * 无有效 token 时由 App 渲染，登录或注册成功后回到主工作区。
 */
export const AuthPage: React.FC = () => {
  const { login, register, isLoading } = useJobCraft();
  const [mode, setMode] = useState<Mode>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');

  const switchMode = (next: Mode) => {
    setMode(next);
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim() || !password) {
      setError('请输入用户名和密码');
      return;
    }
    if (mode === 'register' && password.length < 8) {
      setError('密码长度至少 8 位');
      return;
    }

    try {
      if (mode === 'login') {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password, email.trim() || undefined);
      }
    } catch (err: any) {
      setError(err?.message || '操作失败，请稍后重试');
    }
  };

  return (
    <div className="min-h-screen bg-page flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* 品牌区 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 text-sage mb-3">
            <Sparkles className="w-6 h-6" />
            <span className="text-sm font-bold tracking-wide">JobCraft</span>
          </div>
          <h1 className="text-2xl font-bold text-ink">
            {mode === 'login' ? '欢迎回来' : '创建你的求职工作台'}
          </h1>
          <p className="text-sm text-muted mt-2">
            AI 驱动的 JD 解析 · 简历定制 · 面试准备与复盘
          </p>
        </div>

        {/* 表单卡片 */}
        <div className="bg-white rounded-2xl shadow-xl border border-edge p-8">
          {/* 模式切换 */}
          <div className="flex bg-page rounded-lg p-1 mb-6">
            {(['login', 'register'] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={`flex-1 py-2 text-sm font-medium rounded-md transition ${
                  mode === m ? 'bg-white text-ink shadow-xs' : 'text-muted hover:text-ink'
                }`}
              >
                {m === 'login' ? '登录' : '注册'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="请输入用户名"
                autoComplete="username"
                className="w-full px-3.5 py-2.5 text-sm bg-page border border-edge rounded-lg text-ink placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-sage/30 focus:border-sage transition"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? '至少 8 位，含字母和数字' : '请输入密码'}
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                className="w-full px-3.5 py-2.5 text-sm bg-page border border-edge rounded-lg text-ink placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-sage/30 focus:border-sage transition"
              />
            </div>

            {mode === 'register' && (
              <div>
                <label className="block text-xs font-medium text-muted mb-1.5">
                  邮箱 <span className="text-faint">（选填）</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  className="w-full px-3.5 py-2.5 text-sm bg-page border border-edge rounded-lg text-ink placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-sage/30 focus:border-sage transition"
                />
              </div>
            )}

            {error && (
              <p className="text-xs text-error bg-error-bg rounded-lg px-3 py-2">{error}</p>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 text-sm font-semibold text-white bg-sage hover:bg-sage/90 rounded-lg transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? '处理中…' : mode === 'login' ? '登录' : '注册并开始'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-faint mt-6">
          登录即表示同意将数据保存在本机个人工作空间中
        </p>
      </div>
    </div>
  );
};
import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Shield, Lock, Mail, ArrowRight, UserCheck } from 'lucide-react'
import { authApi } from '../../api/auth.api'
import { useAuthStore } from '../../stores/auth.store'
import { useUIStore } from '../../stores/ui.store'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card'

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { setAuth } = useAuthStore()
  const { addToast } = useUIStore()
  const navigate = useNavigate()
  const location = useLocation()

  const redirectAfterLogin = (roles: string[]) => {
    const searchParams = new URLSearchParams(location.search)
    const from = (location.state as any)?.from?.pathname || searchParams.get('redirect')
    if (from && from !== '/login') {
      navigate(from, { replace: true })
      return
    }
    if (roles.includes('admin')) {
      navigate('/admin', { replace: true })
    } else if (roles.includes('verifier')) {
      navigate('/verifier/queue', { replace: true })
    } else if (roles.includes('maintenance')) {
      navigate('/maintenance/tasks', { replace: true })
    } else {
      navigate('/citizen', { replace: true })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      const tokenData = await authApi.login({ email, password })
      localStorage.setItem('safespace_token', tokenData.access_token)
      // fetch profile with freshly obtained token
      const user = await authApi.getMe(tokenData.access_token)
      setAuth(tokenData.access_token, user)

      addToast({
        type: 'success',
        title: 'Authentication Successful',
        message: `Welcome back, ${user.full_name}`,
      })

      redirectAfterLogin(user.roles)
    } catch (err: any) {
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Invalid email or password. Please verify credentials.'
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
    } finally {
      setIsLoading(false)
    }
  }

  const handleQuickLogin = async (userEmail: string, pass: string) => {
    setEmail(userEmail)
    setPassword(pass)
    setError(null)
    setIsLoading(true)

    try {
      const tokenData = await authApi.login({ email: userEmail, password: pass })
      localStorage.setItem('safespace_token', tokenData.access_token)
      const user = await authApi.getMe(tokenData.access_token)
      setAuth(tokenData.access_token, user)

      addToast({
        type: 'success',
        title: 'Authentication Successful',
        message: `Signed in as ${user.full_name}`,
      })

      redirectAfterLogin(user.roles)
    } catch (err: any) {
      const detail =
        err.response?.data?.detail ||
        err.message ||
        'Invalid email or password. Please verify credentials.'
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xs bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] shadow-xs">
            <Shield className="h-5 w-5" />
          </div>
          <h1 className="font-serif-headline text-2xl font-normal tracking-tight text-[#18372C] dark:text-[#F5F2EA]">
            Sign In to SafeSpace
          </h1>
          <p className="text-xs text-[#73766F] dark:text-[#829783]">
            Civic infrastructure deficiency intelligence and verification platform
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Account Credentials</CardTitle>
            <CardDescription>
              Enter your registered municipal credentials to access your role dashboard.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <div className="mb-4 p-3 rounded-xs bg-[#FBF0EB] border border-[#C36B48]/40 text-[#A25335] text-xs">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Email Address"
                type="email"
                placeholder="name@safespace.org"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              <Input
                label="Password"
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <Button
                type="submit"
                variant="primary"
                className="w-full"
                isLoading={isLoading}
              >
                Sign In <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </form>

            <div className="mt-5 pt-4 border-t border-[#DCE5D9]/60 dark:border-[#829783]/20 text-center text-xs text-[#73766F] dark:text-[#829783]">
              Don't have an account?{' '}
              <Link to="/register" className="text-[#244B3B] dark:text-[#DCE5D9] font-medium hover:underline">
                Create Citizen Account
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Demo Fast Login Pills (Disabled outside development mode) */}
        {import.meta.env.DEV && (
          <div className="rounded-sm border border-[#829783]/30 bg-[#FFFEFA] dark:bg-[#1E211E] p-4 space-y-3">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-[#73766F] dark:text-[#829783]">
              <UserCheck className="h-3.5 w-3.5 text-[#C36B48]" />
              <span>Fast Role Switcher (Preloaded Demo Accounts)</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => handleQuickLogin('citizen@safespace.org', 'CitizenPassword123!')}
                className="p-2.5 rounded-xs text-left border border-[#829783]/30 hover:border-[#244B3B] dark:hover:border-[#DCE5D9] bg-[#FAF8F4] dark:bg-[#18372C]/20 transition-colors cursor-pointer"
              >
                <div className="font-medium text-[#18372C] dark:text-[#F5F2EA]">Aarav Sharma</div>
                <div className="text-[10px] font-mono text-[#73766F] dark:text-[#829783] mt-0.5">Citizen &bull; citizen@safespace.org</div>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('verifier@safespace.org', 'VerifierPassword123!')}
                className="p-2.5 rounded-xs text-left border border-[#829783]/30 hover:border-[#244B3B] dark:hover:border-[#DCE5D9] bg-[#FAF8F4] dark:bg-[#18372C]/20 transition-colors cursor-pointer"
              >
                <div className="font-medium text-[#18372C] dark:text-[#F5F2EA]">Priya Patel</div>
                <div className="text-[10px] font-mono text-[#73766F] dark:text-[#829783] mt-0.5">Verifier &bull; verifier@safespace.org</div>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('admin@safespace.org', 'AdminPassword123!')}
                className="p-2.5 rounded-xs text-left border border-[#829783]/30 hover:border-[#244B3B] dark:hover:border-[#DCE5D9] bg-[#FAF8F4] dark:bg-[#18372C]/20 transition-colors cursor-pointer"
              >
                <div className="font-medium text-[#18372C] dark:text-[#F5F2EA]">Rajesh Iyer</div>
                <div className="text-[10px] font-mono text-[#73766F] dark:text-[#829783] mt-0.5">Admin &bull; admin@safespace.org</div>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('technician@safespace.org', 'TechnicianPassword123!')}
                className="p-2.5 rounded-xs text-left border border-[#829783]/30 hover:border-[#244B3B] dark:hover:border-[#DCE5D9] bg-[#FAF8F4] dark:bg-[#18372C]/20 transition-colors cursor-pointer"
              >
                <div className="font-medium text-[#18372C] dark:text-[#F5F2EA]">Vikram Singh</div>
                <div className="text-[10px] font-mono text-[#73766F] dark:text-[#829783] mt-0.5">Technician &bull; technician@safespace.org</div>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

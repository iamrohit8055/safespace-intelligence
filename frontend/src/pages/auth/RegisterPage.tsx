import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, ArrowRight, CheckCircle2 } from 'lucide-react'
import { authApi } from '../../api/auth.api'
import { useUIStore } from '../../stores/ui.store'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/Card'

export const RegisterPage: React.FC = () => {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [registered, setRegistered] = useState(false)

  const { addToast } = useUIStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setIsLoading(true)

    try {
      await authApi.register({
        email,
        password,
        full_name: fullName,
      })

      setRegistered(true)
      addToast({
        type: 'success',
        title: 'Registration Successful',
        message: 'Your citizen account has been created. Please sign in.',
      })
    } catch (err: any) {
      const detail =
        err.response?.data?.detail || 'Registration failed. The email may already be in use.'
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail))
    } finally {
      setIsLoading(false)
    }
  }

  if (registered) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md text-center p-6 space-y-4">
          <div className="mx-auto p-2.5 rounded-md bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 w-fit">
            <CheckCircle2 className="h-8 w-8" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            Account Created
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Your citizen registration is confirmed. You can now sign in and submit infrastructure deficiency reports.
          </p>
          <Button
            variant="primary"
            className="w-full mt-4"
            onClick={() => navigate('/login')}
          >
            Go to Sign In
          </Button>
        </Card>
      </div>
    )
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xs bg-[#244B3B] text-[#FFFEFA] dark:bg-[#DCE5D9] dark:text-[#18372C] shadow-xs">
            <Shield className="h-5 w-5" />
          </div>
          <h1 className="font-serif-headline text-2xl font-normal tracking-tight text-[#18372C] dark:text-[#F5F2EA]">
            Citizen Registration
          </h1>
          <p className="text-xs text-[#73766F] dark:text-[#829783]">
            Report public infrastructure deficiencies and track municipal resolution
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Create Account</CardTitle>
            <CardDescription>
              Submit observations, track status, and improve municipal safety.
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
                label="Full Name"
                type="text"
                placeholder="Aarav Sharma"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />

              <Input
                label="Email Address"
                type="email"
                placeholder="aarav@example.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              <Input
                label="Password"
                type="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />

              <Input
                label="Confirm Password"
                type="password"
                placeholder="Repeat password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />

              <Button
                type="submit"
                variant="primary"
                className="w-full"
                isLoading={isLoading}
              >
                Create Account <ArrowRight className="h-4 w-4 ml-1" />
              </Button>
            </form>

            <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 text-center text-xs text-slate-500">
              Already have an account?{' '}
              <Link to="/login" className="text-slate-900 dark:text-slate-100 font-medium hover:underline">
                Sign In
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

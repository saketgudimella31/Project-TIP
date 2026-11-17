import { createRootRouteWithContext, Link, Outlet } from '@tanstack/react-router'
import type { QueryClient } from '@tanstack/react-query'
import { Activity, Database, Home, ListTodo } from 'lucide-react'

const navigation = [
  { to: '/', label: 'Dashboard', icon: Home },
  { to: '/tasks', label: 'Tasks', icon: ListTodo },
  { to: '/repositories', label: 'Repositories', icon: Database },
  { to: '/metrics', label: 'Metrics', icon: Activity },
] as const

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: () => (
    <div className="min-h-screen">
      <nav className="border-b border-slate-700 bg-[#003057] text-white" aria-label="Main navigation">
        <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-4 sm:px-8">
          <h1 className="text-xl font-bold">Test Intelligence Platform</h1>
          <div className="flex flex-wrap gap-2 text-sm">
            {navigation.map(({ to, label, icon: Icon }) => (
              <Link key={to} to={to} activeOptions={{ exact: to === '/' }}
                className="inline-flex items-center gap-2 rounded-md px-3 py-2 text-white transition-colors hover:bg-white/10"
                activeProps={{ className: 'bg-white/10 ring-2 ring-brand-orange' }}>
                <Icon className="h-4 w-4" aria-hidden="true" />{label}
              </Link>
            ))}
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-screen-2xl px-4 py-8 sm:px-8 lg:py-10"><Outlet /></main>
    </div>
  ),
})
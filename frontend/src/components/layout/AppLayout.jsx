import { Outlet, Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import Sidebar from './Sidebar'
import NotificationBell from './NotificationBell'

export default function AppLayout() {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="flex justify-end px-6 pt-4">
          <NotificationBell />
        </div>
        <div className="max-w-6xl mx-auto px-6 pb-8 pt-2">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

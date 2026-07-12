import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { notificationsApi } from '../../api/services'
import { useAuth } from '../../context/AuthContext'

/**
 * Every leave decision, HR/IT request status change, profile change-request
 * submission/decision, and chatbot escalation resolution writes a
 * Notification row AND pushes it live over WebSocket (see
 * app/notification_service.py) — but until now nothing in the UI ever
 * showed it. This is that missing piece: a bell with unread count, backed
 * by GET /notifications for history and the WebSocket for real-time pushes.
 */
export default function NotificationBell() {
  const { liveNotification } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef(null)

  async function load() {
    try {
      const r = await notificationsApi.list()
      setItems(r.data)
    } catch (e) { /* non-fatal — bell just stays at its last known state */ }
  }

  useEffect(() => { load() }, [])

  // Real-time push from the WebSocket — prepend immediately so the badge
  // updates the instant something happens, without waiting on a poll.
  useEffect(() => {
    if (!liveNotification) return
    setItems(prev => [
      {
        notification_id: liveNotification.notification_id,
        title: liveNotification.title,
        message: liveNotification.message,
        deep_link: liveNotification.deep_link,
        is_read: false,
        created_at: liveNotification.created_at,
      },
      ...prev.filter(n => n.notification_id !== liveNotification.notification_id),
    ])
  }, [liveNotification])

  useEffect(() => {
    function onClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const unreadCount = items.filter(n => !n.is_read).length

  async function handleClick(n) {
    if (!n.is_read) {
      setItems(prev => prev.map(x => x.notification_id === n.notification_id ? { ...x, is_read: true } : x))
      try { await notificationsApi.markRead(n.notification_id) } catch (e) { /* ignore */ }
    }
    setOpen(false)
    if (n.deep_link) navigate(n.deep_link)
  }

  return (
    <div className="relative" ref={wrapperRef}>
      <button
        onClick={() => setOpen(o => !o)}
        className="relative p-2 rounded-lg hover:bg-gray-100 transition-colors"
        aria-label="Notifications"
      >
        <Bell className="w-5 h-5 text-gray-600" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 flex items-center justify-center
                           rounded-full bg-red-500 text-white text-[10px] font-bold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-xl border border-gray-100 z-50 max-h-96 overflow-y-auto">
          <div className="px-4 py-3 border-b border-gray-100">
            <p className="text-sm font-semibold text-gray-900">Notifications</p>
          </div>
          {items.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">No notifications yet.</p>
          ) : (
            <div className="divide-y divide-gray-50">
              {items.map(n => (
                <button
                  key={n.notification_id}
                  onClick={() => handleClick(n)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${!n.is_read ? 'bg-brand-50/40' : ''}`}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-600 shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{n.title}</p>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.message}</p>
                      {n.created_at && (
                        <p className="text-[11px] text-gray-400 mt-1">
                          {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

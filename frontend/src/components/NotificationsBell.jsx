/** Колокольчик уведомлений: счётчик непрочитанных и список. Счётчик обновляется раз в 30 с и при возврате на вкладку. */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationsApi } from '../api'
import { formatDateTime } from '../utils/format'
import styles from './Header.module.css'

export default function NotificationsBell() {
  const navigate = useNavigate()
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const ref = useRef(null)

  const refreshCount = useCallback(() => {
    notificationsApi.unreadCount().then((r) => setUnread(r.unread)).catch(() => {})
  }, [])

  useEffect(() => {
    refreshCount()
    const timer = setInterval(refreshCount, 30000)
    const onFocus = () => document.visibilityState === 'visible' && refreshCount()
    document.addEventListener('visibilitychange', onFocus)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', onFocus) }
  }, [refreshCount])

  // Клик мимо списка — закрыть
  useEffect(() => {
    if (!open) return undefined
    const onClick = (e) => !ref.current?.contains(e.target) && setOpen(false)
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('mousedown', onClick); document.removeEventListener('keydown', onKey) }
  }, [open])

  const toggle = async () => {
    if (open) { setOpen(false); return }
    setOpen(true)
    const data = await notificationsApi.list({ page_size: 15 }).catch(() => null)
    setItems(data?.results || [])
  }

  const openItem = async (n) => {
    setOpen(false)
    if (!n.is_read) {
      await notificationsApi.read(n.id).catch(() => {})
      refreshCount()
    }
    if (n.link) navigate(n.link)
  }

  const readAll = async () => {
    await notificationsApi.readAll().catch(() => {})
    setItems((list) => list?.map((n) => ({ ...n, is_read: true })))
    setUnread(0)
  }

  return (
    <div className={styles.account} ref={ref}>
      <button className={styles.navLink} onClick={toggle} aria-expanded={open}
              aria-label={unread ? `Уведомления: ${unread} непрочитанных` : 'Уведомления'} title="Уведомления">
        <span aria-hidden="true">🔔</span>
        {unread > 0 && <span className={styles.counter}>{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className={`${styles.menu} ${styles.notifications}`}>
          <div className={styles.notifHead}>
            <strong>Уведомления</strong>
            {unread > 0 && <button className={styles.notifReadAll} onClick={readAll}>Прочитать все</button>}
          </div>
          {items === null ? <div className={styles.notifEmpty}>Загрузка…</div>
            : items.length === 0 ? <div className={styles.notifEmpty}>Пока ничего нет</div>
              : items.map((n) => (
                <button key={n.id} className={`${styles.notifItem} ${n.is_read ? '' : styles.notifUnread}`} onClick={() => openItem(n)}>
                  <span>{n.text}</span>
                  <span className={styles.notifDate}>{formatDateTime(n.created_at)}</span>
                </button>
              ))}
        </div>
      )}
    </div>
  )
}

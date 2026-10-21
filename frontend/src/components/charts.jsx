/**
 * Графики для отчётов — на SVG, без библиотек.
 * Правила: одна ось Y; линия 2px, заливка ~10%; сетка — тонкая и бледная; подписи — цветом текста,
 * а не цветом данных; подсказка при наведении и с клавиатуры (стрелки); у графика есть табличный вид.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { formatMoney } from '../utils/format'
import styles from './charts.module.css'

const compact = new Intl.NumberFormat('ru-RU', { notation: 'compact', maximumFractionDigits: 1 })
const dayMonth = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short' })
const monthYear = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric' })

/** Подпись интервала графика: «7 окт.», «неделя с 6 окт.», «октябрь 2026 г.» */
export function bucketLabel(date, group) {
  const d = new Date(`${date}T00:00:00`)
  if (group === 'month') return monthYear.format(d)
  if (group === 'week') return `неделя с ${dayMonth.format(d)}`
  return dayMonth.format(d)
}

/** «Красивый» верх шкалы и шаг: 0, 250, 500, 750, 1 000 вместо 0, 233, 466… */
function niceScale(max, ticks = 4) {
  if (!max) return { top: ticks, step: 1 }
  const raw = max / ticks
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw)
  return { top: step * ticks, step }
}

function useWidth() {
  const ref = useRef(null)
  const [width, setWidth] = useState(600)
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

// ---------- Плитка показателя ----------

/**
 * value — текущее значение, previous — за прошлый период такой же длины.
 * upIsGood=false для «плохих» показателей (возвраты, отмены): их рост — красным.
 * Изменение подписано стрелкой и словами, а не только цветом.
 */
export function StatTile({ label, value, previous, format = String, upIsGood = true, hint, hero = false }) {
  const cur = Number(value)
  const prev = Number(previous)
  let delta = null
  if (previous !== undefined) {
    if (prev === 0 && cur === 0) delta = { text: 'без изменений', tone: 'flat' }
    else if (prev === 0) delta = { text: 'в прошлом периоде — 0', tone: upIsGood ? 'good' : 'bad', arrow: '▲' }
    else {
      const pct = ((cur - prev) / Math.abs(prev)) * 100
      const up = pct > 0
      delta = Math.abs(pct) < 0.05
        ? { text: 'без изменений', tone: 'flat' }
        : { text: `${Math.abs(pct).toFixed(1).replace('.', ',')}% к прошлому периоду`, arrow: up ? '▲' : '▼',
            tone: up === upIsGood ? 'good' : 'bad' }
    }
  }
  return (
    <div className={`${styles.tile} ${hero ? styles.hero : ''}`}>
      <span className={styles.tileLabel}>{label}</span>
      <span className={styles.tileValue}>{format(value)}</span>
      {delta && (
        <span className={`${styles.delta} ${styles[delta.tone]}`}>
          {delta.arrow && <span aria-hidden="true">{delta.arrow} </span>}{delta.text}
        </span>
      )}
      {hint && <span className={styles.tileHint}>{hint}</span>}
    </div>
  )
}

// ---------- Линия во времени ----------

/**
 * points: [{ date, value, rows: [[подпись, значение-строкой]] }] — rows показываются в подсказке.
 * Одна серия: легенда не нужна, что изображено — говорит заголовок над графиком.
 */
export function TrendChart({ points, group, valueFormat = formatMoney, height = 260, title }) {
  const [ref, width] = useWidth()
  const [active, setActive] = useState(null)
  const pad = { top: 16, right: 16, bottom: 28, left: 56 }
  const innerW = Math.max(width - pad.left - pad.right, 50)
  const innerH = height - pad.top - pad.bottom
  const max = Math.max(...points.map((p) => p.value), 0)
  const { top, step } = niceScale(max)
  const x = (i) => pad.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const y = (v) => pad.top + innerH - (v / top) * innerH

  const line = points.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.value)}`).join(' ')
  const area = `${line} L${x(points.length - 1)},${y(0)} L${x(0)},${y(0)} Z`
  const ticks = Array.from({ length: Math.round(top / step) + 1 }, (_, i) => i * step)
  // Подписи по оси X — не больше 6, чтобы не налезали друг на друга
  const every = Math.max(1, Math.ceil(points.length / 6))

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const rel = (e.clientX - rect.left - pad.left) / innerW
    setActive(Math.min(points.length - 1, Math.max(0, Math.round(rel * (points.length - 1)))))
  }
  const onKey = (e) => {
    if (e.key === 'ArrowRight') setActive((i) => Math.min(points.length - 1, (i ?? -1) + 1))
    if (e.key === 'ArrowLeft') setActive((i) => Math.max(0, (i ?? points.length) - 1))
  }
  const point = active !== null ? points[active] : null
  const tooltipLeft = point ? Math.min(Math.max(x(active) + 12, 0), width - 210) : 0

  return (
    <div className={styles.chartWrap}>
      <div ref={ref} className={styles.chart} tabIndex={0} role="img" aria-label={`${title}. Стрелки влево и вправо — значения по датам`}
           onKeyDown={onKey} onFocus={() => setActive((i) => i ?? points.length - 1)} onBlur={() => setActive(null)}>
        <svg width={width} height={height} onPointerMove={onMove} onPointerLeave={() => setActive(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={pad.left} x2={pad.left + innerW} y1={y(t)} y2={y(t)} className={t === 0 ? styles.baseline : styles.grid} />
              <text x={pad.left - 8} y={y(t)} className={styles.axisText} textAnchor="end" dominantBaseline="middle">
                {t === 0 ? '0' : compact.format(t)}
              </text>
            </g>
          ))}
          {points.map((p, i) => (i % every === 0 || i === points.length - 1) && (
            <text key={p.date} x={x(i)} y={height - 8} className={styles.axisText} textAnchor="middle">
              {group === 'month' ? monthYear.format(new Date(`${p.date}T00:00:00`)).split(' ')[0] : dayMonth.format(new Date(`${p.date}T00:00:00`))}
            </text>
          ))}
          <path d={area} className={styles.area} />
          <path d={line} className={styles.line} />
          {point && (
            <>
              <line x1={x(active)} x2={x(active)} y1={pad.top} y2={pad.top + innerH} className={styles.crosshair} />
              <circle cx={x(active)} cy={y(point.value)} r={5} className={styles.dot} />
            </>
          )}
          {/* Невидимая область наведения — на весь график, а не на тонкую линию */}
          <rect x={pad.left} y={pad.top} width={innerW} height={innerH} fill="transparent" />
        </svg>
        {point && (
          <div className={styles.tooltip} style={{ left: tooltipLeft, top: pad.top }} role="status">
            <div className={styles.tooltipValue}>{valueFormat(point.value)}</div>
            <div className={styles.tooltipDate}>{bucketLabel(point.date, group)}</div>
            {point.rows?.map(([label, value]) => (
              <div key={label} className={styles.tooltipRow}><span>{label}</span><strong>{value}</strong></div>
            ))}
          </div>
        )}
        {max === 0 && <div className={styles.empty}>За период продаж нет</div>}
      </div>
      <details className={styles.tableToggle}>
        <summary>Таблица данных</summary>
        <div className={styles.tableScroll}>
          <table className="table">
            <thead><tr><th>Период</th><th style={{ textAlign: 'right' }}>{title}</th>
              {points[0]?.rows?.map(([label]) => <th key={label} style={{ textAlign: 'right' }}>{label}</th>)}</tr></thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.date}>
                  <td>{bucketLabel(p.date, group)}</td>
                  <td style={{ textAlign: 'right' }}>{valueFormat(p.value)}</td>
                  {p.rows?.map(([label, value]) => <td key={label} style={{ textAlign: 'right' }}>{value}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}

// ---------- Горизонтальные полосы ----------

/** items: [{ key, label, value, valueText, note }] — длина полосы ~ value, подпись значения у конца полосы */
export function BarList({ items, emptyText = 'Нет данных' }) {
  const max = useMemo(() => Math.max(...items.map((i) => i.value), 0), [items])
  if (!items.length || max === 0) return <p className="muted small" style={{ margin: 0 }}>{emptyText}</p>
  return (
    <ul className={styles.bars}>
      {items.map((item) => (
        <li key={item.key} title={`${item.label}: ${item.valueText}`}>
          <span className={styles.barLabel}>{item.label}</span>
          <span className={styles.barTrack}>
            {/* Под подпись значения резервируем место (--label), полоса масштабируется в остатке — подпись не вылезает за край */}
            <span className={styles.bar} style={{ width: `max(2px, calc((100% - var(--label)) * ${item.value / max}))` }} />
            <span className={styles.barValue}>{item.valueText}{item.note && <span className={styles.barNote}> · {item.note}</span>}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

// ---------- Фильтр периода ----------

// Дата по местному времени: toISOString() дал бы дату в UTC — вечером по Москве «сегодня» стало бы «вчера»
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const daysAgo = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return iso(d) }
const PRESETS = [
  ['7', 'Неделя', () => ({ date_from: daysAgo(6), date_to: daysAgo(0) })],
  ['30', '30 дней', () => ({ date_from: daysAgo(29), date_to: daysAgo(0) })],
  ['90', '90 дней', () => ({ date_from: daysAgo(89), date_to: daysAgo(0) })],
  ['month', 'Этот месяц', () => { const d = new Date(); d.setDate(1); return { date_from: iso(d), date_to: daysAgo(0) } }],
]

export function defaultPeriod() {
  return { preset: '30', ...PRESETS[1][2](), group: 'day' }
}

/** Одна строка над всеми графиками: пресеты, свои даты, шаг графика. Меняет период сразу у всего отчёта. */
export function PeriodFilter({ value, onChange }) {
  return (
    <div className={styles.filters}>
      <div className={styles.presets} role="group" aria-label="Период">
        {PRESETS.map(([key, label, make]) => (
          <button key={key} type="button" aria-pressed={value.preset === key}
                  className={`btn btn-sm ${value.preset === key ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => onChange({ ...value, preset: key, ...make() })}>{label}</button>
        ))}
      </div>
      <label className={styles.dateField}>с
        <input className="input" type="date" value={value.date_from} max={value.date_to}
               onChange={(e) => e.target.value && onChange({ ...value, preset: 'custom', date_from: e.target.value })} />
      </label>
      <label className={styles.dateField}>по
        <input className="input" type="date" value={value.date_to} min={value.date_from}
               onChange={(e) => e.target.value && onChange({ ...value, preset: 'custom', date_to: e.target.value })} />
      </label>
      <select className="select" style={{ width: 'auto' }} value={value.group} aria-label="Шаг графика"
              onChange={(e) => onChange({ ...value, group: e.target.value })}>
        <option value="day">по дням</option><option value="week">по неделям</option><option value="month">по месяцам</option>
      </select>
    </div>
  )
}

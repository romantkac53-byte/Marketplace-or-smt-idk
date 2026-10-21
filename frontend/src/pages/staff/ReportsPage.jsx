/** Отчёты руководителя и администратора: сводка, динамика, магазины, категории, товары, доставка. */
import { useState } from 'react'
import { reportsApi } from '../../api'
import { BarList, PeriodFilter, StatTile, TrendChart, defaultPeriod } from '../../components/charts'
import chartStyles from '../../components/charts.module.css'
import { ErrorMessage, Loader } from '../../components/ui'
import { formatDate, formatMoney, plural } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

const pct = (v) => `${String(v).replace('.', ',')}%`
const num = (v) => new Intl.NumberFormat('ru-RU').format(v)

/** Таблица отчёта с кнопкой «Скачать для Excel» */
function ReportTable({ title, report, params, columns, rows, empty }) {
  const [state, setState] = useState({ busy: false, error: '' })
  const download = async () => {
    setState({ busy: true, error: '' })
    try { await reportsApi.exportCsv(report, params) } catch (e) { setState({ busy: false, error: e.message }); return }
    setState({ busy: false, error: '' })
  }
  return (
    <section className="card stack">
      <div className="row">
        <h3 style={{ margin: 0 }}>{title}</h3>
        <span className="spacer" />
        <button className="btn btn-outline btn-sm" onClick={download} disabled={state.busy || !rows.length}>⬇ Скачать для Excel</button>
      </div>
      {state.error && <div className="alert alert-error">{state.error}</div>}
      {rows.length === 0 ? <p className="muted small" style={{ margin: 0 }}>{empty}</p> : (
        <div className={styles.tableWrap}>
          <table className="table">
            <thead><tr>{columns.map(([, label, right]) => <th key={label} className={right ? styles.num : undefined}>{label}</th>)}</tr></thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>{columns.map(([render, label, right]) => <td key={label} className={right ? styles.num : undefined}>{render(row)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default function ReportsPage() {
  const [period, setPeriod] = useState(defaultPeriod)
  const params = { date_from: period.date_from, date_to: period.date_to, group: period.group }
  const key = JSON.stringify(params)
  const dash = useLoad(() => reportsApi.dashboard(params), [key])
  const sellers = useLoad(() => reportsApi.sellers(params), [key])
  const categories = useLoad(() => reportsApi.categories(params), [key])
  const products = useLoad(() => reportsApi.products(params), [key])

  const d = dash.data
  const s = d?.summary
  const p = d?.previous
  const refetching = dash.loading && d // при смене периода держим прошлую картинку, полупрозрачной

  return (
    <>
      <div className={styles.head}><h1>Отчёты</h1>
        {d && <span className="muted">{formatDate(d.period.date_from)} — {formatDate(d.period.date_to)}</span>}</div>
      <PeriodFilter value={period} onChange={setPeriod} />
      <ErrorMessage error={dash.error} onRetry={dash.reload} />

      {!d ? <Loader /> : (
        <div className="stack" style={{ opacity: refetching ? 0.55 : 1, transition: 'opacity .15s', gap: 16 }}>
          <div className={chartStyles.tiles}>
            <StatTile hero label="Оборот (GMV)" value={s.gmv} previous={p.gmv} format={formatMoney}
                      hint="Оплаченные заказы без отменённых частей" />
            <StatTile label="Доход площадки (комиссия)" value={s.commission} previous={p.commission} format={formatMoney} />
            <StatTile label="Выплаты продавцам" value={s.seller_payout} previous={p.seller_payout} format={formatMoney} />
            <StatTile label="Заказы" value={s.orders} previous={p.orders} format={num} hint={`${plural(s.items_sold, ['товар', 'товара', 'товаров'])} продано`} />
            <StatTile label="Средний чек" value={s.average_check} previous={p.average_check} format={formatMoney} />
            <StatTile label="Возвраты" value={s.returns_amount} previous={p.returns_amount} format={formatMoney} upIsGood={false}
                      hint={`${pct(s.returns_share)} оборота · ${s.returns_quantity} шт.`} />
            <StatTile label="Отменено подзаказов" value={s.cancelled_share} previous={p.cancelled_share} format={pct} upIsGood={false} />
            <StatTile label="Новые покупатели" value={s.new_customers} previous={p.new_customers} format={num}
                      hint={`новых магазинов: ${s.new_sellers}${s.pending_sellers ? ` · ждут проверки: ${s.pending_sellers}` : ''}`} />
          </div>

          <section className="card stack">
            <h3 style={{ margin: 0 }}>Оборот по {period.group === 'day' ? 'дням' : period.group === 'week' ? 'неделям' : 'месяцам'}</h3>
            <TrendChart title="Оборот" group={period.group}
                        points={d.series.map((x) => ({
                          date: x.date, value: Number(x.gmv),
                          rows: [['Комиссия', formatMoney(x.commission)], ['Заказов', num(x.orders)]],
                        }))} />
          </section>

          <div className={styles.formGrid}>
            <section className="card stack">
              <h3 style={{ margin: 0 }}>Оборот по категориям</h3>
              {categories.data && (
                <BarList emptyText="Продаж за период нет" items={categories.data.results.map((c) => ({
                  key: c.category_id, label: c.category, value: Number(c.gmv), valueText: formatMoney(c.gmv), note: pct(c.share),
                }))} />
              )}
            </section>
            <section className="card stack">
              <h3 style={{ margin: 0 }}>Доставка</h3>
              {d.deliveries.total === 0 ? <p className="muted small" style={{ margin: 0 }}>Посылок за период не было</p> : (
                <>
                  <div className={styles.money}>
                    <div className={styles.moneyItem}><span className="small muted">Посылок</span><strong>{d.deliveries.total}</strong></div>
                    <div className={styles.moneyItem}><span className="small muted">Получено</span><strong>{pct(d.deliveries.delivered_share)}</strong></div>
                    <div className={styles.moneyItem}><span className="small muted">От оплаты до получения</span>
                      <strong>{d.deliveries.average_hours === null ? '—' : `${String(d.deliveries.average_hours).replace('.', ',')} ч`}</strong></div>
                  </div>
                  <span className="small muted">Курьером: {d.deliveries.courier} · в пункты выдачи: {d.deliveries.pickup}</span>
                  <BarList items={d.deliveries.by_status.filter((x) => x.count).map((x) => ({
                    key: x.status, label: x.label, value: x.count, valueText: num(x.count),
                  }))} />
                </>
              )}
            </section>
          </div>

          {sellers.data && (
            <ReportTable title="Магазины" report="sellers" params={params} rows={sellers.data.results} empty="Продаж за период нет"
                         columns={[
                           [(r) => r.store_name, 'Магазин'], [(r) => num(r.orders), 'Заказов', true], [(r) => num(r.items_sold), 'Продано, шт.', true],
                           [(r) => formatMoney(r.gmv), 'Оборот', true], [(r) => formatMoney(r.commission), 'Комиссия', true],
                           [(r) => formatMoney(r.seller_payout), 'Выплата', true], [(r) => formatMoney(r.returns_amount), 'Возвраты', true],
                           [(r) => (r.rating === null ? '—' : `★ ${String(r.rating).replace('.', ',')}`), 'Рейтинг', true],
                         ]} />
          )}
          {products.data && (
            <ReportTable title="Топ товаров" report="products" params={params} rows={products.data.results.slice(0, 10)} empty="Продаж за период нет"
                         columns={[
                           [(r) => r.name, 'Товар'], [(r) => r.store_name, 'Магазин'],
                           [(r) => num(r.items_sold), 'Продано, шт.', true], [(r) => formatMoney(r.gmv), 'Оборот', true],
                         ]} />
          )}
          {categories.data && (
            <ReportTable title="Категории" report="categories" params={params} rows={categories.data.results} empty="Продаж за период нет"
                         columns={[
                           [(r) => r.category, 'Категория'], [(r) => num(r.items_sold), 'Продано, шт.', true],
                           [(r) => formatMoney(r.gmv), 'Оборот', true], [(r) => formatMoney(r.commission), 'Комиссия', true],
                           [(r) => pct(r.share), 'Доля', true],
                         ]} />
          )}
        </div>
      )}
    </>
  )
}

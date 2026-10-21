/** Сводка продавца: продажи своего магазина за период. */
import { useState } from 'react'
import { sellerApi } from '../../api'
import { BarList, PeriodFilter, StatTile, TrendChart, defaultPeriod } from '../../components/charts'
import chartStyles from '../../components/charts.module.css'
import { ErrorMessage, Loader } from '../../components/ui'
import { formatMoney } from '../../utils/format'
import { useLoad } from '../../utils/useLoad'
import styles from '../cabinet.module.css'

const num = (v) => new Intl.NumberFormat('ru-RU').format(v)
const pct = (v) => `${String(v).replace('.', ',')}%`

export default function SellerStatsPage() {
  const [period, setPeriod] = useState(defaultPeriod)
  const params = { date_from: period.date_from, date_to: period.date_to, group: period.group }
  const { data, loading, error, reload } = useLoad(() => sellerApi.stats(params), [JSON.stringify(params)])
  const s = data?.summary
  const p = data?.previous

  return (
    <>
      <div className={styles.head}><h1>Сводка</h1></div>
      <PeriodFilter value={period} onChange={setPeriod} />
      <ErrorMessage error={error} onRetry={reload} />
      {!data ? <Loader /> : (
        <div className="stack" style={{ opacity: loading ? 0.55 : 1, transition: 'opacity .15s', gap: 16 }}>
          <div className={chartStyles.tiles}>
            <StatTile hero label="К выплате вам" value={s.seller_payout} previous={p.seller_payout} format={formatMoney}
                      hint="Оборот минус комиссия площадки" />
            <StatTile label="Оборот" value={s.gmv} previous={p.gmv} format={formatMoney} />
            <StatTile label="Комиссия площадки" value={s.commission} previous={p.commission} format={formatMoney} upIsGood={false} />
            <StatTile label="Заказы" value={s.orders} previous={p.orders} format={num} hint={`продано ${num(s.items_sold)} шт.`} />
            <StatTile label="Средний чек" value={s.average_check} previous={p.average_check} format={formatMoney} />
            <StatTile label="Возвраты" value={s.returns_amount} previous={p.returns_amount} format={formatMoney} upIsGood={false}
                      hint={`${pct(s.returns_share)} оборота`} />
          </div>
          <section className="card stack">
            <h3 style={{ margin: 0 }}>Оборот магазина</h3>
            <TrendChart title="Оборот" group={period.group}
                        points={data.series.map((x) => ({ date: x.date, value: Number(x.gmv), rows: [['Заказов', num(x.orders)]] }))} />
          </section>
          <section className="card stack">
            <h3 style={{ margin: 0 }}>Лучшие товары</h3>
            <BarList emptyText="Продаж за период нет" items={data.top_products.map((t) => ({
              key: t.product_id, label: t.name, value: t.items_sold, valueText: `${num(t.items_sold)} шт.`, note: formatMoney(t.gmv),
            }))} />
          </section>
        </div>
      )}
    </>
  )
}

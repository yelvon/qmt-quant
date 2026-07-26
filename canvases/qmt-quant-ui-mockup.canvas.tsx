import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Grid,
  H1,
  H2,
  H3,
  LineChart,
  Pill,
  Row,
  Spacer,
  Stack,
  Stat,
  Table,
  Text,
  Toggle,
  UsageBar,
  useCanvasState,
  useHostTheme,
} from "cursor/canvas";

type PageId =
  | "dashboard"
  | "data"
  | "research"
  | "validation"
  | "screening"
  | "live";

const NAV: { id: PageId; label: string; phase: string }[] = [
  { id: "dashboard", label: "总览", phase: "P0" },
  { id: "data", label: "数据中心", phase: "P0" },
  { id: "research", label: "研究回测", phase: "P0" },
  { id: "validation", label: "验证回测", phase: "P0" },
  { id: "screening", label: "选股", phase: "P1" },
  { id: "live", label: "实盘", phase: "P2" },
];

const equityDates = [
  "2024-01", "2024-04", "2024-07", "2024-10",
  "2025-01", "2025-04", "2025-07", "2025-10", "2026-01", "2026-04",
];
const equityVbt = [100, 103, 108, 112, 118, 121, 128, 134, 141, 148];
const equityNt = [100, 102, 106, 109, 114, 116, 122, 127, 132, 138];
const equityBench = [100, 101, 104, 106, 109, 111, 113, 115, 117, 119];

const heatmapCats = ["5/30", "5/60", "10/30", "10/60", "20/60", "20/120"];
const heatmapReturns = [12.4, 18.2, 15.1, 22.8, 19.6, 24.1];

function Sidebar({
  active,
  onSelect,
}: {
  active: PageId;
  onSelect: (id: PageId) => void;
}) {
  const theme = useHostTheme();
  return (
    <Stack
      gap={4}
      style={{
        width: 196,
        minWidth: 196,
        padding: "16px 12px",
        background: theme.bg.chrome,
        borderRight: `1px solid ${theme.stroke.tertiary}`,
        minHeight: 720,
      }}
    >
      <Text weight="semibold" style={{ padding: "4px 8px 12px", fontSize: 15 }}>
        qmt-quant
      </Text>
      <Text tone="tertiary" size="small" style={{ padding: "0 8px 8px" }}>
        QMT 本地量化工作台
      </Text>
      {NAV.map((item) => {
        const selected = active === item.id;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              width: "100%",
              padding: "8px 10px",
              border: "none",
              borderRadius: 6,
              cursor: "pointer",
              textAlign: "left",
              background: selected ? theme.fill.secondary : "transparent",
              color: selected ? theme.text.primary : theme.text.secondary,
            }}
          >
            <span style={{ fontSize: 13 }}>{item.label}</span>
            <span
              style={{
                fontSize: 10,
                color: theme.text.quaternary,
                fontFamily: "monospace",
              }}
            >
              {item.phase}
            </span>
          </button>
        );
      })}
      <Spacer />
      <Stack gap={6} style={{ padding: "8px" }}>
        <Row gap={8} align="center">
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: theme.category.green,
              display: "inline-block",
            }}
          />
          <Text size="small" tone="secondary">
            QMT 已连接
          </Text>
        </Row>
        <Text size="small" tone="quaternary">
          C:\qmt · 国金证券
        </Text>
      </Stack>
    </Stack>
  );
}

function TopBar({ title, subtitle }: { title: string; subtitle: string }) {
  const theme = useHostTheme();
  return (
    <Row
      align="center"
      style={{
        padding: "16px 24px",
        borderBottom: `1px solid ${theme.stroke.tertiary}`,
        background: theme.bg.editor,
      }}
    >
      <Stack gap={2}>
        <H2 style={{ margin: 0 }}>{title}</H2>
        <Text tone="tertiary" size="small">
          {subtitle}
        </Text>
      </Stack>
      <Spacer />
      <Row gap={8}>
        <Button variant="ghost">任务日志</Button>
        <Button variant="ghost">设置</Button>
      </Row>
    </Row>
  );
}

function DashboardPage() {
  const theme = useHostTheme();
  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <Grid columns={4} gap={12}>
        <Stat label="日线覆盖率" value="98.6%" tone="success" />
        <Stat label="财务表同步" value="4/4" tone="success" />
        <Stat label="最近研究任务" value="12.8s" tone="info" />
        <Stat label="验证通过率" value="3/4" tone="warning" />
      </Grid>

      <H3>数据新鲜度</H3>
      <UsageBar
        total={5120}
        topLeftLabel="数据新鲜度 98.6%"
        topRightLabel="4862 完整 · 138 缺口"
        segments={[
          { id: "bars", value: 4862, color: "green" },
          { id: "financial", value: 4120, color: "blue" },
          { id: "gaps", value: 138, color: "yellow" },
        ]}
      />
      <Text tone="quaternary" size="small">
        沪深 A 股 · 前复权 · 截至 2026-07-25
      </Text>

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader trailing={<Pill tone="success">运行中</Pill>}>
            快捷操作
          </CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Button variant="primary">增量同步日线</Button>
              <Button variant="secondary">导出 Parquet Catalog</Button>
              <Button variant="secondary">运行双引擎 Pipeline</Button>
              <Button variant="ghost">全市场选股</Button>
            </Stack>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>最近任务</CardHeader>
          <CardBody style={{ padding: 0 }}>
            <Table
              framed={false}
              headers={["任务", "状态", "耗时"]}
              rows={[
                ["sync bars incremental", <Pill tone="success">完成</Pill>, "11m 24s"],
                ["catalog export", <Pill tone="success">完成</Pill>, "2m 08s"],
                ["research ma_cross sweep", <Pill tone="success">完成</Pill>, "12.8s"],
                ["validate ma_cross", <Pill tone="info">排队</Pill>, "—"],
              ]}
              columnAlign={["left", "center", "right"]}
            />
          </CardBody>
        </Card>
      </Grid>

      <H3>研究工作流</H3>
      <Row gap={8} wrap>
        {["QMT 同步", "Parquet", "VectorBT 扫描", "Nautilus 验证", "选股桥接", "实盘 P2"].map(
          (step, i, arr) => (
            <div key={step} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Pill tone={i < 4 ? "success" : i === 4 ? "info" : "neutral"}>
                {step}
              </Pill>
              {i < arr.length - 1 ? (
                <Text tone="quaternary" size="small">
                  →
                </Text>
              ) : null}
            </div>
          ),
        )}
      </Row>

      <CalloutMini
        tone="info"
        text="建议每日收盘后执行：增量同步 → Catalog 导出 → 选股 → 研究扫描 → 验证确认。"
      />
    </Stack>
  );
}

function CalloutMini({ tone, text }: { tone: "info" | "warning"; text: string }) {
  const theme = useHostTheme();
  const color = tone === "info" ? theme.category.blue : theme.category.yellow;
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 6,
        border: `1px solid ${theme.stroke.secondary}`,
        borderLeft: `3px solid ${color}`,
        background: theme.fill.tertiary,
      }}
    >
      <Text size="small" tone="secondary">
        {text}
      </Text>
    </div>
  );
}

function DataPage() {
  const [autoExport, setAutoExport] = useCanvasState("data-auto-export", true);
  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <Grid columns={3} gap={12}>
        <Card>
          <CardHeader>日线同步</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Row gap={8}>
                <Pill>沪深A股</Pill>
                <Pill tone="info">前复权</Pill>
                <Pill>2020-01-01 起</Pill>
              </Row>
              <Text tone="secondary" size="small">
                上次增量：2026-07-25 18:42 · 成功 5120 / 失败 3
              </Text>
              <Row gap={8}>
                <Button variant="primary">立即增量同步</Button>
                <Button variant="ghost">重试失败项</Button>
              </Row>
            </Stack>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>财务同步</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Row gap={6} wrap>
                {["Balance", "Income", "CashFlow", "Pershareindex"].map((t) => (
                  <span key={t}>
                    <Pill tone="success">{t}</Pill>
                  </span>
                ))}
              </Row>
              <Text tone="secondary" size="small">
                按披露日存储 · 最近更新 2026-07-24
              </Text>
              <Button variant="secondary">同步财务增量</Button>
            </Stack>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>Catalog 导出</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Row gap={8} align="center">
                <Toggle checked={autoExport} onChange={setAutoExport} />
                <Text size="small">同步后自动导出 Parquet</Text>
              </Row>
              <Text tone="secondary" size="small">
                目录 data/catalog · 供 NautilusTrader 读取
              </Text>
              <Button variant="secondary">手动导出</Button>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <H3>数据健康检查 · 2026-07-25</H3>
      <Table
        striped
        headers={["检查项", "结果", "覆盖率", "说明"]}
        rows={[
          ["日线 OHLCV", "通过", "98.6%", "138 只股票存在缺口"],
          ["交易日历", "通过", "100%", "2020–2026 完整"],
          ["财务披露日", "通过", "96.2%", "部分新股无历史报表"],
          ["Parquet Catalog", "通过", "98.6%", "与 SQLite 一致"],
        ]}
        rowTone={["success", "success", "warning", "success"]}
        columnAlign={["left", "left", "right", "left"]}
      />
    </Stack>
  );
}

function ResearchPage() {
  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <Grid columns={3} gap={16}>
        <Card style={{ gridColumn: "span 1" }}>
          <CardHeader>策略配置 · VectorBT</CardHeader>
          <CardBody>
            <Stack gap={12}>
              <ConfigRow label="策略" value="ma_cross · 双均线" />
              <ConfigRow label="标的池" value="watchlist.txt (50)" />
              <ConfigRow label="区间" value="2022-01-01 — 2025-12-31" />
              <ConfigRow label="短均线" value="5, 10, 20" />
              <ConfigRow label="长均线" value="30, 60, 120" />
              <ConfigRow label="组合" value="cash_sharing · 费率 0.03%" />
              <Button variant="primary">开始参数扫描</Button>
            </Stack>
          </CardBody>
        </Card>

        <Stack gap={16} style={{ gridColumn: "span 2" }}>
          <Card>
            <CardHeader trailing={<Pill tone="success">12.8s</Pill>}>
              参数扫描热力图（累计收益 %）
            </CardHeader>
            <CardBody>
              <LineChart
                height={200}
                categories={heatmapCats}
                valueSuffix="%"
                series={[{ name: "累计收益", data: heatmapReturns, tone: "info" }]}
                beginAtZero
              />
              <Text tone="quaternary" size="small">
                快/慢均线窗口组合 · 累计收益 (%) · VectorBT ma_cross · 50 标的 · 2022–2025
              </Text>
            </CardBody>
          </Card>

          <Grid columns={4} gap={12}>
            <Stat label="最优组合" value="20/120" tone="success" />
            <Stat label="累计收益" value="+24.1%" tone="success" />
            <Stat label="夏普" value="1.42" tone="info" />
            <Stat label="最大回撤" value="-11.3%" tone="warning" />
          </Grid>
        </Stack>
      </Grid>

      <Row gap={8}>
        <Button variant="primary">发送到 Nautilus 验证</Button>
        <Button variant="secondary">导出研究报告</Button>
        <Button variant="ghost">Walk-Forward 分析</Button>
      </Row>
    </Stack>
  );
}

function ConfigRow({ label, value }: { label: string; value: string }) {
  const theme = useHostTheme();
  return (
    <Row gap={8} align="center">
      <Text tone="tertiary" size="small" style={{ width: 72 }}>
        {label}
      </Text>
      <Text size="small" style={{ fontFamily: "monospace" }}>
        {value}
      </Text>
    </Row>
  );
}

function ValidationPage() {
  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <Grid columns={3} gap={16}>
        <Card>
          <CardHeader>验证配置 · NautilusTrader</CardHeader>
          <CardBody>
            <Stack gap={12}>
              <ConfigRow label="策略" value="ma_cross" />
              <ConfigRow label="参数" value="short=20 long=120" />
              <ConfigRow label="Venue" value="CN_A_SHARE" />
              <ConfigRow label="规则" value="T+1 · 100股整手" />
              <ConfigRow label="撮合" value="next_open + 5bps" />
              <ConfigRow label="来源" value="研究层推送" />
              <Button variant="primary">运行高保真验证</Button>
            </Stack>
          </CardBody>
        </Card>

        <Stack gap={16} style={{ gridColumn: "span 2" }}>
          <Card>
            <CardHeader>净值曲线对比（归一化 100）</CardHeader>
            <CardBody>
              <LineChart
                height={220}
                categories={equityDates}
                series={[
                  { name: "策略 (NT)", data: equityNt, tone: "success" },
                  { name: "研究 (VBT)", data: equityVbt, tone: "info" },
                  { name: "沪深300", data: equityBench, tone: "neutral" },
                ]}
                beginAtZero={false}
                yMin={95}
                yMax={155}
              />
              <Text tone="quaternary" size="small">
                净值（归一化 100）· 日期 · NautilusTrader 验证 2024-01 至 2026-04
              </Text>
            </CardBody>
          </Card>

          <Grid columns={4} gap={12}>
            <Stat label="验证收益" value="+38.0%" tone="success" />
            <Stat label="与 VBT 偏差" value="-6.1%" tone="warning" />
            <Stat label="成交笔数" value="186" tone="info" />
            <Stat label="验证结论" value="通过" tone="success" />
          </Grid>
        </Stack>
      </Grid>

      <H3>成交明细（最近 5 笔）</H3>
      <Table
        striped
        headers={["日期", "代码", "方向", "价格", "数量", "费用"]}
        rows={[
          ["2026-04-18", "600519.SH", "买入", "1682.00", "100", "50.46"],
          ["2026-04-22", "000001.SZ", "买入", "11.24", "4400", "14.83"],
          ["2026-05-06", "600519.SH", "卖出", "1710.50", "100", "221.37"],
          ["2026-06-11", "300750.SZ", "买入", "198.30", "500", "29.75"],
          ["2026-07-03", "000001.SZ", "卖出", "12.08", "4400", "68.12"],
        ]}
        columnAlign={["left", "left", "center", "right", "right", "right"]}
      />
    </Stack>
  );
}

function ScreeningPage() {
  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>选股规则 · low_pe_momentum</CardHeader>
          <CardBody>
            <pre
              style={{
                margin: 0,
                fontSize: 11,
                lineHeight: 1.5,
                fontFamily: "monospace",
                whiteSpace: "pre-wrap",
              }}
            >
{`filters:
  pe_ttm < 30
  roe > 0.10
  close above_ma(60)
exclude: ST, 上市<120天
rank_by: momentum_20d
top_n: 30`}
            </pre>
            <Row gap={8} style={{ marginTop: 12 }}>
              <Button variant="primary">运行选股</Button>
              <Button variant="ghost">编辑规则</Button>
            </Row>
          </CardBody>
        </Card>

        <Card>
          <CardHeader trailing={<Pill>2026-07-25</Pill>}>
            选股结果 Top 8 / 30
          </CardHeader>
          <CardBody style={{ padding: 0 }}>
            <Table
              framed={false}
              headers={["代码", "名称", "PE", "动量20d", "得分"]}
              rows={[
                ["600519.SH", "贵州茅台", "24.1", "+8.2%", "0.91"],
                ["000858.SZ", "五粮液", "18.6", "+6.4%", "0.87"],
                ["601318.SH", "中国平安", "9.8", "+5.1%", "0.84"],
                ["000333.SZ", "美的集团", "12.3", "+4.8%", "0.82"],
                ["600036.SH", "招商银行", "6.2", "+3.9%", "0.79"],
                ["002415.SZ", "海康威视", "21.4", "+7.1%", "0.78"],
                ["300750.SZ", "宁德时代", "28.7", "+9.3%", "0.76"],
                ["601012.SH", "隆基绿能", "14.5", "+6.0%", "0.74"],
              ]}
              columnAlign={["left", "left", "right", "right", "right"]}
            />
          </CardBody>
        </Card>
      </Grid>

      <Row gap={8}>
        <Button variant="primary">VectorBT 回测选股池</Button>
        <Button variant="secondary">Nautilus 验证选股池</Button>
        <Button variant="ghost">因子 IC 分析</Button>
      </Row>
    </Stack>
  );
}

function LivePage() {
  const [dryRun, setDryRun] = useCanvasState("live-dry-run", true);
  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <CalloutMini
        tone="warning"
        text="实盘模块为 P2 阶段。默认 Dry Run 模式，不会真实下单。启用实盘需二次确认并输入资金账号。"
      />

      <Row gap={16} align="center">
        <Toggle checked={dryRun} onChange={setDryRun} />
        <Text weight="semibold">Dry Run（模拟下单）</Text>
        <Pill tone={dryRun ? "warning" : "deleted"}>
          {dryRun ? "模拟模式" : "实盘模式"}
        </Pill>
      </Row>

      <Grid columns={4} gap={12}>
        <Stat label="总资产" value="¥1,024,680" tone="success" />
        <Stat label="可用资金" value="¥312,400" tone="info" />
        <Stat label="持仓市值" value="¥712,280" tone="info" />
        <Stat label="今日盈亏" value="+0.42%" tone="success" />
      </Grid>

      <H3>当前持仓</H3>
      <Table
        striped
        headers={["代码", "名称", "数量", "成本", "现价", "盈亏"]}
        rows={[
          ["600519.SH", "贵州茅台", "100", "1650.00", "1682.00", "+1.94%"],
          ["000001.SZ", "平安银行", "5000", "11.05", "11.24", "+1.72%"],
          ["300750.SZ", "宁德时代", "300", "195.20", "198.30", "+1.59%"],
        ]}
        columnAlign={["left", "left", "right", "right", "right", "right"]}
        rowTone={["success", "success", "success"]}
      />

      <Row gap={8}>
        <Button variant="secondary" disabled={dryRun}>
          提交待执行信号
        </Button>
        <Button variant="ghost">查看委托流水</Button>
      </Row>
    </Stack>
  );
}

function PageContent({ page }: { page: PageId }) {
  switch (page) {
    case "dashboard":
      return <DashboardPage />;
    case "data":
      return <DataPage />;
    case "research":
      return <ResearchPage />;
    case "validation":
      return <ValidationPage />;
    case "screening":
      return <ScreeningPage />;
    case "live":
      return <LivePage />;
    default:
      return <DashboardPage />;
  }
}

const PAGE_META: Record<PageId, { title: string; subtitle: string }> = {
  dashboard: {
    title: "总览",
    subtitle: "系统状态、数据新鲜度与快捷工作流入口",
  },
  data: {
    title: "数据中心",
    subtitle: "QMT 日线/财务同步、Parquet 导出与健康检查",
  },
  research: {
    title: "研究回测",
    subtitle: "VectorBT 向量化参数扫描与快速策略研究",
  },
  validation: {
    title: "验证回测",
    subtitle: "NautilusTrader 高保真事件驱动验证与结果对比",
  },
  screening: {
    title: "选股",
    subtitle: "横截面因子筛选，结果桥接双引擎回测",
  },
  live: {
    title: "实盘交易",
    subtitle: "xttrader 下单与持仓管理（P2 · Dry Run 默认开启）",
  },
};

export default function QmtQuantUiMockup() {
  const [page, setPage] = useCanvasState<PageId>("active-page", "dashboard");
  const theme = useHostTheme();
  const meta = PAGE_META[page];

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100%",
        background: theme.bg.editor,
        color: theme.text.primary,
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      <Sidebar active={page} onSelect={setPage} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <TopBar title={meta.title} subtitle={meta.subtitle} />
        <PageContent page={page} />
      </div>
    </div>
  );
}

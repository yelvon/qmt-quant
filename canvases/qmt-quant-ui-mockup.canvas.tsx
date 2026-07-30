import {
  Button,
  Card,
  CardBody,
  CardHeader,
  Checkbox,
  Grid,
  H2,
  H3,
  LineChart,
  Pill,
  Row,
  Select,
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

const NAV: { id: PageId; label: string; hint: string }[] = [
  { id: "dashboard", label: "① 总览", hint: "看状态、走流程" },
  { id: "data", label: "② 准备数据", hint: "从 QMT 同步" },
  { id: "research", label: "③ 快速试策略", hint: "找合适参数" },
  { id: "validation", label: "④ 仔细验策略", hint: "确认能上线" },
  { id: "screening", label: "⑤ 选股", hint: "筛股票池" },
  { id: "live", label: "⑥ 实盘", hint: "模拟/真下单" },
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

const DATE_PRESETS = [
  { value: "1y", label: "近 1 年" },
  { value: "3y", label: "近 3 年（推荐）" },
  { value: "5y", label: "近 5 年" },
  { value: "all", label: "全部已有数据" },
];

const SECTOR_OPTIONS = [
  { value: "hs_a", label: "沪深 A 股（默认）" },
  { value: "hs300", label: "沪深 300" },
  { value: "zz500", label: "中证 500" },
  { value: "watchlist", label: "我的自选池" },
];

const ADJUST_OPTIONS = [
  { value: "front", label: "前复权（回测推荐）" },
  { value: "none", label: "不复权" },
  { value: "back", label: "后复权" },
];

const STRATEGY_OPTIONS = [
  { value: "ma_cross", label: "双均线交叉（入门）" },
  { value: "buy_hold", label: "买入持有（基准）" },
  { value: "pe_momentum", label: "低估值 + 动量" },
];

const UNIVERSE_OPTIONS = [
  { value: "sector", label: "跟随上方股票范围" },
  { value: "screen", label: "使用最近一次选股结果" },
  { value: "watchlist", label: "我的自选池（50 只）" },
];

const SHORT_MA_OPTIONS = [
  { value: "preset_std", label: "常用：5 / 10 / 20 日" },
  { value: "preset_fast", label: "激进：3 / 5 / 8 日" },
  { value: "preset_slow", label: "稳健：10 / 15 / 20 日" },
];

const LONG_MA_OPTIONS = [
  { value: "preset_std", label: "常用：30 / 60 / 120 日" },
  { value: "preset_mid", label: "中线：20 / 40 / 60 日" },
  { value: "preset_long", label: "长线：60 / 120 / 250 日" },
];

const FEE_PRESETS = [
  { value: "default", label: "A 股默认（佣金万三 + 印花税千一）" },
  { value: "low", label: "低佣金账户" },
  { value: "custom", label: "自定义（高级）" },
];

const PARAM_COMBO_OPTIONS = [
  { value: "20_120", label: "20 / 120 日（研究最优，收益 +24.1%）" },
  { value: "10_60", label: "10 / 60 日（收益 +22.8%）" },
  { value: "5_30", label: "5 / 30 日（收益 +12.4%）" },
];

const MATCH_OPTIONS = [
  { value: "next_open", label: "次日开盘价（更贴近实盘）" },
  { value: "close", label: "当日收盘价" },
];

const SCREEN_TEMPLATES = [
  { value: "low_pe", label: "低估值动量（内置模板）" },
  { value: "ma_bull", label: "均线多头（内置模板）" },
  { value: "custom", label: "从空白规则新建…" },
];

function FormField({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <Stack gap={4}>
      <Text weight="semibold" size="small">
        {label}
      </Text>
      {children}
      {hint ? (
        <Text tone="quaternary" size="small">
          {hint}
        </Text>
      ) : null}
    </Stack>
  );
}

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
      gap={2}
      style={{
        width: 210,
        minWidth: 210,
        padding: "16px 10px",
        background: theme.bg.chrome,
        borderRight: `1px solid ${theme.stroke.tertiary}`,
        minHeight: 760,
      }}
    >
      <Text weight="semibold" style={{ padding: "4px 10px 4px", fontSize: 15 }}>
        qmt-quant
      </Text>
      <Text tone="tertiary" size="small" style={{ padding: "0 10px 12px" }}>
        按左侧序号操作即可
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
              flexDirection: "column",
              alignItems: "flex-start",
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
            <span style={{ fontSize: 13, fontWeight: selected ? 600 : 400 }}>
              {item.label}
            </span>
            <span style={{ fontSize: 11, color: theme.text.quaternary, marginTop: 2 }}>
              {item.hint}
            </span>
          </button>
        );
      })}
      <Spacer />
      <Stack gap={4} style={{ padding: "8px 10px" }}>
        <Row gap={8} align="center">
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: theme.category.green,
            }}
          />
          <Text size="small" tone="secondary">
            QMT 已连接，可以同步
          </Text>
        </Row>
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
        padding: "14px 24px",
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
        <Button variant="ghost">帮助</Button>
        <Button variant="ghost">任务记录</Button>
      </Row>
    </Row>
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

function DashboardPage({ onGo }: { onGo: (page: PageId) => void }) {
  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <CalloutMini
        tone="info"
        text="建议按顺序操作：准备数据 → 快速试策略 → 仔细验策略。不确定时，直接点下方「一键跑通」由系统帮你串联步骤。"
      />

      <Grid columns={4} gap={12}>
        <Stat label="数据是否够用" value="98.6%" tone="success" />
        <Stat label="财务是否齐全" value="已就绪" tone="success" />
        <Stat label="上次试策略" value="12 秒前" tone="info" />
        <Stat label="待你确认" value="1 个策略" tone="warning" />
      </Grid>

      <Card>
        <CardHeader trailing={<Pill tone="warning">推荐下一步</Pill>}>
          今天建议做什么？
        </CardHeader>
        <CardBody>
          <Stack gap={10}>
            <Text size="small" tone="secondary">
              数据已更新到 2026-07-25。你可以直接试策略，或先选股再回测。
            </Text>
            <Row gap={8} wrap>
              <Button variant="primary" onClick={() => onGo("research")}>
                去试策略（③）
              </Button>
              <Button variant="secondary" onClick={() => onGo("data")}>
                先检查数据（②）
              </Button>
              <Button variant="secondary">一键跑通：同步→试策略→验策略</Button>
            </Row>
          </Stack>
        </CardBody>
      </Card>

      <H3>数据覆盖情况</H3>
      <UsageBar
        total={5120}
        topLeftLabel="日线已覆盖 98.6%"
        topRightLabel="还差 138 只股票"
        segments={[
          { id: "ok", value: 4982, color: "green" },
          { id: "gap", value: 138, color: "yellow" },
        ]}
      />

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>常用操作</CardHeader>
          <CardBody>
            <Stack gap={8}>
              <Button variant="secondary" onClick={() => onGo("data")}>
                更新今日行情
              </Button>
              <Button variant="secondary" onClick={() => onGo("screening")}>
                运行选股
              </Button>
              <Button variant="ghost" onClick={() => onGo("validation")}>
                查看待验证策略
              </Button>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>最近任务</CardHeader>
          <CardBody style={{ padding: 0 }}>
            <Table
              framed={false}
              headers={["做了什么", "结果", "耗时"]}
              rows={[
                ["更新行情", <Pill tone="success">完成</Pill>, "11 分钟"],
                ["试策略：双均线", <Pill tone="success">完成</Pill>, "13 秒"],
                ["验策略：双均线", <Pill tone="info">等待你确认</Pill>, "—"],
              ]}
              columnAlign={["left", "center", "right"]}
            />
          </CardBody>
        </Card>
      </Grid>
    </Stack>
  );
}

function DataPage() {
  const [sector, setSector] = useCanvasState("data-sector", "hs_a");
  const [adjust, setAdjust] = useCanvasState("data-adjust", "front");
  const [range, setRange] = useCanvasState("data-range", "5y");
  const [autoExport, setAutoExport] = useCanvasState("data-auto-export", true);
  const [finBalance, setFinBalance] = useCanvasState("fin-balance", true);
  const [finIncome, setFinIncome] = useCanvasState("fin-income", true);
  const [finCash, setFinCash] = useCanvasState("fin-cash", true);
  const [finPer, setFinPer] = useCanvasState("fin-per", true);

  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <CalloutMini
        tone="info"
        text="第一次使用？选好下面选项后，点「开始同步」即可。日常只需点「更新今日数据」。"
      />

      <Card>
        <CardHeader>同步日线行情</CardHeader>
        <CardBody>
          <Grid columns={3} gap={16}>
            <FormField label="股票范围" hint="决定同步哪些股票">
              <Select value={sector} onChange={setSector} options={SECTOR_OPTIONS} />
            </FormField>
            <FormField label="价格方式" hint="回测一般选前复权">
              <Select value={adjust} onChange={setAdjust} options={ADJUST_OPTIONS} />
            </FormField>
            <FormField label="历史长度" hint="首次同步会按此拉取历史">
              <Select value={range} onChange={setRange} options={DATE_PRESETS} />
            </FormField>
          </Grid>
          <Row gap={8} style={{ marginTop: 16 }}>
            <Button variant="primary">更新今日数据（推荐）</Button>
            <Button variant="secondary">按上面选项全量同步</Button>
            <Button variant="ghost">只重试失败的 3 只</Button>
          </Row>
          <Text tone="quaternary" size="small" style={{ marginTop: 8 }}>
            上次更新：2026-07-25 18:42 · 成功 5120 只 · 失败 3 只
          </Text>
        </CardBody>
      </Card>

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>同步财务报表</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Text size="small" tone="secondary">
                勾选需要的报表，系统会按「披露日」存储，避免回测用到未来数据。
              </Text>
              <Stack gap={8}>
                <Row gap={8} align="center">
                  <Checkbox checked={finBalance} onChange={setFinBalance} />
                  <Text size="small">资产负债表</Text>
                </Row>
                <Row gap={8} align="center">
                  <Checkbox checked={finIncome} onChange={setFinIncome} />
                  <Text size="small">利润表</Text>
                </Row>
                <Row gap={8} align="center">
                  <Checkbox checked={finCash} onChange={setFinCash} />
                  <Text size="small">现金流量表</Text>
                </Row>
                <Row gap={8} align="center">
                  <Checkbox checked={finPer} onChange={setFinPer} />
                  <Text size="small">每股指标（PE、ROE 等）</Text>
                </Row>
              </Stack>
              <Button variant="secondary">更新财务数据</Button>
            </Stack>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>给「仔细验策略」准备数据</CardHeader>
          <CardBody>
            <Stack gap={10}>
              <Row gap={8} align="center">
                <Toggle checked={autoExport} onChange={setAutoExport} />
                <Text size="small">同步完成后自动生成验策略专用文件</Text>
              </Row>
              <Text tone="secondary" size="small">
                你不需要关心技术细节；开启后，第 ④ 步验策略才能直接运行。
              </Text>
              <Button variant="ghost">立即生成一次</Button>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <H3>数据检查结果</H3>
      <Table
        striped
        headers={["检查什么", "结果", "覆盖率", "说明"]}
        rows={[
          ["日线是否齐全", "通过", "98.6%", "138 只缺数据，可重试"],
          ["交易日是否连续", "通过", "100%", "无断档"],
          ["财务披露是否对齐", "通过", "96.2%", "新股可能暂无历史"],
          ["验策略文件是否就绪", "通过", "98.6%", "与数据库一致"],
        ]}
        rowTone={["success", "success", "warning", "success"]}
        columnAlign={["left", "left", "right", "left"]}
      />
    </Stack>
  );
}

function ResearchPage() {
  const [strategy, setStrategy] = useCanvasState("research-strategy", "ma_cross");
  const [universe, setUniverse] = useCanvasState("research-universe", "sector");
  const [dateRange, setDateRange] = useCanvasState("research-range", "3y");
  const [shortMa, setShortMa] = useCanvasState("research-short", "preset_std");
  const [longMa, setLongMa] = useCanvasState("research-long", "preset_std");
  const [fee, setFee] = useCanvasState("research-fee", "default");

  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <CalloutMini
        tone="info"
        text="这一步用来「快速试」：在大量参数组合里找表现较好的。找到后请到 ④ 仔细验策略 做最终确认。"
      />

      <Grid columns={3} gap={16}>
        <Card style={{ gridColumn: "span 1" }}>
          <CardHeader>试策略设置</CardHeader>
          <CardBody>
            <Stack gap={14}>
              <FormField label="选策略" hint="不确定就选双均线">
                <Select value={strategy} onChange={setStrategy} options={STRATEGY_OPTIONS} />
              </FormField>
              <FormField label="在哪些股票上试" hint="可与 ② 股票范围联动">
                <Select value={universe} onChange={setUniverse} options={UNIVERSE_OPTIONS} />
              </FormField>
              <FormField label="回测多长时间" hint="数据够长结果更可信">
                <Select value={dateRange} onChange={setDateRange} options={DATE_PRESETS} />
              </FormField>
              <FormField label="短期均线试哪些" hint="已选好常用组合，无需手填">
                <Select value={shortMa} onChange={setShortMa} options={SHORT_MA_OPTIONS} />
              </FormField>
              <FormField label="长期均线试哪些" hint="会与短期均线自动配对扫描">
                <Select value={longMa} onChange={setLongMa} options={LONG_MA_OPTIONS} />
              </FormField>
              <FormField label="交易成本" hint="一般用默认即可">
                <Select value={fee} onChange={setFee} options={FEE_PRESETS} />
              </FormField>
              <Button variant="primary">开始试策略（约 10–30 秒）</Button>
            </Stack>
          </CardBody>
        </Card>

        <Stack gap={16} style={{ gridColumn: "span 2" }}>
          <Card>
            <CardHeader trailing={<Pill tone="success">已完成</Pill>}>
              哪种参数组合更好？（累计收益）
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
                点击柱子可查看该组合的详细指标 · 当前最优：20 日 / 120 日
              </Text>
            </CardBody>
          </Card>

          <Grid columns={4} gap={12}>
            <Stat label="目前最优" value="20/120 日" tone="success" />
            <Stat label="累计收益" value="+24.1%" tone="success" />
            <Stat label="夏普比率" value="1.42" tone="info" />
            <Stat label="最大回撤" value="-11.3%" tone="warning" />
          </Grid>
        </Stack>
      </Grid>

      <Row gap={8}>
        <Button variant="primary">送到 ④ 仔细验策略</Button>
        <Button variant="secondary">保存本次结果</Button>
      </Row>
    </Stack>
  );
}

function ValidationPage() {
  const [paramCombo, setParamCombo] = useCanvasState("validate-param", "20_120");
  const [match, setMatch] = useCanvasState("validate-match", "next_open");
  const [benchmark, setBenchmark] = useCanvasState("validate-bench", "hs300");

  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <CalloutMini
        tone="info"
        text="这一步模拟真实交易规则（T+1、手续费、100 股一手）。若与 ③ 结果差太多，说明需要调整参数或规则。"
      />

      <Grid columns={3} gap={16}>
        <Card>
          <CardHeader>验策略设置</CardHeader>
          <CardBody>
            <Stack gap={14}>
              <Pill tone="info">来自 ③：双均线 · 已带入参数</Pill>
              <FormField label="用哪组参数" hint="下拉选 ③ 中的候选组合">
                <Select value={paramCombo} onChange={setParamCombo} options={PARAM_COMBO_OPTIONS} />
              </FormField>
              <FormField label="按什么价格成交" hint="实盘更接近次日开盘">
                <Select value={match} onChange={setMatch} options={MATCH_OPTIONS} />
              </FormField>
              <FormField label="和什么比" hint="看策略是否跑赢大盘">
                <Select
                  value={benchmark}
                  onChange={setBenchmark}
                  options={[
                    { value: "hs300", label: "沪深 300" },
                    { value: "zz500", label: "中证 500" },
                    { value: "none", label: "不对比基准" },
                  ]}
                />
              </FormField>
              <Text tone="quaternary" size="small">
                A 股规则已内置：T+1、100 股整数倍、佣金与印花税
              </Text>
              <Button variant="primary">开始仔细验证</Button>
            </Stack>
          </CardBody>
        </Card>

        <Stack gap={16} style={{ gridColumn: "span 2" }}>
          <Card>
            <CardHeader>收益曲线对比</CardHeader>
            <CardBody>
              <LineChart
                height={220}
                categories={equityDates}
                series={[
                  { name: "仔细验证", data: equityNt, tone: "success" },
                  { name: "快速试策略", data: equityVbt, tone: "info" },
                  { name: "沪深300", data: equityBench, tone: "neutral" },
                ]}
                beginAtZero={false}
                yMin={95}
                yMax={155}
              />
              <Text tone="quaternary" size="small">
                绿线低于蓝线属正常（验策略更保守）· 相差 &gt;10% 时会提示复核
              </Text>
            </CardBody>
          </Card>

          <Grid columns={4} gap={12}>
            <Stat label="验证收益" value="+38.0%" tone="success" />
            <Stat label="与快速试差" value="-6.1%" tone="warning" />
            <Stat label="成交次数" value="186 笔" tone="info" />
            <Stat label="能否采用" value="可以采用" tone="success" />
          </Grid>
        </Stack>
      </Grid>

      <H3>最近成交记录</H3>
      <Table
        striped
        headers={["日期", "股票", "买卖", "价格", "数量", "费用"]}
        rows={[
          ["04-18", "贵州茅台", "买入", "1682.00", "100", "50.46"],
          ["04-22", "平安银行", "买入", "11.24", "4400", "14.83"],
          ["05-06", "贵州茅台", "卖出", "1710.50", "100", "221.37"],
        ]}
        columnAlign={["left", "left", "center", "right", "right", "right"]}
      />
    </Stack>
  );
}

function ScreeningPage() {
  const [template, setTemplate] = useCanvasState("screen-template", "low_pe");
  const [topN, setTopN] = useCanvasState("screen-topn", "30");
  const [excludeSt, setExcludeSt] = useCanvasState("screen-st", true);

  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <CalloutMini
        tone="info"
        text="用下拉和勾选组合条件即可，无需写代码。选好模板后还能微调每一项。"
      />

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>选股条件（可视化）</CardHeader>
          <CardBody>
            <Stack gap={14}>
              <FormField label="从模板开始" hint="选一个接近你想法的模板">
                <Select value={template} onChange={setTemplate} options={SCREEN_TEMPLATES} />
              </FormField>

              <Grid columns={3} gap={8}>
                <FormField label="市盈率 PE">
                  <Select
                    value="lt30"
                    onChange={() => {}}
                    options={[
                      { value: "lt20", label: "小于 20" },
                      { value: "lt30", label: "小于 30" },
                      { value: "lt50", label: "小于 50" },
                    ]}
                  />
                </FormField>
                <FormField label="净资产收益率 ROE">
                  <Select
                    value="gt10"
                    onChange={() => {}}
                    options={[
                      { value: "gt8", label: "大于 8%" },
                      { value: "gt10", label: "大于 10%" },
                      { value: "gt15", label: "大于 15%" },
                    ]}
                  />
                </FormField>
                <FormField label="股价位置">
                  <Select
                    value="ma60"
                    onChange={() => {}}
                    options={[
                      { value: "ma60", label: "站上 60 日均线" },
                      { value: "ma20", label: "站上 20 日均线" },
                      { value: "high20", label: "创 20 日新高" },
                    ]}
                  />
                </FormField>
              </Grid>

              <FormField label="选出多少只">
                <Select
                  value={topN}
                  onChange={setTopN}
                  options={[
                    { value: "10", label: "前 10 只" },
                    { value: "30", label: "前 30 只（推荐）" },
                    { value: "50", label: "前 50 只" },
                  ]}
                />
              </FormField>

              <Row gap={8} align="center">
                <Checkbox checked={excludeSt} onChange={setExcludeSt} />
                <Text size="small">排除 ST 股票</Text>
              </Row>

              <Row gap={8}>
                <Button variant="primary">运行选股</Button>
                <Button variant="ghost">切换到高级 YAML（可选）</Button>
              </Row>
            </Stack>
          </CardBody>
        </Card>

        <Card>
          <CardHeader trailing={<Pill>2026-07-25</Pill>}>
            选股结果（共 30 只，展示前 8）
          </CardHeader>
          <CardBody style={{ padding: 0 }}>
            <Table
              framed={false}
              headers={["代码", "名称", "PE", "20日涨跌", "得分"]}
              rows={[
                ["600519.SH", "贵州茅台", "24.1", "+8.2%", "0.91"],
                ["000858.SZ", "五粮液", "18.6", "+6.4%", "0.87"],
                ["601318.SH", "中国平安", "9.8", "+5.1%", "0.84"],
                ["000333.SZ", "美的集团", "12.3", "+4.8%", "0.82"],
              ]}
              columnAlign={["left", "left", "right", "right", "right"]}
            />
          </CardBody>
        </Card>
      </Grid>

      <Row gap={8}>
        <Button variant="primary">用这些股票去 ③ 试策略</Button>
        <Button variant="secondary">用这些股票去 ④ 验策略</Button>
      </Row>
    </Stack>
  );
}

function LivePage() {
  const [dryRun, setDryRun] = useCanvasState("live-dry-run", true);
  const [signalSource, setSignalSource] = useCanvasState("live-source", "validated");

  return (
    <Stack gap={20} style={{ padding: 24 }}>
      <CalloutMini
        tone="warning"
        text="默认是模拟下单，不会花真钱。要真下单需关闭模拟并二次确认。"
      />

      <Grid columns={2} gap={16}>
        <Card>
          <CardHeader>下单方式</CardHeader>
          <CardBody>
            <Stack gap={14}>
              <Row gap={12} align="center">
                <Toggle checked={dryRun} onChange={setDryRun} />
                <Stack gap={2}>
                  <Text weight="semibold" size="small">
                    模拟下单（推荐保持开启）
                  </Text>
                  <Text tone="quaternary" size="small">
                    关闭后将连接真实账户
                  </Text>
                </Stack>
                <Pill tone={dryRun ? "warning" : "deleted"}>
                  {dryRun ? "当前：模拟" : "当前：真实"}
                </Pill>
              </Row>
              <FormField label="信号来源" hint="只执行已通过验证的策略">
                <Select
                  value={signalSource}
                  onChange={setSignalSource}
                  options={[
                    { value: "validated", label: "④ 已验证通过的策略" },
                    { value: "screen", label: "⑤ 最近一次选股结果" },
                    { value: "manual", label: "手动选择股票…" },
                  ]}
                />
              </FormField>
              <Button variant="secondary" disabled={dryRun}>
                预览今日将下的单
              </Button>
            </Stack>
          </CardBody>
        </Card>

        <Grid columns={2} gap={12}>
          <Stat label="总资产" value="102.5 万" tone="success" />
          <Stat label="今日盈亏" value="+0.42%" tone="success" />
          <Stat label="可用资金" value="31.2 万" tone="info" />
          <Stat label="持仓市值" value="71.2 万" tone="info" />
        </Grid>
      </Grid>

      <H3>当前持仓</H3>
      <Table
        striped
        headers={["代码", "名称", "数量", "成本", "现价", "盈亏"]}
        rows={[
          ["600519.SH", "贵州茅台", "100", "1650", "1682", "+1.94%"],
          ["000001.SZ", "平安银行", "5000", "11.05", "11.24", "+1.72%"],
        ]}
        columnAlign={["left", "left", "right", "right", "right", "right"]}
        rowTone={["success", "success"]}
      />
    </Stack>
  );
}

function PageContent({ page, onGo }: { page: PageId; onGo: (p: PageId) => void }) {
  switch (page) {
    case "dashboard":
      return <DashboardPage onGo={onGo} />;
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
      return <DashboardPage onGo={onGo} />;
  }
}

const PAGE_META: Record<PageId, { title: string; subtitle: string }> = {
  dashboard: {
    title: "总览",
    subtitle: "看系统状态，按提示进行下一步",
  },
  data: {
    title: "准备数据",
    subtitle: "从 QMT 同步行情和财报，下拉选好就能同步",
  },
  research: {
    title: "快速试策略",
    subtitle: "大量参数里找较优组合，约十几秒完成",
  },
  validation: {
    title: "仔细验策略",
    subtitle: "按真实交易规则复核，决定能不能用",
  },
  screening: {
    title: "选股",
    subtitle: "用模板和下拉框筛股票，可送去试/验策略",
  },
  live: {
    title: "实盘交易",
    subtitle: "默认模拟下单；真下单需你明确确认",
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
        <PageContent page={page} onGo={setPage} />
      </div>
    </div>
  );
}

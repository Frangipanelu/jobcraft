import React, { useState } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  ArrowLeft,
  CheckCircle2,
  Mic,
  Sparkles,
  Save,
  Check,
  RotateCcw
} from 'lucide-react';

interface InterviewPrepWorkspaceViewProps {
  interviewId?: string;
  onOpenMockInterview: (interviewId: string) => void;
  onOpenNewInterview?: (jobId?: string) => void;
}

const SECTIONS = [
  '公司研究',
  '本场面试判断',
  '推荐经历',
  '高频问题',
  '回答准备',
  '模拟面试'
] as const;

type SectionType = (typeof SECTIONS)[number];

const companyData = {
  name: '字节跳动',
  founded: '2012年',
  headcount: '11万+',
  products: ['抖音', 'TikTok', 'Today头条', 'Lark'],
  focus: 'AI全面转型，将 AI 能力嵌入核心产品，搜索、推荐、创作等场景均在快速升级。',
  news: [
    '字节跳动 2026 Q2 营收同比增长 31%，AI 广告营收占比首次超 40%',
    '「豆包」大模型已面向 B 端商业化，获 300+ 企业采购',
    '搜索部门招聘大幅扩张，主攻 AI 搜索方向'
  ],
  culture: ['Be Real', 'Always Day 1', '不设边界', '追求极致']
};

const initialQuestions = [
  {
    id: '1',
    q: '介绍一个你从 0 到 1 做过的 AI 产品案例',
    type: '经历深挖',
    difficulty: 'high',
    prepared: true,
    starSuggestion:
      '建议使用 STAR 结构：先说明 Situation（AI 搜索评测体系缺失），Task（建立自动化评估 pipeline），Action（设计指标体系 + 标注数据集），Result（效率提升 4× + 召回率 +15%）。避免开头直接说“我负责”，而是先提背景让面试官有代入感。',
    defaultDraft:
      '在快知智能期间，我从 0 到 1 主导了 AI 搜索与评测体系。当时核心挑战是模型幻觉与评估周期过长（2周）。我设计了双裁判仲裁与自动化黄金测试集，将评测时间缩短至 4 小时以内，模型幻觉率下降 34.2%。'
  },
  {
    id: '2',
    q: '你如何平衡用户需求和业务目标的冲突？',
    type: '价值观',
    difficulty: 'medium',
    prepared: true,
    starSuggestion:
      '建议先表明原则：短期看指标妥协，长期看用户价值沉淀。举一个具体的 A/B 测试或功能取舍实例，说明如何通过阶段性灰度和体验守护线达成共赢。',
    defaultDraft:
      '在处理广告召回与用户满意度冲突时，我们设定了不可触碰的体验红线（负反馈率 ≤ 0.2%），并在灰度测试中通过动态权重算法，在保障广告 ROI 的同时维持次留无显著负向。'
  },
  {
    id: '3',
    q: '你对字节搜索的 AI 化有什么看法？',
    type: '行业认知',
    difficulty: 'high',
    prepared: false,
    starSuggestion:
      '建议从三个维度展开：1. 交互形态从传统关键词匹配向问答生成与 Agent 意图承接升级；2. 挑战在于高并发下的推理成本控制与多模态生成质量；3. 结合字节庞大生态（抖音视频、头条图文）的内容资产闭环优势。',
    defaultDraft: ''
  },
  {
    id: '4',
    q: '你在 JD 里最有挑战的经历是什么？',
    type: '经历深挖',
    difficulty: 'medium',
    prepared: false,
    starSuggestion:
      '选一个有明显冲突/资源瓶颈但最终突破的项目。突出你的决策魄力与跨团队统筹手段（如与算法、工程跨部门协作的争议化解）。',
    defaultDraft: ''
  },
  {
    id: '5',
    q: '如何推动跨团队协作中的阻力？',
    type: '软技能',
    difficulty: 'low',
    prepared: false,
    starSuggestion:
      '强调对齐目标（OKR 统一）、机制化沟通（建立对齐例会与指标看板），以及“让算法团队用数据看到价值”而非单纯催促进度。',
    defaultDraft: ''
  }
];

function SectionHeader({
  num,
  title,
  done
}: {
  num: number;
  title: string;
  done?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5 mb-5 pb-3 border-b border-[#E2E8E4]">
      <span className="w-6 h-6 rounded-full bg-[#204E3F] inline-flex items-center justify-center text-[11px] font-bold text-white shrink-0 shadow-xs">
        {String(num).padStart(2, '0')}
      </span>
      <h2 className="text-[16px] font-extrabold text-[#111814] tracking-tight">{title}</h2>
      {done && (
        <span className="text-[11px] text-[#134D3A] bg-[#DCEDE4] border border-[#B6DBCB] px-2 py-0.5 rounded-md font-extrabold ml-1.5">
          ✓ 已准备就绪
        </span>
      )}
    </div>
  );
}

export const InterviewPrepWorkspaceView: React.FC<InterviewPrepWorkspaceViewProps> = ({
  interviewId = 'int-byte-1',
  onOpenMockInterview
}) => {
  const { interviews, navigateTo, showToast } = useJobCraft();

  const currentInterview = interviews.find((i) => i.id === interviewId) || interviews[0];

  const [activeSection, setActiveSection] = useState<SectionType>('公司研究');
  const [expandedQ, setExpandedQ] = useState<string | null>('1');
  const [questions, setQuestions] = useState(initialQuestions);
  const [selectedQIdForAnswer, setSelectedQIdForAnswer] = useState<string>('1');
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({
    '1': initialQuestions[0].defaultDraft,
    '2': initialQuestions[1].defaultDraft,
    '3': '',
    '4': '',
    '5': ''
  });

  const sectionStatus: Record<SectionType, boolean> = {
    '公司研究': true,
    '本场面试判断': true,
    '推荐经历': true,
    '高频问题': questions.some((q) => q.prepared),
    '回答准备': questions.filter((q) => q.prepared).length >= 2,
    '模拟面试': false
  };

  const iv = {
    company: currentInterview?.company || '字节跳动',
    position: currentInterview?.role || 'AI 产品经理',
    round: currentInterview?.roundName || '第2面 · 业务面',
    time: currentInterview?.time || '明天 14:00',
    readiness: currentInterview?.readinessPercent || 72
  };

  const toggleQuestionPrepared = (qId: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    setQuestions((prev) =>
      prev.map((q) => (q.id === qId ? { ...q, prepared: !q.prepared } : q))
    );
    showToast({
      type: 'info',
      title: '状态已更新',
      message: '已更新高频问题备战记录。'
    });
  };

  const handleSaveAnswer = () => {
    setQuestions((prev) =>
      prev.map((q) => (q.id === selectedQIdForAnswer ? { ...q, prepared: true } : q))
    );
    showToast({
      type: 'success',
      title: '回答草稿已保存',
      message: '已记录你的应答思路并标记为已准备。'
    });
  };

  const handleQuickPrepare = (qId: string) => {
    setSelectedQIdForAnswer(qId);
    setActiveSection('回答准备');
  };

  const currentQObj =
    questions.find((q) => q.id === selectedQIdForAnswer) || questions[0];

  const renderContent = () => {
    switch (activeSection) {
      // ── Tab 1: 01 公司研究 ──
      case '公司研究':
        return (
          <div className="space-y-6 animate-in fade-in duration-200">
            <SectionHeader num={1} title="目标雇主背景与业务全景研究" done />

            {/* Basic Info & Strategy Focus (2 Cards Responsive) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
              <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs">
                <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-3">
                  公司基本概况
                </div>
                <div className="space-y-2.5 text-xs sm:text-[13px]">
                  <div className="flex justify-between py-2 border-b border-[#E8EEEB]">
                    <span className="text-[#526058] font-medium">创立时间</span>
                    <span className="text-[#111814] font-extrabold">{companyData.founded}</span>
                  </div>
                  <div className="flex justify-between py-2 border-b border-[#E8EEEB]">
                    <span className="text-[#526058] font-medium">团队规模</span>
                    <span className="text-[#111814] font-extrabold">{companyData.headcount}</span>
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-[#E8EEEB]">
                  <div className="text-[11px] font-bold text-[#526058] mb-2">代表产品矩阵</div>
                  <div className="flex flex-wrap gap-2">
                    {companyData.products.map((p) => (
                      <span
                        key={p}
                        className="text-xs px-3 py-1 bg-[#F2F8F5] text-[#134D3A] rounded-lg font-bold border border-[#B6DBCB]"
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl p-5 sm:p-6 shadow-2xs flex flex-col justify-between">
                <div>
                  <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-2.5">
                    战略重心与当前关键战役
                  </div>
                  <p className="text-xs sm:text-[13.5px] text-[#1B3327] leading-relaxed m-0 font-medium">
                    {companyData.focus}
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-[#BBDDD0] text-xs text-[#204E3F] font-bold flex items-center gap-1.5">
                  <span>💡</span>
                  <span>面试提示：建议在表述中紧扣 AI 转型与核心产品赋能场景。</span>
                </div>
              </div>
            </div>

            {/* Recent News */}
            <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs mb-5">
              <div className="text-sm font-extrabold text-[#111814] mb-3.5">
                近期重大业务动态 (面试破冰与行业思考素材)
              </div>
              <div className="space-y-3">
                {companyData.news.map((n, i) => (
                  <div
                    key={i}
                    className="flex gap-3 p-3 rounded-xl bg-[#F8FAF9] border border-[#E0E7E3] text-xs sm:text-[13px] items-start"
                  >
                    <span className="w-5 h-5 rounded-full bg-[#204E3F] text-white inline-flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-2xs">
                      {i + 1}
                    </span>
                    <p className="text-[#1B2721] font-semibold leading-relaxed m-0">{n}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Cultural Keywords */}
            <div className="bg-[#FAFBF9] border border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs">
              <div className="text-sm font-extrabold text-[#111814] mb-3">企业文化与核心价值观</div>
              <div className="flex flex-wrap gap-2.5">
                {companyData.culture.map((c) => (
                  <span
                    key={c}
                    className="text-xs px-3.5 py-1.5 bg-white text-[#111814] font-bold rounded-xl border border-[#CCD8D1] shadow-2xs"
                  >
                    {c}
                  </span>
                ))}
              </div>
            </div>
          </div>
        );

      // ── Tab 2: 02 本场面试判断 ──
      case '本场面试判断':
        return (
          <div className="space-y-6 animate-in fade-in duration-200">
            <SectionHeader num={2} title="本场面试定位与考察维度研判" done />

            {/* AI Strategy Analysis Box (High Contrast) */}
            <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl p-6 sm:p-7 mb-5 shadow-xs">
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-black text-[#1A5340] uppercase tracking-wider bg-[#DCEDE4] px-2.5 py-1 rounded-md border border-[#B6DBCB]">
                  AI 策略研判
                </span>
                <span className="text-xs font-bold text-[#1F4D3D] bg-white px-3 py-1 rounded-full border border-[#B6DBCB] shadow-2xs">
                  预计时长：45–60 分钟
                </span>
              </div>
              <div className="text-lg sm:text-[19px] font-black text-[#0F3528] tracking-tight mb-2">
                业务面试 · 深度聚焦产品思维与落地闭环
              </div>
              <p className="text-xs sm:text-[13.5px] text-[#254135] leading-relaxed m-0 font-medium">
                第1轮业务面通常由产品总监/组长把关，核心考察你的产品感、思考框架和过往经历的深度。
                建议重点准备 AI 产品案例与 0 到 1 经历，用量化指标和明确的 trade-off 支撑你的业务观点。
              </p>
            </div>

            {/* Key Focus Directions (Grid on Wide Screen) */}
            <div>
              <div className="text-sm font-extrabold text-[#111814] mb-3.5">核心考察方向拆解</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  {
                    focus: '深挖 AI 产品经历',
                    desc: '需要有完整闭环的案例，准备 Challenge & Iteration 细节，清晰阐述评估体系从 0 到 1 过程。'
                  },
                  {
                    focus: '搜索 / 推荐类产品认知',
                    desc: '可能追问你对大模型重塑搜索交互的理解，以及多模态生成质量与时延成本的平衡。'
                  },
                  {
                    focus: '数据驱动与度量决策',
                    desc: '举例时注意量化 Impact（如 nDCG、NPS、耗时降幅），避免用模糊词语描述结果。'
                  }
                ].map((item, i) => (
                  <div
                    key={i}
                    className="bg-white p-5 rounded-2xl border-2 border-[#CCD8D1] shadow-2xs hover:border-[#204E3F] transition space-y-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-[#204E3F] text-white inline-flex items-center justify-center text-xs font-bold shrink-0">
                        {i + 1}
                      </span>
                      <div className="text-sm font-bold text-[#111814]">
                        {item.focus}
                      </div>
                    </div>
                    <p className="text-xs sm:text-[12.5px] text-[#4E5B53] leading-relaxed m-0 font-medium">
                      {item.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );

      // ── Tab 3: 03 推荐经历 ──
      case '推荐经历':
        return (
          <div className="space-y-6 animate-in fade-in duration-200">
            <SectionHeader num={3} title="推荐经历库资产 (针对本场面试重点讲述)" done />
            <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium mb-4">
              基于本场业务面试的岗位画像，AI 建议将以下经历作为主干故事准备：
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {[
                {
                  title: 'AI 搜索优化与评测项目',
                  level: '首推主讲',
                  lc: 'text-[#134D3A]',
                  lb: 'bg-[#DCEDE4]',
                  border: 'border-[#A2CAB8]',
                  bg: 'bg-[#F2F8F5]',
                  match: '与岗位直接相关，包含 AI + 搜索 + 数据分析三大核心标签',
                  tips: [
                    '强调从 0 建立评估体系的完整过程与工程权衡',
                    '量化提升指标：nDCG 提升 0.12，评测耗时下降 4×'
                  ]
                },
                {
                  title: 'AI 产品 MVP 孵化落地项目',
                  level: '重要备选',
                  lc: 'text-warning',
                  lb: 'bg-warning-bg',
                  border: 'border-[#CCD8D1]',
                  bg: 'bg-white',
                  match: '有完整产品闭环和真实用户验证，展示 0 到 1 产品感和推动力',
                  tips: [
                    '准备 1-2 个关键决策点的 trade-off 与灰度测试说明',
                    '强调 NPS 达到 42 与 3 个月敏捷上线的成果'
                  ]
                }
              ].map((exp, i) => (
                <div
                  key={i}
                  className={`border-2 ${exp.border} ${exp.bg} rounded-2xl p-6 shadow-2xs flex flex-col justify-between space-y-3.5`}
                >
                  <div>
                    <div className="flex justify-between items-start mb-2">
                      <div className="text-base font-extrabold text-[#111814]">{exp.title}</div>
                      <span
                        className={`text-xs font-black px-2.5 py-1 rounded-md border border-black/10 ${exp.lc} ${exp.lb}`}
                      >
                        {exp.level}
                      </span>
                    </div>
                    <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium mb-3.5 leading-relaxed">
                      {exp.match}
                    </p>
                    <div className="text-xs font-extrabold text-[#111814] mb-2">核心讲述要点建议：</div>
                    <div className="space-y-1.5 bg-white/80 p-3 rounded-xl border border-black/5">
                      {exp.tips.map((tip, ti) => (
                        <div key={ti} className="flex items-start gap-2 text-xs sm:text-[12.5px] text-[#254135] font-medium">
                          <span className="text-[#204E3F] font-bold">✓</span>
                          <span>{tip}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      // ── Tab 4: 04 高频问题 ──
      case '高频问题':
        return (
          <div className="space-y-6 animate-in fade-in duration-200">
            <SectionHeader num={4} title="高频高概率面试真题预测" />
            <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium mb-4">
              AI 根据岗位 JD、公司面试风格及往期面经预测，共 {questions.length} 道精选题目：
            </p>

            <div className="space-y-3">
              {questions.map((q) => {
                const dStars =
                  q.difficulty === 'high'
                    ? '★★★ (难)'
                    : q.difficulty === 'medium'
                    ? '★★ (中)'
                    : '★ (易)';
                const dColor =
                  q.difficulty === 'high'
                    ? 'text-warning bg-warning-bg'
                    : q.difficulty === 'medium'
                    ? 'text-[#204E3F] bg-[#E3EFE9]'
                    : 'text-[#526058] bg-[#F2F4F1]';

                const isExpanded = expandedQ === q.id;

                return (
                  <div
                    key={q.id}
                    className="border-2 border-[#CCD8D1] hover:border-[#204E3F]/70 rounded-2xl overflow-hidden bg-white shadow-2xs transition"
                  >
                    <div
                      onClick={() => setExpandedQ(isExpanded ? null : q.id)}
                      className="w-full flex justify-between items-center px-5 py-4 cursor-pointer hover:bg-[#F9FCFA] transition text-left"
                    >
                      <div className="flex items-center gap-3 flex-1 pr-4">
                        <button
                          type="button"
                          onClick={(e) => toggleQuestionPrepared(q.id, e)}
                          className="shrink-0 cursor-pointer p-0.5 hover:scale-110 transition"
                          title="标记为已准备"
                        >
                          {q.prepared ? (
                            <CheckCircle2 className="w-5 h-5 text-[#204E3F] fill-[#DCEDE4]" />
                          ) : (
                            <span className="w-5 h-5 rounded-full border-2 border-[#CCD8D1] inline-block hover:border-[#204E3F]" />
                          )}
                        </button>
                        <span className="text-sm sm:text-[15px] font-bold text-[#111814]">
                          {q.q}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xs font-bold text-[#3A4A41] bg-[#EEF2F0] px-2.5 py-1 rounded-md">
                          {q.type}
                        </span>
                        <span className={`text-xs font-extrabold px-2 py-0.5 rounded-md ${dColor}`}>
                          {dStars}
                        </span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="px-5 pb-5 pt-2 bg-[#F6FAF8] border-t border-[#E8EEEB] space-y-3">
                        <div className="text-xs sm:text-[13px] text-[#254135] leading-relaxed font-medium bg-white p-3.5 rounded-xl border border-[#CCDCD4]">
                          <strong className="text-[#11382A]">💡 STAR 应答要点建议：</strong>
                          {q.starSuggestion}
                        </div>
                        <div className="flex justify-end">
                          <button
                            type="button"
                            onClick={() => handleQuickPrepare(q.id)}
                            className="px-4 py-2 text-xs sm:text-[13px] font-bold text-white bg-[#204E3F] hover:bg-[#16382D] rounded-xl shadow-xs transition cursor-pointer"
                          >
                            去草稿箱准备这道题 →
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );

      // ── Tab 5: 05 回答准备 ──
      case '回答准备':
        return (
          <div className="space-y-6 animate-in fade-in duration-200">
            <SectionHeader num={5} title="针对性回答草稿与 STAR 结构推演" />
            <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium mb-4">
              选择左侧问题并撰写你的作答思路，右侧实时参考 AI STAR 优化框架：
            </p>

            <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6">
              {/* Left Column: Questions List */}
              <div className="space-y-2">
                {questions.map((q) => {
                  const isSelected = selectedQIdForAnswer === q.id;
                  return (
                    <div
                      key={q.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => setSelectedQIdForAnswer(q.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setSelectedQIdForAnswer(q.id);
                        }
                      }}
                      className={`w-full text-left p-3.5 rounded-2xl border-2 transition cursor-pointer flex items-start gap-3 ${
                        isSelected
                          ? 'border-[#204E3F] bg-[#F2F8F5] text-[#0F3528] shadow-xs'
                          : 'border-[#CCD8D1] bg-white text-[#111814] hover:bg-[#FAFBF9]'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={(e) => toggleQuestionPrepared(q.id, e)}
                        className="mt-0.5 shrink-0 hover:opacity-80 transition cursor-pointer"
                        title={q.prepared ? '标记为未准备' : '标记为已准备'}
                      >
                        {q.prepared ? (
                          <CheckCircle2 className="w-4.5 h-4.5 text-[#204E3F] fill-[#DCEDE4]" />
                        ) : (
                          <span className="w-4.5 h-4.5 rounded-full border-2 border-[#CCD8D1] inline-block" />
                        )}
                      </button>
                      <span
                        className={`text-xs sm:text-[13px] leading-relaxed ${
                          isSelected ? 'font-black' : 'font-semibold'
                        }`}
                      >
                        {q.q}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Right Column: Active Question, Answer Box & AI Suggestions */}
              <div className="space-y-4">
                {/* Active Question Box */}
                <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl p-5 shadow-2xs">
                  <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-1.5">
                    当前选定问题
                  </div>
                  <div className="text-base font-extrabold text-[#0F3528]">{currentQObj.q}</div>
                </div>

                {/* My Answer Editor Box */}
                <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 shadow-2xs">
                  <div className="flex justify-between items-center mb-2.5">
                    <span className="text-xs font-bold text-[#111814]">我的应答草稿 / 核心讲点 (STAR)</span>
                    <button
                      type="button"
                      onClick={handleSaveAnswer}
                      className="px-3.5 py-1.5 bg-[#204E3F] hover:bg-[#16382D] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-xs transition"
                    >
                      <Save className="w-3.5 h-3.5" />
                      <span>保存草稿并标记就绪</span>
                    </button>
                  </div>
                  <textarea
                    rows={7}
                    value={answerDrafts[selectedQIdForAnswer] || ''}
                    onChange={(e) =>
                      setAnswerDrafts((prev) => ({
                        ...prev,
                        [selectedQIdForAnswer]: e.target.value
                      }))
                    }
                    placeholder="按 STAR 结构列出你的作答提纲（Situation 背景 / Task 任务 / Action 行动 / Result 结果）..."
                    className="w-full p-4 bg-[#F8FAF9] border border-[#CCDCD4] focus:border-[#204E3F] focus:bg-white rounded-xl text-xs sm:text-[13.5px] text-[#111814] placeholder:text-[#8D9A92] outline-none resize-y leading-relaxed font-sans shadow-inner transition"
                  />
                </div>

                {/* AI STAR Optimization Suggestions */}
                <div className="bg-[#FAFBF9] border-2 border-[#CCD8D1] rounded-2xl p-5 shadow-2xs">
                  <div className="text-xs font-extrabold text-[#111814] mb-2 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#204E3F]" />
                    <span>AI STAR 结构优化指南</span>
                  </div>
                  <p className="text-xs sm:text-[13px] text-[#334239] leading-relaxed m-0 font-medium">
                    {currentQObj.starSuggestion}
                  </p>
                </div>
              </div>
            </div>
          </div>
        );

      // ── Tab 6: 06 模拟面试 ──
      case '模拟面试':
        return (
          <div className="space-y-6 animate-in fade-in duration-200">
            <SectionHeader num={6} title="AI 实时对练与模拟实战" />
            <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-3xl p-10 md:p-14 text-center shadow-xs">
              <div className="w-16 h-16 rounded-2xl bg-[#DCEDE4] border border-[#B6DBCB] flex items-center justify-center mx-auto mb-4 text-3xl shadow-2xs">
                🎤
              </div>
              <div className="text-xl font-black text-[#0F3528] mb-2 tracking-tight">
                AI 模拟面试官即刻开练
              </div>
              <p className="text-xs sm:text-sm text-[#254135] leading-relaxed max-w-lg mx-auto mb-8 font-medium">
                模拟真实业务面场景，AI 面试官将基于本岗位 JD 展开追问，并在每轮问答后给出即时反馈与打分建议。
              </p>
              <button
                type="button"
                onClick={() => onOpenMockInterview(currentInterview.id)}
                className="px-8 py-3.5 bg-[#204E3F] hover:bg-[#16382D] text-white rounded-2xl text-sm font-extrabold shadow-md transition cursor-pointer"
              >
                开始全流程模拟面试 →
              </button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-full bg-white pb-24">
      {/* ── Sticky Header (Responsive & High Contrast) ── */}
      <div className="bg-white border-b border-[#CCD8D1] sticky top-0 z-10 shadow-2xs">
        <div className="w-full max-w-5xl xl:max-w-6xl mx-auto px-6 sm:px-8 lg:px-10 pt-4 sm:pt-5">
          {/* Job Title & Readiness Indicator */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-[#111814] tracking-tight">
                {iv.company} · {iv.position}
              </h1>
              <div className="text-xs sm:text-[13px] text-[#526058] font-medium mt-1">
                {iv.round} · 预约时间：{iv.time}
              </div>
            </div>

            {/* Readiness */}
            <div className="flex items-center gap-3 bg-[#F4F8F6] px-4 py-2 rounded-xl border border-[#CCD8D1]">
              <div className="text-right">
                <div
                  className={`text-xl font-black leading-none ${
                    iv.readiness >= 80 ? 'text-[#0F3528]' : 'text-warning'
                  }`}
                >
                  {iv.readiness}%
                </div>
                <div className="text-[11px] text-[#526058] font-bold mt-0.5">综合备战度</div>
              </div>
              <div className="w-20 h-2 bg-[#DDE5E1] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    iv.readiness >= 80 ? 'bg-[#204E3F]' : 'bg-warning'
                  }`}
                  style={{ width: `${iv.readiness}%` }}
                />
              </div>
            </div>
          </div>

          {/* Section Tabs (6 items with ✓ badge) */}
          <div className="flex gap-2 overflow-x-auto custom-scrollbar">
            {SECTIONS.map((s, i) => {
              const isDone = sectionStatus[s];
              const isActive = activeSection === s;
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => setActiveSection(s)}
                  className={`flex items-center gap-1.5 px-4 py-2.5 text-xs sm:text-[13px] transition cursor-pointer whitespace-nowrap border-b-2 -mb-px ${
                    isActive
                      ? 'font-black text-[#111814] border-[#204E3F]'
                      : 'text-[#526058] hover:text-[#111814] font-semibold border-transparent'
                  }`}
                >
                  {isDone && <span className="text-[#204E3F] font-bold text-xs">✓</span>}
                  <span>
                    {String(i + 1).padStart(2, '0')} {s}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Content Container (Responsive Width) ── */}
      <div className="w-full max-w-5xl xl:max-w-6xl mx-auto px-6 sm:px-8 lg:px-10 pt-6 sm:pt-8">
        {renderContent()}
      </div>
    </div>
  );
};

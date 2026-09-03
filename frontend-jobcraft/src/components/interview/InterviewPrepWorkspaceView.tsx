import React, { useState, useMemo } from 'react';
import { useJobCraft } from '../../context/JobCraftContext';
import {
  ArrowLeft,
  Sparkles,
  Save,
  FileText,
  Users
} from 'lucide-react';

interface InterviewPrepWorkspaceViewProps {
  interviewId?: string;
  onOpenMockInterview: (interviewId: string) => void;
  onOpenNewInterview?: (jobId?: string) => void;
}

const SECTIONS = [
  '公司调研',
  '本场判断',
  '维度题准备',
  '面试逐字稿',
  '模拟面试'
] as const;

type SectionType = (typeof SECTIONS)[number];

interface LocalQuestion {
  id: string;
  q: string;
  type: string;
  difficulty: 'high' | 'medium' | 'low';
  prepared: boolean;
  starSuggestion: string;
  defaultDraft: string;
}

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

function InfoRow({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div className="flex justify-between py-2 border-b border-[#E8EEEB]">
      <span className="text-[#526058] font-medium">{label}</span>
      <span className="text-[#111814] font-extrabold text-right">{value}</span>
    </div>
  );
}

export const InterviewPrepWorkspaceView: React.FC<InterviewPrepWorkspaceViewProps> = ({
  interviewId,
  onOpenMockInterview
}) => {
  const { interviews, navigateTo, showToast } = useJobCraft();

  const currentInterview = interviews.find((i) => i.id === interviewId) || interviews[0];
  const src = currentInterview?.prepSource;
  const prep = currentInterview?.preparation;
  const cr = (src?.company_research || {}) as Record<string, any>;

  const [activeSection, setActiveSection] = useState<SectionType>('公司调研');
  const [selectedQIdForAnswer, setSelectedQIdForAnswer] = useState<string>('');
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});

  // 真实维度题 -> 本地问题形状
  const questions: LocalQuestion[] = useMemo(() => {
    const dims = src?.dimension_questions || prep?.highFreqQuestions || [];
    return (dims as any[]).map((dq: any, idx: number) => {
      const answerTxt = Array.isArray(dq.answer_points)
        ? (dq.answer_points as string[]).join(' → ')
        : ((dq.preparedAnswer?.aiReference as string) || String(dq.answer_points || ''));
      const dimName = dq.dimension || (dq.evaluationFocus as string) || `维度 D${idx + 1}`;
      return {
        id: `q-${idx}`,
        q: dq.question || `第 ${idx + 1} 题`,
        type: String(dimName).replace(/^D\d+\s*/, ''),
        difficulty: 'medium',
        prepared: !!(dq as any).isPrepared,
        starSuggestion: answerTxt || '根据自身经历准备 STAR 应答（背景→任务→行动→结果）。',
        defaultDraft: ''
      };
    });
  }, [src, prep]);

  const sectionStatus: Record<SectionType, boolean> = {
    '公司调研': !!(cr?.basic || prep?.companyResearch?.background),
    '本场判断': !!(prep?.aiStrategy?.roundTypeDesc || src?.round_type),
    '维度题准备': questions.length > 0,
    '面试逐字稿': !!(src?.full_version || src?.elevator_pitch),
    '模拟面试': questions.length > 0
  };

  const iv = {
    company: currentInterview?.company || src?.company || '目标公司',
    position: currentInterview?.role || src?.position || '目标岗位',
    round: currentInterview?.roundName || src?.round_type || '面试准备',
    time: currentInterview?.time || src?.created_at || '',
    readiness: currentInterview?.readinessPercent || 40
  };

  const handleSaveAnswer = () => {
    if (!selectedQIdForAnswer) return;
    showToast({
      type: 'success',
      title: '回答草稿已保存',
      message: '已记录你的应答思路。'
    });
  };

  const currentQObj = questions.find((q) => q.id === selectedQIdForAnswer) || questions[0];

  const renderCompanyResearch = () => {
    const basic = cr?.basic || {};
    const business = cr?.business || {};
    const funding = cr?.funding || {};
    const team = cr?.team || {};
    const industry = cr?.industry || {};
    const news: any[] = cr?.news || prep?.companyResearch?.recentNews?.map((t: string) => ({ title: t })) || [];
    const products = basic?.name
      ? [
          ...(Array.isArray(business?.main_products)
            ? business.main_products
            : business?.main_products
            ? [business.main_products]
            : []),
          ...((prep?.companyResearch?.keyProducts as string[]) || [])
        ]
      : (prep?.companyResearch?.keyProducts as string[]) || [];

    return (
      <div className="space-y-6 animate-in fade-in duration-200">
        <SectionHeader num={1} title="目标雇主背景与业务全景研究" done />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">
          <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs">
            <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-3">
              公司基本概况
            </div>
            <InfoRow label="公司名称" value={basic?.full_name || basic?.name || iv.company} />
            <InfoRow label="成立时间" value={basic?.founded} />
            <InfoRow label="总部地点" value={basic?.headquarters} />
            <InfoRow label="团队规模" value={basic?.size} />
            <InfoRow label="发展阶段" value={basic?.stage} />
            {basic?.website && (
              <div className="flex justify-between py-2 border-b border-[#E8EEEB]">
                <span className="text-[#526058] font-medium">官网</span>
                <span className="text-[#204E3F] font-bold">{basic.website}</span>
              </div>
            )}
            <div className="mt-4 pt-3 border-t border-[#E8EEEB]">
              <div className="text-[11px] font-bold text-[#526058] mb-2">核心产品 / 业务</div>
              <div className="flex flex-wrap gap-2">
                {Array.isArray(products) && products.length > 0
                  ? products.map((p, i) => (
                      <span
                        key={i}
                        className="text-xs px-3 py-1 bg-[#F2F8F5] text-[#134D3A] rounded-lg font-bold border border-[#B6DBCB]"
                      >
                        {p}
                      </span>
                    ))
                  : (
                      <span className="text-xs text-[#8D9A92]">
                        {(business?.main_products && String(business.main_products)) || '待补充'}
                      </span>
                    )}
              </div>
            </div>
          </div>

          <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl p-5 sm:p-6 shadow-2xs flex flex-col justify-between">
            <div>
              <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-2.5">
                商业模式与目标客户
              </div>
              <p className="text-xs sm:text-[13.5px] text-[#1B3327] leading-relaxed m-0 font-medium">
                {business?.business_model || prep?.companyResearch?.coreBusiness || '待补充'}
              </p>
              {business?.target_customers && (
                <p className="text-xs sm:text-[13px] text-[#254135] leading-relaxed mt-3 m-0 font-medium">
                  目标客户：{String(business.target_customers)}
                </p>
              )}
              {business?.competitors && (
                <p className="text-xs sm:text-[13px] text-[#254135] leading-relaxed mt-2 m-0 font-medium">
                  主要竞对：{String(business.competitors)}
                </p>
              )}
            </div>
            <div className="mt-4 pt-3 border-t border-[#BBDDD0] text-xs text-[#204E3F] font-bold flex items-center gap-1.5">
              <span>💡</span>
              <span>{prep?.companyResearch?.aiHiringIntent || '面试提示：表述中紧扣公司业务与岗位价值。'}</span>
            </div>
          </div>
        </div>

        {/* Recent News */}
        <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs mb-5">
          <div className="text-sm font-extrabold text-[#111814] mb-3.5">
            近期重大业务动态 (面试破冰与行业思考素材)
          </div>
          {Array.isArray(news) && news.length > 0 ? (
            <div className="space-y-3">
              {news.slice(0, 5).map((n, i) => (
                <div
                  key={i}
                  className="flex gap-3 p-3 rounded-xl bg-[#F8FAF9] border border-[#E0E7E3] text-xs sm:text-[13px] items-start"
                >
                  <span className="w-5 h-5 rounded-full bg-[#204E3F] text-white inline-flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 shadow-2xs">
                    {i + 1}
                  </span>
                  <div>
                    <p className="text-[#1B2721] font-semibold leading-relaxed m-0">
                      {n?.title || n}
                      {n?.date && <span className="text-[#8D9A92] font-medium ml-2">{n.date}</span>}
                    </p>
                    {n?.summary && (
                      <p className="text-[#4E5B53] font-medium leading-relaxed mt-1 m-0">{n.summary}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[#8D9A92]">暂无可展示的新闻素材。</p>
          )}
        </div>

        {/* Industry / Funding / Team */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-white border border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs">
            <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-3">行业与趋势</div>
            <InfoRow label="所处赛道" value={industry?.sector} />
            <InfoRow label="行业趋势" value={industry?.trends} />
            <InfoRow label="机遇" value={industry?.opportunities} />
            <InfoRow label="风险" value={industry?.risks} />
          </div>
          <div className="bg-white border border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs">
            <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-3">融资与估值</div>
            <InfoRow label="最新轮次" value={funding?.latest_round} />
            <InfoRow label="投资方" value={funding?.investors} />
            <InfoRow label="估值" value={funding?.valuation} />
            <div className="text-[11px] text-[#8D9A92] mt-3">以上为 AI 检索生成，面试前请复核。</div>
          </div>
          <div className="bg-white border border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs">
            <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-3">核心团队</div>
            <InfoRow label="创始人" value={team?.founders} />
            <InfoRow label="关键高管" value={team?.key_executives} />
          </div>
        </div>
      </div>
    );
  };

  const renderRoundStrategy = () => {
    const keyFocus = prep?.aiStrategy?.keyFocusAreas || [];
    const dimensionTitles: Record<string, string> = {
      D1: '技术深度', D2: '业务理解', D3: '问题拆解', D4: '方案设计',
      D5: '落地执行', D6: '数据复盘', D7: '协作沟通', D8: '职业规划'
    };
    const focusAreas = keyFocus.length
      ? keyFocus
      : (src?.dimension_questions || []).map((dq: any) => ({
          name: dtTitle(dq.dimension, dimensionTitles),
          importance: '★★★★★',
          desc: dq.question
        }));

    return (
      <div className="space-y-6 animate-in fade-in duration-200">
        <SectionHeader num={2} title="本场面试定位与考察维度研判" done />
        <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl p-6 sm:p-7 mb-5 shadow-xs">
          <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
            <span className="text-xs font-black text-[#1A5340] uppercase tracking-wider bg-[#DCEDE4] px-2.5 py-1 rounded-md border border-[#B6DBCB]">
              AI 策略研判
            </span>
            <span className="text-xs font-bold text-[#1F4D3D] bg-white px-3 py-1 rounded-full border border-[#B6DBCB] shadow-2xs">
              预计时长：{src?.duration || prep?.aiStrategy?.roundTypeDesc?.includes('时长') ? '见下方说明' : '10-15 分钟'}
            </span>
          </div>
          <div className="text-lg sm:text-[19px] font-black text-[#0F3528] tracking-tight mb-2">
            {src?.round_type || iv.round}
          </div>
          <p className="text-xs sm:text-[13.5px] text-[#254135] leading-relaxed m-0 font-medium">
            {prep?.aiStrategy?.roundTypeDesc ||
              `围绕 ${src?.round_type || '目标岗位'} 的考察要点，结合自身经历组织应答，强调量化结果与业务落地。`}
          </p>
        </div>

        <div>
          <div className="text-sm font-extrabold text-[#111814] mb-3.5">核心考察方向拆解</div>
          {Array.isArray(focusAreas) && focusAreas.length ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {focusAreas.map((item: any, i: number) => (
                <div
                  key={i}
                  className="bg-white p-5 rounded-2xl border-2 border-[#CCD8D1] shadow-2xs hover:border-[#204E3F] transition space-y-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-[#204E3F] text-white inline-flex items-center justify-center text-xs font-bold shrink-0">
                      {i + 1}
                    </span>
                    <div className="text-sm font-bold text-[#111814]">{item.name}</div>
                  </div>
                  <p className="text-xs sm:text-[12.5px] text-[#4E5B53] leading-relaxed m-0 font-medium">
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-[#8D9A92]">暂无可展示的考察方向。</p>
          )}
        </div>
      </div>
    );
  };

  const renderQuestionPrep = () => {
    if (!questions.length) {
      return (
        <div className="space-y-6 animate-in fade-in duration-200">
          <SectionHeader num={3} title="维度题准备" />
          <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium">
            该场面试尚未生成维度题，请先在「面试准备」页生成逐字稿。
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-6 animate-in fade-in duration-200">
        <SectionHeader num={3} title="维度题准备与 STAR 应答" />
        <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium mb-4">
          共 {questions.length} 道维度题，右侧撰写你的作答思路：
        </p>

        <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6">
          {/* Left: Question List */}
          <div className="space-y-2">
            {questions.map((q, i) => {
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
                  <span
                    className={`mt-0.5 shrink-0 text-[11px] font-black rounded-md px-1.5 py-0.5 ${
                      isSelected ? 'bg-[#204E3F] text-white' : 'bg-[#EEF2F0] text-[#3A4A41]'
                    }`}
                  >
                    {i + 1}
                  </span>
                  <span className="text-xs sm:text-[13px] leading-relaxed">
                    <span className={isSelected ? 'font-black' : 'font-semibold'}>{q.q}</span>
                    <span className={`block mt-0.5 text-[11px] ${isSelected ? 'text-[#1F4D3D]' : 'text-[#8D9A92]'}`}>
                      {q.type}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>

          {/* Right: Active Question, Answer Box, AI Guidance */}
          <div className="space-y-4">
            {currentQObj && (
              <>
                <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl p-5 shadow-2xs">
                  <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider mb-1.5">
                    当前选定问题
                  </div>
                  <div className="text-base font-extrabold text-[#0F3528]">{currentQObj.q}</div>
                </div>

                <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 shadow-2xs">
                  <div className="flex justify-between items-center mb-2.5">
                    <span className="text-xs font-bold text-[#111814]">我的应答草稿 (STAR)</span>
                    <button
                      type="button"
                      onClick={handleSaveAnswer}
                      className="px-3.5 py-1.5 bg-[#204E3F] hover:bg-[#16382D] text-white rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-xs transition"
                    >
                      <Save className="w-3.5 h-3.5" />
                      <span>保存草稿</span>
                    </button>
                  </div>
                  <textarea
                    rows={7}
                    value={answerDrafts[currentQObj.id] || ''}
                    onChange={(e) =>
                      setAnswerDrafts((prev) => ({ ...prev, [currentQObj.id]: e.target.value }))
                    }
                    placeholder="按 STAR 结构列出你的作答提纲（Situation 背景 / Task 任务 / Action 行动 / Result 结果）..."
                    className="w-full p-4 bg-[#F8FAF9] border border-[#CCDCD4] focus:border-[#204E3F] focus:bg-white rounded-xl text-xs sm:text-[13.5px] text-[#111814] placeholder:text-[#8D9A92] outline-none resize-y leading-relaxed font-sans shadow-inner transition"
                  />
                </div>

                <div className="bg-[#FAFBF9] border-2 border-[#CCD8D1] rounded-2xl p-5 shadow-2xs">
                  <div className="text-xs font-extrabold text-[#111814] mb-2 flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-[#204E3F]" />
                    <span>AI STAR 应答要点建议</span>
                  </div>
                  <p className="text-xs sm:text-[13px] text-[#334239] leading-relaxed m-0 font-medium whitespace-pre-wrap">
                    {currentQObj.starSuggestion}
                  </p>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderFullScript = () => {
    const full = src?.full_version
      ? String(src.full_version)
      : '';
    const pitch = src?.elevator_pitch ? String(src.elevator_pitch) : '';
    return (
      <div className="space-y-6 animate-in fade-in duration-200">
        <SectionHeader num={4} title="面试逐字稿 · 完整版报告" done />
        <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium mb-4">
          以下为 AI 为本场面试生成的完整逐字稿，可直接通读熟悉，也可结合自己的经历做调整。
        </p>

        {pitch && (
          <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 sm:p-6 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-black text-[#1A5340] uppercase tracking-wider mb-3">
              <Users className="w-4 h-4" />
              开场自我介绍（电梯式演讲）
            </div>
            <div className="text-xs sm:text-[13.5px] text-[#1B3327] leading-loose font-medium whitespace-pre-wrap">
              {pitch}
            </div>
          </div>
        )}

        {full ? (
          <div className="bg-white border-2 border-[#CCD8D1] rounded-2xl p-5 sm:p-7 shadow-2xs">
            <div className="flex items-center gap-2 text-xs font-black text-[#1A5340] uppercase tracking-wider mb-4">
              <FileText className="w-4 h-4" />
              完整版逐字稿
            </div>
            <div className="text-xs sm:text-[13.5px] text-[#1B3327] leading-loose font-medium whitespace-pre-wrap">
              {full}
            </div>
          </div>
        ) : (
          <div className="bg-white border border-[#CCD8D1] rounded-2xl p-8 text-center shadow-2xs">
            <FileText className="w-8 h-8 text-[#A8ADA8] mx-auto mb-3" />
            <p className="text-xs sm:text-sm text-[#4E5B53] font-medium">
              本场面试暂无可展示的完整逐字稿报告。
            </p>
          </div>
        )}

        <div className="flex items-start gap-2 text-[11px] text-[#8D9A92] bg-[#F8FAF9] border border-[#E0E7E3] rounded-xl p-3">
          <Sparkles className="w-3.5 h-3.5 text-[#204E3F] shrink-0 mt-0.5" />
          使用建议：回答时避免照读，用「关键词 + 结构」方式记忆 —— 开场熟练、每题讲清背景→任务→行动→结果，反问环节结合上方公司调研提出 2-3 个有深度的问题。
        </div>
      </div>
    );
  };

  const renderMock = () => (
    <div className="space-y-6 animate-in fade-in duration-200">
      <SectionHeader num={5} title="AI 实时对练与模拟实战" />
      <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-3xl p-10 md:p-14 text-center shadow-xs">
        <div className="w-16 h-16 rounded-2xl bg-[#DCEDE4] border border-[#B6DBCB] flex items-center justify-center mx-auto mb-4 text-3xl shadow-2xs">
          🎤
        </div>
        <div className="text-xl font-black text-[#0F3528] mb-2 tracking-tight">
          AI 模拟面试官即刻开练
        </div>
        <p className="text-xs sm:text-sm text-[#254135] leading-relaxed max-w-lg mx-auto mb-8 font-medium">
          模拟真实面试场景，AI 面试官将基于本岗位 JD 与维度题展开追问，并在每轮问答后给出即时反馈与打分建议。
        </p>
        <button
          type="button"
          onClick={() => currentInterview && onOpenMockInterview(currentInterview.id)}
          className="px-8 py-3.5 bg-[#204E3F] hover:bg-[#16382D] text-white rounded-2xl text-sm font-extrabold shadow-md transition cursor-pointer"
        >
          开始全流程模拟面试 →
        </button>
      </div>
    </div>
  );

  const renderContent = () => {
    switch (activeSection) {
      case '公司调研':
        return renderCompanyResearch();
      case '本场判断':
        return renderRoundStrategy();
      case '维度题准备':
        return renderQuestionPrep();
      case '面试逐字稿':
        return renderFullScript();
      case '模拟面试':
        return renderMock();
      default:
        return null;
    }
  };

  return (
    <div className="min-h-full bg-white pb-24">
      {/* ── Sticky Header ── */}
      <div className="bg-white border-b border-[#CCD8D1] sticky top-0 z-10 shadow-2xs">
        <div className="w-full max-w-5xl xl:max-w-6xl mx-auto px-6 sm:px-8 lg:px-10 pt-4 sm:pt-5">
          {/* Back + Title */}
          <div className="flex items-center gap-2 mb-3">
            <button
              type="button"
              onClick={() => navigateTo('interview_prep_center')}
              className="inline-flex items-center gap-1 text-xs font-bold text-[#526058] hover:text-[#111814] transition cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              返回面试准备中心
            </button>
          </div>

          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-[#111814] tracking-tight">
                {iv.company} · {iv.position}
              </h1>
              <div className="text-xs sm:text-[13px] text-[#526058] font-medium mt-1">
                {iv.round}
                {iv.time && <span> · 生成时间：{iv.time}</span>}
              </div>
            </div>

            <div className="flex items-center gap-3 bg-[#F4F8F6] px-4 py-2 rounded-xl border border-[#CCD8D1]">
              <div className="text-right">
                <div className="text-xl font-black leading-none text-[#0F3528]">{iv.readiness}%</div>
                <div className="text-[11px] text-[#526058] font-bold mt-0.5">综合备战度</div>
              </div>
              <div className="w-20 h-2 bg-[#DDE5E1] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 bg-[#204E3F]"
                  style={{ width: `${iv.readiness}%` }}
                />
              </div>
            </div>
          </div>

          {/* Section Tabs */}
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

      {/* ── Content Container ── */}
      <div className="w-full max-w-5xl xl:max-w-6xl mx-auto px-6 sm:px-8 lg:px-10 pt-6 sm:pt-8">
        {renderContent()}
      </div>
    </div>
  );
};

function dtTitle(dim: string, map: Record<string, string>): string {
  if (!dim) return '核心能力';
  const key = String(dim).trim().toUpperCase().split(' ')[0] || '';
  return map[key] || String(dim).replace(/^D\d+\s*/, '') || '核心能力';
}
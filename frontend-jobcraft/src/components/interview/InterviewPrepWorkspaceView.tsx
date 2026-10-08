import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useToastActions } from '../../context/JobCraftContext';
import { useTabNavigate } from '../../router/tabPaths';
import {
  useInterviewsQuery,
  useRefreshCompanyResearchMutation,
  useSavePrepDraftsMutation
} from '../../features/interview/hooks';
import { useCreateExpressionMutation } from '../../features/experiences/expressionHooks';
import { makeExperiencesQueryFn } from '../../features/experiences/hooks';
import { EXPERIENCES_QUERY_KEY } from '../../features/experiences/mappers';
import { DIMENSION_LABELS } from '../../utils/dimensions';
import { CompanyResearchShape } from '../../api/types';
import type { Experience } from '../../types/jobcraft';
import {
  ArrowLeft,
  Sparkles,
  Save,
  FileText,
  Users,
  RefreshCw
} from 'lucide-react';

interface NewsItemShape {
  title?: string;
  date?: string;
  summary?: string;
}

// 后端维度题 / 前端高亮题 的消费子集（两者形似，按需归并）
interface DqShape {
  dimension?: string;
  question?: string;
  answer_points?: string[] | null;
  evaluationFocus?: string;
  isPrepared?: boolean;
  preparedAnswer?: { aiReference?: string } | null;
}

interface InterviewPrepWorkspaceViewProps {
  interviewId?: string;
}

/**
 * 工作区 3-tab（T-M7-2 裁决）：
 * 01 总览 = 公司调研 + 本场判断（信息聚合）
 * 02 演练 = 维度题准备（演练心脏，答题草稿）
 * 03 模拟 = 面试逐字稿（AI 模拟面试已下线为「待开发」，不再占 tab）
 */
const SECTIONS = ['总览', '演练', '模拟'] as const;

type SectionType = (typeof SECTIONS)[number];

interface LocalQuestion {
  id: string;
  q: string;
  type: string;
  prepared: boolean;
  starSuggestion: string;
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
  interviewId
}) => {
  const { showToast } = useToastActions();
  const go = useTabNavigate();
  const { data: interviewData } = useInterviewsQuery();
  const interviews = interviewData || [];

  const currentInterview = interviews.find((i) => i.id === interviewId);
  const src = currentInterview?.prepSource;
  const prep = currentInterview?.preparation;
  const cr = src?.company_research || ({} as CompanyResearchShape);

  const [activeSection, setActiveSection] = useState<SectionType>('总览');
  const [selectedQIdForAnswer, setSelectedQIdForAnswer] = useState<string>('');
  const [answerDrafts, setAnswerDrafts] = useState<Record<string, string>>({});
  const saveDrafts = useSavePrepDraftsMutation();
  const syncedPrepIdRef = useRef<number | null>(null);

  // T-M9-3「沉淀为表达」弹层（Q4-A：复用 POST /expressions，source_refs=interview_prep）
  const [sedimentOpen, setSedimentOpen] = useState(false);
  const [sedimentCardId, setSedimentCardId] = useState('');
  const [sedimentContent, setSedimentContent] = useState('');
  const createExpression = useCreateExpressionMutation();
  const queryClient = useQueryClient();
  // 经历卡懒加载：弹层打开才挂载 EXPERIENCES 查询（复用 W12 缓存 key；
  // 后端 GET /cards 默认 include_inactive=false → 只列启用卡）
  const { data: sedimentCards = [] } = useQuery<Experience[]>({
    queryKey: [...EXPERIENCES_QUERY_KEY],
    enabled: sedimentOpen,
    queryFn: makeExperiencesQueryFn(queryClient),
  });

  // 服务端已落库草稿 -> 本地编辑态（每份准备稿只灌入一次；
  // 保存成功后的 cache 回写不冲掉用户尚未保存的编辑）
  useEffect(() => {
    const prepId = src?.id;
    if (prepId === undefined || syncedPrepIdRef.current === prepId) return;
    syncedPrepIdRef.current = prepId;
    setAnswerDrafts(src?.drafts || {});
  }, [src?.id, src?.drafts]);

  // 真实维度题 -> 本地问题形状
  const questions: LocalQuestion[] = useMemo(() => {
    const dims = (src?.dimension_questions || prep?.highFreqQuestions || []) as DqShape[];
    return dims.map((dq, idx) => {
      const answerTxt = Array.isArray(dq.answer_points)
        ? dq.answer_points.join(' → ')
        : (dq.preparedAnswer?.aiReference || String(dq.answer_points || ''));
      const dimName = dq.dimension || dq.evaluationFocus || `维度 D${idx + 1}`;
      return {
        id: `q-${idx}`,
        q: dq.question || `第 ${idx + 1} 题`,
        type: String(dimName).replace(/^D\d+\s*/, ''),
        prepared: !!dq.isPrepared,
        starSuggestion: answerTxt || '暂无 AI 生成的应答要点（完成岗位分析后可重新生成）。',
      };
    });
  }, [src, prep]);

  const sectionStatus: Record<SectionType, boolean> = {
    '总览': !!(
      cr?.basic ||
      prep?.companyResearch?.background ||
      prep?.aiStrategy?.roundTypeDesc ||
      src?.round_type
    ),
    '演练': questions.length > 0,
    '模拟': !!(src?.full_version || src?.elevator_pitch)
  };

  // 综合备战度 = 三个分区的真实完成占比（不再伪造 40%，FE-FAKE-01）
  const readiness = Math.round(
    (Object.values(sectionStatus).filter(Boolean).length / SECTIONS.length) * 100
  );

  const iv = {
    company: currentInterview?.company || src?.company || '目标公司',
    position: currentInterview?.role || src?.position || '目标岗位',
    round: currentInterview?.roundName || src?.round_type || '面试准备',
    time: currentInterview?.time || src?.created_at || ''
  };

  const handleSaveAnswer = async () => {
    const prepId = src?.id;
    if (prepId === undefined || prepId <= 0) {
      showToast({
        type: 'error',
        title: '草稿无法保存',
        message: '当前面试稿尚未落库，请稍后重试。'
      });
      return;
    }
    try {
      await saveDrafts.mutateAsync({ prepId, drafts: answerDrafts });
      showToast({
        type: 'success',
        title: '回答草稿已保存',
        message: '已记录你的应答思路，刷新与切换页面不丢失。'
      });
    } catch {
      showToast({
        type: 'error',
        title: '草稿保存失败',
        message: '网络或服务异常，请稍后重试。'
      });
    }
  };

  const currentQObj = questions.find((q) => q.id === selectedQIdForAnswer) || questions[0];

  /** 切换当前题：沉淀弹层按题预填，切题即收起，避免 content 与溯源题号错位。 */
  const handleSelectQuestion = (qid: string) => {
    setSelectedQIdForAnswer(qid);
    setSedimentOpen(false);
  };

  /** 展开/收起「沉淀为表达」弹层，打开时以当前题草稿预填内容并清空卡选择。 */
  const handleToggleSediment = () => {
    if (sedimentOpen) {
      setSedimentOpen(false);
      return;
    }
    const draft = currentQObj ? answerDrafts[currentQObj.id] || '' : '';
    if (!draft.trim()) return;
    setSedimentContent(draft);
    setSedimentCardId('');
    setSedimentOpen(true);
  };

  /** 确认沉淀：把当前题草稿存为目标经历卡的 candidate 表达（溯源 interview_prep）。 */
  const handleConfirmSediment = async () => {
    if (!currentQObj) return;
    const prepId = src?.id;
    const cardId = parseInt(sedimentCardId, 10);
    if (prepId === undefined || prepId <= 0 || !Number.isFinite(cardId)) {
      showToast({
        type: 'error',
        title: '无法沉淀为表达',
        message: '请先选择经历卡，并确认本场准备稿已落库。'
      });
      return;
    }
    try {
      await createExpression.mutateAsync({
        cardId,
        content: sedimentContent,
        source_refs: [
          {
            id: `interview_prep:${prepId}:${currentQObj.id}`,
            source_type: 'interview_prep',
            source_id: String(prepId),
            locator: String(currentQObj.id)
          }
        ]
      });
      showToast({
        type: 'success',
        title: '已沉淀为表达',
        message: '候选态，可在经历库表达面板激活。'
      });
      setSedimentOpen(false);
    } catch {
      showToast({
        type: 'error',
        title: '沉淀失败',
        message: '网络或服务异常，请稍后重试。'
      });
    }
  };

  // T-M7-6：公司调研「重新调研」（force 绕 7 天缓存）
  const refreshResearch = useRefreshCompanyResearchMutation();
  const handleRefreshResearch = async () => {
    const prepId = src?.id;
    if (prepId === undefined || prepId <= 0) {
      showToast({
        type: 'error',
        title: '无法重新调研',
        message: '当前面试稿尚未落库，请稍后重试。'
      });
      return;
    }
    try {
      await refreshResearch.mutateAsync(prepId);
      showToast({
        type: 'success',
        title: '公司调研已更新',
        message: '已绕过缓存重新检索最新资料并同步到本场准备稿。'
      });
    } catch {
      showToast({
        type: 'error',
        title: '重新调研失败',
        message: '网络或服务异常，请稍后重试。'
      });
    }
  };

  const renderCompanyResearch = () => {
    const basic = cr?.basic || {};
    const business = cr?.business || {};
    const funding = cr?.funding || {};
    const team = cr?.team || {};
    const industry = cr?.industry || {};
    const news: NewsItemShape[] = [
      ...(cr?.news || []).map((n) => (typeof n === 'string' ? { title: n } : n)),
      ...((prep?.companyResearch?.recentNews as string[]) || []).map((t) => ({ title: t }))
    ];
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
      <>
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div className="text-xs font-black text-[#1A5340] uppercase tracking-wider">
            公司调研（AI 检索，7 天缓存）
          </div>
          <button
            type="button"
            onClick={handleRefreshResearch}
            disabled={refreshResearch.isPending || !src?.id}
            className="inline-flex items-center gap-1.5 text-xs font-bold text-[#134D3A] bg-[#F2F8F5] border border-[#A2CAB8] px-3 py-1.5 rounded-lg hover:bg-[#DCEDE4] disabled:opacity-60 disabled:cursor-not-allowed transition shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshResearch.isPending ? 'animate-spin' : ''}`} />
            {refreshResearch.isPending ? '重新调研中…' : '重新调研'}
          </button>
        </div>
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
                      {n?.title || ''}
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
      </>
    );
  };

  const renderRoundStrategy = () => {
    const keyFocus = prep?.aiStrategy?.keyFocusAreas || [];
    const dimensionTitles: Record<string, string> = DIMENSION_LABELS;
    const focusAreas = keyFocus.length
      ? keyFocus
      : (src?.dimension_questions || []).map((dq) => ({
          name: dtTitle(dq.dimension, dimensionTitles),
          desc: dq.question
        }));

    return (
      <>
        <div className="bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl p-6 sm:p-7 mb-5 shadow-xs">
          <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
            <span className="text-xs font-black text-[#1A5340] uppercase tracking-wider bg-[#DCEDE4] px-2.5 py-1 rounded-md border border-[#B6DBCB]">
              AI 策略研判
            </span>
            {src?.duration && (
              <span className="text-xs font-bold text-[#1F4D3D] bg-white px-3 py-1 rounded-full border border-[#B6DBCB] shadow-2xs">
                预计时长：{src.duration}
              </span>
            )}
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
              {focusAreas.map((item, i) => (
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
      </>
    );
  };

  /** 总览 tab：公司调研 + 本场判断合并渲染（T-M7-2）。 */
  const renderOverview = () => (
    <div className="space-y-6 animate-in fade-in duration-200">
      <SectionHeader num={1} title="公司调研与本场研判" done={sectionStatus['总览']} />
      {renderCompanyResearch()}
      {renderRoundStrategy()}
    </div>
  );

  const renderQuestionPrep = () => {
    if (!questions.length) {
      return (
        <div className="space-y-6 animate-in fade-in duration-200">
          <SectionHeader num={2} title="维度题准备" />
          <p className="text-xs sm:text-[13px] text-[#4E5B53] font-medium">
            该场面试尚未生成维度题，请先在「面试准备」页生成逐字稿。
          </p>
        </div>
      );
    }

    return (
      <div className="space-y-6 animate-in fade-in duration-200">
        <SectionHeader num={2} title="维度题准备与 STAR 应答" done={sectionStatus['演练']} />
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
                  onClick={() => handleSelectQuestion(q.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSelectQuestion(q.id);
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
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleToggleSediment}
                        disabled={!(answerDrafts[currentQObj.id] || '').trim()}
                        className="px-3.5 py-1.5 bg-white border border-[#A2CAB8] hover:bg-[#DCEDE4] disabled:opacity-60 disabled:cursor-not-allowed text-[#134D3A] rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-xs transition"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        <span>沉淀为表达</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleSaveAnswer}
                        disabled={saveDrafts.isPending}
                        className="px-3.5 py-1.5 bg-[#204E3F] hover:bg-[#16382D] disabled:opacity-60 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-xs transition"
                      >
                        <Save className="w-3.5 h-3.5" />
                        <span>{saveDrafts.isPending ? '保存中…' : '保存草稿'}</span>
                      </button>
                    </div>
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

                  {/* T-M9-3 沉淀为表达弹层（Q4-A：candidate 表达，source_refs=interview_prep） */}
                  {sedimentOpen && (
                    <div className="mt-3 p-4 bg-[#F2F8F5] border-2 border-[#A2CAB8] rounded-2xl space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-black text-[#1A5340] uppercase tracking-wider">
                          沉淀为标准化表达（候选态）
                        </span>
                        <button
                          type="button"
                          onClick={() => setSedimentOpen(false)}
                          className="text-xs font-bold text-[#526058] hover:text-[#111814] transition cursor-pointer"
                        >
                          取消
                        </button>
                      </div>

                      <div>
                        <label
                          htmlFor="sediment-experience-card"
                          className="block text-xs font-semibold text-[#334239] mb-1"
                        >
                          目标经历卡（必选，仅启用卡）
                        </label>
                        <select
                          id="sediment-experience-card"
                          value={sedimentCardId}
                          onChange={(e) => setSedimentCardId(e.target.value)}
                          className="w-full px-3 py-2 text-xs rounded-lg border border-[#CCDCD4] bg-white text-[#111814] focus:border-[#204E3F] focus:outline-none"
                        >
                          <option value="">
                            {sedimentCards.length ? '请选择经历卡' : '加载中 / 暂无启用的经历卡'}
                          </option>
                          {sedimentCards.map((card) => (
                            <option key={card.id} value={card.id}>
                              {card.title}
                              {card.company ? `（${card.company}${card.role ? ` · ${card.role}` : ''}）` : ''}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label
                          htmlFor="sediment-expression-content"
                          className="block text-xs font-semibold text-[#334239] mb-1"
                        >
                          表达内容（预填当前草稿，可编辑）
                        </label>
                        <textarea
                          id="sediment-expression-content"
                          rows={4}
                          value={sedimentContent}
                          onChange={(e) => setSedimentContent(e.target.value)}
                          className="w-full p-3 bg-white border border-[#CCDCD4] focus:border-[#204E3F] rounded-xl text-xs sm:text-[13px] text-[#111814] outline-none resize-y leading-relaxed font-sans transition"
                        />
                      </div>

                      <button
                        type="button"
                        onClick={handleConfirmSediment}
                        disabled={
                          createExpression.isPending ||
                          !sedimentCardId ||
                          !sedimentContent.trim()
                        }
                        className="px-3.5 py-1.5 bg-[#204E3F] hover:bg-[#16382D] disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold flex items-center gap-1.5 cursor-pointer shadow-xs transition"
                      >
                        <Save className="w-3.5 h-3.5" />
                        <span>{createExpression.isPending ? '沉淀中…' : '确认沉淀'}</span>
                      </button>
                    </div>
                  )}
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
        <SectionHeader num={3} title="面试逐字稿 · 完整版报告" done={sectionStatus['模拟']} />
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
          使用建议：回答时避免照读，用「关键词 + 结构」方式记忆 —— 开场熟练、每题讲清背景→任务→行动→结果，反问环节结合「总览」中的公司调研提出 2-3 个有深度的问题。
        </div>
      </div>
    );
  };

  const renderContent = () => {
    switch (activeSection) {
      case '总览':
        return renderOverview();
      case '演练':
        return renderQuestionPrep();
      case '模拟':
        return renderFullScript();
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
              onClick={() => go('interview_prep_center')}
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
                <div className="text-xl font-black leading-none text-[#0F3528]">{readiness}%</div>
                <div className="text-[11px] text-[#526058] font-bold mt-0.5">综合备战度</div>
              </div>
              <div className="w-20 h-2 bg-[#DDE5E1] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 bg-[#204E3F]"
                  style={{ width: `${readiness}%` }}
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
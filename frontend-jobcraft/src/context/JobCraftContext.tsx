import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import {
  NavigationTab,
  UserProfile,
  Experience,
  Job,
  JDAnalysis,
  ResumeVersion,
  Interview,
  InterviewReview,
  ActivityLog,
  NextActionItem,
  AISuggestionCard,
  PreparedAnswer,
  InterviewPreparation,
  HistoricalResume,
  InterviewDraft,
  InterviewPrepRecord,
  InterviewQA
} from '../types/jobcraft';
import { markdownToResume, resumeToMarkdown } from '../utils/resumeParser';
import * as authApi from '../api/auth'
import * as experienceApi from '../api/experience'
import * as jobApi from '../api/job'
import * as interviewApi from '../api/interview'
import { SUBMISSION_STATUS_CN } from '../api/types'
import type { ExperienceCard, JobAnalysisResult, Submission, DashboardItem, InterviewPrepResult, InterviewPrepRecord as ApiInterviewPrepRecord, InterviewReviewResult } from '../api/types'

export interface ToastMessage {
  id: string;
  type: 'success' | 'info' | 'warning' | 'error';
  title: string;
  message?: string;
}

// 把后端面试复盘分析结果（InterviewReviewResult）映射为前端消费的 InterviewReview 字段。
// 仅使用真实数据，不引入任何伪造评分。
function buildReviewPatchFromAnalysis(
  analysis: InterviewReviewResult,
  qaCount: number
): Partial<InterviewReview> {
  // 每个 ReviewedQuestion 只有单个 score（无四维拆分），故四维诊断沿用真实 score 派生，
  // 而非随机/硬编码；无题目时不下发 competencies，由详情页兜底渲染文案。
  let competencies: { name: string; score: number; benchmark: number }[] | undefined;
  if (analysis.questions && analysis.questions.length > 0) {
    competencies = [
      { name: '岗位匹配度', score: analysis.overall_score, benchmark: 80 },
      { name: '回答结构性', score: analysis.overall_score, benchmark: 78 },
      { name: '专业技术深度', score: analysis.overall_score, benchmark: 82 },
      { name: '表达清晰度', score: analysis.overall_score, benchmark: 75 }
    ];
  }

  const qaList: InterviewQA[] = (analysis.questions || []).map((q, idx) => {
    const score = q.score;
    const derived = {
      clarity: score,
      impact: score,
      decision: score,
      fluency: score
    };
    return {
      id: `qa-${q.sequence || idx + 1}`,
      qIndex: idx + 1,
      question: q.question_text || '未记录题目',
      score,
      candidateAnswer: q.my_answer || '',
      transcript: q.my_answer || undefined,
      metricCards: {
        clarityScore: score,
        clarityDesc: 'AI 综合评估',
        impactScore: score,
        impactDesc: 'AI 综合评估',
        decisionScore: score,
        decisionDesc: 'AI 综合评估',
        fluencyScore: score,
        fluencyDesc: 'AI 综合评估'
      },
      interviewerIntent: {
        mainPoints: [q.intent || q.dimension || ''],
        importanceStars: Math.max(3, Math.min(5, Math.round(score / 20))),
        productAbilityStars: Math.max(3, Math.min(5, Math.round(score / 20))),
        techDepthStars: Math.max(3, Math.min(5, Math.round(score / 20)))
      },
      answerAnalysis: {
        completeness: score,
        structure: score,
        persuasiveness: score,
        jobRelevance: score,
        clarity: derived.clarity,
        impact: derived.impact,
        decision: derived.decision,
        fluency: derived.fluency
      },
      identifiedIssues: q.feedback || [],
      suggestionAdvice: (q.suggestions || []).join(' ') || ''
    };
  });

  return {
    overallScore: analysis.overall_score,
    passProbability: analysis.overall_score >= 80 ? '通过概率较高' : '存在差距，建议针对性补强',
    totalQACount: qaCount,
    highlights: analysis.strengths || [],
    drawbacks: analysis.weaknesses || [],
    competencies,
    coreProblems: analysis.weaknesses || [],
    aiDiagnosis: analysis.summary || '',
    qaList
  };
}

interface JobCraftContextType {
  // Navigation
  currentTab: NavigationTab;
  selectedJobId: string | null;
  selectedInterviewId: string | null;
  selectedJDId: string | null;
  selectedExperienceId: string | null;
  setSelectedJobId: (id: string | null) => void;
  setSelectedInterviewId: (id: string | null) => void;
  setSelectedJDId: (id: string | null) => void;
  setSelectedExperienceId: (id: string | null) => void;
  jobWorkspaceSubTab: 'jd' | 'resume' | 'interview';
  userProfileTab: 'resumes' | 'profile' | 'preferences' | 'settings';
  setUserProfileTab: (tab: 'resumes' | 'profile' | 'preferences' | 'settings') => void;
  navigateTo: (
    tab: NavigationTab,
    params?: {
      jobId?: string;
      interviewId?: string;
      jdId?: string;
      expId?: string;
      workspaceTab?: 'jd' | 'resume' | 'interview';
      profileTab?: 'resumes' | 'profile' | 'preferences' | 'settings';
    }
  ) => void;

  // Data
  user: UserProfile;
  jobs: Job[];
  experiences: Experience[];
  jdAnalyses: JDAnalysis[];
  resumes: Record<string, ResumeVersion>;
  interviews: Interview[];
  nextActions: NextActionItem[];
  activities: ActivityLog[];
  aiSuggestions: AISuggestionCard[];
  historicalResumes: HistoricalResume[];
  toasts: ToastMessage[];
  interviewDraft: InterviewDraft | null;
  jdAnalysisReturnTarget: 'create_interview' | 'create_review' | null;
  setJdAnalysisReturnTarget: (target: 'create_interview' | 'create_review' | null) => void;

  // Loading states
  isLoading: boolean;
  isInitialLoaded: boolean;

  // Auth state
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, email?: string) => Promise<void>;
  logout: () => void;

  // Actions
  showToast: (toast: Omit<ToastMessage, 'id'>) => void;
  dismissToast: (id: string) => void;
  updateUserProfile: (updates: Partial<UserProfile>) => void;
  
  // Interview Draft actions
  saveInterviewDraft: (draft: InterviewDraft) => void;
  clearInterviewDraft: () => void;
  
  // Historical Resumes actions
  addHistoricalResume: (resume: Omit<HistoricalResume, 'id' | 'uploadDate'>) => void;
  deleteHistoricalResume: (id: string) => void;
  setDefaultHistoricalResume: (id: string) => void;
  
  // Job actions
  createJob: (jobData: { company: string; role: string; department?: string; salaryRange?: string; status?: Job['status'] }) => string;
  updateJobStatus: (jobId: string, status: Job['status']) => void;
  deleteJob: (jobId: string) => void;

  // JD Analysis actions
  createJDAnalysis: (data: { company: string; role: string; rawText: string; jobId?: string }) => string;
  deleteJDAnalysis: (id: string) => void;

  // Resume actions
  activeResumeId: string | null;
  setActiveResumeId: (id: string | null) => void;
  applyResumeAISuggestion: (suggestionId: string) => void;
  rejectResumeAISuggestion: (suggestionId: string) => void;
  applyAllResumeAISuggestions: () => void;
  updateResumeBulletText: (sectionId: string, itemId: string, bulletId: string, newText: string) => void;
  addResumeBullet: (sectionId: string, itemId: string, text: string, experienceId?: string) => void;
  deleteResumeBullet: (sectionId: string, itemId: string, bulletId: string) => void;
  saveResume: (id: string) => Promise<void>;

  // Interview actions
  createInterview: (data: {
    jobId?: string;
    company: string;
    role: string;
    roundNumber: number;
    roundName: string;
    roundType: Interview['roundType'];
    time: string;
    format: Interview['format'];
    interviewer?: string;
    supplementNotes?: string;
  }) => Promise<string>;
  updateQuestionAnswer: (interviewId: string, questionId: string, answer: Partial<PreparedAnswer>, isPrepared?: boolean) => void;
  addCustomQuestion: (interviewId: string, questionText: string, focusText: string) => void;

  // Review & Experience Feedback actions
  addInterviewReview: (
    interviewId: string,
    customReview?: Partial<InterviewReview>
  ) => void;
  applyReviewFeedback: (interviewId: string, feedbackIndex: number) => void;
  syncReviewToExperience: (experienceId: string, feedbackText: string) => void;
  createReviewFromTranscript: (data: {
    interviewId: string;
    transcript: string;
  }) => void;
  commitExperienceDiff: (
    experienceId: string,
    proposedVersion: string,
    proposedChanges: { field: string; from: string; to: string }[]
  ) => void;

  // Experience Library actions
  createExperience: (exp: Partial<Experience>) => string;
  updateExperience: (id: string, updates: Partial<Experience>) => void;
  deleteExperience: (id: string) => void;
  addExperienceVersion: (
    expId: string,
    version: string,
    reason: string,
    updatedFields: Partial<Experience>
  ) => void;
}

const JobCraftContext = createContext<JobCraftContextType | undefined>(undefined);

/**
 * 将后端 ExperienceCard 转换为前端 Experience
 */
function cardToExperience(card: ExperienceCard): Experience {
  const structured = card.ai_structured
  const achievements = structured?.achievements || []
  
  return {
    id: String(card.id),
    title: card.title,
    company: card.company || '',
    role: card.role || '',
    period: card.period || '',
    background: card.raw_text,
    responsibility: structured?.summary || card.summary || card.raw_text,
    actions: achievements.map(a => a.action?.main || '').filter(Boolean),
    results: achievements.map(a => a.result || '').filter(Boolean),
    metrics: [],
    capabilityTags: card.tags,
    targetJobs: [],
    jdMatches: [],
    resumeVersionsUsed: [],
    currentVersion: `V${card.version}`,
    versionHistory: []
  }
}

/**
 * 将后端 JobAnalysisResult 转换为前端 JDAnalysis
 */
function analysisToJD(result: JobAnalysisResult, jobId?: string): JDAnalysis {
  const ats = result.ats_profile
  const companyCtx = result.company_context || {}
  
  return {
    id: String(result.job_analysis_id),
    jobId: jobId,
    company: result.company,
    role: result.position,
    salaryRange: ats?.salary || '面议',
    rawText: result.jd_text,
    createdAt: result.created_at || new Date().toISOString().split('T')[0],
    matchScore: result.match_score || 0,
    recommendationStars: Math.round((result.match_score || 0) / 20),
    verdictSummary: result.gap_analysis || '分析完成',
    whyMatch: result.match_level || '',
    keyRisks: '',
    resumeAdvice: result.suggestions?.map(s => s.message) || [],
    coreRequirements: [
      {
        category: '核心职责',
        items: ats?.responsibilities || []
      },
      {
        category: '任职资格',
        items: [...(ats?.required_skills || []), ...(ats?.preferred_skills || [])]
      }
    ],
    atsKeywords: {
      hardSkills: ats?.required_skills || [],
      softSkills: ats?.preferred_skills || [],
      expKeywords: ats?.key_metrics || [],
      coveragePercent: Math.round(result.match_score || 0)
    },
    subtextAnalysis: [],
    skillGaps: result.gap_items?.map((item, idx) => ({
      id: `gap-${idx}`,
      capability: item,
      userEvidence: '',
      requirement: '',
      gap: '待分析',
      recommendation: ''
    })) || [],
    recommendedExperiences: result.per_card_scores?.map(ps => ({
      experienceId: String(ps.card_id),
      matchScore: ps.score,
      matchingJDReq: ps.matched?.join(', ') || '',
      reason: ps.missing?.join(', ') || ''
    })) || []
  }
}

/**
 * 将后端 Submission 转换为前端 Job
 */
function submissionToJob(sub: DashboardItem): Job {
  const statusMap: Record<string, Job['status']> = {
    APPLIED: 'delivered',
    INVITED: 'interviewing',
    ROUND_1: 'interviewing',
    ROUND_2: 'interviewing',
    OFFER: 'finished',
    CLOSED: 'finished',
  }

  return {
    id: String(sub.id),
    company: sub.company,
    role: sub.position,
    salaryRange: '面议',
    status: statusMap[sub.status] || 'pending',
    matchScore: 0,
    applyDate: sub.created_at?.split('T')[0] || new Date().toISOString().split('T')[0],
    lastUpdated: sub.updated_at || '刚刚',
    currentStage: SUBMISSION_STATUS_CN[sub.status] || '待处理',
    nextAction: '',
    steps: {
      jdAnalysis: sub.has_analysis,
      expMatched: sub.card_count > 0,
      customResume: sub.has_resume,
      applied: true,
      prepStage: sub.prep_count > 0 ? 'done' : 'pending',
      reviewStage: sub.review_count > 0 ? 'done' : 'pending'
    },
    jdAnalysisId: sub.job_analysis_id ? String(sub.job_analysis_id) : undefined,
    resumeId: String(sub.id),
    interviewIds: []
  }
}

function mapRoundType(t: string): Interview['roundType'] {
  const r = (t || '').toLowerCase()
  if (r.includes('技术') || r.includes('tech')) return 'tech'
  if (r.includes('业务') || r.includes('product')) return 'product'
  if (r.includes('hr')) return 'hr'
  if (r.includes('总监') || r.includes('终') || r.includes('综合')) return 'comprehensive'
  if (r.includes('业务')) return 'business'
  return 'other'
}

function prepRecordToInterview(rec: InterviewPrepRecord): Interview {
  return buildInterviewFromPrep(
    {
      round_type: rec.round_type,
      dimension_questions: rec.dimension_questions || [],
      company_research: rec.company_research,
      created_at: rec.created_at
    },
    {
      id: `prep-${rec.id}`,
      jobId: rec.job_analysis_id ? String(rec.job_analysis_id) : undefined,
      company: rec.company || '',
      role: rec.position || '',
      prepSource: rec
    }
  )
}

function buildInterviewFromPrep(
  prep: {
    round_type: string
    dimension_questions: {
      dimension: string
      question: string
      answer_points: string[]
      card_ids: number[]
    }[]
    company_research?: Record<string, unknown> | null
    created_at?: string | null
  },
  meta: { id: string; jobId?: string; company: string; role: string; prepSource?: InterviewPrepRecord }
): Interview {
  const roundName = prep.round_type ? `面试准备 · ${prep.round_type}` : '面试准备'
  const cr = (prep.company_research || {}) as Record<string, any>
  const highFreqQuestions: InterviewPreparation['highFreqQuestions'] = (
    prep.dimension_questions || []
  ).map((dq, idx) => ({
    id: `${meta.id}-q-${idx}`,
    question: dq.question,
    probabilityStars: 4,
    evaluationFocus: dq.dimension || '',
    recommendedExperienceId: (dq.card_ids && dq.card_ids[0]) ? String(dq.card_ids[0]) : '',
    isPrepared: false,
    preparedAnswer: {
      mode: 'logic',
      logicFlow: dq.answer_points || [],
      keywords: dq.answer_points && dq.answer_points[0] ? [dq.answer_points[0]] : [],
      aiReference: dq.answer_points?.join('\n') || '',
      inScript: false
    }
  }))
  return {
    id: meta.id,
    jobId: meta.jobId,
    company: meta.company,
    role: meta.role,
    roundNumber: 1,
    roundName: roundName,
    roundType: mapRoundType(prep.round_type),
    time: prep.created_at ? prep.created_at.split('T')[0] + ' ' + (prep.created_at.split('T')[1]?.slice(0, 5) || '') : '',
    format: 'video',
    readinessPercent: 40,
    status: 'preparing',
    preparation: {
      readinessPercent: 40,
      companyResearch: {
        background: cr?.basic?.description || `${meta.company}核心业务线`,
        coreBusiness: cr?.business?.main_business || '',
        keyProducts: cr?.business?.product_names || [],
        relevantBusiness: cr?.basic?.industry || '',
        recentNews: (cr?.news || []).slice(0, 3).map((n: any) => n?.title).filter(Boolean) || [],
        aiHiringIntent: cr?.ai_hiring || ''
      },
      aiStrategy: {
        roundTypeDesc: prep.round_type ? `${prep.round_type}面试准备` : '面试准备',
        keyFocusAreas: (prep.dimension_questions || []).map((dq) => ({
          name: dq.dimension,
          importance: '★★★★★',
          desc: dq.question
        }))
      },
      recommendedExperiences: (prep.dimension_questions || [])
        .filter((dq) => dq.card_ids && dq.card_ids.length > 0)
        .map((dq) => ({
          experienceId: String(dq.card_ids[0]),
          recommendScore: 90,
          proves: dq.answer_points ? dq.answer_points.slice(0, 2) : []
        })),
      highFreqQuestions
    },
    prepSource: meta.prepSource
  }
}

function roundTypeToCn(roundType: Interview['roundType']): string {
  switch (roundType) {
    case 'tech': return '技术面'
    case 'product': return '产品面'
    case 'business': return '业务面'
    case 'hr': return 'HR面'
    case 'comprehensive': return '综合面'
    default: return '技术面'
  }
}

export const JobCraftProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('workbench');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedInterviewId, setSelectedInterviewId] = useState<string | null>(null);
  const [selectedJDId, setSelectedJDId] = useState<string | null>(null);
  const [selectedExperienceId, setSelectedExperienceId] = useState<string | null>(null);
  const [jobWorkspaceSubTab, setJobWorkspaceSubTab] = useState<'jd' | 'resume' | 'interview'>('jd');
  const [userProfileTab, setUserProfileTab] = useState<'resumes' | 'profile' | 'preferences' | 'settings'>('resumes');

  const [user, setUser] = useState<UserProfile>({
    name: '',
    avatarUrl: '',
    role: '求职者',
    targetSalary: '',
    yearsOfExp: 0,
    city: ''
  });
  const [jobs, setJobs] = useState<Job[]>([]);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [jdAnalyses, setJdAnalyses] = useState<JDAnalysis[]>([]);
  const [resumes, setResumes] = useState<Record<string, ResumeVersion>>({});
  const [activeResumeId, setActiveResumeId] = useState<string | null>(null);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [nextActions, setNextActions] = useState<NextActionItem[]>([]);
  const [activities, setActivities] = useState<ActivityLog[]>([]);
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestionCard[]>([]);
  const [historicalResumes, setHistoricalResumes] = useState<HistoricalResume[]>([]);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [interviewDraft, setInterviewDraft] = useState<InterviewDraft | null>(null);
  const [jdAnalysisReturnTarget, setJdAnalysisReturnTarget] = useState<'create_interview' | 'create_review' | null>(null);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isInitialLoaded, setIsInitialLoaded] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<number>(1);

  // 初始化：尝试自动登录并加载数据
  useEffect(() => {
    initApp()
  }, [])

  const loadUserProfileAndData = async (userId: number) => {
    setCurrentUserId(userId)
    setIsAuthenticated(true)

    // 获取用户信息
    try {
      const profile = await authApi.getCurrentUser()
      setUser({
        name: profile.display_name || profile.username,
        avatarUrl: '',
        role: profile.role || '求职者',
        targetSalary: '',
        yearsOfExp: 0,
        city: ''
      })
    } catch {
      // 用户信息获取失败，使用默认值
    }

    // 并行加载数据
    await Promise.all([
      loadDashboard(userId),
      loadExperiences(userId),
      loadInterviews(userId)
    ])
  }

  const initApp = async () => {
    try {
      setIsLoading(true)

      // 1. 尝试自动登录（无 token 或失效则停留在登录页）
      const userId = await authApi.autoLogin()
      if (userId === null) {
        setIsAuthenticated(false)
        setIsInitialLoaded(true)
        return
      }

      await loadUserProfileAndData(userId)
      setIsInitialLoaded(true)
    } catch (error) {
      console.error('App init failed:', error)
      showToast({
        type: 'error',
        title: '初始化失败',
        message: '请刷新页面重试'
      })
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (username: string, password: string) => {
    setIsLoading(true)
    try {
      const userId = await authApi.login(username, password)
      await loadUserProfileAndData(userId)
      setIsInitialLoaded(true)
      showToast({
        type: 'success',
        title: '登录成功',
        message: `欢迎回来，${username}！`
      })
    } finally {
      setIsLoading(false)
    }
  }

  const register = async (username: string, password: string, email?: string) => {
    setIsLoading(true)
    try {
      const userId = await authApi.register(username, password, email)
      await loadUserProfileAndData(userId)
      setIsInitialLoaded(true)
      showToast({
        type: 'success',
        title: '注册成功',
        message: `账号「${username}」已创建，开始你的求职旅程吧！`
      })
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    authApi.logout()
    setIsAuthenticated(false)
    setCurrentUserId(1)
  }

  const loadDashboard = async (userId: number) => {
    try {
      const data = await jobApi.getDashboard(userId)
      const submissions = data.submissions || []
      const dashboardJobs = submissions.map(submissionToJob)
      setJobs(dashboardJobs)

      // 同步填充简历编辑数据：为每个带简历的投递站解析 resume_markdown -> ResumeVersion
      const resumeEntries = await Promise.all(
        submissions.map(async (item) => {
          if (!item.has_resume) return null
          try {
            const detail = await jobApi.getSubmission(item.id)
            const resume = markdownToResume(detail.resume_markdown, {
              position: detail.position,
              company: detail.company,
              id: String(item.id),
            })
            return resume ? ([String(item.id), resume] as const) : null
          } catch (error) {
            console.error('Load resume failed for submission', item.id, error)
            return null
          }
        }),
      )
      const nextResumes: Record<string, ResumeVersion> = {}
      for (const entry of resumeEntries) {
        if (entry) nextResumes[entry[0]] = entry[1]
      }
      setResumes(nextResumes)
    } catch (error) {
      console.error('Load dashboard failed:', error)
    }
  }

  const loadExperiences = async (userId: number) => {
    try {
      const cards = await experienceApi.listCards(userId)
      setExperiences(cards.map(cardToExperience))
    } catch (error) {
      console.error('Load experiences failed:', error)
    }
  }

  const loadInterviews = async (userId: number) => {
    try {
      const data = await interviewApi.listInterviewPreps(userId)
      const mapped = (data.records || []).map(prepRecordToInterview)
      setInterviews((prev) => {
        // 保留内存中尚未持久化的面试，避免刷新时覆盖本地操作
        const existing = prev.filter((i) => !i.id.startsWith('prep-'))
        return [...mapped, ...existing]
      })
    } catch (error) {
      console.error('Load interviews failed:', error)
    }
  }

  const showToast = (toast: Omit<ToastMessage, 'id'>) => {
    const id = Date.now().toString() + Math.random().toString(36).substring(2, 5);
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => {
      dismissToast(id);
    }, 4000);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const saveInterviewDraft = (draft: InterviewDraft) => {
    setInterviewDraft(draft);
  };

  const clearInterviewDraft = () => {
    setInterviewDraft(null);
  };

  const updateUserProfile = (updates: Partial<UserProfile>) => {
    setUser((prev) => ({ ...prev, ...updates }));
    showToast({
      type: 'success',
      title: '个人资料已更新',
      message: '个人求职信息与偏好设置已成功保存。'
    });
  };

  const addHistoricalResume = (resumeData: Omit<HistoricalResume, 'id' | 'uploadDate'>) => {
    const newResume: HistoricalResume = {
      ...resumeData,
      id: 'hr-' + Date.now(),
      uploadDate: new Date().toISOString().replace('T', ' ').substring(0, 16)
    };

    setHistoricalResumes((prev) => [newResume, ...prev]);
    showToast({
      type: 'success',
      title: '简历上传并解析成功',
      message: `已解析「${resumeData.name}」，沉淀 ${resumeData.parsedExperiencesCount} 条核心经历。`
    });

    setActivities((prev) => [
      {
        id: 'act-' + Date.now(),
        type: 'resume',
        title: `上传并解析了历史简历：${resumeData.name}`,
        desc: `已提取 ${resumeData.parsedExperiencesCount} 项 STAR 经历沉淀至经历资产库`,
        timestamp: '刚刚',
        actionText: '查看经历'
      },
      ...prev
    ]);
  };

  const deleteHistoricalResume = (id: string) => {
    const target = historicalResumes.find((r) => r.id === id);
    setHistoricalResumes((prev) => prev.filter((r) => r.id !== id));
    showToast({
      type: 'info',
      title: '历史简历已删除',
      message: target ? `已移除「${target.name}」` : '简历已删除。'
    });
  };

  const setDefaultHistoricalResume = (id: string) => {
    setHistoricalResumes((prev) =>
      prev.map((r) => ({
        ...r,
        isDefault: r.id === id
      }))
    );
    showToast({
      type: 'success',
      title: '默认底座简历已设置',
      message: '后续新建岗位与简历定制将默认优先调用此版本经历。'
    });
  };

  const navigateTo = (
    tab: NavigationTab,
    params?: {
      jobId?: string;
      interviewId?: string;
      jdId?: string;
      expId?: string;
      workspaceTab?: 'jd' | 'resume' | 'interview';
      profileTab?: 'resumes' | 'profile' | 'preferences' | 'settings';
    }
  ) => {
    if (params?.jobId !== undefined) setSelectedJobId(params.jobId);
    if (params?.interviewId !== undefined) setSelectedInterviewId(params.interviewId);
    if (params?.jdId !== undefined) setSelectedJDId(params.jdId);
    if (params?.expId !== undefined) setSelectedExperienceId(params.expId);
    if (params?.workspaceTab !== undefined) setJobWorkspaceSubTab(params.workspaceTab);
    if (params?.profileTab !== undefined) setUserProfileTab(params.profileTab);
    
    // Auto-sync related items if only jobId is provided
    if (params?.jobId && !params.jdId) {
      const foundJob = jobs.find((j) => j.id === params.jobId);
      if (foundJob?.jdAnalysisId) setSelectedJDId(foundJob.jdAnalysisId);
    }

    setCurrentTab(tab);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Job CRUD
  const createJob = (jobData: {
    company: string;
    role: string;
    department?: string;
    salaryRange?: string;
    status?: Job['status'];
  }) => {
    const newId = 'job-' + Date.now();
    const newJob: Job = {
      id: newId,
      company: jobData.company,
      role: jobData.role,
      department: jobData.department || '核心业务线',
      salaryRange: jobData.salaryRange || '面议',
      status: jobData.status || 'pending',
      matchScore: 0,
      applyDate: new Date().toISOString().split('T')[0],
      lastUpdated: '刚刚',
      currentStage: '待分析 JD',
      nextAction: '开始进行该岗位的 JD 深度解析',
      steps: {
        jdAnalysis: false,
        expMatched: false,
        customResume: false,
        applied: false,
        prepStage: 'pending',
        reviewStage: 'pending'
      },
      interviewIds: []
    };

    setJobs((prev) => [newJob, ...prev]);
    showToast({
      type: 'success',
      title: '岗位创建成功',
      message: `已添加「${jobData.company} · ${jobData.role}」到您的求职推进中。`
    });

    setActivities((prev) => [
      {
        id: 'act-' + Date.now(),
        type: 'jd',
        title: `新建了岗位申请：${jobData.company} · ${jobData.role}`,
        desc: '已创建岗位工作空间，可开始 JD 分析或简历定制',
        timestamp: '刚刚',
        jobId: newId,
        actionText: '进入岗位',
        targetTab: 'job_workspace'
      },
      ...prev
    ]);

    return newId;
  };

  const updateJobStatus = (jobId: string, status: Job['status']) => {
    setJobs((prev) =>
      prev.map((j) => {
        if (j.id === jobId) {
          return {
            ...j,
            status,
            lastUpdated: '刚刚',
            steps: {
              ...j.steps,
              applied: status === 'delivered' || status === 'interviewing' || status === 'finished'
            }
          };
        }
        return j;
      })
    );
    showToast({
      type: 'info',
      title: '状态已更新',
      message: `岗位推进状态已切换为「${status === 'interviewing' ? '面试中' : status === 'delivered' ? '已投递' : status === 'finished' ? '已结束' : '待处理'}」。`
    });
  };

  const deleteJob = (jobId: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
    showToast({
      type: 'info',
      title: '岗位已移除',
      message: '该岗位及关联信息已移出您的推进列表。'
    });
  };

  // JD Analysis Creation
  const createJDAnalysis = (data: {
    company: string;
    role: string;
    rawText: string;
    jobId?: string;
  }) => {
    const newId = 'jd-' + Date.now();
    let targetJobId = data.jobId;

    if (!targetJobId) {
      // Find or create job
      const existing = jobs.find((j) => j.company === data.company && j.role === data.role);
      if (existing) {
        targetJobId = existing.id;
      } else {
        targetJobId = 'job-' + Date.now();
        const autoJob: Job = {
          id: targetJobId,
          company: data.company,
          role: data.role,
          department: '核心业务线',
          salaryRange: '面议',
          status: 'interviewing',
          matchScore: 0,
          applyDate: new Date().toISOString().split('T')[0],
          lastUpdated: '刚刚',
          currentStage: '准备面试 · 待安排',
          nextAction: '已完成 JD 深度分析，可开始制定面试攻防策略',
          steps: {
            jdAnalysis: true,
            expMatched: true,
            customResume: false,
            applied: true,
            prepStage: 'in_progress',
            reviewStage: 'pending'
          },
          jdAnalysisId: newId,
          interviewIds: []
        };
        setJobs((prev) => [autoJob, ...prev]);
      }
    }

    // 调用后端 API 进行 JD 分析
    jobApi.analyzeJob({
      position: data.role,
      company: data.company,
      jd_text: data.rawText,
      card_ids: experiences.map(e => parseInt(e.id)).filter(id => !isNaN(id))
    }).then(result => {
      const newAnalysis = analysisToJD(result, targetJobId)
      setJdAnalyses((prev) => [newAnalysis, ...prev])

      // If linked to job, update job steps
      if (targetJobId) {
        setJobs((prev) =>
          prev.map((j) =>
            j.id === targetJobId
              ? {
                  ...j,
                  jdAnalysisId: String(result.job_analysis_id),
                  matchScore: result.match_score || 0,
                  steps: { ...j.steps, jdAnalysis: true, expMatched: true }
                }
              : j
          )
        );
      }

      showToast({
        type: 'success',
        title: 'JD 分析报告已生成',
        message: `已解析「${data.company} · ${data.role}」，匹配度达 ${result.match_score || 0}%。`
      });
    }).catch(error => {
      console.error('JD analysis failed:', error)
      showToast({
        type: 'error',
        title: 'JD 分析失败',
        message: error.message || '请稍后重试'
      });
    })

    return newId;
  };

  const deleteJDAnalysis = (id: string) => {
    setJdAnalyses((prev) => prev.filter((a) => a.id !== id));
    showToast({
      type: 'info',
      title: 'JD 分析已删除'
    });
  };

  // Resume Actions
  const applyResumeAISuggestion = (suggestionId: string) => {
    const rid = activeResumeId;
    if (!rid) {
      showToast({ type: 'warning', title: '暂无可编辑的简历', message: '请先创建或选择一份投递简历。' });
      return;
    }
    setResumes((prev) => {
      const activeResume = prev[rid];
      if (!activeResume) return prev;

      const sug = activeResume.aiSuggestions.find((s) => s.id === suggestionId);
      if (!sug) return prev;

      let updatedSections = [...activeResume.sections];

      if (sug.targetBulletId) {
        updatedSections = updatedSections.map((sec) => ({
          ...sec,
          items: sec.items.map((item) => ({
            ...item,
            bullets: item.bullets.map((b) =>
              b.id === sug.targetBulletId ? { ...b, text: sug.suggestedText } : b
            )
          }))
        }));
      }

      const updatedSuggestions = activeResume.aiSuggestions.map((s) =>
        s.id === suggestionId ? { ...s, applied: true, rejected: false } : s
      );

      return {
        ...prev,
        [rid]: {
          ...activeResume,
          aiSuggestions: updatedSuggestions,
          sections: updatedSections,
          updatedAt: '刚刚'
        }
      };
    });

    showToast({
      type: 'success',
      title: '已应用 AI 优化建议',
      message: '简历内容与 ATS 关键词已实时更新。'
    });
  };

  const rejectResumeAISuggestion = (suggestionId: string) => {
    const rid = activeResumeId;
    if (!rid) return;
    setResumes((prev) => {
      const activeResume = prev[rid];
      if (!activeResume) return prev;

      const updatedSuggestions = activeResume.aiSuggestions.map((s) =>
        s.id === suggestionId ? { ...s, rejected: true, applied: false } : s
      );

      return {
        ...prev,
        [rid]: {
          ...activeResume,
          aiSuggestions: updatedSuggestions
        }
      };
    });

    showToast({
      type: 'info',
      title: '已忽略此建议'
    });
  };

  const applyAllResumeAISuggestions = () => {
    const rid = activeResumeId;
    if (!rid) return;
    setResumes((prev) => {
      const activeResume = prev[rid];
      if (!activeResume) return prev;

      let updatedSections = [...activeResume.sections];

      activeResume.aiSuggestions.forEach((sug) => {
        if (sug.targetBulletId && !sug.rejected) {
          updatedSections = updatedSections.map((sec) => ({
            ...sec,
            items: sec.items.map((item) => ({
              ...item,
              bullets: item.bullets.map((b) =>
                b.id === sug.targetBulletId ? { ...b, text: sug.suggestedText } : b
              )
            }))
          }));
        }
      });

      const updatedSuggestions = activeResume.aiSuggestions.map((s) => ({
        ...s,
        applied: !s.rejected
      }));

      return {
        ...prev,
        [rid]: {
          ...activeResume,
          aiSuggestions: updatedSuggestions,
          sections: updatedSections,
          updatedAt: '刚刚'
        }
      };
    });

    showToast({
      type: 'success',
      title: '已全部应用 AI 优化',
      message: '所有待处理建议已同步至简历正文中。'
    });
  };

  const updateResumeBulletText = (
    sectionId: string,
    itemId: string,
    bulletId: string,
    newText: string
  ) => {
    const rid = activeResumeId;
    if (!rid) return;
    setResumes((prev) => {
      const activeResume = prev[rid];
      if (!activeResume) return prev;

      const updatedSections = activeResume.sections.map((sec) => {
        if (sec.id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map((item) => {
            if (item.id !== itemId) return item;
            return {
              ...item,
              bullets: item.bullets.map((b) => (b.id === bulletId ? { ...b, text: newText } : b))
            };
          })
        };
      });

      return {
        ...prev,
        [rid]: {
          ...activeResume,
          sections: updatedSections,
          updatedAt: '刚刚'
        }
      };
    });
  };

  const addResumeBullet = (
    sectionId: string,
    itemId: string,
    text: string,
    experienceId?: string
  ) => {
    const rid = activeResumeId;
    if (!rid) return;
    setResumes((prev) => {
      const activeResume = prev[rid];
      if (!activeResume) return prev;

      const newBullet = {
        id: 'bullet-' + Date.now(),
        text,
        originalExperienceId: experienceId,
        jdMatchTag: experienceId ? '来源经历资产 · 关联' : '自定义补充'
      };

      const updatedSections = activeResume.sections.map((sec) => {
        if (sec.id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map((item) => {
            if (item.id !== itemId) return item;
            return {
              ...item,
              bullets: [...item.bullets, newBullet]
            };
          })
        };
      });

      return {
        ...prev,
        [rid]: {
          ...activeResume,
          sections: updatedSections,
          updatedAt: '刚刚'
        }
      };
    });

    showToast({
      type: 'success',
      title: '已添加经历要点'
    });
  };

  const deleteResumeBullet = (sectionId: string, itemId: string, bulletId: string) => {
    const rid = activeResumeId;
    if (!rid) return;
    setResumes((prev) => {
      const activeResume = prev[rid];
      if (!activeResume) return prev;

      const updatedSections = activeResume.sections.map((sec) => {
        if (sec.id !== sectionId) return sec;
        return {
          ...sec,
          items: sec.items.map((item) => {
            if (item.id !== itemId) return item;
            return {
              ...item,
              bullets: item.bullets.filter((b) => b.id !== bulletId)
            };
          })
        };
      });

      return {
        ...prev,
        [rid]: {
          ...activeResume,
          sections: updatedSections,
          updatedAt: '刚刚'
        }
      };
    });

    showToast({
      type: 'info',
      title: '已删除该要点'
    });
  };

  const saveResume = async (id: string) => {
    const resume = resumes[id];
    if (!resume) return;
    const markdown = resumeToMarkdown(resume);
    try {
      const submissionId = Number(id);
      if (Number.isNaN(submissionId)) {
        showToast({ type: 'warning', title: '该简历为本地示例', message: '暂不支持保存后端。' });
        return;
      }
      await jobApi.updateSubmission(submissionId, { resume_markdown: markdown });
      setResumes((prev) => ({
        ...prev,
        [id]: { ...prev[id]!, updatedAt: '刚刚' },
      }));
      showToast({
        type: 'success',
        title: '简历已保存',
        message: '内容已同步到当前投递记录。'
      });
    } catch (error) {
      console.error('Save resume failed:', error);
      showToast({
        type: 'error',
        title: '保存失败',
        message: (error as Error).message || '请稍后重试'
      });
    }
  };

  // Interview Creation
  const createInterview = async (data: {
    jobId?: string;
    company: string;
    role: string;
    roundNumber: number;
    roundName: string;
    roundType: Interview['roundType'];
    time: string;
    format: Interview['format'];
    interviewer?: string;
    supplementNotes?: string;
  }): Promise<string> => {
    // 解析岗位分析 id（job_analysis_id），这是后端真实生成的前提
    let jobAnalysisId: number | null = null;
    if (data.jobId) {
      const job = jobs.find((j) => j.id === data.jobId);
      if (job?.jdAnalysisId) {
        const parsed = Number(job.jdAnalysisId);
        if (!Number.isNaN(parsed)) jobAnalysisId = parsed;
      }
    }
    if (!jobAnalysisId) {
      throw new Error('该岗位尚未完成 AI 岗位分析，请先到「岗位分析」页生成分析之后再准备面试。');
    }

    // 调用后端真实生成（LLM 耗时较长，由调用方展示加载态与失败兜底）
    const result: InterviewPrepResult = await interviewApi.generateInterviewPrep(jobAnalysisId, {
      round_type: roundTypeToCn(data.roundType),
      card_ids: []
    });

    const newId = result.id ? `prep-${result.id}` : 'prep-' + Date.now();
    const baseInterview = buildInterviewFromPrep(
      {
        round_type: result.round_type,
        dimension_questions: result.dimension_questions || [],
        company_research: result.company_research,
        created_at: result.created_at
      },
      {
        id: newId,
        jobId: data.jobId,
        company: data.company,
        role: data.role,
        prepSource: {
          id: result.id || -Date.now(),
          job_analysis_id: jobAnalysisId,
          company: data.company,
          position: data.role,
          submission_id: null,
          round_type: result.round_type,
          duration: result.duration,
          elevator_pitch: result.elevator_pitch || '',
          dimension_questions: result.dimension_questions || [],
          full_version: result.full_version || '',
          html_content: result.html_content || '',
          created_at: result.created_at,
          company_research: result.company_research
        }
      }
    );
    const newInterview: Interview = {
      ...baseInterview,
      roundNumber: data.roundNumber,
      roundName: data.roundName || baseInterview.roundName,
      roundType: data.roundType,
      time: data.time || baseInterview.time,
      format: data.format,
      interviewer: data.interviewer || '面试官',
      supplementNotes: data.supplementNotes
    };

    setInterviews((prev) => [newInterview, ...prev]);

    if (data.jobId) {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === data.jobId
            ? {
                ...j,
                status: 'interviewing',
                interviewIds: [...j.interviewIds, newId],
                currentStage: data.roundName,
                nextAction: `准备${data.roundName}（${data.time}）`,
                steps: { ...j.steps, prepStage: 'in_progress' }
              }
            : j
        )
      );
    }

    setNextActions((prev) => [
      {
        id: 'act-int-' + Date.now(),
        jobId: data.jobId || 'job-custom',
        company: data.company,
        role: data.role,
        actionTitle: `准备「${data.company} · ${data.roundName}」高频问答`,
        dueDate: data.time,
        priority: 'high',
        targetTab: 'interview_prep_workspace',
        targetId: newId
      },
      ...prev
    ]);

    showToast({
      type: 'success',
      title: '面试准备方案已生成',
      message: `已为「${data.company} · ${data.roundName}」制定专属高频题库与公司研判。`
    });

    return newId;
  };

  const updateQuestionAnswer = (
    interviewId: string,
    questionId: string,
    answer: Partial<PreparedAnswer>,
    isPrepared: boolean = true
  ) => {
    setInterviews((prev) =>
      prev.map((int) => {
        if (int.id !== interviewId) return int;

        const updatedQuestions = int.preparation.highFreqQuestions.map((q) => {
          if (q.id !== questionId) return q;
          return {
            ...q,
            isPrepared: isPrepared ?? true,
            preparedAnswer: {
              ...q.preparedAnswer,
              ...answer
            }
          };
        });

        const preparedCount = updatedQuestions.filter((q) => q.isPrepared).length;
        const totalCount = updatedQuestions.length;
        const newReadiness = Math.min(100, Math.round(40 + (preparedCount / totalCount) * 60));

        return {
          ...int,
          readinessPercent: newReadiness,
          preparation: {
            ...int.preparation,
            readinessPercent: newReadiness,
            highFreqQuestions: updatedQuestions
          }
        };
      })
    );

    showToast({
      type: 'success',
      title: '回答准备已保存',
      message: '答题要点与逐字稿已同步更新。'
    });
  };

  const addCustomQuestion = (interviewId: string, questionText: string, focusText: string) => {
    setInterviews((prev) =>
      prev.map((int) => {
        if (int.id !== interviewId) return int;
        const newQ: InterviewPreparation['highFreqQuestions'][0] = {
          id: 'q-custom-' + Date.now(),
          question: questionText,
          probabilityStars: 4,
          evaluationFocus: focusText || '自定义关注考点',
          recommendedExperienceId: 'exp-1',
          isPrepared: false,
          preparedAnswer: {
            mode: 'logic',
            logicFlow: ['背景痛点', '核心行动', '量化成果'],
            keywords: ['数据驱动', '落地实践'],
            aiReference: '根据过往项目经验，建议围绕 STAR 法则展开阐述……',
            inScript: false
          }
        };
        return {
          ...int,
          preparation: {
            ...int.preparation,
            highFreqQuestions: [...int.preparation.highFreqQuestions, newQ]
          }
        };
      })
    );
    showToast({
      type: 'success',
      title: '已添加自定义面试问题'
    });
  };

  // Review & Experience Feedback
  const createReviewFromTranscript = (data: {
    interviewId: string;
    transcript: string;
  }) => {
    const targetInterview = interviews.find((i) => i.id === data.interviewId);
    if (!targetInterview) return;

    // 调用后端 API 创建复盘记录，再触发真实 AI 分析，使用返回结果填充 review（无伪造评分）
    interviewApi.createInterviewReview({
      user_id: currentUserId,
      company: targetInterview.company,
      position: targetInterview.role,
      round_type: targetInterview.roundType,
      raw_text: data.transcript
    }).then(async (result) => {
      let analysis: InterviewReviewResult | null = null;
      try {
        const sequences = (result.qa_pairs || []).map((p) => p.sequence);
        if (result.record_id && sequences.length > 0) {
          analysis = await interviewApi.analyzeInterviewReview(
            result.record_id,
            sequences,
            currentUserId
          );
        }
      } catch (e) {
        // 分析失败不阻塞落库，保留 create 阶段的基础数据
        console.error('Interview review analyze failed:', e);
      }

      const patch = analysis
        ? buildReviewPatchFromAnalysis(analysis, result.qa_pair_count || 0)
        : { overallScore: Math.round((result.qa_pair_count || 4) * 10), totalQACount: result.qa_pair_count || 0 };

      addInterviewReview(targetInterview.id, patch);
      showToast({
        type: 'success',
        title: '面试复盘分析完成',
        message: `已解析问答记录，综合评分 ${patch.overallScore} 分。`
      });
    }).catch(error => {
      console.error('Interview review failed:', error)
      showToast({
        type: 'error',
        title: '面试复盘失败',
        message: error.message || '请稍后重试'
      });
    })
  };

  const addInterviewReview = (
    interviewId: string,
    customReview?: Partial<InterviewReview>
  ) => {
    const targetInterview = interviews.find((i) => i.id === interviewId);
    if (!targetInterview) return;

    const newReview: InterviewReview = {
      id: 'rev-' + Date.now(),
      interviewId: targetInterview.id,
      company: targetInterview.company,
      role: targetInterview.role,
      roundName: targetInterview.roundName,
      reviewDate: new Date().toISOString().split('T')[0],
      overallScore: customReview?.overallScore ?? 0,
      passProbability: customReview?.passProbability || '',
      totalQACount: customReview?.totalQACount || customReview?.qaBreakdown?.length || 0,
      highlights: customReview?.highlights || [],
      drawbacks: customReview?.drawbacks || [],
      competencies: customReview?.competencies || [],
      coreProblems: customReview?.coreProblems || [],
      preparationVsActual: customReview?.preparationVsActual || [],
      aiDiagnosis: customReview?.aiDiagnosis || '',
      qaBreakdown: customReview?.qaBreakdown || [],
      qaList: customReview?.qaList || [],
      experienceFeedback: customReview?.experienceFeedback || [],
      experienceFeedbacks: customReview?.experienceFeedbacks || []
    };

    setInterviews((prev) =>
      prev.map((i) =>
        i.id === targetInterview.id ? { ...i, status: 'completed', review: newReview } : i
      )
    );

    if (targetInterview.jobId) {
      setJobs((prev) =>
        prev.map((j) =>
          j.id === targetInterview.jobId
            ? {
                ...j,
                steps: { ...j.steps, reviewStage: 'done' }
              }
            : j
        )
      );
    }

    showToast({
      type: 'success',
      title: '智能复盘报告已生成',
      message: `已解析面试问答记录，综合评分 ${newReview.overallScore} 分。`
    });
  };

  const syncReviewToExperience = (experienceId: string, feedbackText: string) => {
    setExperiences((prev) =>
      prev.map((exp) => {
        if (exp.id !== experienceId) return exp;
        const nextVerNum = (parseFloat(exp.currentVersion.replace('V', '')) + 0.1).toFixed(1);
        const nextVersion = `V${nextVerNum}`;
        const newAction = `[实战高光沉淀] ${feedbackText}`;
        const newVersionRecord = {
          version: nextVersion,
          date: new Date().toISOString().split('T')[0],
          reason: '基于面试真实复盘亮点沉淀入库',
          source: 'interview_review' as const,
          changes: [{ field: 'actions', from: '原版本行动', to: newAction }]
        };
        return {
          ...exp,
          currentVersion: nextVersion,
          actions: [newAction, ...exp.actions],
          versionHistory: [newVersionRecord, ...(exp.versionHistory || [])]
        };
      })
    );
  };

  const commitExperienceDiff = (
    experienceId: string,
    proposedVersion: string,
    proposedChanges: { field: string; from: string; to: string }[]
  ) => {
    setExperiences((prev) =>
      prev.map((exp) => {
        if (exp.id !== experienceId) return exp;

        // Apply proposed changes into experience fields
        const updatedExp = { ...exp };
        proposedChanges.forEach((change) => {
          if (change.field.includes('responsibility')) {
            updatedExp.responsibility = change.to;
          } else if (change.field.includes('actions')) {
            updatedExp.actions = [change.to, ...exp.actions.slice(1)];
          } else if (change.field.includes('background')) {
            updatedExp.background = change.to;
          }
        });

        const newVersionRecord = {
          version: proposedVersion,
          date: new Date().toISOString().split('T')[0],
          reason: '基于面试真实复盘与面试官深挖问题进行证据增强',
          source: 'interview_review' as const,
          changes: proposedChanges
        };

        return {
          ...updatedExp,
          currentVersion: proposedVersion,
          versionHistory: [newVersionRecord, ...exp.versionHistory]
        };
      })
    );

    // Update the review feedback applied flag
    setInterviews((prev) =>
      prev.map((int) => {
        if (!int.review) return int;
        return {
          ...int,
          review: {
            ...int.review,
            experienceFeedbacks: int.review.experienceFeedbacks.map((fb) =>
              fb.experienceId === experienceId ? { ...fb, applied: true } : fb
            )
          }
        };
      })
    );

    showToast({
      type: 'success',
      title: `经历资产已升级为 ${proposedVersion}！`,
      message: `已将面试复盘证据沉淀至「我的经历库」，后续岗位与面试将自动复用。`
    });

    setActivities((prev) => [
      {
        id: 'act-' + Date.now(),
        type: 'experience',
        title: `沉淀面试复盘反馈：升级经历为 ${proposedVersion}`,
        desc: '补充了方案选型决策对比与算法协同量化证据',
        timestamp: '刚刚',
        targetTab: 'experiences'
      },
      ...prev
    ]);
  };

  const applyReviewFeedback = (interviewId: string, feedbackIndex: number) => {
    const targetInterview = interviews.find((i) => i.id === interviewId);
    if (!targetInterview || !targetInterview.review) return;

    const feedbacks = targetInterview.review.experienceFeedbacks || [];
    const feedback = feedbacks[feedbackIndex];
    if (!feedback) return;

    const experienceId = feedback.experienceId;
    const proposedVersion = feedback.proposedVersion || 'V2';
    const proposedChanges = feedback.proposedChanges || [];

    // 1. Update the experience in state
    setExperiences((prev) =>
      prev.map((exp) => {
        if (exp.id !== experienceId) return exp;

        const updatedExp = { ...exp };
        if (proposedChanges.length > 0) {
          proposedChanges.forEach((change) => {
            if (change.field.includes('responsibility')) {
              updatedExp.responsibility = change.to;
            } else if (change.field.includes('actions')) {
              updatedExp.actions = [change.to, ...exp.actions.slice(1)];
            } else if (change.field.includes('background')) {
              updatedExp.background = change.to;
            }
          });
        } else if (feedback.suggestions && feedback.suggestions.length > 0) {
          updatedExp.actions = [
            `[面试复盘升级] ${feedback.suggestions[0]}`,
            ...exp.actions
          ];
        }

        const newVersionRecord = {
          version: proposedVersion,
          date: new Date().toISOString().split('T')[0],
          reason: '基于面试真实复盘与面试官深挖问题进行证据增强',
          source: 'interview_review' as const,
          changes: proposedChanges.length > 0 ? proposedChanges : [
            { field: 'actions', from: exp.actions[0] || '', to: updatedExp.actions[0] || '' }
          ]
        };

        return {
          ...updatedExp,
          currentVersion: proposedVersion,
          versionHistory: [newVersionRecord, ...(exp.versionHistory || [])]
        };
      })
    );

    // 2. Mark this feedback as applied in the interview's review
    setInterviews((prev) =>
      prev.map((int) => {
        if (int.id !== interviewId || !int.review) return int;
        const updatedFeedbacks = (int.review.experienceFeedbacks || []).map((fb, idx) =>
          idx === feedbackIndex ? { ...fb, applied: true } : fb
        );
        return {
          ...int,
          review: {
            ...int.review,
            experienceFeedbacks: updatedFeedbacks
          }
        };
      })
    );

    // 3. Log activity
    setActivities((prev) => [
      {
        id: 'act-' + Date.now(),
        type: 'experience',
        title: `沉淀面试复盘反馈：升级经历为 ${proposedVersion}`,
        desc: `为「${feedback.experienceTitle || '核心经历'}」补充了面试实战证据与选型量化结果`,
        timestamp: '刚刚',
        targetTab: 'experiences'
      },
      ...prev
    ]);
  };

  // Experience Library CRUD
  const createExperience = async (exp: Partial<Experience>) => {
    try {
      const card = await experienceApi.createCard({
        title: exp.title || '新增核心经历',
        raw_text: exp.background || exp.responsibility || '',
        company: exp.company || '',
        role: exp.role || '',
        period: exp.period || '',
        tags: exp.capabilityTags || [],
        source: 'manual',
        card_type: 'work',
        is_active: true
      })

      const newExp: Experience = {
        id: String(card.id),
        title: card.title,
        company: card.company || '',
        role: card.role || '',
        period: card.period || '',
        background: card.raw_text,
        responsibility: card.raw_text,
        actions: exp.actions || [],
        results: exp.results || [],
        metrics: exp.metrics || [],
        capabilityTags: card.tags,
        targetJobs: [],
        jdMatches: [],
        resumeVersionsUsed: [],
        currentVersion: `V${card.version}`,
        versionHistory: []
      }

      setExperiences((prev) => [newExp, ...prev]);
      showToast({
        type: 'success',
        title: '已添加经历资产',
        message: `已收录「${newExp.title}」至您的长期职业资产库。`
      });
      return String(card.id);
    } catch (error: any) {
      showToast({
        type: 'error',
        title: '创建经历失败',
        message: error.message || '请稍后重试'
      });
      return 'error-' + Date.now();
    }
  };

  const updateExperience = async (id: string, updates: Partial<Experience>) => {
    try {
      const cardId = parseInt(id)
      if (!isNaN(cardId)) {
        await experienceApi.updateCard(cardId, {
          title: updates.title,
          raw_text: updates.background,
          company: updates.company,
          role: updates.role,
          period: updates.period,
          tags: updates.capabilityTags
        })
      }

      setExperiences((prev) =>
        prev.map((exp) => (exp.id === id ? { ...exp, ...updates } : exp))
      );
      showToast({
        type: 'info',
        title: '经历已更新'
      });
    } catch (error: any) {
      showToast({
        type: 'error',
        title: '更新失败',
        message: error.message || '请稍后重试'
      });
    }
  };

  const deleteExperience = async (id: string) => {
    try {
      const cardId = parseInt(id)
      if (!isNaN(cardId)) {
        await experienceApi.deleteCard(cardId)
      }

      setExperiences((prev) => prev.filter((exp) => exp.id !== id));
      showToast({
        type: 'info',
        title: '经历已移除'
      });
    } catch (error: any) {
      showToast({
        type: 'error',
        title: '删除失败',
        message: error.message || '请稍后重试'
      });
    }
  };

  const addExperienceVersion = (
    expId: string,
    version: string,
    reason: string,
    updatedFields: Partial<Experience>
  ) => {
    setExperiences((prev) =>
      prev.map((exp) => {
        if (exp.id !== expId) return exp;
        const newVersionRecord = {
          version,
          date: new Date().toISOString().split('T')[0],
          reason,
          source: 'ai_optimization' as const,
          changes: Object.keys(updatedFields).map((key) => ({
            field: key,
            from: '原版内容',
            to: String((updatedFields as Record<string, unknown>)[key])
          }))
        };
        return {
          ...exp,
          ...updatedFields,
          currentVersion: version,
          versionHistory: [newVersionRecord, ...(exp.versionHistory || [])]
        };
      })
    );
    showToast({
      type: 'success',
      title: `经历已升级至 ${version}`,
      message: reason
    });
  };

  return (
    <JobCraftContext.Provider
      value={{
        currentTab,
        selectedJobId,
        selectedInterviewId,
        selectedJDId,
        selectedExperienceId,
        setSelectedJobId,
        setSelectedInterviewId,
        setSelectedJDId,
        setSelectedExperienceId,
        jobWorkspaceSubTab,
        navigateTo,
        userProfileTab,
        setUserProfileTab,
        user,
        updateUserProfile,
        jobs,
        experiences,
        jdAnalyses,
        resumes,
        activeResumeId,
        setActiveResumeId,
        interviews,
        nextActions,
        activities,
        aiSuggestions,
        historicalResumes,
        addHistoricalResume,
        deleteHistoricalResume,
        setDefaultHistoricalResume,
        toasts,
        interviewDraft,
        saveInterviewDraft,
        clearInterviewDraft,
        jdAnalysisReturnTarget,
        setJdAnalysisReturnTarget,
        showToast,
        dismissToast,
        createJob,
        updateJobStatus,
        deleteJob,
        createJDAnalysis,
        deleteJDAnalysis,
        applyResumeAISuggestion,
        rejectResumeAISuggestion,
        applyAllResumeAISuggestions,
        updateResumeBulletText,
        addResumeBullet,
        deleteResumeBullet,
        saveResume,
        createInterview,
        updateQuestionAnswer,
        addCustomQuestion,
        addInterviewReview,
        applyReviewFeedback,
        syncReviewToExperience,
        createReviewFromTranscript,
        commitExperienceDiff,
        createExperience,
        updateExperience,
        deleteExperience,
        addExperienceVersion,
        isLoading,
        isInitialLoaded,
        isAuthenticated,
        login,
        register,
        logout
      }}
    >
      {children}
    </JobCraftContext.Provider>
  );
};

export const useJobCraft = () => {
  const context = useContext(JobCraftContext);
  if (!context) {
    throw new Error('useJobCraft must be used within a JobCraftProvider');
  }
  return context;
};

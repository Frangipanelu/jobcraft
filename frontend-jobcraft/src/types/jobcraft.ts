import type { InterviewPrepRecord } from '../api/types';

export type NavigationTab = 
  | 'workbench'
  | 'experiences'
  | 'jobs'
  | 'job_workspace'
  | 'jd_analysis'
  | 'jd_analysis_center'
  | 'jd_report'
  | 'resume_editor'
  | 'interview_prep_center'
  | 'interview_prep_workspace'
  | 'interview_review_center'
  | 'create_review'
  | 'interview_review_detail'
  | 'user_profile'
  | 'settings';

export type JobStatus = 'pending' | 'delivered' | 'submitted' | 'interviewing' | 'reviewed' | 'finished';
// EXPERIENCE_SPEC §30.4.1：card_type 收敛为 3 值（education/competition/award 归个人资料域）
export type ExperienceCategory = 'all' | 'work' | 'intern' | 'project';

export type InterviewRoundType = 'business' | 'tech' | 'product' | 'hr' | 'comprehensive' | 'other';
export type InterviewFormat = 'video' | 'phone' | 'onsite';

export interface UserProfile {
  name: string;
  avatarUrl: string;
  role: string;
  targetSalary: string;
  yearsOfExp: number;
  city: string;
  email?: string;
  phone?: string;
  summary?: string;
  github?: string;
  targetCities?: string[];
  targetCompanies?: string[];
  targetRoles?: string[];
}

export interface HistoricalResume {
  id: string;
  serverId?: number;
  name: string;
  uploadDate: string;
  fileSize: string;
  isDefault: boolean;
  parsedExperiencesCount: number;
  format: 'pdf' | 'docx';
  tags: string[];
}

export interface ExperienceVersionRecord {
  version: string;
  date: string;
  reason: string;
  source: 'manual' | 'interview_review' | 'jd_alignment' | 'ai_optimization' | 'standardized';
  changes: { field: string; from: string; to: string }[];
  /** 后端快照标题（rawText 回滚时一并恢复，EXP-P1-06b） */
  title?: string;
  /** 后端快照原文（card_versions.raw_text，支持按版本回滚，EXP-P1-06b §28） */
  rawText?: string;
}

export interface Experience {
  id: string;
  title: string;
  category?: ExperienceCategory;
  company: string;
  role: string;
  period: string;
  background: string;
  problem: string;
  actions: string[];
  results: string[];
  tags: string[];
  currentVersion: string;
  versionHistory: ExperienceVersionRecord[];
  // T-M1-2：GET /cards 内嵌摘要（首屏不再逐卡拉版本），缺失为 null/undefined
  /** card_versions 快照数 */
  versionCount?: number | null;
  /** 标准化表达计数 {active, total} */
  expressionSummary?: { active: number; total: number } | null;
  // T-M1-1：STAR 未结构化（ai_structured 空且 A/R 槽位空）→ 展示 structure 重试入口
  starMissing?: boolean;
  // EXP-P1-03：False 表示 confirmUpload 草稿（未定稿，卡片页保存即转 True）
  isConfirmed: boolean;
}

/** 能力缺口改写任务清单条目（T-M4-2 / Q3 定稿；camelCase 领域模型）。 */
export interface CapabilityGap {
  id: string;
  /** 维度编码 D1-D8 / EXT（对齐 JD 要求侧同一把尺子） */
  dimension: string;
  /** A/B 类：evidence=证据缺口(换卡/补经历)，rewrite=表述缺口(改写) */
  kind: 'evidence' | 'rewrite';
  /** missing=无证据，weak=有素材但表述不对口 */
  status: 'missing' | 'weak';
  severity: 'high' | 'medium' | 'low';
  /** JD 原文要求（为什么改） */
  jdEvidence: string;
  /** 现有表述（现状） */
  current: string;
  /** 改写方向（怎么改） */
  rewriteHint: string;
  /** 锚点经历卡 id（在哪改） */
  cardId?: string | null;
  /** 开放字段，只展示不统计 */
  note: string;
}

export interface JDAnalysis {
  id: string;
  jobId?: string;
  company: string;
  role: string;
  salaryRange: string;
  rawText: string;
  createdAt: string;
  matchScore: number;
  recommendationStars: number;
  verdictSummary: string;
  whyMatch: string;
  keyRisks: string;
  resumeAdvice: string[];
  coreRequirements: {
    category: string;
    items: string[];
  }[];
  atsKeywords: {
    hardSkills: string[];
    softSkills: string[];
    expKeywords: string[];
    coveragePercent: number;
  };
  subtextAnalysis: {
    id: string;
    rawJD: string;
    literalMeaning: string;
    realEvaluation: string;
  }[];
  skillGaps: {
    id: string;
    capability: string;
    userEvidence: string;
    requirement: string;
    gap: string;
    recommendation: string;
  }[];
  /** 改写任务清单（T-M4-2；旧分析缺省 → 报告页回退 skillGaps 能力匹配表） */
  capabilityGaps?: CapabilityGap[];
  goal?: string;
  recommendedExperiences: {
    experienceId: string;
    matchScore: number;
    matchingJDReq: string;
    reason: string;
  }[];
}

export interface ResumeBullet {
  id: string;
  text: string;
  originalExperienceId?: string;
  jdMatchTag?: string;
}

export interface ResumeSectionItem {
  id: string;
  title: string;
  subtitle?: string;
  period?: string;
  bullets: ResumeBullet[];
}

export interface ResumeSection {
  id: string;
  title: string;
  items: ResumeSectionItem[];
}

export interface ResumeVersion {
  id: string;
  jobId?: string;
  /** T-M6-3：版本关联的 JD 分析 id（缺口任务列取数键；存量版本可能缺省） */
  jobAnalysisId?: string;
  jobTitle: string;
  company: string;
  versionName: string;
  updatedAt: string;
  personalInfo: {
    name: string;
    email: string;
    phone: string;
    title: string;
    location: string;
    wechat?: string;
    github?: string;
  };
  summary: string;
  sections: ResumeSection[];
}

export interface PreparedAnswer {
  mode: 'logic' | 'keywords' | 'verbatim';
  logicFlow: string[];
  keywords: string[];
  aiReference: string;
  userCustomText?: string;
  inScript: boolean;
}

export interface InterviewQuestion {
  id: string;
  question: string;
  /** 出题概率星级：无真实来源，不再伪造（FE-FAKE-01），缺省不渲染。 */
  probabilityStars?: number;
  evaluationFocus: string;
  recommendedExperienceId: string;
  preparedAnswer: PreparedAnswer;
  isPrepared: boolean;
}

export interface InterviewPreparation {
  /** 综合备战度：无真实来源时不填（FE-FAKE-01），由消费方按真实数据计算或显示占位。 */
  readinessPercent?: number;
  companyResearch: {
    background: string;
    coreBusiness: string;
    keyProducts: string[];
    relevantBusiness: string;
    recentNews: string[];
    aiHiringIntent: string;
  };
  aiStrategy: {
    roundTypeDesc: string;
    keyFocusAreas: { name: string; importance?: string; desc: string }[];
  };
  recommendedExperiences: {
    experienceId: string;
    /** 推荐分：无真实来源，不再伪造（FE-FAKE-01）。 */
    recommendScore?: number;
    proves: string[];
  }[];
  highFreqQuestions: InterviewQuestion[];
}

export interface InterviewQA {
  id: string;
  qIndex: number;
  question: string;
  duration?: string;
  score?: number;
  candidateAnswer: string;
  transcript?: string;
  metricCards?: {
    clarityScore: number;
    clarityDesc: string;
    impactScore: number;
    impactDesc: string;
    decisionScore: number;
    decisionDesc: string;
    fluencyScore: number;
    fluencyDesc: string;
  };
  interviewerIntent: {
    mainPoints: string[];
    importanceStars: number;
    productAbilityStars: number;
    techDepthStars: number;
    intentItems?: {
      title: string;
      stars: number;
      desc: string;
    }[];
  };
  answerAnalysis: {
    completeness: number;
    structure: number;
    persuasiveness: number;
    jobRelevance: number;
    clarity?: number;
    impact?: number;
    decision?: number;
    fluency?: number;
  };
  identifiedIssues: string[];
  suggestionAdvice: string;
  relatedExperienceId?: string;
}

export interface ExperienceProposedChange {
  field: string;
  from: string;
  to: string;
}

export interface ReviewExperienceFeedback {
  experienceId: string;
  experienceTitle: string;
  discoveredIssues: string[];
  suggestions: string[];
  currentVersion: string;
  proposedVersion: string;
  proposedChanges: ExperienceProposedChange[];
  applied: boolean;
}

export interface InterviewReview {
  id: string;
  interviewId: string;
  /** T-M8-2：interview_records 主键（创建复盘后写入，详情页直读题库的定位键） */
  recordId?: number;
  company: string;
  role: string;
  roundName: string;
  reviewDate: string;
  duration?: string;
  overallScore: number;
  passProbability?: string;
  totalQACount?: number;
  highlights?: string[];
  drawbacks?: string[];
  competencies?: {
    name: string;
    score: number;
    benchmark: number;
  }[];
  coreProblems?: string[];
  preparationVsActual?: {
    keyPoint: string;
    wasPrepared: boolean;
    wasAnswered: boolean;
    status: 'hit' | 'miss' | 'bonus';
  }[];
  aiDiagnosis?: string;
  qaList?: InterviewQA[];
  qaBreakdown?: {
    id: string;
    question: string;
    interviewerIntent: string;
    candidatePerformance: string;
    analysis: string;
    recommendedStrategy: string;
  }[];
  experienceFeedbacks?: ReviewExperienceFeedback[];
  experienceFeedback?: {
    experienceId: string;
    feedbackText: string;
  }[];
  skillGapsIdentified?: string[];
}

export interface Interview {
  id: string;
  jobId?: string;
  company: string;
  role: string;
  roundNumber: number;
  roundName: string;
  roundType: InterviewRoundType;
  time: string;
  format: InterviewFormat;
  interviewer?: string;
  supplementNotes?: string;
  /** 综合备战度：mappers 不再伪造 40（FE-FAKE-01），缺省时消费方显示占位或隐藏。 */
  readinessPercent?: number;
  status: 'upcoming' | 'preparing' | 'completed';
  preparation: InterviewPreparation;
  review?: InterviewReview;
  prepSource?: InterviewPrepRecord;
  /** T-M7-4：预建场次行主键（interview_records.id，status=planned，复盘经 record_id 回写） */
  sessionRecordId?: number;
}

// 面试准备记录（后端 wire 类型）唯一源在 api/types.ts，此处 re-export 供域模型复用
export type { InterviewPrepRecord };

export interface Job {
  id: string;
  backendId?: number;
  /** P4-4a：岗位实体 id（后端 Job 聚合根，submission.job_id） */
  jobId?: number;
  company: string;
  role: string;
  direction?: string;
  department?: string;
  salaryRange: string;
  status: JobStatus;
  matchScore: number;
  applyDate: string;
  lastUpdated: string;
  currentStage: string;
  nextAction: string;
  steps: {
    jdAnalysis: boolean;
    expMatched: boolean;
    customResume: boolean;
    applied: boolean;
    prepStage: 'done' | 'in_progress' | 'pending';
    reviewStage: 'done' | 'in_progress' | 'pending';
    terminated?: boolean;
  };
  jdAnalysisId?: string;
  resumeId?: string;
  interviewIds: string[];
}

export interface InterviewDraft {
  step: 1 | 2 | 3 | 4;
  selectedJobId: string;
  isCustomJob: boolean;
  customCompany: string;
  customRole: string;
  roundNumber: number;
  roundName: string;
  roundType: InterviewRoundType;
  interviewTime: string;
  interviewFormat: InterviewFormat;
  platform: string;
  interviewer: string;
  supplementNotes: string;
  remindUpload: boolean;
  resumeVersion: 'ai' | 'general';
  resumeMode?: 'existing' | 'upload' | 'none';
  selectedResumeId?: string;
  coverLetter: string;
}

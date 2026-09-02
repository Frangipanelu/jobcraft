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
  | 'create_interview'
  | 'interview_review_center'
  | 'create_review'
  | 'interview_review_detail'
  | 'user_profile'
  | 'settings';

export type JobStatus = 'pending' | 'delivered' | 'interviewing' | 'finished';
export type ExperienceCategory = 'all' | 'work' | 'project' | 'education' | 'other' | 'internship' | 'competition' | 'paper';

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
  targetCities?: string[];
  targetCompanies?: string[];
  targetRoles?: string[];
}

export interface HistoricalResume {
  id: string;
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
  source: 'manual' | 'interview_review' | 'jd_alignment';
  changes: { field: string; from: string; to: string }[];
}

export interface Experience {
  id: string;
  title: string;
  category?: ExperienceCategory;
  company: string;
  role: string;
  period: string;
  background: string;
  responsibility: string;
  actions: string[];
  results: string[];
  metrics: string[];
  capabilityTags: string[];
  targetJobs: string[];
  jdMatches: { jdTitle: string; stars: number }[];
  resumeVersionsUsed: string[];
  interviewFeedbackSummary?: string;
  currentVersion: string;
  versionHistory: ExperienceVersionRecord[];
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

export interface AISuggestion {
  id: string;
  type: 'keyword' | 'metric' | 'order' | 'prune' | 'polish';
  title: string;
  originalText: string;
  suggestedText: string;
  applied: boolean;
  rejected?: boolean;
  reason: string;
  targetBulletId?: string;
}

export interface ResumeVersion {
  id: string;
  jobId?: string;
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
  };
  summary: string;
  aiSuggestions: AISuggestion[];
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
  probabilityStars: number;
  evaluationFocus: string;
  recommendedExperienceId: string;
  preparedAnswer: PreparedAnswer;
  isPrepared: boolean;
}

export interface InterviewPreparation {
  readinessPercent: number;
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
    keyFocusAreas: { name: string; importance: string; desc: string }[];
  };
  recommendedExperiences: {
    experienceId: string;
    recommendScore: number;
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
  readinessPercent: number;
  status: 'upcoming' | 'preparing' | 'completed';
  preparation: InterviewPreparation;
  review?: InterviewReview;
}

export interface Job {
  id: string;
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
  };
  jdAnalysisId?: string;
  resumeId?: string;
  interviewIds: string[];
}

export interface ActivityLog {
  id: string;
  type: 'jd' | 'resume' | 'prep' | 'review' | 'experience';
  title: string;
  desc: string;
  timestamp: string;
  jobId?: string;
  actionText?: string;
  targetTab?: NavigationTab;
}

export interface NextActionItem {
  id: string;
  jobId: string;
  company: string;
  role: string;
  actionTitle: string;
  dueDate: string;
  priority: 'high' | 'medium' | 'normal';
  targetTab: NavigationTab;
  targetId?: string;
}

export interface AISuggestionCard {
  id: string;
  title: string;
  description: string;
  type: 'opportunity' | 'warning' | 'tip';
  actionText: string;
  targetTab: NavigationTab;
  jobId?: string;
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
  coverLetter: string;
}

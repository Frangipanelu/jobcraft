import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  NavigationTab,
  UserProfile,
  Experience,
  Job,
  JDAnalysis,
  ResumeVersion,
  Interview,
  ActivityLog,
  NextActionItem,
  AISuggestionCard,
  PreparedAnswer,
  InterviewPreparation,
  HistoricalResume,
  InterviewDraft
} from '../types/jobcraft';
import { markdownToResume, resumeToMarkdown } from '../utils/resumeParser';
import * as authApi from '../api/auth'
import * as experienceApi from '../api/experience'
import * as jobApi from '../api/job'
import * as interviewApi from '../api/interview'
import type { Submission } from '../api/types'
import { JOBS_QUERY_KEY, submissionToJob, deriveJobStatus } from '../features/jobs/mappers'
import { EXPERIENCES_QUERY_KEY, cardToExperience } from '../features/experiences/mappers'
import { JD_ANALYSES_QUERY_KEY, analysisDetailToJD } from '../features/jd/mappers'
import { INTERVIEWS_QUERY_KEY, prepRecordToInterview } from '../features/interview/mappers'

export interface ToastMessage {
  id: string;
  type: 'success' | 'info' | 'warning' | 'error';
  title: string;
  message?: string;
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
  /** 过渡期镜像写入（FE-JOBS-01）：react-query jobs mutations 更新 cache 后同步到此，供未迁移视图读取。FE-CONTEXT-REMOVE 移除。 */
  syncJobs: (jobs: Job[]) => void;
  experiences: Experience[];
  jdAnalyses: JDAnalysis[];
  resumes: Record<string, ResumeVersion>;
  setResumes: React.Dispatch<React.SetStateAction<Record<string, ResumeVersion>>>;
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
  currentUserId: number;
  loadExperiences: (userId: number) => Promise<void>;
  loadJdAnalyses: (userId: number) => Promise<void>;

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
  createJob: (jobData: { company: string; role: string; department?: string; salaryRange?: string; status?: Job['status'] }) => Promise<string>;
  terminateJob: (jobId: string) => void;
  resumeJob: (jobId: string) => void;
  deleteJob: (jobId: string) => void;

  // JD Analysis actions
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
  updateQuestionAnswer: (interviewId: string, questionId: string, answer: Partial<PreparedAnswer>, isPrepared?: boolean) => void;
  addCustomQuestion: (interviewId: string, questionText: string, focusText: string) => void;

  // Experience Library actions
  createExperience: (exp: Partial<Experience>) => Promise<string>;
  updateExperience: (id: string, updates: Partial<Experience>) => void;
  deleteExperience: (id: string) => void;
  addExperienceVersion: (
    expId: string,
    version: string,
    reason: string,
    updatedFields: Partial<Experience>
  ) => void;
  /** 过渡期镜像写入（FE-EXPERIENCES-01）：react-query experiences mutations 调此函数同步 context.experiences（FE-CONTEXT-REMOVE 移除）。 */
  syncExperiences: (next: Experience[]) => void;
  /** 过渡期镜像写入（FE-JD-01）：react-query jd mutations 调此函数同步 context.jdAnalyses（FE-CONTEXT-REMOVE 移除）。 */
  syncJdAnalyses: (next: JDAnalysis[]) => void;
  /** 过渡期镜像写入（FE-INTERVIEW-01）：react-query interviews mutations 调此函数同步 context.interviews（FE-CONTEXT-REMOVE 移除）。 */
  syncInterviews: (next: Interview[]) => void;
}

const JobCraftContext = createContext<JobCraftContextType | undefined>(undefined);

/**
 * 将后端 Submission/DashboardItem 映射为前端 Job、由 steps 派生岗位状态：
 * 实现已移入 features/jobs/mappers.ts（submissionToJob / deriveJobStatus），
 * 此处与 hooks 共享同一实现，避免双份映射漂移。
 */

/**
 * 将后端面试准备记录（InterviewPrepRecord / InterviewPrepResult）映射为前端 Interview：
 * 实现已移入 features/interview/mappers.ts（prepRecordToInterview / buildInterviewFromPrep /
 * roundTypeToCn / mapRoundType），此处与 hooks 共享同一实现，避免双份映射漂移。
 */

export const JobCraftProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const queryClient = useQueryClient();
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

    // 获取用户信息（auth + profile 两个 API 并行）
    try {
      const [authUser, profileData] = await Promise.all([
        authApi.getCurrentUser(),
        authApi.getProfile().catch(() => ({})),
      ])
      const pd = profileData as Record<string, unknown>
      setUser({
        name: (pd.display_name as string) || authUser.display_name || authUser.username,
        avatarUrl: (pd.avatar_url as string) || '',
        role: (pd.role as string) || '求职者',
        targetSalary: (pd.target_salary as string) || '',
        yearsOfExp: (pd.years_of_exp as number) || 0,
        city: (pd.city as string) || '',
        email: (pd.email as string) || authUser.email || '',
        phone: (pd.phone as string) || '',
        summary: (pd.summary as string) || '',
        targetRoles: (pd.target_roles as string[]) || [],
        targetCompanies: (pd.target_companies as string[]) || [],
      })
    } catch {
      // 用户信息获取失败，使用默认值
    }

    // 并行加载数据
    await Promise.all([
      loadDashboard(userId),
      loadExperiences(userId),
      loadInterviews(userId),
      loadJdAnalyses(userId),
      loadHistoricalResumes(userId)
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
      // 过渡期双写（FE-JOBS-01）：react-query cache 与 context 镜像同一份数据，FE-CONTEXT-REMOVE 移除。
      queryClient.setQueryData([...JOBS_QUERY_KEY], dashboardJobs)

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
      const list = cards.map(cardToExperience)
      setExperiences(list)
      queryClient.setQueryData([...EXPERIENCES_QUERY_KEY], list)
    } catch (error) {
      console.error('Load experiences failed:', error)
    }
  }

  const loadHistoricalResumes = async (userId: number) => {
    try {
      const records = await jobApi.listBaseResumes()
      const list = records.map((r) => {
        const format = (r.format === 'pdf' ? 'pdf' : 'docx') as HistoricalResume['format']
        const formatTags = r.tags && r.tags.length > 0 ? r.tags : (r.parsed_count > 0 ? ['已解析', 'AI 结构化'] : ['已上传'])
        return {
          id: 'hr-' + r.id,
          serverId: r.id,
          name: r.name || '上传简历',
          uploadDate: (r.created_at || '').replace('T', ' ').substring(0, 16),
          fileSize: r.file_size || '',
          isDefault: !!r.is_default,
          parsedExperiencesCount: r.parsed_count || 0,
          format,
          tags: formatTags
        }
      })
      setHistoricalResumes(list)
    } catch (error) {
      console.error('Load historical resumes failed:', error)
    }
  }

  const loadJdAnalyses = async (userId: number) => {
    try {
      const data = await jobApi.listJobAnalyses(userId)
      const summaries = data.analyses || []
      // 为每个分析获取完整数据
      const fullAnalyses = await Promise.all(
        summaries.map(async (s) => {
          try {
            const summary = s as { id?: number; job_analysis_id?: number }
            const detail = await jobApi.getJobAnalysis(Number(summary.id || summary.job_analysis_id))
            return analysisDetailToJD(detail)
          } catch {
            return null
          }
        })
      )
      const mapped = fullAnalyses.filter(Boolean) as JDAnalysis[]
      setJdAnalyses(mapped)
      queryClient.setQueryData([...JD_ANALYSES_QUERY_KEY], mapped)
    } catch (error) {
      console.error('Load JD analyses failed:', error)
    }
  }

  const loadInterviews = async (userId: number) => {
    try {
      const data = await interviewApi.listInterviewPreps(userId)
      const mapped = (data.records || []).map(prepRecordToInterview)
      setInterviews((prev) => {
        // 保留内存中尚未持久化的面试，避免刷新时覆盖本地操作
        const existing = prev.filter((i) => !i.id.startsWith('prep-'))
        const next = [...mapped, ...existing]
        // 过渡期双写（FE-INTERVIEW-01）：react-query cache 与 context 镜像同一份数据，FE-CONTEXT-REMOVE 移除。
        queryClient.setQueryData([...INTERVIEWS_QUERY_KEY], next)
        return next
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

  const updateUserProfile = async (updates: Partial<UserProfile>) => {
    // 乐观更新 UI
    setUser((prev) => ({ ...prev, ...updates }));
    try {
      // 映射前端字段名到后端字段名
      const apiUpdates: Record<string, unknown> = {};
      if (updates.name !== undefined) apiUpdates.display_name = updates.name;
      if (updates.role !== undefined) apiUpdates.role = updates.role;
      if (updates.targetSalary !== undefined) apiUpdates.target_salary = updates.targetSalary;
      if (updates.yearsOfExp !== undefined) apiUpdates.years_of_exp = updates.yearsOfExp;
      if (updates.city !== undefined) apiUpdates.city = updates.city;
      if (updates.email !== undefined) apiUpdates.email = updates.email;
      if (updates.phone !== undefined) apiUpdates.phone = updates.phone;
      if (updates.summary !== undefined) apiUpdates.summary = updates.summary;
      if (updates.targetRoles !== undefined) apiUpdates.target_roles = updates.targetRoles;
      if (updates.targetCompanies !== undefined) apiUpdates.target_companies = updates.targetCompanies;
      if (updates.targetCities !== undefined) apiUpdates.target_cities = updates.targetCities;
      if (updates.avatarUrl !== undefined) apiUpdates.avatar_url = updates.avatarUrl;

      await authApi.updateProfile(apiUpdates);
      showToast({
        type: 'success',
        title: '个人资料已更新',
        message: '个人求职信息与偏好设置已成功保存。'
      });
    } catch {
      showToast({
        type: 'error',
        title: '保存失败',
        message: '请检查网络后重试。'
      });
    }
  };

  const addHistoricalResume = (resumeData: Omit<HistoricalResume, 'id' | 'uploadDate'>) => {
    const newResume: HistoricalResume = {
      ...resumeData,
      id: 'hr-' + Date.now(),
      uploadDate: new Date().toISOString().replace('T', ' ').substring(0, 16)
    };

    // 持久化到后端（刷新后可通过历史版本列表恢复）
    jobApi.createBaseResume({
      name: resumeData.name,
      file_size: resumeData.fileSize,
      format: resumeData.format,
      parsed_count: resumeData.parsedExperiencesCount,
      tags: resumeData.tags
    }).then((record) => {
      setHistoricalResumes((prev) =>
        prev.map((r) =>
          r.id === newResume.id ? { ...r, serverId: record.id } : r
        )
      );
    }).catch((error) => {
      console.error('Persist base resume failed:', error);
    });

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
    if (target?.serverId) {
      jobApi.deleteBaseResume(target.serverId).catch((error) => {
        console.error('Delete base resume failed:', error);
      });
    }
    showToast({
      type: 'info',
      title: '历史简历已删除',
      message: target ? `已移除「${target.name}」` : '简历已删除。'
    });
  };

  const setDefaultHistoricalResume = (id: string) => {
    const target = historicalResumes.find((r) => r.id === id);
    setHistoricalResumes((prev) =>
      prev.map((r) => ({
        ...r,
        isDefault: r.id === id
      }))
    );
    if (target?.serverId) {
      jobApi.setDefaultBaseResume(target.serverId).catch((error) => {
        console.error('Set default base resume failed:', error);
      });
    }
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
  const createJob = async (jobData: {
    company: string;
    role: string;
    department?: string;
    salaryRange?: string;
  }) => {
    const newId = 'job-' + Date.now();
    const steps: Job['steps'] = {
      jdAnalysis: false,
      expMatched: false,
      customResume: false,
      applied: false,
      prepStage: 'pending',
      reviewStage: 'pending'
    };
    const newJob: Job = {
      id: newId,
      company: jobData.company,
      role: jobData.role,
      department: jobData.department || '核心业务线',
      salaryRange: jobData.salaryRange || '面议',
      status: deriveJobStatus(steps),
      matchScore: 0,
      applyDate: new Date().toISOString().split('T')[0],
      lastUpdated: '刚刚',
      currentStage: '待分析 JD',
      nextAction: '开始进行该岗位的 JD 深度解析',
      steps,
      interviewIds: []
    };

    // 持久化到后端（fire-and-forget，失败不影响本地体验）
    try {
      const sub = await jobApi.createSubmission({
        position: jobData.role,
        company: jobData.company,
      });
      newJob.id = 'job-' + sub.id;
      newJob.backendId = sub.id;
    } catch {
      // 后端不可用时仅保留本地状态
    }

    setJobs((prev) => [newJob, ...prev]);
    // 过渡期双写（FE-JOBS-01）：legacy writer 产物同步进 query cache，供已迁移视图读取。
    queryClient.setQueryData([...JOBS_QUERY_KEY], (prev: Job[] | undefined) => [newJob, ...(prev || [])]);
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

  const terminateJob = (jobId: string) => {
    setJobs((prev) =>
      prev.map((j) =>
        j.id === jobId
          ? {
              ...j,
              lastUpdated: '刚刚',
              steps: { ...j.steps, terminated: true, applied: true }
            }
          : j
      )
    );
    // 过渡期双写（FE-JOBS-01）
    queryClient.setQueryData([...JOBS_QUERY_KEY], (prev: Job[] | undefined) =>
      (prev || []).map((j) =>
        j.id === jobId
          ? { ...j, lastUpdated: '刚刚', steps: { ...j.steps, terminated: true, applied: true } }
          : j
      )
    );
    showToast({
      type: 'info',
      title: '流程已结束',
      message: '该岗位流程已标记为「已结束」，可随时恢复处理。'
    });
  };

  const resumeJob = (jobId: string) => {
    setJobs((prev) =>
      prev.map((j) =>
        j.id === jobId
          ? {
              ...j,
              lastUpdated: '刚刚',
              steps: { ...j.steps, terminated: false }
            }
          : j
      )
    );
    // 过渡期双写（FE-JOBS-01）
    queryClient.setQueryData([...JOBS_QUERY_KEY], (prev: Job[] | undefined) =>
      (prev || []).map((j) =>
        j.id === jobId
          ? { ...j, lastUpdated: '刚刚', steps: { ...j.steps, terminated: false } }
          : j
      )
    );
    showToast({
      type: 'success',
      title: '岗位已恢复',
      message: '该岗位已重新进入推进列表，状态按实际进度自动展示。'
    });
  };

  const deleteJob = (jobId: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== jobId));
    // 过渡期双写（FE-JOBS-01）
    queryClient.setQueryData([...JOBS_QUERY_KEY], (prev: Job[] | undefined) =>
      (prev || []).filter((j) => j.id !== jobId)
    );
    showToast({
      type: 'info',
      title: '岗位已移除',
      message: '该岗位及关联信息已移出您的推进列表。'
    });
  };

  // JD Analysis Creation
  const deleteJDAnalysis = async (id: string) => {
    // 从本地状态移除
    setJdAnalyses((prev) => prev.filter((a) => a.id !== id));
    queryClient.setQueryData(
      [...JD_ANALYSES_QUERY_KEY],
      (prev: JDAnalysis[] | undefined) => (prev || []).filter((a) => a.id !== id)
    );
    // 尝试删除后端 submission（id 格式为 "sub-{number}"）
    const match = id.match(/^sub-(\d+)$/);
    if (match) {
      try { await jobApi.deleteSubmission(Number(match[1])); } catch { /* ignore */ }
    }
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

  // Interview Creation（FE-INTERVIEW-01：已迁移至 features/interview/hooks.ts useCreateInterviewMutation）

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

  // Experience Library CRUD
  // 过渡期 legacy 经历写入方（FE-EXPERIENCES-01）：视图已迁 hooks，此处保留给 context 内部流程，
  // 每个写入点同步 query cache 防镜像漂移（FE-CONTEXT-REMOVE 移除）。
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
      queryClient.setQueryData(
        [...EXPERIENCES_QUERY_KEY],
        (prev: Experience[] | undefined) => [newExp, ...(prev || [])]
      );
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
      queryClient.setQueryData(
        [...EXPERIENCES_QUERY_KEY],
        (prev: Experience[] | undefined) =>
          (prev || []).map((exp) => (exp.id === id ? { ...exp, ...updates } : exp))
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
      queryClient.setQueryData(
        [...EXPERIENCES_QUERY_KEY],
        (prev: Experience[] | undefined) => (prev || []).filter((exp) => exp.id !== id)
      );
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
    const applyVersion = (exp: Experience) => {
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
    };
    setExperiences((prev) => prev.map(applyVersion));
    queryClient.setQueryData(
      [...EXPERIENCES_QUERY_KEY],
      (prev: Experience[] | undefined) => (prev || []).map(applyVersion)
    );
    showToast({
      type: 'success',
      title: `经历已升级至 ${version}`,
      message: reason
    });
  };

  // 过渡期镜像写入（FE-JOBS-01）：react-query jobs mutations 调此函数同步 context.jobs（FE-CONTEXT-REMOVE 移除）。
  const syncJobs = (next: Job[]) => {
    setJobs(next);
  };

  // 过渡期镜像写入（FE-EXPERIENCES-01）：react-query experiences mutations 调此函数同步 context.experiences（FE-CONTEXT-REMOVE 移除）。
  const syncExperiences = (next: Experience[]) => {
    setExperiences(next);
  };

  // 过渡期镜像写入（FE-JD-01）：react-query jd mutations 调此函数同步 context.jdAnalyses（FE-CONTEXT-REMOVE 移除）。
  const syncJdAnalyses = (next: JDAnalysis[]) => {
    setJdAnalyses(next);
  };

  // 过渡期镜像写入（FE-INTERVIEW-01）：react-query interviews mutations 调此函数同步 context.interviews（FE-CONTEXT-REMOVE 移除）。
  const syncInterviews = (next: Interview[]) => {
    setInterviews(next);
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
        syncJobs,
        experiences,
        syncExperiences,
        syncJdAnalyses,
        jdAnalyses,
        resumes,
        setResumes,
        activeResumeId,
        setActiveResumeId,
        interviews,
        syncInterviews,
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
        terminateJob,
        resumeJob,
        deleteJob,
        deleteJDAnalysis,
        applyResumeAISuggestion,
        rejectResumeAISuggestion,
        applyAllResumeAISuggestions,
        updateResumeBulletText,
        addResumeBullet,
        deleteResumeBullet,
        saveResume,
        updateQuestionAnswer,
        addCustomQuestion,
        createExperience,
        updateExperience,
        deleteExperience,
        addExperienceVersion,
        isLoading,
        isInitialLoaded,
        isAuthenticated,
        login,
        register,
        logout,
        currentUserId,
        loadExperiences,
        loadJdAnalyses
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

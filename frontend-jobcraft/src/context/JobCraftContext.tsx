import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  NavigationTab,
  Experience,
  Job,
  JDAnalysis,
  Interview,
  InterviewDraft
} from '../types/jobcraft';
import * as authApi from '../api/auth'
import * as experienceApi from '../api/experience'
import * as jobApi from '../api/job'
import * as interviewApi from '../api/interview'
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
  jobs: Job[];
  /** 过渡期镜像写入（FE-JOBS-01）：react-query jobs mutations 更新 cache 后同步到此，供未迁移视图读取。FE-CONTEXT-REMOVE 移除。 */
  syncJobs: (jobs: Job[]) => void;
  experiences: Experience[];
  jdAnalyses: JDAnalysis[];
  interviews: Interview[];
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

  // Actions
  showToast: (toast: Omit<ToastMessage, 'id'>) => void;
  dismissToast: (id: string) => void;
  
  // Interview Draft actions
  saveInterviewDraft: (draft: InterviewDraft) => void;
  clearInterviewDraft: () => void;
  
  // Job actions
  createJob: (jobData: { company: string; role: string; department?: string; salaryRange?: string; status?: Job['status'] }) => Promise<string>;

  // Experience Library actions
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

  const [jobs, setJobs] = useState<Job[]>([]);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [jdAnalyses, setJdAnalyses] = useState<JDAnalysis[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
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

    // 并行加载数据
    await Promise.all([
      loadDashboard(userId),
      loadExperiences(userId),
      loadInterviews(userId),
      loadJdAnalyses(userId)
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

  const loadJdAnalyses = async (userId: number) => {
    try {
      const data = await jobApi.listJobAnalyses(userId)
      const analyses = data.analyses || []
      // 列表接口已返回完整详情（单次查询），无需逐条 GET（消除 N+1）。
      const mapped = analyses.map(analysisDetailToJD)
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

    return newId;
  };

  // JD Analysis Creation

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
        jobs,
        syncJobs,
        experiences,
        syncExperiences,
        syncJdAnalyses,
        jdAnalyses,
        interviews,
        syncInterviews,
        toasts,
        interviewDraft,
        saveInterviewDraft,
        clearInterviewDraft,
        jdAnalysisReturnTarget,
        setJdAnalysisReturnTarget,
        showToast,
        dismissToast,
        createJob,
        isLoading,
        isInitialLoaded,
        isAuthenticated,
        login,
        register,
        logout,
        currentUserId,
        loadExperiences
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

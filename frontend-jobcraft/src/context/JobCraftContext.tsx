import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from 'react';
import {
  NavigationTab,
  InterviewDraft
} from '../types/jobcraft';
import * as authApi from '../api/auth'

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

  // Transient UI state
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

  // Interview Draft actions
  saveInterviewDraft: (draft: InterviewDraft) => void;
  clearInterviewDraft: () => void;
}

const JobCraftContext = createContext<JobCraftContextType | undefined>(undefined);

// ---- Toast 高变上下文（独立拆分：toast 队列变化不影响 useJobCraft 消费者）----

const ToastStateContext = createContext<ToastMessage[]>([]);
const ToastActionsContext = createContext<{
  showToast: (toast: Omit<ToastMessage, 'id'>) => void;
  dismissToast: (id: string) => void;
} | undefined>(undefined);

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback((toast: Omit<ToastMessage, 'id'>) => {
    const id = Date.now().toString() + Math.random().toString(36).substring(2, 5);
    setToasts((prev) => [...prev, { ...toast, id }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastStateContext.Provider value={toasts}>
      <ToastActionsContext.Provider value={useMemo(() => ({ showToast, dismissToast }), [showToast, dismissToast])}>
        {children}
      </ToastActionsContext.Provider>
    </ToastStateContext.Provider>
  );
};

/** 读取当前 toast 队列（仅 ToastContainer 消费，队列变化只重渲染本组件）。 */
export const useToasts = () => useContext(ToastStateContext);

/** 获取稳定的 showToast/dismissToast（useCallback 稳定引用，触发 toast 不会重渲染消费者）。 */
export const useToastActions = () => {
  const context = useContext(ToastActionsContext);
  if (!context) {
    throw new Error('useToastActions must be used within a ToastProvider');
  }
  return context;
};

/**
 * JobCraft 全局上下文（FE-CONTEXT-REMOVE 清账后瘦身 + FE-CONTEXT-MEMO-01 拆 Toast/加 memo）：
 * 仅保留——认证与权限（isAuthenticated/currentUserId/login/register/logout）、
 * 导航过渡态（currentTab / selected 系列选中状态 / navigateTo）、瞬态 UI（interviewDraft、
 * jdAnalysisReturnTarget、isLoading）。toasts/showToast/dismissToast 已拆至 ToastProvider（高变隔离）。
 * 域状态（jobs/experiences/jdAnalyses/interviews）已全部迁移至 react-query 缓存，
 * 由 features 目录下 hooks.ts 的 useXxxQuery 与 useXxxMutation 单一持有，context 不再镜像。
 * value 经 useMemo 缓存：仅当 state/action 引用变化时才重建，避免无关重渲染全量扩散。
 */
export const JobCraftProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const { showToast } = useToastActions();

  const [currentTab, setCurrentTab] = useState<NavigationTab>('workbench');
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedInterviewId, setSelectedInterviewId] = useState<string | null>(null);
  const [selectedJDId, setSelectedJDId] = useState<string | null>(null);
  const [selectedExperienceId, setSelectedExperienceId] = useState<string | null>(null);
  const [jobWorkspaceSubTab, setJobWorkspaceSubTab] = useState<'jd' | 'resume' | 'interview'>('jd');
  const [userProfileTab, setUserProfileTab] = useState<'resumes' | 'profile' | 'preferences' | 'settings'>('resumes');

  const [interviewDraft, setInterviewDraft] = useState<InterviewDraft | null>(null);
  const [jdAnalysisReturnTarget, setJdAnalysisReturnTarget] = useState<'create_interview' | 'create_review' | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isInitialLoaded, setIsInitialLoaded] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<number>(1);

  // 初始化：尝试自动登录。域数据由路由下的 react-query hooks 自行加载，不再经 context 聚合。
  useEffect(() => {
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

        setCurrentUserId(userId)
        setIsAuthenticated(true)
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
    initApp()
  }, [showToast])

  const login = useCallback(async (username: string, password: string) => {
    setIsLoading(true)
    try {
      const userId = await authApi.login(username, password)
      setCurrentUserId(userId)
      setIsAuthenticated(true)
      setIsInitialLoaded(true)
      showToast({
        type: 'success',
        title: '登录成功',
        message: `欢迎回来，${username}！`
      })
    } finally {
      setIsLoading(false)
    }
  }, [showToast])

  const register = useCallback(async (username: string, password: string, email?: string) => {
    setIsLoading(true)
    try {
      const userId = await authApi.register(username, password, email)
      setCurrentUserId(userId)
      setIsAuthenticated(true)
      setIsInitialLoaded(true)
      showToast({
        type: 'success',
        title: '注册成功',
        message: `账号「${username}」已创建，开始你的求职旅程吧！`
      })
    } finally {
      setIsLoading(false)
    }
  }, [showToast])

  const logout = useCallback(() => {
    authApi.logout()
    setIsAuthenticated(false)
    setCurrentUserId(1)
  }, [])

  const saveInterviewDraft = useCallback((draft: InterviewDraft) => {
    setInterviewDraft(draft);
  }, []);

  const clearInterviewDraft = useCallback(() => {
    setInterviewDraft(null);
  }, []);

  const navigateTo = useCallback(
    (
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

      setCurrentTab(tab);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    [setSelectedJobId, setSelectedInterviewId, setSelectedJDId, setSelectedExperienceId, setJobWorkspaceSubTab, setUserProfileTab]
  );

  const value = useMemo(
    () => ({
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
      interviewDraft,
      saveInterviewDraft,
      clearInterviewDraft,
      jdAnalysisReturnTarget,
      setJdAnalysisReturnTarget,
      isLoading,
      isInitialLoaded,
      isAuthenticated,
      login,
      register,
      logout,
      currentUserId
    }),
    [
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
      interviewDraft,
      saveInterviewDraft,
      clearInterviewDraft,
      jdAnalysisReturnTarget,
      setJdAnalysisReturnTarget,
      isLoading,
      isInitialLoaded,
      isAuthenticated,
      login,
      register,
      logout,
      currentUserId
    ]
  );

  return (
    <JobCraftContext.Provider value={value}>
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